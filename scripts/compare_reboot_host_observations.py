#!/usr/bin/env python3
"""Offline PRE/POST comparison of two authority host observations across one reboot.

Record: docs/architecture/slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline.md (§5, §7).

Input is two saved transcripts of
`services/authority-dev/ceremony/observe_authority_dev_host.py observe`: one
taken immediately before the owner-authorized DEV reboot, one after it. This
tool runs on the owner workstation only. It reads the two files and writes
JSON to stdout. It never contacts DEV, runs no subprocess, and judges no
authority. `install_authority_dev.py status --expect P1A-9` still owns exact
authority state, the broker verifier owns broker continuity, and DR-5 owns
routine-deployer denial.

A reboot legitimately changes only these observed facts:

- `host.bootId` (must change), `host.kernel` (must equal the kernel the
  owner expected from the PRE inventory), `host.rebootRequired`
  (true -> false), and the two volatile facts;
- the broker unit's process-lifetime properties (the broker verifier judges
  the new incarnation);
- OR-6: `/run/lilith-authority-dev` and `/run/lilith-recovery-witness`, which
  the installed tmpfiles files create at boot. They must then exist with
  exactly the installed tmpfiles spec. Their tmpfs inode, device and times
  are new;
- entries of the `/run` namespace inventory that nothing recreated. The
  broker's own tmpfiles directory `lilith-memory` must be recreated.

Every other observed fact must be byte-identical. Anything else is
UNEXPECTED, and the ceremony stops (§11).

A second, stricter mode, `routine-deploy`, compares the post-M-R2 observation
with the one taken after the §10 routine DEV deployment. No reboot and no
broker restart may happen in between, so every section must be identical,
broker lifetime included. There is exactly one reviewed exception: the pinned
deploy helper (`scripts/dev_deployer/lilith-dev-deploy`, the
`DEPLOY_HELPER_SHA` the broker verifier checks) runs `umask 077; exec
9>/run/lilith-dev-deploy.lock` as root and never removes the file. The first
deployment after a boot therefore adds that one `/run` name. The observer
records names only, so the addition is accepted only together with a fixed
read-only `stat` line for that exact path, proving a regular empty file,
`0:0`, mode `600`, one link. Any other `/run` addition or removal, and any
other difference, is UNEXPECTED.

    runtime directory existence != witness state != authority readiness
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "LILITH_AUTHORITY_DEV_REBOOT_OBSERVATION_COMPARISON"
OBSERVER_SCHEMA = "LILITH_AUTHORITY_DEV_HOST_OBSERVATION"
VOLATILE = (("host", "utcNow"), ("host", "uptimeSeconds"))
SECTIONS = ("host", "releases", "hostFiles", "units", "accounts", "currentBlob", "hostKey", "listings",
            "pr1Objects", "filesystems", "namespaceInventory")
# Sections a reboot must not touch at all.
IDENTICAL_SECTIONS = ("releases", "hostFiles", "accounts", "currentBlob", "hostKey", "listings", "filesystems")
HOST_IDENTICAL = ("hostname", "machineId", "osPrettyName", "swaps", "localtime")
BROKER_UNIT = "lilith-memory-broker.service"
BROKER_PROCESS_LIFETIME = frozenset({"ActiveState", "SubState", "NRestarts", "MainPID", "InvocationID",
                                     "ExecMainStartTimestamp", "InactiveExitTimestamp", "ActiveEnterTimestamp"})
SIGNER_ACCOUNT = "lilith-authority-dev"
# OR-6. Specs are the installed tmpfiles lines:
#   d /run/lilith-authority-dev 0700 root root -
#   d /run/lilith-recovery-witness 0710 root lilith-authority-dev -
# (kind, uid, gid, mode); gid None means the signer account's group.
TMPFILES_RUNTIME_DIRS = {"/run/lilith-authority-dev": ("dir", 0, 0, "0700"),
                         "/run/lilith-recovery-witness": ("dir", 0, None, "0710")}
RUN_ROOT = "/run"
RUN_RECREATED_REQUIRED = frozenset({"lilith-memory"})
BOOT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FINAL_LINE = re.compile(r"PR1A_HOST_OBSERVATION=COMPLETE stableSha256=([0-9a-f]{64})\Z")
ROUTINE_SCHEMA = "LILITH_AUTHORITY_DEV_ROUTINE_DEPLOY_OBSERVATION_COMPARISON"
# The one reviewed routine-deploy /run effect (see the module docstring).
DEPLOY_LOCK = "/run/lilith-dev-deploy.lock"
DEPLOY_LOCK_NAME = "lilith-dev-deploy.lock"
# Operator command: sudo -n stat -c '%n|%F|%u|%g|%a|%s|%h' /run/lilith-dev-deploy.lock
LOCK_STAT_FORMAT = "%n|%F|%u|%g|%a|%s|%h"
DEPLOY_LOCK_SPEC = {"path": DEPLOY_LOCK, "type": "regular empty file", "uid": "0", "gid": "0", "mode": "600",
                    "size": "0", "links": "1"}
LOCK_STAT_LINE = re.compile(r"([^|\n]+)\|([a-z ]+)\|([0-9]+)\|([0-9]+)\|([0-7]{1,4})\|([0-9]+)\|([0-9]+)\Z")


class CompareError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _digest(value) -> str:
    """The observer's own canonical digest (observe_authority_dev_host._digest)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                          .encode("ascii")).hexdigest()


