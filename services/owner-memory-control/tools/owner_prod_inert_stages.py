#!/usr/bin/env python3
"""OWNER_PROD inert install, stages 2-5 of R3b (SOURCE ONLY; PREPARED, NOT RUN). Root on `lilith-01` only.

Record: docs/architecture/canonical-memory-prod-integration-plan.md R3b. Each stage is its own owner-approved window,
needs the previous stage INSTALLED (and stage 1, `owner_prod_inert_install`, the foundation), is single-use, journals
every item before creating it, and has its own owner-adjudicated return. Nothing is started, enabled, reloaded,
keyed, registered or granted:

  2 release   the attested authority release 88a1168 (archive verified by the installer's own `verify_archive`,
              manifest = the P3 pin, payload = d82f7da + the 18-member delta): /opt/lilith-authority-dev/releases/<sha>,
              its venv (offline, hash-pinned wheels), and `current` -> releases/<sha>
  3 units     the release's signer and witness unit files and tmpfiles (the witness units are the E-23 NEW bytes),
              each `.service` with a reviewed drop-in `50-owner-prod.conf` = `Environment=LILITH_ENV=prod`.
              NO daemon-reload, enable or start: the units are files on disk, not loaded services
  4 host tree the trusted First Memory host tree at 88a1168 (96 files) and canonical-config.json = DISABLED
              (no capability: recall and memory creation are both off)
  5 context   the canonical context service and its socket/service units (+ LILITH_ENV=prod drop-in), not enabled
              or started; the owner-channel grant must be ABSENT before and after (never written by any stage)

Strict separation from DEV_SYNTHETIC: the host guard (lilith-01, not the DEV machine), stage 1's OWNER_PROD
`deployment.json` byte-exact, the P3 release and manifest pins, and no DEV path or DEV key is ever named.
LILITH's live files (identity, router, stores, the 15B2a keys) are digested before and after every stage and return.

The generated venv is the one item whose bytes are not known before it is created: once `venv` and `pip` both
succeed, its complete manifest (every entry's type, mode, owner, file SHA-256 or link target; links never followed)
is journaled before the item is marked done. A return removes the venv only when that manifest is intact and the
venv matches it exactly, entry by entry (unlink / rmdir; never a recursive delete). A venv without a recorded
manifest (an interrupted `venv` or `pip`) or one that differs is a STOP before anything is removed: owner
adjudication, never an automatic deletion.

H-1/H-2 (plan §13, `owner_prod_safe_fs`): every created file, directory and link is journaled (schema 2) with its
observed mode, owner and integrity; a return refuses a legacy or incomplete journal, an interrupted item that exists,
or any difference. Removal goes through descriptors (never following a link), only for an inode unchanged since
verification, every removal journaled; a partly returned stage is never resumed automatically. Install and return
hold the installer's exclusive host lock, shared with stage 1.

    python owner_prod_inert_stages.py plan <stage>
    python owner_prod_inert_stages.py install <stage> <approval> [inputs...]
    python owner_prod_inert_stages.py return <stage> <approval>

    staged files != loaded units != running services != an activated authority
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

HERE = Path(__file__).resolve().parent
for _p in (HERE, HERE.parents[1] / "authority-dev/ceremony"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import owner_prod_inert_install as F1  # noqa: E402  (stage 1: host guard, live digests, deployment bytes)
import owner_prod_safe_fs as SF  # noqa: E402  (H-1/H-2: descriptor-relative verify-then-remove, the host lock)
import owner_prod_signer_upgrade as P3  # noqa: E402  (the release, manifest and delta pins)
import e23_privacy_anchor_upgrade as E23  # noqa: E402  (the E-23 NEW witness unit bytes)
import install_authority_dev as I  # noqa: E402  (unit targets; the accepted installer V1, unchanged)
import install_authority_dev_v3 as V3  # noqa: E402  (archive layout v3 verify)

RELEASE = P3.NEW_RELEASE
OPT = "opt/lilith-authority-dev"
RELEASES = OPT + "/releases"
RELEASE_DIR = f"{RELEASES}/{RELEASE}"
CURRENT = OPT + "/current"
UNIT_DIR = "etc/systemd/system"
DROPIN_NAME = "50-owner-prod.conf"
DROPIN = b"# OWNER_PROD (R3b stage 3): this host is lilith-01 under OWNER_PROD; read with deployment.json.\n" \
         b"[Service]\nEnvironment=LILITH_ENV=prod\n"
HOST_TREE = "opt/lilith-first-memory-dev"
HOST_TREE_CURRENT = HOST_TREE + "/current"
HOST_TREE_TAR_SHA256 = "2b8d28e27d5ec65e9c519faf05c790edd2f87ec516026babb47db3555746e6a2"
HOST_TREE_MANIFEST_SHA256 = "af8140a81ab4029d723a0983b0174d5a7c1008d34ef10b3396de46a83fefe444"
HOST_TREE_FILES = 96
FM_CONFIG_DIR = "etc/lilith-first-memory-dev"
CANONICAL_CONFIG = FM_CONFIG_DIR + "/canonical-config.json"
CANONICAL_CONFIG_DISABLED = json.dumps({"activeCapabilities": [], "canonicalLtmEnabled": False, "schemaVersion": 1},
                                       sort_keys=True, separators=(",", ":")).encode("ascii")
GRANT = FM_CONFIG_DIR + "/hermes-owner-channel.json"
ROUTER_SETTINGS = "home/lilith/.hermes/lilith_router/canonical_memory.json"
CONTEXT_LIB = "usr/local/lib/lilith-canonical-context"
CONTEXT_SERVICE = CONTEXT_LIB + "/canonical_context_service.py"
CONTEXT_UNITS = ("lilith-first-memory-context.socket", "lilith-first-memory-context@.service")
STATE = F1.STATE
STAGES = ("release", "units", "hosttree", "context")
NEVER = (GRANT, ROUTER_SETTINGS)                    # no stage may ever create these
JOURNAL_SCHEMA = 2


Stop = F1.Stop
_need = F1._need


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def venv_walk(host_root: Path, relative: str) -> dict[str, tuple]:
    """Every entry under the venv at host_root/relative ("." = the venv itself) -> (Meta, inode identity), through
    descriptors; links recorded, never followed; anything but a directory, regular file or link is a STOP."""
    try:
        return SF.walk(host_root, relative)
    except SF.Stop as exc:
        if exc.reason.startswith("ENTRY_TYPE:"):
            raise Stop("VENV_ENTRY_TYPE:" + exc.reason.split(":", 1)[1]) from exc
        raise


def venv_manifest(host_root: Path, relative: str) -> dict[str, list]:
    """The journaled form: relative path -> [kind, mode, uid, gid, sha256 | link target]."""
    return {name: meta.as_list() for name, (meta, _identity) in venv_walk(host_root, relative).items()}


def _first_difference(recorded: dict[str, list], current: dict[str, list]) -> str:
    for name in sorted(set(recorded) | set(current)):
        if recorded.get(name) != current.get(name):
            return name
    return ""


@dataclass(frozen=True)
class Item:
    kind: str                     # "dir" | "file" | "link" | "venv"
    path: str                     # relative to the host root
    data: bytes = b""             # file bytes, or the link target
    mode: int = 0o644


class Stages:
    def __init__(self, root: Path, *, run: Callable[[Sequence[str]], subprocess.CompletedProcess], hostname: str,
                 euid: int, chown: bool = True):
        self.root, self.run, self.hostname, self.euid, self.chown = root, run, hostname, euid, chown
        self.f1 = F1.Foundation(root, run=run, hostname=hostname, euid=euid, accounts=F1.Accounts(), chown=chown)
        self.before_remove: Optional[Callable[[str], None]] = None     # TEST seam: runs after verification, per removal

    def p(self, relative: str) -> Path:
        return self.root / relative

    def journal_path(self, stage: str) -> Path:
        return self.p(f"{STATE}/{stage}.journal")

    def journal(self, stage: str) -> list[dict[str, Any]]:
        path = self.journal_path(stage)
        if not os.path.lexists(path):
            return []
        return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line.strip()]

    def _append(self, stage: str, entry: dict[str, Any]) -> None:
        with open(self.journal_path(stage), "a", encoding="ascii") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def installed(self, stage: str) -> bool:
        entries = self.journal(stage)
        return bool(entries) and entries[-1].get("result") == "INSTALLED"

    # ------------------------------------------------------------------ items ---
    def items(self, stage: str, inputs: Sequence[Path]) -> list[Item]:
        if stage == "release":
            _need(len(inputs) == 2, "INPUTS: <archive> <builder-stamp>")
            return self._release_items(Path(inputs[0]), Path(inputs[1]))
        payloads = self._installed_release_payloads()
        if stage == "units":
            items = []
            for member, target in {**I.UNIT_TARGETS, **I.WITNESS_UNIT_TARGETS}.items():
                data = payloads[member]
                if member in E23.PAYLOAD_DELTA:
                    _need(sha(data) == E23.PAYLOAD_DELTA[member][1], "WITNESS_UNIT_NOT_E23_NEW:" + member)
                items.append(Item("file", target.lstrip("/"), data, 0o644))
                if target.endswith(".service"):
                    items.append(Item("dir", f"{target.lstrip('/')}.d", mode=0o755))
                    items.append(Item("file", f"{target.lstrip('/')}.d/{DROPIN_NAME}", DROPIN, 0o644))
            return items
        if stage == "hosttree":
            _need(len(inputs) == 1, "INPUTS: <host-tree.tar>")
            return self._hosttree_items(Path(inputs[0]))
        if stage == "context":
            _need(len(inputs) == 3, "INPUTS: <canonical_context_service.py> <socket unit> <service unit>")
            service, socket_unit, service_unit = (Path(x).read_bytes() for x in inputs)
            items = [Item("dir", CONTEXT_LIB, mode=0o755), Item("file", CONTEXT_SERVICE, service, 0o644),
                     Item("file", f"{UNIT_DIR}/{CONTEXT_UNITS[0]}", socket_unit, 0o644),
                     Item("file", f"{UNIT_DIR}/{CONTEXT_UNITS[1]}", service_unit, 0o644),
                     Item("dir", f"{UNIT_DIR}/{CONTEXT_UNITS[1]}.d", mode=0o755),
                     Item("file", f"{UNIT_DIR}/{CONTEXT_UNITS[1]}.d/{DROPIN_NAME}", DROPIN, 0o644)]
            _need(b"/opt/lilith-authority-dev/current/venv/bin/python" in service_unit, "CONTEXT_UNIT_NOT_THE_RELEASE_VENV")
            return items
        raise Stop("STAGE_UNKNOWN")

    def _release_items(self, archive: Path, stamp: Path) -> list[Item]:
        _need(P3.ready_to_transition(), "RELEASE_NOT_PINNED")
        manifest, payloads = V3.verify_archive(archive, stamp, RELEASE)
        _need(I.digest(I.canonical(manifest)) == P3.NEW_MANIFEST_SHA256, "MANIFEST_NOT_THE_P3_PIN")
        for member, (_before, after) in P3.PAYLOAD_DELTA.items():
            _need(sha(payloads[member]) == after, "DELTA_MEMBER_NOT_PINNED:" + member)
        items = [Item("dir", OPT, mode=0o755), Item("dir", RELEASES, mode=0o755), Item("dir", RELEASE_DIR, mode=0o755)]
        dirs = sorted({"/".join(m.split("/")[:i]) for m in payloads for i in range(1, m.count("/") + 1)},
                      key=lambda d: (d.count("/"), d))
        items += [Item("dir", f"{RELEASE_DIR}/{d}", mode=0o755) for d in dirs]
        items += [Item("file", f"{RELEASE_DIR}/{m}", payloads[m], 0o755 if m in I.CLI_TARGETS else 0o644)
                  for m in sorted(payloads)]
        items.append(Item("file", f"{RELEASE_DIR}/{I.MANIFEST}", I.canonical(manifest), 0o644))
        items.append(Item("venv", f"{RELEASE_DIR}/venv"))
        items.append(Item("link", CURRENT, f"releases/{RELEASE}".encode("ascii")))
        return items

    def _installed_release_payloads(self) -> dict[str, bytes]:
        _need(self.installed("release"), "RELEASE_STAGE_NOT_INSTALLED")
        manifest = json.loads(self.p(f"{RELEASE_DIR}/{I.MANIFEST}").read_bytes())
        _need(I.digest(I.canonical(manifest)) == P3.NEW_MANIFEST_SHA256, "INSTALLED_MANIFEST_NOT_THE_PIN")
        out = {}
        for entry in manifest["files"]:
            data = self.p(f"{RELEASE_DIR}/{entry['path']}").read_bytes()
            _need(sha(data) == entry["sha256"], "INSTALLED_RELEASE_FILE_CHANGED:" + entry["path"])
            out[entry["path"]] = data
        return out

    def _hosttree_items(self, tar_path: Path) -> list[Item]:
        data = tar_path.read_bytes()
        _need(sha(data) == HOST_TREE_TAR_SHA256, "HOST_TREE_TAR_NOT_PINNED")
        files, dirs = [], set()
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            for member in tar.getmembers():
                _need(member.isfile() or member.isdir(), "HOST_TREE_MEMBER_TYPE")
                _need(member.name == "current" or member.name.startswith("current/"), "HOST_TREE_MEMBER_PATH")
                _need(".." not in Path(member.name).parts, "HOST_TREE_MEMBER_PATH")
                if member.isfile():
                    files.append((member.name, tar.extractfile(member).read()))
                else:
                    dirs.add(member.name)
        manifest = "".join(f"{sha(b)}  {n}\n" for n, b in sorted(files)).encode()
        _need(sha(manifest) == HOST_TREE_MANIFEST_SHA256 and len(files) == HOST_TREE_FILES, "HOST_TREE_MANIFEST")
        items = [Item("dir", HOST_TREE, mode=0o755)]
        items += [Item("dir", f"{HOST_TREE}/{d}", mode=0o755) for d in sorted(dirs, key=lambda d: (d.count("/"), d))]
        items += [Item("file", f"{HOST_TREE}/{n}", b, 0o644) for n, b in sorted(files)]
        items += [Item("dir", FM_CONFIG_DIR, mode=0o755), Item("file", CANONICAL_CONFIG, CANONICAL_CONFIG_DISABLED, 0o644)]
        return items

    # ----------------------------------------------------------------- checks ---
    def guard(self, stage: str) -> dict[str, str]:
        _need(stage in STAGES, "STAGE_UNKNOWN")
        self.f1.host_guard()
        _need(self.f1.journal() and self.f1.journal()[-1].get("result") == "FOUNDATION_INSTALLED",
              "FOUNDATION_NOT_INSTALLED")
        _need(self.p(F1.DEPLOYMENT).read_bytes() == F1.DEPLOYMENT_BYTES, "DEPLOYMENT_NOT_OWNER_PROD")
        index = STAGES.index(stage)
        for earlier in STAGES[:index]:
            _need(self.installed(earlier), "EARLIER_STAGE_NOT_INSTALLED:" + earlier)
        for never in NEVER:
            _need(not os.path.lexists(self.p(never)), "PRESENT:/" + never)
        return self.f1.live_digests()

    def plan_text(self, stage: str) -> str:
        return (f"OWNER_PROD inert install, stage {STAGES.index(stage) + 2} ({stage}), lilith-01 only; release {RELEASE}, "
                f"manifest {P3.NEW_MANIFEST_SHA256}. Every item journaled first; nothing started, enabled, reloaded, "
                "keyed, registered or granted; any surprise is a STOP.\n")

    def approval(self, stage: str) -> str:
        return sha(self.plan_text(stage).encode("ascii"))[:16]

    # ----------------------------------------------------------------- install ---
    def install(self, stage: str, approval: str, inputs: Sequence[Path] = ()) -> dict[str, Any]:
        _need(approval == self.approval(stage), "APPROVAL_NOT_THIS_PLAN")
        self.f1.host_guard()
        _need(os.path.isdir(self.p(STATE)) and not os.path.islink(self.p(STATE)), "FOUNDATION_NOT_INSTALLED")
        with SF.HostLock(self.root, STATE):
            return self._install_locked(stage, inputs)

    def _install_locked(self, stage: str, inputs: Sequence[Path]) -> dict[str, Any]:
        live = self.guard(stage)
        try:
            items = self.items(stage, inputs)
        except I.InstallError as exc:                          # the installer's own archive verification refused
            raise Stop("RELEASE_ARCHIVE_REFUSED:" + str(exc.reason)) from exc
        except (OSError, KeyError, ValueError) as exc:
            raise Stop("INPUT_INVALID:" + type(exc).__name__) from exc
        planned = {item.path for item in items}
        for item in items:                                     # nothing may pre-exist: no file, dir or symlink
            _need(not os.path.lexists(self.p(item.path)), "PRESENT:/" + item.path)
            parent = str(Path(item.path).parent)
            _need(parent in planned or (os.path.isdir(self.p(parent)) and not os.path.islink(self.p(parent))),
                  "PARENT_MISSING:/" + parent)
        fd = os.open(self.journal_path(stage), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)      # single use
        os.close(fd)
        self._append(stage, {"step": "begin", "live": live, "items": [[i.kind, i.path, sha(i.data)] for i in items],
                             "schema": JOURNAL_SCHEMA})
        for item in items:
            self._append(stage, {"step": "item", "phase": "intent", "path": item.path})
            self._create(item)
            done: dict[str, Any] = {"step": "item", "phase": "done", "path": item.path}
            if item.kind == "venv":                            # its only description: recorded before it is done
                manifest = venv_manifest(self.root, item.path)
                self._append(stage, {"step": "venv", "path": item.path, "manifest": manifest,
                                     "sha256": sha(_canonical(manifest))})
            else:
                done["meta"] = self._created_meta(item)
            self._append(stage, done)
        for item in items:
            _need(self._matches(item), "ITEM_NOT_AS_INSTALLED:" + item.path)
        _need(self.f1.live_digests() == live, "LIVE_FILES_CHANGED")
        for never in NEVER:
            _need(not os.path.lexists(self.p(never)), "PRESENT:/" + never)
        self._append(stage, {"step": "end", "result": "INSTALLED"})
        return {"result": f"STAGE_{stage.upper()}_INSTALLED", "items": len(items)}

    def _create(self, item: Item) -> None:
        path = self.p(item.path)
        if item.kind == "dir":
            path.mkdir(mode=item.mode)
            os.chmod(path, item.mode)
        elif item.kind == "file":
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, item.mode)
            try:
                os.write(fd, item.data)
                os.fsync(fd)
            finally:
                os.close(fd)
            os.chmod(path, item.mode)
        elif item.kind == "link":
            os.symlink(item.data.decode("ascii"), path)
        elif item.kind == "venv":
            release = path.parent
            done = self.run(["/usr/bin/python3", "-m", "venv", str(path)])
            _need(done.returncode == 0, "VENV_FAILED")
            done = self.run([str(path / "bin/python"), "-m", "pip", "install", "--no-index", "--no-input",
                             "--disable-pip-version-check", "--require-hashes", "--find-links", str(release / "wheels"),
                             "-r", str(release / "requirements.lock")])
            _need(done.returncode == 0, "PIP_FAILED")
        else:
            raise Stop("ITEM_KIND")
        if self.chown and item.kind != "venv":
            os.lchown(path, 0, 0)

    @staticmethod
    def _intended(item: Item) -> tuple[str, int, str]:
        """The kind, mode and integrity an item is created with (H-1)."""
        if item.kind == "file":
            return "file", item.mode, sha(item.data)
        if item.kind == "link":
            return "link", 0, item.data.decode("ascii")
        return "dir", item.mode, ""

    def _created_meta(self, item: Item) -> list:
        meta, _identity = SF.observe(self.root, item.path)
        _need((meta.kind, meta.mode, meta.integrity) == self._intended(item)
              and (not self.chown or (meta.uid, meta.gid) == (0, 0)), "ITEM_NOT_AS_INSTALLED:" + item.path)
        return meta.as_list()

    def _matches(self, item: Item) -> bool:
        try:
            if item.kind == "venv":
                record = self._venv_record(self.journal(self._stage_of(item.path)), item.path)
                return record is not None and venv_manifest(self.root, item.path) == record["manifest"]
            meta, _identity = SF.observe(self.root, item.path)
        except SF.Stop:
            return False
        return (meta.kind, meta.mode, meta.integrity) == self._intended(item)

    def _stage_of(self, path: str) -> str:
        for stage in STAGES:
            entries = self.journal(stage)
            if entries and any(path == p for _kind, p, _digest in entries[0]["items"]):
                return stage
        raise Stop("ITEM_NOT_JOURNALED:" + path)

    @staticmethod
    def _venv_record(entries: list[dict[str, Any]], path: str) -> Optional[dict[str, Any]]:
        records = [e for e in entries if e.get("step") == "venv" and e.get("path") == path]
        _need(len(records) <= 1, "VENV_MANIFEST_INVALID:" + path)
        return records[0] if records else None

    # ------------------------------------------------------------------ return ---
    def return_(self, stage: str, approval: str) -> dict[str, Any]:
        """Remove exactly this stage's journaled items, newest first, after verifying ALL of them (and that every later
        stage is already returned): a refused return changes nothing."""
        _need(approval == self.approval(stage), "APPROVAL_NOT_THIS_PLAN")
        self.f1.host_guard()
        _need(os.path.isdir(self.p(STATE)) and not os.path.islink(self.p(STATE)), "NO_JOURNAL")
        with SF.HostLock(self.root, STATE):
            return self._return_locked(stage)

    def _return_locked(self, stage: str) -> dict[str, Any]:
        for later in STAGES[STAGES.index(stage) + 1:]:
            _need(not self.journal(later) or not os.path.lexists(self.journal_path(later)), "LATER_STAGE_PRESENT:" + later)
        entries = self.journal(stage)
        _need(bool(entries) and entries[0]["step"] == "begin", "NO_JOURNAL")
        _need(entries[0].get("schema") == JOURNAL_SCHEMA, "JOURNAL_LEGACY")
        _need(not any(e.get("step") == "remove" for e in entries), "RETURN_PARTIAL")    # never resumed automatically
        kinds = {path: kind for kind, path, _digest in entries[0]["items"]}
        done = {e["path"]: e for e in entries if e.get("phase") == "done"}
        intents = [e["path"] for e in entries if e.get("phase") == "intent"]
        for path in intents:                                    # interrupted: what exists is unverified
            if path not in done and os.path.lexists(self.p(path)):
                _need(kinds[path] != "venv", "VENV_UNVERIFIED:" + path)
                raise Stop("ITEM_INTERRUPTED:" + path)
        created = [path for path in intents if path in done]
        digests = {path: digest for _kind, path, digest in entries[0]["items"]}
        planned = set(kinds)
        verified: dict[str, Any] = {}
        for path in created:                                    # verify everything first (H-1)
            kind = kinds[path]
            if kind == "venv":
                record = self._venv_record(entries, path)
                # no recorded manifest = an interrupted venv or pip: its contents are unknown, owner adjudication
                _need(record is not None, "VENV_UNVERIFIED:" + path)
                _need(isinstance(record.get("manifest"), dict) and sha(_canonical(record["manifest"])) == record.get("sha256")
                      and record["manifest"].get(".", [None])[0] == "dir", "VENV_MANIFEST_INVALID:" + path)
                walked = venv_walk(self.root, path)
                current = {name: meta.as_list() for name, (meta, _identity) in walked.items()}
                _need(current == record["manifest"],
                      "VENV_CHANGED:" + path + ":" + _first_difference(record["manifest"], current))
                verified[path] = walked
                continue
            expected = SF.Meta.from_journal(done[path].get("meta"), path)
            if kind == "dir":
                extra = [c for c in SF.list_dir(self.root, path) if f"{path}/{c}" not in planned]
                _need(not extra, "UNEXPECTED_ENTRY:" + path + "/" + (extra[0] if extra else ""))
            meta, ident = SF.observe(self.root, path)
            journaled = digests[path]
            integrity_ok = (meta.integrity == journaled if kind == "file"
                            else sha(meta.integrity.encode("ascii")) == journaled if kind == "link" else True)
            _need(meta.kind == kind and integrity_ok and meta == expected, "ITEM_CHANGED:" + path)
            verified[path] = ident
        _need(self.f1.live_digests() == entries[0]["live"], "LIVE_FILES_CHANGED")
        removed = 0
        for path in reversed(created):                         # then remove, newest first (H-2)
            if self.before_remove is not None:
                self.before_remove(path)
            self._append(stage, {"step": "remove", "phase": "intent", "path": path})
            if kinds[path] == "venv":
                self._remove_verified_venv(path, verified[path])
            else:
                SF.remove_verified(self.root, path, verified[path], kinds[path])
            self._append(stage, {"step": "remove", "phase": "done", "path": path})
            removed += 1
        _need(self.f1.live_digests() == entries[0]["live"], "LIVE_FILES_CHANGED")
        self.journal_path(stage).rename(self.p(f"{STATE}/{stage}.journal.returned"))
        return {"result": f"STAGE_{stage.upper()}_RETURNED", "removed": removed}

    def _remove_verified_venv(self, path: str, walked: dict[str, tuple]) -> None:
        """Remove exactly the verified venv entries, deepest first, each only if its inode is unchanged since
        verification: unlink files and links (a link is never followed), rmdir directories (only when empty).
        Never a recursive delete."""
        for name in sorted((n for n in walked if n != "."), key=lambda n: (-n.count("/"), n)):
            meta, ident = walked[name]
            if self.before_remove is not None:
                self.before_remove(f"{path}/{name}")
            SF.remove_verified(self.root, f"{path}/{name}", ident, meta.kind)
        SF.remove_verified(self.root, path, walked["."][1], "dir")


def main(argv: list[str]) -> int:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess:
        return subprocess.run(list(args), capture_output=True, timeout=900, check=False, stdin=subprocess.DEVNULL,
                              env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "HOME": "/nonexistent"})

    s = Stages(Path("/"), run=run, hostname=os.uname().nodename, euid=os.geteuid())
    try:
        if len(argv) == 2 and argv[0] == "plan":
            print(s.plan_text(argv[1]) + f"approval {s.approval(argv[1])}")
            return 0
        if len(argv) >= 3 and argv[0] == "install":
            print(json.dumps(s.install(argv[1], argv[2], [Path(x) for x in argv[3:]]), sort_keys=True))
            return 0
        if len(argv) == 3 and argv[0] == "return":
            print(json.dumps(s.return_(argv[1], argv[2]), sort_keys=True))
            return 0
        print(__doc__)
        return 2
    except F1.Stop as exc:
        print(f"owner_prod_inert_stages: STOP {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
