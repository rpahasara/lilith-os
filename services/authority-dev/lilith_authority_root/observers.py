"""Root read-only observations for PR-1 (S-2, S-11, §23, §24).

Every observation `lstat`s without following links and reads through
`O_NOFOLLOW` descriptors. Credential blobs are hashed as ciphertext only and
never decrypted; the host credential key is `stat`-observed only and never
opened. Nothing here writes, repairs, starts, or reloads anything.

    observation != authority
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Callable, Mapping, Sequence

import rfc8785
from lilith_authority_host import paths as P
from lilith_authority_host.store_observer import kind_of
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import witness_readiness as WR

MAX_BLOB_BYTES = 64 * 1024
MAX_TREE_FILE = 64 * 1024 * 1024
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}


def _host(root: Path, absolute: str) -> Path:
    return Path(root) / absolute.lstrip("/")


def _hash_regular(path: Path, *, limit: int) -> tuple[os.stat_result, str]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise OSError("not a bounded regular file")
        digest = hashlib.sha256()
        while chunk := os.read(fd, 65536):
            digest.update(chunk)
        return meta, digest.hexdigest()
    finally:
        os.close(fd)


# ------------------------------------------------------ CURRENT (§24) ---

def observe_current_blob(root: Path | str = Path("/"), absolute: str = P.CURRENT_SLOT) -> PA.CurrentBlobObservationV1:
    """Identity, custody, times, and ciphertext SHA-256. Never decrypted."""
    path = _host(Path(root), absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return PA.CurrentBlobObservationV1(absolute, WR.ABSENT)
    kind = kind_of(meta.st_mode)
    base = dict(path=absolute, kind=kind, uid=meta.st_uid, gid=meta.st_gid, mode=stat.S_IMODE(meta.st_mode),
                device=meta.st_dev, inode=meta.st_ino, size=meta.st_size, mtime_ns=meta.st_mtime_ns,
                ctime_ns=meta.st_ctime_ns)
    if kind != WR.REGULAR:
        return PA.CurrentBlobObservationV1(**base)
    opened, sha256 = _hash_regular(path, limit=MAX_BLOB_BYTES)
    if (opened.st_dev, opened.st_ino) != (meta.st_dev, meta.st_ino):
        return PA.CurrentBlobObservationV1(**{**base, "kind": WR.OTHER})
    return PA.CurrentBlobObservationV1(**base, sha256=sha256)


def observe_host_key(root: Path | str = Path("/")) -> dict:
    """`stat` only: the host credential key is never read, hashed, or copied."""
    try:
        meta = os.lstat(_host(Path(root), P.HOST_KEY))
    except FileNotFoundError:
        return {"path": P.HOST_KEY, "kind": WR.ABSENT}
    return {"path": P.HOST_KEY, "kind": kind_of(meta.st_mode), "uid": meta.st_uid, "gid": meta.st_gid,
            "mode": format(stat.S_IMODE(meta.st_mode), "04o"), "device": str(meta.st_dev),
            "inode": str(meta.st_ino), "size": meta.st_size, "mtimeNs": str(meta.st_mtime_ns),
            "ctimeNs": str(meta.st_ctime_ns)}


# ------------------------------------------------ credential inventory ---

def _location(root: Path, role: str, absolute: str) -> WR.CredentialLocationObservationV1:
    path = _host(root, absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return WR.CredentialLocationObservationV1(role, WR.ABSENT)
    kind = kind_of(meta.st_mode)
    entries = []
    if kind == WR.DIRECTORY:
        for name in sorted(os.listdir(path)):
            entry = path / name
            item = os.lstat(entry)
            entry_kind = kind_of(item.st_mode)
            sha256 = _hash_regular(entry, limit=MAX_BLOB_BYTES)[1] if entry_kind == WR.REGULAR else None
            entries.append(WR.CredentialFileObservationV1(name, entry_kind, item.st_uid, item.st_gid,
                                                          stat.S_IMODE(item.st_mode), sha256))
    return WR.CredentialLocationObservationV1(role, kind, meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode),
                                              tuple(entries))


def observe_credential_inventory(root: Path | str = Path("/")) -> WR.CredentialInventoryObservationV1:
    """RR-19 inventory: credstore, PREPARED, RETIRED (ciphertext hashes only)."""
    root = Path(root)
    return WR.CredentialInventoryObservationV1((
        _location(root, WR.CREDSTORE, P.CREDSTORE), _location(root, WR.PREPARED, P.PREPARED_DIR),
        _location(root, WR.RETIRED, P.RETIRED_DIR)))


_CREDENTIAL_DIRECTIVE = re.compile(r"^(LoadCredential|LoadCredentialEncrypted|SetCredential|SetCredentialEncrypted|"
                                   r"ImportCredential)=(.*)$")


def observe_unit_credentials(root: Path | str = Path("/"), unit: str = P.AUTHORITY_SERVICE
                             ) -> WR.UnitCredentialObservationV1:
    """Every credential directive of the installed unit file, as given (B5)."""
    text = (_host(Path(root), f"{P.UNIT_DIR}/{unit}")).read_text(encoding="utf-8")
    references = []
    for line in text.splitlines():
        match = _CREDENTIAL_DIRECTIVE.match(line.strip())
        if match:
            name, _, source = match.group(2).partition(":")
            references.append(WR.UnitCredentialReferenceV1(match.group(1), name, source))
    return WR.UnitCredentialObservationV1(unit, tuple(references))


# -------------------------------------------------- installed release (§23) ---

def _venv_digest(venv: Path) -> str:
    """Drift detection only: SHA-256 of JCS [[relpath, kind, size-or-target, sha256-or-null], ...]."""
    rows = []
    for directory, subdirs, files in os.walk(venv, followlinks=False):
        subdirs.sort()
        for name in sorted(subdirs + files):
            path = Path(directory) / name
            meta = os.lstat(path)
            relative = path.relative_to(venv).as_posix()
            kind = kind_of(meta.st_mode)
            if kind == WR.SYMLINK:
                rows.append([relative, kind, os.readlink(path), None])
            elif kind == WR.REGULAR:
                rows.append([relative, kind, meta.st_size, _hash_regular(path, limit=MAX_TREE_FILE)[1]])
            else:
                rows.append([relative, kind, None, None])
    rows.sort(key=lambda row: row[0])
    return hashlib.sha256(rfc8785.dumps(rows)).hexdigest()


def observe_installed_release(root: Path | str, *, release_sha: str,
                              host_targets: Mapping[str, str]) -> PA.InstalledReleaseObservationV1:
    """The selected release tree (excluding `venv/`), its manifest, the venv
    file-set digest, and the SHA-256 of every host-installed target."""
    root = Path(root)
    selector = _host(root, P.CURRENT_RELEASE)
    target = os.readlink(selector) if selector.is_symlink() else None
    releases = _host(root, P.RELEASES)
    entries = tuple(sorted(os.listdir(releases))) if releases.is_dir() and not releases.is_symlink() else ()
    tree_root = releases / release_sha
    manifest = None
    tree = []
    venv_digest = None
    if tree_root.is_dir() and not tree_root.is_symlink():
        for directory, subdirs, files in os.walk(tree_root, followlinks=False):
            if Path(directory) == tree_root and "venv" in subdirs:
                subdirs.remove("venv")
            for name in sorted(subdirs + files):
                path = Path(directory) / name
                meta = os.lstat(path)
                relative = path.relative_to(tree_root).as_posix()
                kind = kind_of(meta.st_mode)
                sha256 = _hash_regular(path, limit=MAX_TREE_FILE)[1] if kind == WR.REGULAR else None
                tree.append(PA.ReleaseTreeEntryV1(relative, kind, meta.st_uid, meta.st_gid,
                                                  stat.S_IMODE(meta.st_mode), sha256))
        manifest_path = tree_root / PA.MANIFEST_NAME
        if manifest_path.is_file() and not manifest_path.is_symlink():
            fd = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            with os.fdopen(fd, "rb") as handle:
                manifest = handle.read(MAX_TREE_FILE)
        venv = tree_root / "venv"
        if venv.is_dir() and not venv.is_symlink():
            venv_digest = _venv_digest(venv)
    host_files = {}
    for absolute in host_targets:
        path = _host(root, absolute)
        try:
            host_files[absolute] = _hash_regular(path, limit=MAX_TREE_FILE)[1] if not path.is_symlink() else None
        except OSError:
            host_files[absolute] = None
    return PA.InstalledReleaseObservationV1(target, entries, manifest, tuple(sorted(tree, key=lambda e: e.path)),
                                            venv_digest, host_files)


# ------------------------------------------------------------ unit state ---

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


def default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(list(argv), env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)


def observe_units(units: Sequence[str], *, run: Runner = default_runner,
                  root: Path | str = Path("/")) -> tuple[PA.UnitStateObservationV1, ...]:
    """`systemctl show` (read-only) plus the installed unit file's SHA-256."""
    states = []
    for unit in units:
        result = run(["/usr/bin/systemctl", "show", "--property=LoadState,ActiveState,UnitFileState,NeedDaemonReload",
                      "--", unit])
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        path = _host(Path(root), f"{P.UNIT_DIR}/{unit}")
        try:
            fragment = _hash_regular(path, limit=MAX_BLOB_BYTES)[1] if not path.is_symlink() else None
        except OSError:
            fragment = None
        states.append(PA.UnitStateObservationV1(unit, values.get("LoadState"), values.get("ActiveState"),
                                                values.get("UnitFileState"), values.get("NeedDaemonReload"), fragment))
    return tuple(states)