def stable_facts(facts: dict) -> dict:
    stable = json.loads(json.dumps(facts))
    for section, key in VOLATILE:
        stable[section].pop(key, None)
    return stable


def parse_transcript(text: str) -> dict:
    """One observer transcript: the JSON report, then exactly the COMPLETE line.
    The stable digest is recomputed from the facts, never trusted."""
    body, _, last = text.rstrip("\n").rpartition("\n")
    match = FINAL_LINE.fullmatch(last.strip())
    if match is None:
        raise CompareError("TRANSCRIPT_NOT_COMPLETE")
    try:
        report = json.loads(body)
    except ValueError as exc:
        raise CompareError("TRANSCRIPT_JSON_MALFORMED") from exc
    if not isinstance(report, dict) or report.get("schema") != OBSERVER_SCHEMA or report.get("schemaVersion") != 1:
        raise CompareError("OBSERVER_SCHEMA_MISMATCH")
    facts = report.get("facts")
    if not isinstance(facts, dict) or set(facts) != set(SECTIONS):
        raise CompareError("OBSERVER_SECTIONS_MISMATCH")
    stable = stable_facts(facts)
    recomputed = _digest(stable)
    if recomputed != report.get("stableSha256") or recomputed != match.group(1):
        raise CompareError("STABLE_DIGEST_MISMATCH")
    if report.get("sectionSha256") != {name: _digest(value) for name, value in sorted(stable.items())}:
        raise CompareError("SECTION_DIGEST_MISMATCH")
    return report


def _diff_keys(pre: dict, post: dict) -> list[str]:
    return sorted(key for key in set(pre) | set(post) if pre.get(key) != post.get(key))


def _runtime_dir_state(meta: dict | None, spec: tuple, signer_gid) -> str:
    if meta is None:
        return "ABSENT"
    kind, uid, gid, mode = spec
    gid = signer_gid if gid is None else gid
    if (meta.get("kind"), meta.get("uid"), meta.get("gid"), meta.get("mode")) == (kind, uid, gid, mode):
        return "PRESENT_EXACT_TMPFILES_SPEC"
    return "PRESENT_WRONG_SPEC"


