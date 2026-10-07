#!/usr/bin/env python3
"""15B2b-B1b-3e M-B6: OFF-HOST post-M-B6 DR-5 target derivation and phase-bound comparison.

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ceremony-package.md §4 (rule:
the M-B6 remediation record §12, `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`,
owner decision R-2A).

Owner workstation, stdlib only. It reads local files, writes nothing and
contacts nothing.

| Form | Effect |
| --- | --- |
| `extract <deploy-log>` | the three DR-5 sets of one DEV deploy log (the accepted `dr5_extract.py` rule, `341a99eb…`): their line counts and SHA-256 |
| `derive <pre-result-set> <pre-dr5-block> <pre-predeploy-block>` | the accepted pre-M-B6 texts must hash to the accepted pins; applies exactly the two M-B6 substitutions (DR6-2) and nothing else; checks the invariants; reports the target texts, counts and SHA-256, which must equal the pinned target |
| `compare <verified-host-phase> <deploy-log>` | selects the comparison target from the INDEPENDENTLY verified host phase (DR6-5): `W6_0_NO_MB6_MUTATION` → the pre baseline; `LEDGER_COMMITTED_EXACT` → the derived post target; anything else → `NO_BASELINE_STOP` (DR6-6, DR6-7). `EQUAL` only on byte equality of all three sets |

The derived target is a PROPOSED comparison target. Producing it, or a
`compare` result of `EQUAL`, accepts nothing: owner acceptance of the
post-M-B6 baseline is separate (DR6-12).

    derived target != accepted baseline;  EQUAL != owner acceptance;  phase argument != phase proof
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

PREFIXES = ("DENIED", "ALLOWED", "PASS", "OK", "FAIL", "HOST_PREREQ", "DEFERRED", "UNOBSERVABLE", "PR1_",
            "AUTHORITY_", "ACTIVATION", "BROKER_", "SUDO_", "FEDERATION", "UNEXPECTED")
_TIMESTAMP = re.compile(r"^(?:[^\t]*\t[^\t]*\t)?\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z ?")
SETS = ("result-set", "dr5-block", "predeploy-block")
MAX_INPUT = 64 * 1024 * 1024

# The accepted pre-M-B6 baseline: run 36552218231 (`c0adb70`), condition-2 record §2.
PRE = {
    "result-set": (186, "f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b"),
    "dr5-block": (147, "a1d98773bcd07c39b2a17f0628f75db858a3e1e6bcd19e7bcd8918c0e79f1390"),
    "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
}
# The derived post-M-B6 target (ceremony package §4). PROPOSED; not owner-accepted.
POST = {
    "result-set": (188, "3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494"),
    "dr5-block": (149, "d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801"),
    "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
}

STATE = "/var/lib/lilith-authority-dev"
LEDGER = STATE + "/authority_ledger.db"
# The exact DR-5 lines (scripts/deployer_authority_boundary_proof.sh, unchanged): the
# `AB_PR1_UNOBSERVABLE` leaf loop and `ab_check_later_state`.
SUBSTITUTIONS = (
    (f"DEFERRED_UNTIL_OBJECT_EXISTS: {LEDGER} ({STATE} absent)",
     (f"UNOBSERVABLE_BY_DESIGN: {LEDGER} (beneath root-only {STATE}; checked only by root tooling)",)),
    (f"DEFERRED_UNTIL_OBJECT_EXISTS: {STATE} (later step)",
     (f"DENIED: test -w {STATE}", f"DENIED: test -r {STATE}", f"DENIED: test -x {STATE}")),
)
# Lines that must be present, unchanged, in every target.
INVARIANT_LINES = ("PR1_AUTHORITY_BOUNDARY maturity=P1A-9", "AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3")
GRANT_ABSENT = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT "

PRE_PHASE = "W6_0_NO_MB6_MUTATION"
POST_PHASE = "LEDGER_COMMITTED_EXACT"


class TargetError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise TargetError(reason)


def encode(lines: list[str]) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def digest(lines: list[str]) -> str:
    return hashlib.sha256(encode(lines)).hexdigest()


def decode(data: bytes) -> list[str]:
    _need(len(data) <= MAX_INPUT, "INPUT_TOO_LARGE")
    _need(data.endswith(b"\n") and b"\r" not in data, "INPUT_NOT_LF_TERMINATED")
    return data.decode("utf-8").split("\n")[:-1]


def extract(log: str) -> dict[str, list[str]]:
    """The accepted extraction rule (`dr5_extract.py`, SHA-256 `341a99eb…`): strip Actions timestamps,
    keep result-prefixed lines in order, cut the DR-5 and the pre-deploy blocks."""
    lines = [_TIMESTAMP.sub("", raw.rstrip("\r\n").lstrip("\ufeff")) for raw in log.splitlines(keepends=True)]
    full = [line for line in lines if line.startswith(PREFIXES)]
    dr5, on = [], False
    for line in full:
        if line == "DENIED: test -w /opt":
            on = True
        if on:
            dr5.append(line)
        if on and line.startswith("AUTHORITY_BOUNDARY_PROOF="):
            break
    pre, on = [], False
    for line in full:
        if line.startswith("DENIED: sudo -n true"):
            on = True
        if on:
            pre.append(line)
        if on and line.startswith("ACTIVATION="):
            break
    return {"result-set": full, "dr5-block": dr5, "predeploy-block": pre}


def counts(lines: list[str]) -> dict[str, int]:
    kinds = Counter(line.split(":", 1)[0].split(" ", 1)[0].split("=", 1)[0].split("(", 1)[0] for line in lines)
    return {"lines": len(lines), "DENIED": kinds["DENIED"], "ALLOWED": kinds["ALLOWED"], "FAIL": kinds["FAIL"],
            "DEFERRED_UNTIL_OBJECT_EXISTS": kinds["DEFERRED_UNTIL_OBJECT_EXISTS"],
            "UNOBSERVABLE_BY_DESIGN": kinds["UNOBSERVABLE_BY_DESIGN"]}


def _substitute(lines: list[str]) -> list[str]:
    out = list(lines)
    for old, new in SUBSTITUTIONS:
        _need(out.count(old) == 1, "SUBSTITUTION_SOURCE_NOT_EXACTLY_ONCE")
        for line in new:
            _need(line not in out, "SUBSTITUTION_TARGET_ALREADY_PRESENT")
        at = out.index(old)
        out[at:at + 1] = list(new)
    return out


def _invariants(name: str, lines: list[str]) -> None:
    kinds = counts(lines)
    _need(kinds["ALLOWED"] == 0 and kinds["FAIL"] == 0, "TARGET_HAS_ALLOWED_OR_FAIL:" + name)
    if name != "predeploy-block":
        for line in INVARIANT_LINES:
            _need(lines.count(line) == 1, "TARGET_INVARIANT_MISSING:" + name)
    if name != "dr5-block":
        grants = [line for line in lines if line.startswith("ACTIVATION=")]
        _need(len(grants) == 1 and grants[0].startswith(GRANT_ABSENT), "TARGET_NOT_GRANT_ABSENT:" + name)


def derive(pre: dict[str, bytes], *, pre_pins: dict = PRE, post_pins: dict | None = POST) -> dict:
    """The post-M-B6 target from the accepted pre-M-B6 texts: exactly the two M-B6 substitutions in the
    result set and the DR-5 block; the pre-deploy block unchanged. `post_pins=None` skips the pinned-target
    equality (TEST seam for synthetic baselines)."""
    _need(set(pre) == set(SETS), "INPUT_SETS")
    texts = {}
    for name in SETS:
        lines = decode(pre[name])
        _need((len(lines), hashlib.sha256(pre[name]).hexdigest()) == pre_pins[name], "PRE_NOT_ACCEPTED:" + name)
        texts[name] = lines
    post = {"result-set": _substitute(texts["result-set"]), "dr5-block": _substitute(texts["dr5-block"]),
            "predeploy-block": list(texts["predeploy-block"])}
    for name in SETS:
        _invariants(name, texts[name])
        _invariants(name, post[name])
        removed = [line for line in texts[name] if line not in post[name]]
        added = [line for line in post[name] if line not in texts[name]]
        expected_removed = [old for old, _ in SUBSTITUTIONS] if name != "predeploy-block" else []
        expected_added = [line for _, new in SUBSTITUTIONS for line in new] if name != "predeploy-block" else []
        _need(sorted(removed) == sorted(expected_removed) and sorted(added) == sorted(expected_added),
              "DELTA_NOT_EXACT:" + name)
    result = {name: {"lines": len(post[name]), "sha256": digest(post[name]), "counts": counts(post[name]),
                     "preCounts": counts(texts[name]), "preSha256": pre_pins[name][1]} for name in SETS}
    if post_pins is not None:
        for name in SETS:
            _need((result[name]["lines"], result[name]["sha256"]) == post_pins[name], "TARGET_NOT_PINNED:" + name)
    return {"resultType": "LILITH_MB6_POST_DR5_TARGET", "schemaVersion": 1, "rule":
            "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA", "sets": result,
            "texts": {name: post[name] for name in SETS}, "accepted": False, "derived": True}


def target_for(phase: str) -> dict:
    if phase == PRE_PHASE:
        return PRE
    if phase == POST_PHASE:
        return POST
    raise TargetError("NO_BASELINE_STOP:" + phase)


def compare(phase: str, log: str) -> dict:
    target = target_for(phase)
    sets = extract(log)
    observed = {name: (len(lines), digest(lines)) for name, lines in sets.items()}
    unequal = [name for name in SETS if observed[name] != target[name]]
    kinds = counts(sets["result-set"])
    return {"resultType": "LILITH_MB6_DR5_PHASE_COMPARISON", "phase": phase,
            "target": "PRE_MB6_ACCEPTED" if phase == PRE_PHASE else "POST_MB6_DERIVED_NOT_ACCEPTED",
            "observed": {name: {"lines": n, "sha256": h} for name, (n, h) in observed.items()},
            "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "unequal": unequal,
            "result": "EQUAL" if not unequal and kinds["ALLOWED"] == 0 else "DRIFT", "accepted": False}


def _read(path: str) -> bytes:
    data = Path(path).read_bytes()
    _need(len(data) <= MAX_INPUT, "INPUT_TOO_LARGE")
    return data


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "extract":
            sets = extract(_read(argv[1]).decode("utf-8", "replace"))
            out = {name: {"lines": len(lines), "sha256": digest(lines), "counts": counts(lines)}
                   for name, lines in sets.items()}
        elif len(argv) == 4 and argv[0] == "derive":
            out = derive(dict(zip(SETS, (_read(path) for path in argv[1:]))))
        elif len(argv) == 3 and argv[0] == "compare":
            out = compare(argv[1], _read(argv[2]).decode("utf-8", "replace"))
        else:
            print("mb6_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"mb6_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
