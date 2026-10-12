#!/usr/bin/python3 -IB
"""15B2b-B1b-3e M-B12 PR-B2: the PRESERVATION_SET proof producer (E-23). Stdlib only; reads, never writes.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md.
DESIGN / SOURCE ONLY. Running `observe` live needs a separate owner authorization.

Preflight §19 E-23 is "preservation set (B1b-3d §23) unchanged: Stage III, broker, API unit"; B1b-3d §23 defines the
set: "the B1c helper, library, verifier, and sudoers; activation; the legacy broker release, selector, units,
`dev.json`, and state file metadata; the Stage III artifacts; the API unit". `MEMBERS` is exactly that set (22). Two
forms:

- `observe` (root, DEV): one read-only observation of every member. Every directory is opened `O_DIRECTORY |
  O_NOFOLLOW` and walked relative to its descriptor; every entry is `lstat`-ed through that descriptor; every regular
  file is opened `O_NOFOLLOW` through it and its `fstat` must be the same file (device, inode, size, mtime) before and
  after the read; symlinks are recorded by target and never followed. Trees record every entry (path, type, owner,
  mode, size, SHA-256), so additions, removals and modifications all change the observation. Bounds (`LIMITS`) are
  checked BEFORE allocation and a member that exceeds one, holds an unsupported type, or changes during the read is
  recorded as `refused` (never truncated); a refused member is never EQUAL. The broker state files are metadata only
  (§23); absent members are recorded ABSENT. It prints one canonical JSON observation: evidence, never a proof.
- `compare <baseline.json> <observation.json>` (owner, off-host): member-by-member equality against a BASELINE
  observation that the owner accepted and that is pinned by its SHA-256 in `ACCEPTED_BASELINES` (EMPTY: no baseline
  is accepted, so compare FAILS `BASELINE_NOT_ESTABLISHED` today). A PASS transcript is exactly `expected_pass(…)`.

What this proof is NOT (each is a separate judgement with its own producer):

    DR-5 result equality (deployer denial, mb10/mb11 DR-5 targets)      != preservation-set equality
    HELD / hold-store, CURRENT, credstore, witness, ledger preservation (W10 / W11 verifiers, §24) != this proof
    broker continuity (BROKER_PRESERVATION)                             != this proof (it overlaps, never replaces)

No authority, custody, HELD, witness, ledger or credential path is a member (a test enforces it).

Last line: `PRESERVATION_SET_PROOF=PASS baseline=<sha256>` (exit 0) or `…=FAIL …` (exit 1); usage is exit 2.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

OBSERVATION_TYPE = "LILITH_MB12_PRESERVATION_SET_OBSERVATION"
FILE, TREE, LINK, METADATA = "FILE", "TREE", "LINK", "METADATA"
STAGE3_VAULT = "/var/lib/.lilith-memory-broker-stage3-a2"
# B1b-3d §23, in order. Paths: scripts/dev_deployer/install_dev_deployer_boundary.sh (B1c),
# scripts/verify_broker_dev_current_incarnation.py (broker, Stage III), the B1b-3d design §2 (API unit).
MEMBERS: tuple[tuple[str, str, str], ...] = (
    ("B1C_HELPER", "/usr/local/sbin/lilith-dev-deploy", FILE),
    ("B1C_LIBRARY", "/usr/local/lib/lilith-dev-deploy", TREE),
    ("B1C_VERIFIER", "/usr/local/sbin/lilith-activation-verify", FILE),
    ("B1C_SUDOERS", "/etc/sudoers.d/lilith-dev-deployer", FILE),
    ("ACTIVATION", "/etc/lilith-os-dev", TREE),
    ("BROKER_RELEASES", "/opt/lilith-memory-broker/releases", TREE),       # the release CONTENTS, every file hashed
    ("BROKER_SELECTOR", "/opt/lilith-memory-broker/current", LINK),
    ("BROKER_SERVICE_UNIT", "/etc/systemd/system/lilith-memory-broker.service", FILE),
    ("BROKER_SOCKET_UNIT", "/etc/systemd/system/lilith-memory-broker.socket", FILE),
    ("BROKER_TMPFILES", "/etc/tmpfiles.d/lilith-memory-broker.conf", FILE),
    ("BROKER_DEV_JSON", "/etc/lilith-memory-broker/dev.json", FILE),
    ("BROKER_OWNER_DB", "/var/lib/lilith-memory-broker/owner-control/owner_control.db", METADATA),
    ("BROKER_EVIDENCE_DB", "/var/lib/lilith-memory-broker/state/synthetic_evidence.db", METADATA),
    ("STAGE3_VAULT", STAGE3_VAULT, TREE),
    ("STAGE3_DISPATCH_ATTEMPT", "/var/lib/.lilith-memory-broker-stage3-a2-dispatch-attempt.json", FILE),
    ("STAGE3_FINAL_ATTEMPT", "/var/lib/.lilith-memory-broker-stage3-a2-final-attempt.json", FILE),
    ("STAGE3_AUTHORIZATION", "/etc/lilith-memory-broker/b1b2b-stage3-a2-authorization.json", FILE),
    ("STAGE3_AUTHORIZATION_USED", "/etc/lilith-memory-broker/b1b2b-stage3-a2-authorization.used.json", FILE),
    ("STAGE3_ARM", "/run/lilith-memory-stage3/a2-arm.json", FILE),
    ("STAGE3_GUARD", "/run/lilith-stage3-a2/guard.json", FILE),
    ("STAGE3_ACTIVATION_READY", "/run/lilith-stage3-a2/activation.ready", FILE),
    ("API_UNIT", "/etc/systemd/system/lilith-os-api-dev.service", FILE),
)
# Never members: authority / custody / HELD / witness / ledger / credentials (judged elsewhere, or never read).
EXCLUDED_PREFIXES = ("/etc/credstore", "/etc/lilith-authority", "/var/lib/lilith-authority", "/opt/lilith-authority",
                     "/etc/lilith-recovery-witness", "/var/lib/lilith-recovery-witness", "/run/credentials",
                     "/var/lib/systemd/credential.secret", "/run/lilith-authority", "/run/lilith-recovery-witness")
# Bounds, per member, checked before allocation. The broker release holds a Python venv whose size on DEV is NOT
# observed: these bound memory (≈ 200 B of JSON per entry), time and output while admitting a venv of tens of thousands
# of files; a larger tree is REFUSED (the proof then cannot pass until an owner decision), never truncated.
LIMITS = {"maxFileBytes": 64 * 1024 * 1024, "maxTreeEntries": 65536, "maxTreeBytes": 1024 * 1024 * 1024,
          "maxDepth": 32}
CHUNK = 1 << 20
# Owner-accepted baseline observations: SHA-256 of the exact observation bytes -> the acceptance record SHA-256. EMPTY.
ACCEPTED_BASELINES: Mapping[str, str] = {}
NONCLAIM = ("NONCLAIM: DR-5 equality, HELD / custody / CURRENT / witness / ledger preservation and broker continuity "
            "are not judged here")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
# TEST seam only: called after an entry's `lstat` and before it is opened (a race can be simulated).
_AFTER_LSTAT: Callable[[int | None, str], None] | None = None


class Refusal(Exception):
    pass


def _kind(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "SYMLINK"
    if stat.S_ISDIR(mode):
        return "DIRECTORY"
    if stat.S_ISREG(mode):
        return "REGULAR"
    return "OTHER"


def _meta(meta: os.stat_result) -> dict[str, Any]:
    return {"kind": _kind(meta.st_mode), "uid": meta.st_uid, "gid": meta.st_gid,
            "mode": format(stat.S_IMODE(meta.st_mode), "04o")}


def _same(a: os.stat_result, b: os.stat_result) -> bool:
    return (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, stat.S_IFMT(a.st_mode)) == \
        (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, stat.S_IFMT(b.st_mode))


class _Budget:
    def __init__(self) -> None:
        self.entries = 0
        self.bytes = 0

    def entry(self) -> None:
        self.entries += 1
        if self.entries > LIMITS["maxTreeEntries"]:
            raise Refusal("TREE_TOO_MANY_ENTRIES")

    def size(self, size: int) -> None:
        if size > LIMITS["maxFileBytes"]:
            raise Refusal("FILE_TOO_LARGE")
        self.bytes += size
        if self.bytes > LIMITS["maxTreeBytes"]:
            raise Refusal("TREE_TOO_MANY_BYTES")


def _hash_file(dirfd: int | None, name: str, meta: os.stat_result, budget: _Budget) -> str:
    budget.size(meta.st_size)                                   # before any allocation
    fd = os.open(name, _FILE_FLAGS, dir_fd=dirfd)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or not _same(meta, opened):
            raise Refusal("IDENTITY_CHANGED")
        digest, total = hashlib.sha256(), 0
        while chunk := os.read(fd, CHUNK):
            total += len(chunk)
            if total > meta.st_size:
                raise Refusal("CHANGED_DURING_READ")
            digest.update(chunk)
        if total != meta.st_size or not _same(meta, os.fstat(fd)):
            raise Refusal("CHANGED_DURING_READ")
        return digest.hexdigest()
    finally:
        os.close(fd)


def _entry(dirfd: int | None, name: str, budget: _Budget, depth: int) -> dict[str, Any]:
    """One entry relative to `dirfd`, never through a symlink. Directories recurse; other types are refused."""
    try:
        meta = os.lstat(name, dir_fd=dirfd)
    except FileNotFoundError:
        return {"kind": "ABSENT"}
    if _AFTER_LSTAT is not None:
        _AFTER_LSTAT(dirfd, name)
    value = _meta(meta)
    if value["kind"] == "REGULAR":
        value["size"] = meta.st_size
        value["sha256"] = _hash_file(dirfd, name, meta, budget)
    elif value["kind"] == "SYMLINK":
        value["target"] = os.readlink(name, dir_fd=dirfd)
    elif value["kind"] == "DIRECTORY":
        if depth > LIMITS["maxDepth"]:
            raise Refusal("TREE_TOO_DEEP")
        fd = os.open(name, _DIR_FLAGS, dir_fd=dirfd)
        try:
            if not _same(meta, os.fstat(fd)):
                raise Refusal("IDENTITY_CHANGED")
            names = []
            with os.scandir(fd) as iterator:
                for item in iterator:
                    budget.entry()                              # before the name is kept
                    names.append(item.name)
            value["entries"] = [[child, _entry(fd, child, budget, depth + 1)] for child in sorted(names)]
        finally:
            os.close(fd)
    else:
        raise Refusal("UNSUPPORTED_TYPE")
    return value


def observe_member(path: str, form: str) -> dict[str, Any]:
    """The observation of one member. A refusal is recorded (with the member's own `lstat` facts if any), never
    hidden; the member is then never EQUAL."""
    parent, name = os.path.split(path)
    budget = _Budget()
    try:
        parent_fd = os.open(parent, _DIR_FLAGS)
    except FileNotFoundError:
        return {"kind": "ABSENT"}
    try:
        if form == METADATA:
            try:
                return _meta(os.lstat(name, dir_fd=parent_fd))
            except FileNotFoundError:
                return {"kind": "ABSENT"}
        try:
            value = _entry(parent_fd, name, budget, 0)
        except Refusal as refusal:
            return {"refused": refusal.args[0]}
        if form == TREE and value["kind"] not in ("DIRECTORY", "ABSENT"):
            return {"refused": "NOT_A_DIRECTORY", "kind": value["kind"]}
        if form in (FILE, LINK) and value["kind"] == "DIRECTORY":
            return {"refused": "UNEXPECTED_DIRECTORY", "kind": "DIRECTORY"}
        return value
    finally:
        os.close(parent_fd)


def canonical(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def observe(*, member: Callable[[str, str], dict] = observe_member, euid: Callable[[], int] = os.geteuid,
            now: Callable[[], str] = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")) -> bytes:
    if euid() != 0:
        raise PermissionError("NOT_ROOT")
    return canonical({"observationType": OBSERVATION_TYPE, "schemaVersion": 1, "environment": "dev",
                      "observedAt": now(), "limits": dict(LIMITS),
                      "members": [{"name": name, "path": path, "form": form, "observed": member(path, form)}
                                  for name, path, form in MEMBERS]})


class CompareError(ValueError):
    pass


def parse_observation(raw: bytes) -> dict[str, Any]:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise CompareError("OBSERVATION_DUPLICATE_KEY")
        return dict(pairs)
    try:
        doc = json.loads(raw.decode("ascii"), object_pairs_hook=no_duplicates)
    except CompareError:
        raise
    except (UnicodeDecodeError, ValueError) as exc:
        raise CompareError("OBSERVATION_MALFORMED") from exc
    if not isinstance(doc, dict) or canonical(doc) != raw or set(doc) != {"observationType", "schemaVersion",
                                                                          "environment", "observedAt", "limits",
                                                                          "members"} \
            or doc["observationType"] != OBSERVATION_TYPE or doc["schemaVersion"] != 1 or doc["environment"] != "dev" \
            or not isinstance(doc["observedAt"], str) or not _INSTANT.fullmatch(doc["observedAt"]) \
            or doc["limits"] != LIMITS:
        raise CompareError("OBSERVATION_MALFORMED")
    members = doc["members"]
    if not isinstance(members, list) or [(m.get("name"), m.get("path"), m.get("form")) if isinstance(m, dict)
                                         else None for m in members] != [tuple(x) for x in MEMBERS] \
            or any(set(m) != {"name", "path", "form", "observed"} or not isinstance(m["observed"], dict)
                   for m in members):
        raise CompareError("OBSERVATION_MEMBERS_NOT_EXACT")
    return doc


def expected_pass(baseline_sha256: str, baseline_at: str, observation_sha256: str, observation_at: str) -> bytes:
    lines = [f"BASELINE: sha256={baseline_sha256} observedAt={baseline_at}",
             f"OBSERVATION: sha256={observation_sha256} observedAt={observation_at}"]
    lines += [f"EQUAL: {name} {path}" for name, path, _form in MEMBERS]
    lines += [NONCLAIM, f"PRESERVATION_SET_PROOF=PASS baseline={baseline_sha256}"]
    return ("\n".join(lines) + "\n").encode("ascii")


def complete(observed: Any) -> bool:
    """No refusal anywhere in the member (a refused, oversized, changing or unsupported member is never EQUAL)."""
    if not isinstance(observed, Mapping) or "refused" in observed:
        return False
    return all(isinstance(pair, list) and len(pair) == 2 and complete(pair[1]) for pair in observed.get("entries", ()))


def compare(baseline_raw: bytes, observation_raw: bytes, *, accepted: Mapping[str, str] = ACCEPTED_BASELINES,
            say: Callable[[str], None] = print) -> bool:
    baseline_sha = hashlib.sha256(baseline_raw).hexdigest()
    try:
        baseline, observation = parse_observation(baseline_raw), parse_observation(observation_raw)
    except CompareError as exc:
        say(f"PRESERVATION_SET_PROOF=FAIL reason={exc.args[0]}")
        return False
    observation_sha = hashlib.sha256(observation_raw).hexdigest()
    if baseline_sha not in accepted:
        say(f"PRESERVATION_SET_PROOF=FAIL reason=BASELINE_NOT_ESTABLISHED baseline={baseline_sha}")
        return False
    if observation["observedAt"] <= baseline["observedAt"]:
        say("PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_NOT_AFTER_BASELINE")
        return False
    say(f"BASELINE: sha256={baseline_sha} observedAt={baseline['observedAt']}")
    say(f"OBSERVATION: sha256={observation_sha} observedAt={observation['observedAt']}")
    failures = []
    for before, after in zip(baseline["members"], observation["members"]):
        if before["observed"] == after["observed"] and complete(after["observed"]):
            say(f"EQUAL: {after['name']} {after['path']}")
        else:
            failures.append(f"FAIL: CHANGED_OR_INCOMPLETE {after['name']} {after['path']}")
    for line in failures:
        say(line)
    say(NONCLAIM)
    say(f"PRESERVATION_SET_PROOF={'FAIL' if failures else 'PASS'} baseline={baseline_sha}")
    return not failures


def main(argv: Sequence[str]) -> int:
    if list(argv) == ["observe"]:
        try:
            sys.stdout.buffer.write(observe())
        except (PermissionError, OSError) as exc:
            print(f"PRESERVATION_SET_OBSERVATION=FAIL reason={exc.args[0] if exc.args else type(exc).__name__}")
            return 1
        return 0
    if len(argv) == 3 and argv[0] == "compare":
        try:
            baseline, observation = Path(argv[1]).read_bytes(), Path(argv[2]).read_bytes()
        except OSError:
            print("PRESERVATION_SET_PROOF=FAIL reason=INPUT_UNREADABLE")
            return 1
        return 0 if compare(baseline, observation) else 1
    print("PRESERVATION_SET_PROOF=FAIL reason=USAGE")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