def compare(pre: dict, post: dict, *, expected_kernel: str, accepted_pre_stable: str | None = None) -> dict:
    """Pure: two parsed observer reports -> classification."""
    expected: list[str] = []
    unexpected: list[str] = []
    a, b = pre["facts"], post["facts"]

    # Host identity and the reboot itself.
    for key in HOST_IDENTICAL:
        if a["host"].get(key) != b["host"].get(key):
            unexpected.append("HOST_CHANGED:" + key)
    pre_boot, post_boot = a["host"].get("bootId"), b["host"].get("bootId")
    if not (BOOT_ID.fullmatch(str(pre_boot)) and BOOT_ID.fullmatch(str(post_boot))):
        unexpected.append("BOOT_ID_INVALID")
    elif pre_boot == post_boot:
        unexpected.append("REBOOT_NOT_OBSERVED")
    else:
        expected.append("BOOT_ID_CHANGED")
    if b["host"].get("kernel") != expected_kernel:
        unexpected.append("KERNEL_NOT_EXPECTED")
    elif a["host"].get("kernel") != expected_kernel:
        expected.append("KERNEL_CHANGED_TO_EXPECTED")
    else:
        expected.append("KERNEL_UNCHANGED_AS_EXPECTED")
    if a["host"].get("rebootRequired") is not True:
        unexpected.append("PRE_REBOOT_REQUIRED_NOT_PRESENT")
    if b["host"].get("rebootRequired") is not False:
        unexpected.append("POST_REBOOT_REQUIRED_STILL_PRESENT")
    else:
        expected.append("REBOOT_REQUIRED_CLEARED")
    if not str(a["host"].get("utcNow", "")) < str(b["host"].get("utcNow", "")):
        unexpected.append("POST_NOT_AFTER_PRE")

    for section in IDENTICAL_SECTIONS:
        if a[section] != b[section]:
            unexpected.append("SECTION_CHANGED:" + section)

    # Units: only the broker's process-lifetime properties may change.
    shows_a, shows_b = a["units"].get("show", {}), b["units"].get("show", {})
    if set(shows_a) != set(shows_b):
        unexpected.append("UNIT_SET_CHANGED")
    for unit in sorted(set(shows_a) & set(shows_b)):
        changed = _diff_keys(shows_a[unit], shows_b[unit])
        allowed = BROKER_PROCESS_LIFETIME if unit == BROKER_UNIT else frozenset()
        for key in changed:
            if key in allowed:
                expected.append(f"BROKER_PROCESS_LIFETIME_CHANGED:{key}")
            else:
                unexpected.append(f"UNIT_PROPERTY_CHANGED:{unit}:{key}")
    broker_a, broker_b = shows_a.get(BROKER_UNIT, {}), shows_b.get(BROKER_UNIT, {})
    if broker_b.get("InvocationID") and broker_b.get("InvocationID") == broker_a.get("InvocationID"):
        unexpected.append("BROKER_INVOCATION_SURVIVED_REBOOT")
    if a["units"].get("enablementOrDropInEntries") != b["units"].get("enablementOrDropInEntries"):
        unexpected.append("ENABLEMENT_OR_DROPIN_CHANGED")

    # PR-1 objects: identical, except the OR-6 tmpfiles runtime directories.
    signer = b["accounts"].get(SIGNER_ACCOUNT) or {}
    signer_gid = signer.get("gid")
    or6: dict[str, dict] = {}
    if set(a["pr1Objects"]) != set(b["pr1Objects"]):
        unexpected.append("PR1_OBJECT_SET_CHANGED")
    for path in sorted(set(a["pr1Objects"]) & set(b["pr1Objects"])):
        before, after = a["pr1Objects"][path], b["pr1Objects"][path]
        if path in TMPFILES_RUNTIME_DIRS:
            spec = TMPFILES_RUNTIME_DIRS[path]
            pre_state = _runtime_dir_state(before, spec, signer_gid)
            post_state = _runtime_dir_state(after, spec, signer_gid)
            or6[path] = {"pre": pre_state, "post": post_state,
                         "postMeta": None if after is None else
                         {key: after.get(key) for key in ("kind", "uid", "gid", "mode", "device", "inode", "nlink")}}
            if pre_state == "PRESENT_WRONG_SPEC":
                unexpected.append("PRE_RUNTIME_DIR_WRONG_SPEC:" + path)
            if post_state == "PRESENT_EXACT_TMPFILES_SPEC":
                expected.append("OR6_TMPFILES_RUNTIME_DIR_CREATED:" + path)
            elif post_state == "ABSENT":
                unexpected.append("OR6_TMPFILES_RUNTIME_DIR_NOT_CREATED:" + path)
            else:
                unexpected.append("OR6_RUNTIME_DIR_WRONG_SPEC:" + path)
            continue
        if before != after:
            unexpected.append("PR1_OBJECT_CHANGED:" + path)

    # Namespace inventory: /run is tmpfs and is rebuilt; everything else is identical.
    inv_a, inv_b = a["namespaceInventory"], b["namespaceInventory"]
    if set(inv_a) != set(inv_b):
        unexpected.append("NAMESPACE_ROOTS_CHANGED")
    for root in sorted(set(inv_a) & set(inv_b)):
        if root != RUN_ROOT:
            if inv_a[root] != inv_b[root]:
                unexpected.append("NAMESPACE_CHANGED:" + root)
            continue
        added, removed = set(inv_b[root]) - set(inv_a[root]), set(inv_a[root]) - set(inv_b[root])
        runtime_names = {Path(path).name for path in TMPFILES_RUNTIME_DIRS}
        for name in sorted(added):
            (expected if name in runtime_names else unexpected).append("RUN_ENTRY_ADDED:" + name)
        for name in sorted(removed):
            (unexpected if name in RUN_RECREATED_REQUIRED | runtime_names else expected).append(
                "RUN_ENTRY_NOT_RECREATED:" + name)
        for name in sorted(RUN_RECREATED_REQUIRED - set(inv_b[root])):
            if name not in removed:
                unexpected.append("RUN_ENTRY_NOT_RECREATED:" + name)

    pre_matches = None if accepted_pre_stable is None else pre["stableSha256"] == accepted_pre_stable
    if pre_matches is False:
        unexpected.append("PRE_NOT_ACCEPTED_BASELINE")
    return {
        "schema": SCHEMA, "schemaVersion": 1, "operation": "OFFLINE_COMPARISON", "judgment": "OBSERVATION_DELTA_ONLY",
        "REBOOT_OBSERVATION_COMPARISON": "PASS" if not unexpected else "FAIL",
        "unexpected": unexpected, "expected": expected,
        "preBootId": pre_boot, "postBootId": post_boot,
        "kernel": {"pre": a["host"].get("kernel"), "post": b["host"].get("kernel"), "expected": expected_kernel},
        "or6": or6,
        "preStableSha256": pre["stableSha256"], "postStableSha256": post["stableSha256"],
        "acceptedPreStableSha256": accepted_pre_stable, "preMatchesAccepted": pre_matches,
        "unchangedSections": {name: pre["sectionSha256"][name] for name in IDENTICAL_SECTIONS
                              if pre["sectionSha256"][name] == post["sectionSha256"][name]},
        "nonclaims": ["NOT_AUTHORITY_STATE", "NOT_P1A9_STATUS", "NOT_BROKER_BASELINE", "NOT_DR5",
                      "RUNTIME_DIRECTORY_IS_NOT_WITNESS_STATE"],
    }


