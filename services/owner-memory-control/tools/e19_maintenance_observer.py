#!/usr/bin/env python3
"""15B2b-B1b-3e E-19: READ-ONLY maintenance observer and two-release-aware verification (DEV, design only).

Record: docs/architecture/slice-15b2b-b1b3e-e19-maintenance-observer.md. Contract (merged, unchanged):
`e19_p1b10_upgrade.py` and docs/architecture/slice-15b2b-b1b3e-e19-release-maintenance.md.

DESIGN / SOURCE ONLY. Running `observe` live needs a separate owner authorization. Nothing here stages, selects or
retires a release, stops or starts a unit, runs daemon-reload, installs a drop-in, loads K-WIT or K-ACT, writes HELD
or the ledger, or grants an acceptance.

`observe` (root, DEV, release interpreter) captures exactly the closed observation document the merged U0–U5
classifier judges, from root reads only:

- the release set, the `current` target, interrupted-operation residue, and a per-release tree verification against
  its own manifest (never the single-release installer `status`, never the judge's E-01);
- the witness service and both sockets (`systemctl show`), the witness cwd (`/proc/<MainPID>/cwd`), and the EFFECTIVE
  restart boundary: unit properties plus the installed drop-in bytes against the merged candidate pins;
- the journal cursor and the witness invocations (K-WIT loads) after the supplied U0 cursor;
- the signer side (dark, no K-ACT invocation ever);
- the preserved custody, trust, HELD, ledger, genesis, broker and activation facts.

The ledger head and the committed genesis come from the UNCHANGED W10 verifier (`mb10_held_verifier.evaluate`, which
runs the W9 / M-B6 ledger judgement); the broker facts from the unchanged broker `preservation` read. A read that
cannot be made is `null` (UNKNOWN). A path that is absent is the observed string `"ABSENT"` (drift), never `null`.

The witness owner socket is contacted (`health`) ONLY when the witness is RUNNING with both sockets active AND the
restart boundary is exactly effective, and the InvocationID / MainPID are re-read after the call; otherwise health
is `null`. A stopped witness is never contacted.

Verification is pure: `verify` = the merged classifier against the owner-accepted U0 bundle; `post9a_r_evidence`
assembles the POST9A-R evidence document from an observation, its W10 report, its bound health capture and the three
denial-proof transcripts (judged by their terminal lines), and `post9a_r` judges it. Nothing grants an acceptance:
the local acceptance remains the owner's verbatim statement (merged contract §4.6).

Forms:

    ... observe-inline <inputs-b64url> <inputs-sha256>  root, DEV: one read-only observation bundle (JSON); the live
                                                      route (the pinned mb6 BOOT bundle over stdin, no host file)
    ... observe <inputs.json>                         root: the same, inputs from a local file (workstation / tests)
    ... verify <bundle.json> <u0-acceptance.json> [<replacement-acceptance.json>]   pure
    ... post9a-r <bundle.json> <denials.json> <u0-acceptance.json>                  pure; grants nothing

Live route (E-19 transition implementation, record docs/architecture/slice-15b2b-b1b3e-e19-transition-implementation.md):
under the mb6 BOOT loader every module's `__file__` is `<mb6-bundle:NAME>` and no tool file exists on DEV. The
contract pin is then judged from the pin map the loader itself enforced before executing anything (argv[1]), the
broker reads come from the pinned bundled `verify_broker_dev_current_incarnation` module, and the inputs arrive in
argv as canonical JSON bound to their SHA-256 (echoed as `inputsSha256` for the operator's record).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

# F1 (PR #189 review): read-only Python. Set before ANY tool or release module import: importing release modules
# from /opt/lilith-authority-dev/current as root would otherwise write __pycache__ into the release tree. The live
# operator must also run the interpreter read-only (`-I -B`, as the mb6 BOOT loader does).
sys.dont_write_bytecode = True

BOOT_FILE_PREFIX = "<mb6-bundle:"
BUNDLED = str(globals().get("__file__", "")).startswith(BOOT_FILE_PREFIX)
HERE = Path(__file__).resolve().parent
if not BUNDLED and str(HERE) not in sys.path:      # never put the remote cwd on sys.path under the BOOT loader
    sys.path.insert(0, str(HERE))

import e19_p1b10_upgrade as E  # noqa: E402  (the merged contract; pinned below)
import mb11_restart_boundary_install as RBI  # noqa: E402  (SHADOW_BASES only; the P1B-10R shadow list)

E19_CONTRACT_SHA256 = "152022eeff26993f383ce0ba94c0ea552c7dda01ff3b87bc249be295106f34cb"
# The broker preservation reader: `scripts/verify_broker_dev_current_incarnation.py` at the owner-accepted post-reboot
# re-pin (= mb9_operator.TOOL_PINS[BROKER]); bundled under the BOOT loader, loaded from the repository otherwise.
BROKER_MODULE = "verify_broker_dev_current_incarnation"
BROKER_SHA256 = "b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf"
MAX_INLINE_INPUTS = 4096
_B64URL = re.compile(r"[A-Za-z0-9_-]+={0,2}\Z")
BUNDLE_TYPE = "LILITH_E19_MAINTENANCE_OBSERVATION_BUNDLE"
INPUT_FIELDS = frozenset({"newRelease", "afterCursor", "expectedHead", "candidateDigest", "updatedAt"})
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
SYSTEMCTL = "/usr/bin/systemctl"
JOURNALCTL = "/usr/bin/journalctl"
ACTIVATION_VERIFY = "/usr/local/sbin/lilith-activation-verify"
OWNER_CLI = "/usr/local/sbin/lilith-recovery-witness-owner-dev"
MAX_FILE = 64 * 1024 * 1024
ABSENT = "ABSENT"
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")

# Host paths (= install_authority_dev constants; a test cross-checks every one).
OPT = E.OPT
RELEASES = OPT + "/releases"
CURRENT = OPT + "/current"
MANIFEST = "release-manifest.json"
CREDENTIAL = "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred"
CREDSTORE = "/etc/credstore.encrypted"
HOST_KEY = "/var/lib/systemd/credential.secret"
CUSTODY_ROOT = "/etc/lilith-authority-custody"
WITNESS_CREDENTIAL_ROOT = "/etc/lilith-recovery-witness/credentials"
WITNESS_BLOB = WITNESS_CREDENTIAL_ROOT + "/lilith-recovery-witness.witness.cred"
KACT_PUBLICATION = "/root/b1b3d-l2b-publication.json"                      # = mb6_operator.KACT_PUBLICATION
TRUST_DIR = "/etc/lilith-authority-dev/trust"
REGISTRY = "/etc/lilith-authority-dev/registry/authority-registry.v1.json"
OWNER_INPUTS = ("/etc/lilith-authority-dev/owner/genesis-pin.json",
                "/etc/lilith-authority-dev/owner/authorization-register.json")
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
HOLD_STORE = "/var/lib/lilith-authority-custody/holds"
LEDGER_STATE = "/var/lib/lilith-authority-dev"
LEDGER_NAMES = ("authority_ledger.db", "authority_ledger.db-wal", "authority_ledger.db-shm")
SIGNER_UNIT_FILES = ("/etc/systemd/system/lilith-authority-dev.service",
                     "/etc/systemd/system/lilith-authority-dev.socket",
                     "/etc/tmpfiles.d/lilith-authority-dev.conf")
WITNESS_UNIT_FILES = ("/etc/systemd/system/lilith-recovery-witness.service",
                      "/etc/systemd/system/lilith-recovery-witness-owner.socket",
                      "/etc/systemd/system/lilith-recovery-witness-signer.socket",
                      "/etc/tmpfiles.d/lilith-recovery-witness.conf")
CLIS = tuple(f"/usr/local/sbin/{name}" for name in (
    "lilith-authority-keygen-dev", "lilith-authority-ledger-dev", "lilith-authority-hold-dev",
    "lilith-authority-verify-dev", "lilith-authority-recovery-dev", "lilith-recovery-witness-owner-dev"))
HELD_NAME = E.PRESERVED_PINS["holdListing"][0]
SIGNER_SERVICE = "lilith-authority-dev.service"
BROKER_SERVICE = "lilith-memory-broker.service"
UNIT_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "UnitFileState", "NeedDaemonReload", "MainPID",
                   "NRestarts", "InvocationID", "Result", "DropInPaths", "Restart", "StopWhenUnneeded",
                   "RefuseManualStart", "FragmentPath")
# F3: the accepted fragment of each witness unit, and the systemd locations a shadow fragment or drop-in could use.
WITNESS_FRAGMENTS = {unit: f"/etc/systemd/system/{unit}" for unit in (E.WITNESS_SERVICE, E.OWNER_SOCKET,
                                                                      E.SIGNER_SOCKET)}
SHADOW_BASES = RBI.SHADOW_BASES
W10_EXACT = ("W10_1_HELD_EXACT", "W10_1S_HELD_EXACT_WITNESS_STOPPED")
W9_SEAMED_EXACT = ("W9_5_GENESIS_COMMITTED_EXACT", "W9_5S_GENESIS_COMMITTED_STOPPED")
# The three reviewed read-only denial proofs of POST10 and their exact terminal PASS lines.
DENIAL_PASS = {
    "P1B-9b": re.compile(r"MB9_WITNESS_DENIAL_PROOF=PASS phase=P1B-9b denied=[1-9][0-9]* allowed_by_design=[0-9]+ "
                         r"allowed=0\Z"),
    "P1B-10": re.compile(r"MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=[1-9][0-9]* allowed=0\Z"),
    "P1B-5": re.compile(r"AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5\Z"),
}

Refused = E.Refused
_need = E._need


def bundle_pins() -> dict[str, str] | None:
    """Under the mb6 BOOT loader: the `name=sha256,...` map in argv[1], which the loader enforced (exit 96 unless every
    bundled module's source hashes to its pin and the module set equals the pin set) before executing any module.
    None when not running under the loader."""
    if not BUNDLED or len(sys.argv) < 3:
        return None
    try:
        pins = dict(item.split("=", 1) for item in sys.argv[1].split(","))
    except ValueError:
        return None
    return pins if all(re.fullmatch(r"[0-9a-f]{64}", value) for value in pins.values()) else None


def _check_contract() -> None:
    pins = bundle_pins()
    if BUNDLED:                                         # no file exists: judge the loader-enforced pin of the contract
        _need(pins is not None and pins.get("e19_p1b10_upgrade") == E19_CONTRACT_SHA256, "E19_CONTRACT_PIN_MISMATCH")
        return
    _need(hashlib.sha256(Path(E.__file__).read_bytes()).hexdigest() == E19_CONTRACT_SHA256, "E19_CONTRACT_PIN_MISMATCH")


def encode_inputs(inputs: Mapping[str, Any]) -> tuple[str, str]:
    """The operator side: canonical JSON (= the contract's canonical form), base64url, and its SHA-256."""
    raw = E._canonical(dict(inputs))
    return base64.urlsafe_b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest()


def decode_inputs(encoded: str, digest: str) -> dict[str, Any]:
    """The host side: exactly the canonical inputs whose SHA-256 the operator bound on the same command line."""
    _need(isinstance(encoded, str) and len(encoded) <= MAX_INLINE_INPUTS and _B64URL.fullmatch(encoded) is not None,
          "INPUTS_ENCODING")
    _need(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "INPUTS_DIGEST")
    try:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        value = json.loads(raw.decode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise Refused("INPUTS_ENCODING") from exc
    _need(hashlib.sha256(raw).hexdigest() == digest, "INPUTS_DIGEST")
    _need(isinstance(value, dict) and E._canonical(value) == raw, "INPUTS_NOT_CANONICAL")
    return value


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


# ------------------------------------------------------------------ bounded reads ---

def _sha_file(path: Path) -> str | None:
    """SHA-256 through O_NOFOLLOW, bounded; ABSENT when the path does not exist; None (UNKNOWN) when unreadable."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except FileNotFoundError:
        return ABSENT
    except OSError:
        return None
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_FILE:
            return None
        digest, left = hashlib.sha256(), MAX_FILE + 1
        while chunk := os.read(fd, min(1 << 20, left)):
            digest.update(chunk)
            left -= len(chunk)
            if left <= 0:
                return None
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        os.close(fd)


def _identity(path: Path) -> Any:
    """lstat identity only (the file is never opened)."""
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return ABSENT
    except OSError:
        return None
    return {"kind": "file" if stat.S_ISREG(meta.st_mode) else "other", "device": meta.st_dev, "inode": meta.st_ino,
            "size": meta.st_size, "uid": meta.st_uid, "gid": meta.st_gid,
            "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
            "mtimeNs": meta.st_mtime_ns, "ctimeNs": meta.st_ctime_ns}


def _listing(path: Path) -> Any:
    try:
        if path.is_symlink():
            return None
        return sorted(os.listdir(path))
    except FileNotFoundError:
        return ABSENT
    except OSError:
        return None


def _tree_names(path: Path) -> Any:
    """Relative names beneath a root-only directory (names only; nothing is opened)."""
    try:
        if path.is_symlink() or not path.is_dir():
            return ABSENT if not os.path.lexists(path) else None
        out = []
        for directory, subdirs, files in os.walk(path, followlinks=False):
            here = Path(directory)
            out.extend((here / name).relative_to(path).as_posix() + ("/" if name in subdirs else "")
                       for name in sorted(subdirs + files))
        return sorted(out)
    except OSError:
        return None


def release_tree_verified(root: Path, sha: str, owner: tuple[int, int] = (0, 0)) -> bool | None:
    """The per-release tree check (installer `release_tree_failures`, restated read-only and bounded): the manifest is
    canonical for this SHA; every listed file is present with its bytes; root-owned; dirs 0755; files 0644 / 0755;
    no symlink; nothing extra outside `venv/`. None when unreadable."""
    top = _host(root, f"{RELEASES}/{sha}")
    try:
        manifest_path = top / MANIFEST
        if top.is_symlink() or not top.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
            return False
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        expected = {item["path"]: item["sha256"] for item in manifest["files"]}
        if manifest.get("candidateSha") != sha or raw != (json.dumps(manifest, sort_keys=True, separators=(",", ":"))
                                                          + "\n").encode("ascii"):
            return False
    except (ValueError, KeyError, TypeError):
        return False
    except OSError:
        return None
    expected[MANIFEST] = hashlib.sha256(raw).hexdigest()
    try:                                     # F5: a genuine root-owned 0755 directory, never a symlink or other type
        venv = os.lstat(top / "venv")
    except FileNotFoundError:
        return False
    except OSError:
        return None
    if not stat.S_ISDIR(venv.st_mode) or (venv.st_uid, venv.st_gid) != owner or stat.S_IMODE(venv.st_mode) != 0o755:
        return False
    seen = set()
    try:
        for directory, subdirs, files in os.walk(top, followlinks=False):
            here = Path(directory)
            if here == top and "venv" in subdirs:
                subdirs.remove("venv")
            for name in subdirs + files:
                path = here / name
                relative = path.relative_to(top).as_posix()
                meta = os.lstat(path)
                if (meta.st_uid, meta.st_gid) != owner or stat.S_ISLNK(meta.st_mode):
                    return False
                if stat.S_ISDIR(meta.st_mode):
                    if stat.S_IMODE(meta.st_mode) != 0o755:
                        return False
                elif relative not in expected or stat.S_IMODE(meta.st_mode) not in (0o644, 0o755) \
                        or _sha_file(path) != expected[relative]:
                    return False
                else:
                    seen.add(relative)
    except OSError:
        return None
    return seen == set(expected)


# --------------------------------------------------------------- default host seams ---

def _units(names: Sequence[str], run: Callable[..., Any] = subprocess.run) -> dict[str, dict[str, str]] | None:
    result = run([SYSTEMCTL, "show", "-p", ",".join(UNIT_PROPERTIES), "--no-pager", "--", *names], env=FIXED_ENV,
                 capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        return None
    out: dict[str, dict[str, str]] = {}
    for block in result.stdout.strip().split("\n\n"):
        facts = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if facts.get("Id") in names:
            out[facts["Id"]] = facts
    return out if set(out) == set(names) else None


def _journal_tail(run: Callable[..., Any] = subprocess.run) -> str | None:
    result = run([JOURNALCTL, "-n", "1", "-o", "json", "--no-pager", "--quiet"], env=FIXED_ENV, capture_output=True,
                 text=True, timeout=60, check=False)
    try:
        cursor = json.loads(result.stdout.strip().splitlines()[-1]).get("__CURSOR") if result.returncode == 0 else None
    except (ValueError, IndexError, AttributeError):
        return None
    return cursor if isinstance(cursor, str) else None


def parse_invocations(lines: Sequence[str]) -> list[str] | None:
    """The distinct invocation ids of `journalctl -u <unit> -o json` lines, in first-seen order (each one is an exec,
    i.e. one credential load attempt). Unreadable is None (UNKNOWN), never empty."""
    order: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            return None
        if not isinstance(entry, dict):
            return None
        invocation = entry.get("_SYSTEMD_INVOCATION_ID") or entry.get("INVOCATION_ID")
        if isinstance(invocation, str) and re.fullmatch(r"[0-9a-f]{32}", invocation) and invocation not in order:
            order.append(invocation)
    return order


def _invocations(unit: str, after: str | None, run: Callable[..., Any] = subprocess.run) -> list[str] | None:
    argv = [JOURNALCTL, "-u", unit, "-o", "json", "--no-pager", "--quiet"]
    if after is not None:
        if not isinstance(after, str) or not after or any(c.isspace() for c in after):
            return None
        argv.append("--after-cursor=" + after)
    result = run(argv, env=FIXED_ENV, capture_output=True, text=True, timeout=60, check=False)
    return parse_invocations(result.stdout.splitlines()) if result.returncode == 0 else None


def _cursor_retained(cursor: str, popen: Callable[..., Any] = subprocess.Popen) -> bool | None:
    """F4: True only when the journal still holds the EXACT entry at `cursor`: a seek to a vacuumed or rotated-out
    cursor silently lands on the nearest retained entry, and `--after-cursor` would then undercount. Reads one bounded
    JSON line and stops journalctl. The exact live behaviour is a DEV proof obligation (record §2)."""
    if not isinstance(cursor, str) or not cursor or any(c.isspace() for c in cursor):
        return None
    proc = popen([JOURNALCTL, "-o", "json", "--no-pager", "--quiet", "--cursor=" + cursor], env=FIXED_ENV,
                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        line = proc.stdout.readline(1 << 20)
    finally:
        proc.kill()
        proc.wait(timeout=30)
    try:
        entry = json.loads(line) if line.strip() else None
    except ValueError:
        return None
    return isinstance(entry, dict) and entry.get("__CURSOR") == cursor


def _process_cwd(root: Path, pid: str) -> str | None:
    if not pid.isdigit() or pid in ("0", "1"):
        return None
    try:
        return os.readlink(_host(root, f"/proc/{pid}/cwd"))
    except OSError:
        return None


def _activation(run: Callable[..., Any] = subprocess.run) -> str | None:
    """The B1c activation line: exactly one LF-terminated line, verbatim (any other line is observed drift)."""
    result = run([ACTIVATION_VERIFY], env=FIXED_ENV, capture_output=True, text=True, timeout=30, check=False)
    text = result.stdout
    if not isinstance(text, str) or not text.endswith("\n") or text.count("\n") != 1:
        return None
    return text[:-1]


def _health(run: Callable[..., Any] = subprocess.run) -> bytes | None:
    result = run([OWNER_CLI, "health"], env=FIXED_ENV, capture_output=True, timeout=30, check=False)
    return result.stdout if result.returncode == 0 else None


def _w10(args: Mapping[str, str], root: Path) -> dict[str, Any] | None:
    import mb10_held_verifier as V10

    return V10.evaluate(args["expectedHead"], args["candidateDigest"], args["updatedAt"], root=root)


def broker_module() -> Any:
    """The pinned broker reader. Bundled: the loader-verified module (its pin must be the accepted one); otherwise the
    repository file, hash-checked before it is executed. Never a path derived from a synthetic `__file__`."""
    if BUNDLED:
        pins = bundle_pins()
        module = sys.modules.get(BROKER_MODULE)
        _need(pins is not None and pins.get(BROKER_MODULE) == BROKER_SHA256 and module is not None
              and str(getattr(module, "__file__", "")) == f"{BOOT_FILE_PREFIX}{BROKER_MODULE}>", "BROKER_NOT_BUNDLED")
        return module
    import importlib.util

    path = HERE.parents[2] / "scripts" / f"{BROKER_MODULE}.py"
    _need(hashlib.sha256(path.read_bytes()).hexdigest() == BROKER_SHA256, "BROKER_PIN_MISMATCH")
    spec = importlib.util.spec_from_file_location("e19_broker_preservation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _broker() -> dict[str, Any] | None:
    module = broker_module()
    return module.evaluate_preservation(module.collect())


# ------------------------------------------------------------------- the observer ---

def _boundary(units: Mapping[str, Mapping[str, str]] | None, root: Path) -> dict[str, Any] | None:
    """The EFFECTIVE restart boundary in the merged `RESTART_BOUNDARY` shape: the unit properties systemd reports plus
    the installed drop-in bytes (ABSENT when not installed)."""
    if units is None:
        return None
    shaped = {unit: {key: units[unit].get(key) for key in expected}
              for unit, expected in E.RESTART_BOUNDARY["units"].items()}
    return {"units": shaped, "dropIns": {path: _sha_file(_host(root, path)) for path in E.WITNESS_DROPINS}}


def _boundary_exact(boundary: Any) -> bool:
    return E._canonical(boundary) == E._canonical(E.RESTART_BOUNDARY) if boundary is not None else False


def _health_fields(raw: bytes | None) -> dict[str, Any] | None:
    import mb9_witness_verifier as V9

    if raw is None:
        return None
    check = V9.check_health(raw, expected_classification="CONSISTENT", kwit_public_key_sha256=E.KWIT_PUBLIC_KEY_SHA256,
                            witness_key_id=E.KWIT_KEY_ID)
    health = check.get("health") if isinstance(check.get("health"), dict) else {}
    fields = {name: health.get(name) for name in E.HEALTH_EXACT}
    if not check.get("exact"):                         # every other reply check failing is observed drift
        fields["classification"] = "NOT_EXACT:" + ",".join(check.get("failures") or ["UNKNOWN"])
    return fields


def _ledger_head(report: Mapping[str, Any] | None) -> str | None:
    """From the unchanged W9 / M-B6 judgement inside W10: the accepted head when W10 and the seamed W9 phase are exact;
    observed drift when W9 reports a ledger failure; otherwise UNKNOWN."""
    if not isinstance(report, Mapping):
        return None
    failures = [str(f) for f in list(report.get("w9Failures") or []) + list(report.get("failures") or [])]
    if any(f.startswith("LEDGER_") for f in failures):
        return "LEDGER_NOT_EXACT"
    if report.get("phase") in W10_EXACT and report.get("w9PhaseHoldJudgedSeparately") in W9_SEAMED_EXACT:
        return E.PRESERVED_PINS["ledgerHead"]
    return None


def _genesis(report: Mapping[str, Any] | None) -> str | None:
    if not isinstance(report, Mapping):
        return None
    value = report.get("committedGenesisDigest")
    return value if isinstance(value, str) else ABSENT


def _broker_facts(result: Mapping[str, Any] | None, units: Mapping[str, Mapping[str, str]] | None) -> dict[str, Any]:
    ok = isinstance(result, Mapping)
    pid = units.get(BROKER_SERVICE, {}).get("MainPID") if units else None
    return {"brokerInvocationId": result.get("runtimeIncarnation") if ok else None,
            "brokerMainPid": pid,
            "brokerBaselineSha256": result.get("baselineCandidateSha256") if ok else None,
            "brokerPreservation": result.get("BROKER_PRESERVATION") if ok else None}


def _safe(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except Exception:  # noqa: BLE001 - a read that cannot be made is UNKNOWN, never success
        return None


def observe(inputs: Mapping[str, Any], *, root: Path | str = Path("/"), units: Callable | None = None,
            journal_tail: Callable | None = None, invocations: Callable | None = None, cwd: Callable | None = None,
            activation: Callable | None = None, health: Callable | None = None, w10: Callable | None = None,
            broker: Callable | None = None, cursor_retained: Callable | None = None,
            new_release: str | None = E.NEW_RELEASE, owner: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """One read-only observation bundle: {observation, healthCapture, w10Report, w10ReportSha256}. The keyword
    arguments after `root` are TEST seams; the defaults are the root host reads."""
    _check_contract()
    _need(isinstance(inputs, Mapping) and set(inputs) == INPUT_FIELDS, "INPUT_FIELDS")
    _need(isinstance(new_release, str) and _SHA40.fullmatch(new_release) is not None and new_release != E.OLD_RELEASE
          and inputs["newRelease"] == new_release, "NEW_RELEASE_NOT_ESTABLISHED")
    root = Path(root)
    units = units or _units
    witness_units = (E.WITNESS_SERVICE, E.OWNER_SOCKET, E.SIGNER_SOCKET)

    unit_facts = _safe(lambda: units((*witness_units, SIGNER_SERVICE, BROKER_SERVICE)))
    cursor = _safe(journal_tail or _journal_tail)
    after = inputs["afterCursor"] if inputs["afterCursor"] is not None else cursor
    retained = _safe(lambda: (cursor_retained or _cursor_retained)(after)) if after is not None else None
    witness_loads = (_safe(lambda: (invocations or _invocations)(E.WITNESS_SERVICE, after)) if retained is True
                     else None)                                    # F4: an unretained baseline is UNKNOWN
    signer_loads = _safe(lambda: (invocations or _invocations)(SIGNER_SERVICE, None))
    boundary = _boundary(unit_facts, root)

    service = None if unit_facts is None else {k: unit_facts[E.WITNESS_SERVICE].get(k) for k in E.SERVICE_FIELDS}
    owner_socket = None if unit_facts is None else {"ActiveState": unit_facts[E.OWNER_SOCKET].get("ActiveState")}
    signer_socket = None if unit_facts is None else {"ActiveState": unit_facts[E.SIGNER_SOCKET].get("ActiveState")}
    running = service is not None and (service["ActiveState"], service["SubState"]) == ("active", "running") \
        and service["MainPID"] not in (None, "", "0") and owner_socket["ActiveState"] == "active" \
        and signer_socket["ActiveState"] == "active"
    pid = service["MainPID"] if running else "0"
    process_cwd = _safe(lambda: (cwd or _process_cwd)(root, pid)) if running else None

    # Socket contact ONLY when RUNNING and the boundary is exactly effective; identity re-read after the call.
    capture = None
    contacted = running and _boundary_exact(boundary)
    if contacted:
        raw = _safe(health or _health)
        after_units = _safe(lambda: units(witness_units))
        before = {"InvocationID": service["InvocationID"], "MainPID": service["MainPID"]}
        after_id = None if after_units is None else {"InvocationID": after_units[E.WITNESS_SERVICE].get("InvocationID"),
                                                     "MainPID": after_units[E.WITNESS_SERVICE].get("MainPID")}
        fields = _safe(lambda: _health_fields(raw))
        if fields is not None and after_id == before:
            capture = {"before": before, "after": after_id, "health": fields}

    signer = None
    if unit_facts is not None and signer_loads is not None:
        signer = {k: unit_facts[SIGNER_SERVICE].get(k) for k in E.SIGNER_FIELDS if k != "invocationsEver"}
        signer["invocationsEver"] = signer_loads

    report = _safe(lambda: (w10 or _w10)(inputs, root))
    w10_bound = report is not None and service is not None and w10_identity(report) == observation_identity(service)
    if not w10_bound:
        report = None                    # F2: a report for another incarnation is not evidence for this one: UNKNOWN
    broker_result = _safe(broker or _broker)
    preserved = {
        "kActCurrentBlobSha256": _sha_file(_host(root, CREDENTIAL)),
        "kActPublicationFileSha256": _sha_file(_host(root, KACT_PUBLICATION)),
        "kWitBlobSha256": _sha_file(_host(root, WITNESS_BLOB)),
        "registryRootAnchorSha256": _sha_file(_host(root, TRUST_DIR + "/registry-root.json")),
        "witnessAnchorSha256": _sha_file(_host(root, TRUST_DIR + "/witness-anchor.json")),
        "registrySha256": _sha_file(_host(root, REGISTRY)),
        "ledgerHead": _ledger_head(report),
        "witnessGenesis": _genesis(report),
        "witnessChain1Sha256": _sha_file(_host(root, WITNESS_STATE + "/chain/1.json")),
        "witnessJsonSha256": _sha_file(_host(root, WITNESS_STATE + "/witness.json")),
        "holdListing": _listing(_host(root, HOLD_STORE)),
        "heldSha256": _sha_file(_host(root, f"{HOLD_STORE}/{HELD_NAME}")),
        **_broker_facts(broker_result, unit_facts),
        "activationLine": _safe(activation or _activation),
        "kActCurrentBlobIdentity": _identity(_host(root, CREDENTIAL)),
        "kWitBlobIdentity": _identity(_host(root, WITNESS_BLOB)),
        "hostKeyIdentity": _identity(_host(root, HOST_KEY)),
        "credstoreListing": _listing(_host(root, CREDSTORE)),
        "custodyListing": _tree_names(_host(root, CUSTODY_ROOT)),
        "witnessCredentialListing": _listing(_host(root, WITNESS_CREDENTIAL_ROOT)),
        "ledgerBytesSha256": {name: _sha_file(_host(root, f"{LEDGER_STATE}/{name}")) for name in LEDGER_NAMES},
        "ownerInputsSha256": {path: _sha_file(_host(root, path)) for path in OWNER_INPUTS},
        "signerUnitFilesSha256": {path: _sha_file(_host(root, path)) for path in SIGNER_UNIT_FILES},
        "witnessUnitFilesSha256": {path: _sha_file(_host(root, path)) for path in WITNESS_UNIT_FILES},
        "installedClisSha256": {path: _sha_file(_host(root, path)) for path in CLIS},
    }
    entries = _listing(_host(root, RELEASES))
    trees = None
    if isinstance(entries, list):
        trees = {e: release_tree_verified(root, e, owner) for e in entries if _SHA40.fullmatch(e)}
    selector = _host(root, CURRENT)
    target = _safe(lambda: os.readlink(selector) if selector.is_symlink()
                   else ABSENT if not os.path.lexists(selector) else "NOT_A_SYMLINK")
    boot = _safe(lambda: _host(root, "/proc/sys/kernel/random/boot_id").read_text("ascii").strip())

    observation = {
        "observationType": E.OBSERVATION_TYPE, "schemaVersion": 1, "mode": E.MODE, "oldRelease": E.OLD_RELEASE,
        "newRelease": new_release, "bootId": boot, "journalCursor": cursor,
        "optEntries": _listing(_host(root, OPT)) if os.path.lexists(_host(root, OPT)) else [],
        "releaseEntries": entries if isinstance(entries, list) else (None if entries is None else []),
        "currentTarget": target, "treeVerified": trees,
        "witness": {"service": service, "ownerSocket": owner_socket, "signerSocket": signer_socket,
                    "cwd": process_cwd, "invocations": {"afterCursor": after, "ids": witness_loads},
                    "health": None if capture is None else capture["health"], "restartBoundary": boundary},
        "signer": signer, "preserved": preserved,
    }
    return {"bundleType": BUNDLE_TYPE, "schemaVersion": 1, "observation": observation, "healthCapture": capture,
            "w10Report": report, "w10ReportSha256": None if report is None else E.document_sha256(report),
            "socketContacted": contacted, "baselineCursorRetained": retained,
            "unitIdentity": _unit_identity(unit_facts, root), "inputsSha256": E.document_sha256(dict(inputs)),
            "authorizes": "NOTHING"}


# ------------------------------------------------------------ pure verification ---

def boundary_reasons(observation: Mapping[str, Any]) -> list[str]:
    """Why the observed restart boundary is not exactly the merged candidate (empty = effective)."""
    boundary = (observation.get("witness") or {}).get("restartBoundary")
    if boundary is None:
        return ["BOUNDARY_UNOBSERVED"]
    reasons = []
    for unit, expected in E.RESTART_BOUNDARY["units"].items():
        for key, value in expected.items():
            if (boundary.get("units") or {}).get(unit, {}).get(key) != value:
                reasons.append(f"{unit}:{key}")
    for path, digest in E.WITNESS_DROPINS.items():
        observed = (boundary.get("dropIns") or {}).get(path)
        if observed != digest:
            reasons.append(f"DROPIN:{path}:{'ABSENT' if observed == ABSENT else 'BYTES'}")
    if set(boundary.get("dropIns") or {}) != set(E.WITNESS_DROPINS):
        reasons.append("DROPIN_SET")
    return reasons


def w10_identity(report: Mapping[str, Any]) -> tuple:
    return (report.get("witnessInvocationId") or None, str(report.get("witnessMainPid")),
            str(report.get("witnessNRestarts")))


def observation_identity(service: Mapping[str, Any]) -> tuple:
    return (service.get("InvocationID") or None, str(service.get("MainPID")), str(service.get("NRestarts")))


def _unit_identity(units: Mapping[str, Mapping[str, str]] | None, root: Path) -> dict[str, Any] | None:
    """F3: each witness unit's effective FragmentPath and every shadow fragment / drop-in path present elsewhere."""
    if units is None:
        return None
    out = {}
    for unit in WITNESS_FRAGMENTS:
        shadows = [f"{base}/{unit}{suffix}" for base in SHADOW_BASES for suffix in ("", ".d")
                   if os.path.lexists(_host(root, f"{base}/{unit}{suffix}"))]
        out[unit] = {"FragmentPath": units[unit].get("FragmentPath"), "shadows": shadows}
    return out


def unit_fragment_reasons(bundle: Mapping[str, Any]) -> list[str]:
    """Why a witness unit is not exactly its accepted /etc fragment (empty = exact)."""
    identity = bundle.get("unitIdentity")
    if not isinstance(identity, Mapping):
        return ["UNIT_IDENTITY_UNOBSERVED"]
    reasons = []
    for unit, fragment in WITNESS_FRAGMENTS.items():
        facts = identity.get(unit) if isinstance(identity.get(unit), Mapping) else {}
        if facts.get("FragmentPath") != fragment:
            reasons.append(f"{unit}:FragmentPath")
        if not isinstance(facts.get("shadows"), list) or facts["shadows"]:
            reasons.extend(f"SHADOW:{path}" for path in facts.get("shadows") or ["UNOBSERVED"])
    return reasons


def verify(bundle: Mapping[str, Any], u0_acceptance: Any, replacement: Any = None, *,
           new_release: str | None = E.NEW_RELEASE) -> dict[str, Any]:
    """The merged classifier against the owner-accepted U0 bundle (two-release aware; no installer status, no E-01).
    `maintenanceReady` is true only on an exact phase with the restart boundary exactly effective."""
    _check_contract()
    _need(isinstance(bundle, Mapping) and bundle.get("bundleType") == BUNDLE_TYPE, "BUNDLE_TYPE")
    verdict = E.classify(bundle["observation"], u0_acceptance, replacement, new_release=new_release)
    reasons = boundary_reasons(bundle["observation"])
    fragments = unit_fragment_reasons(bundle)
    return {**verdict, "restartBoundaryReasons": reasons, "unitFragmentReasons": fragments,
            "maintenanceReady": verdict["phase"] in E.EXACT_PHASES and not reasons and not fragments}


def denial_result(proof: str, transcript: bytes, exit_code: int) -> str:
    """PASS only on exit 0 and the proof's exact terminal PASS line; anything else is FAIL."""
    _need(proof in DENIAL_PASS, "DENIAL_PROOF_UNKNOWN", proof)
    if type(exit_code) is not int or exit_code != 0 or not isinstance(transcript, bytes) or b"\r" in transcript \
            or not transcript.endswith(b"\n"):
        return "FAIL"
    last = transcript.decode("utf-8", "replace").rstrip("\n").split("\n")[-1]
    return "PASS" if DENIAL_PASS[proof].fullmatch(last) else "FAIL"


def post9a_r_evidence(bundle: Mapping[str, Any], denials: Mapping[str, tuple[bytes, int]], u0_acceptance: Any, *,
                      new_release: str | None = E.NEW_RELEASE) -> dict[str, Any]:
    """The POST9A-R evidence document (merged §4.5) from ONE observation bundle: its observation, its own W10 report
    (digest-bound) and its own bound health capture, plus the three denial transcripts. It decides nothing."""
    _check_contract()
    _need(isinstance(bundle, Mapping) and bundle.get("bundleType") == BUNDLE_TYPE, "BUNDLE_TYPE")
    _need(isinstance(denials, Mapping) and set(denials) == set(DENIAL_PASS), "DENIAL_SET")
    report = bundle["w10Report"]
    _need(isinstance(report, Mapping) and bundle.get("w10ReportSha256") == E.document_sha256(report), "W10_NOT_BOUND")
    service = ((bundle.get("observation") or {}).get("witness") or {}).get("service")
    _need(isinstance(service, Mapping) and w10_identity(report) == observation_identity(service),
          "W10_NOT_THIS_OBSERVATION")                              # F2: digest-valid but stale / substituted
    base = E.trusted_baseline(u0_acceptance, new_release=new_release)
    capture = bundle["healthCapture"]
    return {"evidenceType": E.POST9A_R_TYPE, "schemaVersion": 1, "mode": E.MODE,
            "baselineSubjectSha256": E.document_sha256(base), "observation": bundle["observation"],
            "w9PhaseDirect": report.get("w9PhaseDirect"), "w9PhaseSeamed": report.get("w9PhaseHoldJudgedSeparately"),
            "w10Phase": report.get("phase"), "w10OutputSha256": bundle["w10ReportSha256"],
            "healthCapture": capture if capture is not None else {"before": None, "after": None, "health": None},
            "denials": {proof: denial_result(proof, *denials[proof]) for proof in sorted(DENIAL_PASS)}}


def post9a_r(bundle: Mapping[str, Any], denials: Mapping[str, tuple[bytes, int]], u0_acceptance: Any, *,
             new_release: str | None = E.NEW_RELEASE) -> dict[str, Any]:
    """POST9A-R over the assembled evidence (the merged `post9a_r`). Never an acceptance: the owner's verbatim
    statement and the local record remain required (merged §4.6)."""
    evidence = post9a_r_evidence(bundle, denials, u0_acceptance, new_release=new_release)
    report = E.post9a_r(evidence, u0_acceptance, new_release=new_release)
    return {**report, "evidence": evidence, "acceptanceGranted": False}


# ------------------------------------------------------------------------ entry ---

def _read_json(path: str) -> Any:
    raw = Path(path).read_bytes()
    _need(len(raw) <= 4 * E.MAX_OBSERVATION, "INPUT_TOO_LARGE")
    return json.loads(raw)


def main(argv: list[str]) -> int:
    try:
        if (len(argv) == 2 and argv[0] == "observe") or (len(argv) == 3 and argv[0] == "observe-inline"):
            inputs = _read_json(argv[1]) if argv[0] == "observe" else decode_inputs(argv[1], argv[2])
            import mb6_ledger_verifier as V6

            V6.require_dev_root()
            if V6.RELEASE_TREE not in sys.path:
                sys.path.insert(0, V6.RELEASE_TREE)
            result = observe(inputs)
        elif len(argv) in (3, 4) and argv[0] == "verify":
            result = verify(_read_json(argv[1]), _read_json(argv[2]), _read_json(argv[3]) if len(argv) == 4 else None)
        elif len(argv) == 4 and argv[0] == "post9a-r":
            raw = _read_json(argv[2])
            denials = {name: (item["transcript"].encode("utf-8"), item["exitCode"]) for name, item in raw.items()}
            result = post9a_r(_read_json(argv[1]), denials, _read_json(argv[3]))
        else:
            raise Refused("USAGE")
    except (Refused, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"e19_maintenance_observer: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 3
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
