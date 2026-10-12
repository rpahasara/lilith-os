#!/usr/bin/python3 -IB
"""15B2b-B1b-3e M-B12 PR-B2: the PRESERVATION_SET proof producer (E-23). Stdlib only; reads, never writes.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md.
DESIGN / SOURCE ONLY. Running `observe` live needs a separate owner authorization.

Preflight §19 E-23 is "preservation set (B1b-3d §23) unchanged: Stage III, broker, API unit"; B1b-3d §23 defines the
set: "the B1c helper, library, verifier, and sudoers; activation; the legacy broker release, selector, units,
`dev.json`, and state file metadata; the Stage III artifacts; the API unit". `MEMBERS` is exactly that set. Two forms:

- `observe` (root, DEV): one read-only `lstat` / bounded read of every member (never through a symlink; directories
  listed recursively with per-entry hashes; the broker state files as metadata only; absent members recorded as
  ABSENT). It prints one canonical JSON observation. An observation is evidence, never a proof.
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
FILE, TREE, LINK, LISTING, METADATA = "FILE", "TREE", "LINK", "LISTING", "METADATA"
STAGE3_VAULT = "/var/lib/.lilith-memory-broker-stage3-a2"
# B1b-3d §23, in order. Paths: scripts/dev_deployer/install_dev_deployer_boundary.sh (B1c),
# scripts/verify_broker_dev_current_incarnation.py (broker, Stage III), the B1b-3d design §2 (API unit).
MEMBERS: tuple[tuple[str, str, str], ...] = (
    ("B1C_HELPER", "/usr/local/sbin/lilith-dev-deploy", FILE),
    ("B1C_LIBRARY", "/usr/local/lib/lilith-dev-deploy", TREE),
    ("B1C_VERIFIER", "/usr/local/sbin/lilith-activation-verify", FILE),
    ("B1C_SUDOERS", "/etc/sudoers.d/lilith-dev-deployer", FILE),
    ("ACTIVATION", "/etc/lilith-os-dev", TREE),
    ("BROKER_RELEASES", "/opt/lilith-memory-broker/releases", LISTING),
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
MAX_FILE = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 4096
# Owner-accepted baseline observations: SHA-256 of the exact observation bytes -> the acceptance record SHA-256. EMPTY.
ACCEPTED_BASELINES: Mapping[str, str] = {}
NONCLAIM = ("NONCLAIM: DR-5 equality, HELD / custody / CURRENT / witness / ledger preservation and broker continuity "
            "are not judged here")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


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


def _file_sha(path: str, meta: os.stat_result) -> str | None:
    if meta.st_size > MAX_FILE:
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        digest, total = hashlib.sha256(), 0
        while chunk := os.read(fd, 1 << 20):
            total += len(chunk)
            if total > MAX_FILE:
                return None
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(fd)


def _entry(path: str) -> dict[str, Any]:
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return {"kind": "ABSENT"}
    value = _meta(meta)
    if value["kind"] == "REGULAR":
        value["size"] = meta.st_size
        value["sha256"] = _file_sha(path, meta)
    elif value["kind"] == "SYMLINK":
        value["target"] = os.readlink(path)
    return value


def observe_member(path: str, form: str) -> dict[str, Any]:
    if form == METADATA:
        try:
            return _meta(os.lstat(path))
        except FileNotFoundError:
            return {"kind": "ABSENT"}
    value = _entry(path)
    if form == LISTING and value["kind"] == "DIRECTORY":
        value["names"] = sorted(os.listdir(path))[:MAX_TREE_ENTRIES + 1]
    if form == TREE and value["kind"] == "DIRECTORY":
        entries, stack = [], [""]
        while stack and len(entries) <= MAX_TREE_ENTRIES:
            relative = stack.pop()
            for name in sorted(os.listdir(os.path.join(path, relative) if relative else path)):
                child = f"{relative}/{name}" if relative else name
                item = _entry(os.path.join(path, child))
                entries.append([child, item])
                if item["kind"] == "DIRECTORY":
                    stack.append(child)
        value["entries"] = sorted(entries, key=lambda pair: pair[0])
    return value


def canonical(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def observe(*, member: Callable[[str, str], dict] = observe_member, euid: Callable[[], int] = os.geteuid,
            now: Callable[[], str] = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")) -> bytes:
    if euid() != 0:
        raise PermissionError("NOT_ROOT")
    return canonical({"observationType": OBSERVATION_TYPE, "schemaVersion": 1, "environment": "dev",
                      "observedAt": now(),
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
                                                                          "environment", "observedAt", "members"} \
            or doc["observationType"] != OBSERVATION_TYPE or doc["schemaVersion"] != 1 or doc["environment"] != "dev" \
            or not isinstance(doc["observedAt"], str) or not _INSTANT.fullmatch(doc["observedAt"]):
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
        if before["observed"] == after["observed"] and _complete(after["observed"]):
            say(f"EQUAL: {after['name']} {after['path']}")
        else:
            failures.append(f"FAIL: CHANGED_OR_INCOMPLETE {after['name']} {after['path']}")
    for line in failures:
        say(line)
    say(NONCLAIM)
    say(f"PRESERVATION_SET_PROOF={'FAIL' if failures else 'PASS'} baseline={baseline_sha}")
    return not failures


def _complete(observed: Mapping[str, Any]) -> bool:
    """A member whose bytes could not be hashed (too large, not regular after open) or whose tree was truncated
    is never EQUAL, even when the baseline shows the same gap."""
    if observed.get("kind") == "REGULAR" and "sha256" in observed and observed["sha256"] is None:
        return False
    if len(observed.get("entries", ())) > MAX_TREE_ENTRIES or len(observed.get("names", ())) > MAX_TREE_ENTRIES:
        return False
    return all(_complete(item) for _name, item in observed.get("entries", ()))


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