def parse_lock_stat(text: str) -> dict:
    """Exactly one `stat -c LOCK_STAT_FORMAT` line; anything else is refused."""
    lines = text.splitlines()
    match = LOCK_STAT_LINE.fullmatch(lines[0]) if len(lines) == 1 else None
    if match is None:
        raise CompareError("LOCK_STAT_MALFORMED")
    return dict(zip(("path", "type", "uid", "gid", "mode", "size", "links"), match.groups()))


def compare_routine_deploy(before: dict, after: dict, *, lock_stat: dict | None = None) -> dict:
    """Pure: post-M-R2 and post-routine-deploy observations -> classification.
    Everything must be identical except the reviewed deploy-lock creation."""
    expected: list[str] = []
    unexpected: list[str] = []
    a, b = before["facts"], after["facts"]
    for key in sorted(set(a["host"]) | set(b["host"])):
        if key not in ("utcNow", "uptimeSeconds") and a["host"].get(key) != b["host"].get(key):
            unexpected.append("HOST_CHANGED:" + key)  # bootId, kernel, rebootRequired included
    if not str(a["host"].get("utcNow", "")) < str(b["host"].get("utcNow", "")):
        unexpected.append("AFTER_NOT_LATER")
    for section in IDENTICAL_SECTIONS:
        if a[section] != b[section]:
            unexpected.append("SECTION_CHANGED:" + section)
    shows_a, shows_b = a["units"].get("show", {}), b["units"].get("show", {})
    if set(shows_a) != set(shows_b):
        unexpected.append("UNIT_SET_CHANGED")
    for unit in sorted(set(shows_a) & set(shows_b)):
        for key in _diff_keys(shows_a[unit], shows_b[unit]):  # broker lifetime is NOT exempt here
            unexpected.append(f"UNIT_PROPERTY_CHANGED:{unit}:{key}")
    if a["units"].get("enablementOrDropInEntries") != b["units"].get("enablementOrDropInEntries"):
        unexpected.append("ENABLEMENT_OR_DROPIN_CHANGED")
    if set(a["pr1Objects"]) != set(b["pr1Objects"]):
        unexpected.append("PR1_OBJECT_SET_CHANGED")
    for path in sorted(set(a["pr1Objects"]) & set(b["pr1Objects"])):
        if a["pr1Objects"][path] != b["pr1Objects"][path]:  # OR-6 dirs included: same tmpfs inode
            unexpected.append("PR1_OBJECT_CHANGED:" + path)
    inv_a, inv_b = a["namespaceInventory"], b["namespaceInventory"]
    if set(inv_a) != set(inv_b):
        unexpected.append("NAMESPACE_ROOTS_CHANGED")
    lock_after = DEPLOY_LOCK_NAME in inv_b.get(RUN_ROOT, [])
    for root in sorted(set(inv_a) & set(inv_b)):
        added, removed = set(inv_b[root]) - set(inv_a[root]), set(inv_a[root]) - set(inv_b[root])
        for name in sorted(removed):
            unexpected.append(f"NAMESPACE_ENTRY_REMOVED:{root}:{name}")
        for name in sorted(added):
            if root == RUN_ROOT and name == DEPLOY_LOCK_NAME:
                if lock_stat is None:
                    unexpected.append("DEPLOY_LOCK_FACTS_MISSING")
                else:
                    expected.append("DEPLOY_LOCK_CREATED")
            else:
                unexpected.append(f"NAMESPACE_ENTRY_ADDED:{root}:{name}")
    if lock_stat is not None:
        if not lock_after:
            unexpected.append("DEPLOY_LOCK_FACTS_WITHOUT_ENTRY")
        for field in sorted(key for key in DEPLOY_LOCK_SPEC if lock_stat.get(key) != DEPLOY_LOCK_SPEC[key]):
            unexpected.append("DEPLOY_LOCK_WRONG_SPEC:" + field)
    return {
        "schema": ROUTINE_SCHEMA, "schemaVersion": 1, "operation": "OFFLINE_COMPARISON",
        "judgment": "OBSERVATION_DELTA_ONLY",
        "ROUTINE_DEPLOY_OBSERVATION_COMPARISON": "PASS" if not unexpected else "FAIL",
        "unexpected": unexpected, "expected": expected,
        "bootId": b["host"].get("bootId"), "deployLock": lock_stat, "deployLockSpec": DEPLOY_LOCK_SPEC,
        "beforeStableSha256": before["stableSha256"], "afterStableSha256": after["stableSha256"],
        "rawDigestEqual": before["stableSha256"] == after["stableSha256"],
        "nonclaims": ["NOT_AUTHORITY_STATE", "NOT_P1A9_STATUS", "NOT_BROKER_BASELINE", "NOT_DR5",
                      "DEPLOY_LOCK_IS_NOT_AUTHORITY"],
    }


def main_routine_deploy(argv: list[str]) -> int:
    try:
        if len(argv) not in (2, 3):
            raise CompareError("USAGE: compare_reboot_host_observations.py routine-deploy BEFORE AFTER [LOCK_STAT]")
        before = parse_transcript(Path(argv[0]).read_text(encoding="utf-8"))
        after = parse_transcript(Path(argv[1]).read_text(encoding="utf-8"))
        lock = parse_lock_stat(Path(argv[2]).read_text(encoding="utf-8")) if len(argv) == 3 else None
        result = compare_routine_deploy(before, after, lock_stat=lock)
    except (CompareError, OSError) as exc:
        print(f"compare_reboot_host_observations: REFUSED {getattr(exc, 'reason', exc)}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=1))
    print(f"ROUTINE_DEPLOY_OBSERVATION_COMPARISON={result['ROUTINE_DEPLOY_OBSERVATION_COMPARISON']} "
          f"unexpected={len(result['unexpected'])}")
    return 0 if result["ROUTINE_DEPLOY_OBSERVATION_COMPARISON"] == "PASS" else 2


def main(argv: list[str]) -> int:
    if argv[:1] == ["routine-deploy"]:
        return main_routine_deploy(argv[1:])
    try:
        if len(argv) not in (3, 4) or (len(argv) == 4 and not SHA256.fullmatch(argv[3])) \
                or not re.fullmatch(r"[0-9A-Za-z._+-]{1,64}", argv[2]):
            raise CompareError("USAGE: compare_reboot_host_observations.py PRE POST EXPECTED_KERNEL "
                               "[ACCEPTED_PRE_STABLE_SHA256]")
        pre = parse_transcript(Path(argv[0]).read_text(encoding="utf-8"))
        post = parse_transcript(Path(argv[1]).read_text(encoding="utf-8"))
        result = compare(pre, post, expected_kernel=argv[2], accepted_pre_stable=argv[3] if len(argv) == 4 else None)
    except (CompareError, OSError) as exc:
        print(f"compare_reboot_host_observations: REFUSED {getattr(exc, 'reason', exc)}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=1))
    print(f"REBOOT_OBSERVATION_COMPARISON={result['REBOOT_OBSERVATION_COMPARISON']} "
          f"unexpected={len(result['unexpected'])}")
    return 0 if result["REBOOT_OBSERVATION_COMPARISON"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
