#!/usr/bin/env python3
"""15B2b-B1b-3e Package B (M-B9a + M-B9b): OFF-HOST phase-bound DR-5 targets for the witness phases.

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md §12 (rule:
`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`, owner decision OD-B8; ADR-0015 dependency-bound invalidation).

Owner workstation, stdlib only. It reads local files, writes nothing and contacts nothing.

The routine DR-5 script (`scripts/deployer_authority_boundary_proof.sh`, unchanged) prints, for each
`AB_LATER` path, one `DEFERRED_UNTIL_OBJECT_EXISTS: <path> (later step)` line while the path is absent, and
`DENIED: test -w`, `-r`, `-x` (in that order, for `/var/lib/*` and `/run/*`) once it exists. Package B makes
exactly two of those paths exist, and nothing beneath either is ever listed by the script:

- `/var/lib/lilith-recovery-witness` (installer `witness-state`, M-B9a stage 9A-1; it stays after a stop);
- `/run/credentials/lilith-recovery-witness.service` (systemd, only while the witness service runs).

M-B9b writes `chain/`, `chain/1.json`, `witness.json` and `authorizations/` beneath the first path only, so it
adds no further DR-5 line. The two targets below are derived from the ACCEPTED post-M-B6 baseline texts by
exactly those substitutions; every other line keeps its text and order (no global rebaseline).

| Form | Effect |
| --- | --- |
| `extract <deploy-log>` | the three DR-5 sets of one DEV deploy log (the accepted `mb6_dr5_target.extract` rule) |
| `derive <result-set> <dr5-block> <predeploy-block>` | the accepted post-M-B6 texts must hash to the accepted pins; derives the STOPPED and RUNNING targets; each must equal its pin |
| `compare <verified-w9-phase> <deploy-log>` | the comparison target from the INDEPENDENTLY verified W9 host phase; anything else is `NO_BASELINE_STOP`. `EQUAL` only on byte equality of all three sets |

Both derived targets are PROPOSED comparison targets. Producing them, or a `compare` result of `EQUAL`,
accepts nothing: each needs live evidence and a separate owner acceptance.

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

# The ACCEPTED post-M-B6 baseline (owner-accepted 2026-10-08; preserved EQUAL by deploys 37727603638 and
# 37729152982). It is the only input, and the target for `W9_0_PRE_WITNESS` (= W8 `OWNER_INPUTS_INSTALLED_EXACT`).
BASE = {
    "result-set": (188, "3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494"),
    "dr5-block": (149, "d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801"),
    "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
}
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
WITNESS_CREDENTIALS = "/run/credentials/lilith-recovery-witness.service"
# The exact `ab_check_later_state` lines for the two Package B paths.
STATE_SUBSTITUTION = (f"DEFERRED_UNTIL_OBJECT_EXISTS: {WITNESS_STATE} (later step)",
                      tuple(f"DENIED: test {op} {WITNESS_STATE}" for op in ("-w", "-r", "-x")))
CREDENTIAL_SUBSTITUTION = (f"DEFERRED_UNTIL_OBJECT_EXISTS: {WITNESS_CREDENTIALS} (later step)",
                           tuple(f"DENIED: test {op} {WITNESS_CREDENTIALS}" for op in ("-w", "-r", "-x")))

STOPPED = "WITNESS_STATE_PRESENT_SERVICE_STOPPED"
RUNNING = "WITNESS_RUNNING"
SUBSTITUTIONS = {STOPPED: (STATE_SUBSTITUTION,), RUNNING: (STATE_SUBSTITUTION, CREDENTIAL_SUBSTITUTION)}
# The derived targets (PROPOSED; not owner-accepted). Tests re-derive them from the accepted texts.
TARGETS = {
    STOPPED: {
        "result-set": (190, "7f70aa3bd0c51622b362e78a2d75edca6fe2801eccf6bc9da015de093a670989"),
        "dr5-block": (151, "3d7cd041d21e034849af031d1a1971a09a54efe2d5490cf7c1bfba9549d450af"),
        "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
    },
    RUNNING: {
        "result-set": (192, "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65"),
        "dr5-block": (153, "ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a"),
        "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
    },
}
# Lines that must be present, unchanged, in every target.
INVARIANT_LINES = ("PR1_AUTHORITY_BOUNDARY maturity=P1A-9", "AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3")
GRANT_ABSENT = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT "

# W9 host phase (independently verified by `mb9_witness_verifier.py`) -> comparison target. A partial, torn,
# mismatched, later, foreign or unclassified state never uses a baseline as evidence of normality.
PHASE_TARGETS = {
    "W9_0_PRE_WITNESS": "POST_MB6_ACCEPTED",
    "W9_1_STATE_DIR_ONLY": STOPPED,
    "W9_2S_STOPPED_UNINITIALIZED": STOPPED,
    "W9_5S_GENESIS_COMMITTED_STOPPED": STOPPED,
    "W9_2_STARTED_UNINITIALIZED": RUNNING,
    "W9_5_GENESIS_COMMITTED_EXACT": RUNNING,
}


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
    """The accepted extraction rule (`mb6_dr5_target.extract`, restated byte-for-byte)."""
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


def substitute(lines: list[str], substitutions) -> list[str]:
    out = list(lines)
    for old, new in substitutions:
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


def derive(base: dict[str, bytes], *, base_pins: dict = BASE, target_pins: dict | None = TARGETS) -> dict:
    """Both targets from the accepted post-M-B6 texts: only the Package B substitutions in the result set and
    the DR-5 block; the pre-deploy block unchanged. `target_pins=None` skips the pinned-target equality (TEST
    seam for synthetic baselines)."""
    _need(set(base) == set(SETS), "INPUT_SETS")
    texts = {}
    for name in SETS:
        lines = decode(base[name])
        _need((len(lines), hashlib.sha256(base[name]).hexdigest()) == base_pins[name], "BASE_NOT_ACCEPTED:" + name)
        _invariants(name, lines)
        texts[name] = lines
    out: dict = {}
    for target, subs in SUBSTITUTIONS.items():
        derived = {name: (substitute(texts[name], subs) if name != "predeploy-block" else list(texts[name]))
                   for name in SETS}
        sets = {}
        for name in SETS:
            _invariants(name, derived[name])
            removed = [line for line in texts[name] if line not in derived[name]]
            added = [line for line in derived[name] if line not in texts[name]]
            expected_removed = [old for old, _ in subs] if name != "predeploy-block" else []
            expected_added = [line for _, new in subs for line in new] if name != "predeploy-block" else []
            _need(sorted(removed) == sorted(expected_removed) and sorted(added) == sorted(expected_added),
                  "DELTA_NOT_EXACT:" + target + ":" + name)
            sets[name] = {"lines": len(derived[name]), "sha256": digest(derived[name]),
                          "counts": counts(derived[name]), "baseCounts": counts(texts[name]),
                          "baseSha256": base_pins[name][1]}
            if target_pins is not None:
                _need((sets[name]["lines"], sets[name]["sha256"]) == target_pins[target][name],
                      "TARGET_NOT_PINNED:" + target + ":" + name)
        out[target] = {"sets": sets, "texts": derived}
    return {"resultType": "LILITH_MB9_DR5_TARGETS", "schemaVersion": 1,
            "rule": "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA", "targets": out, "accepted": False,
            "derived": True, "mb9bAddsNoDr5Line": True}


def target_for(phase: str) -> tuple[str, dict]:
    name = PHASE_TARGETS.get(phase)
    if name is None:
        raise TargetError("NO_BASELINE_STOP:" + phase)
    return name, (BASE if name == "POST_MB6_ACCEPTED" else TARGETS[name])


def compare(phase: str, log: str) -> dict:
    name, target = target_for(phase)
    sets = extract(log)
    observed = {set_name: (len(lines), digest(lines)) for set_name, lines in sets.items()}
    unequal = [set_name for set_name in SETS if observed[set_name] != target[set_name]]
    kinds = counts(sets["result-set"])
    return {"resultType": "LILITH_MB9_DR5_PHASE_COMPARISON", "phase": phase, "target": name,
            "targetAccepted": name == "POST_MB6_ACCEPTED",
            "observed": {set_name: {"lines": n, "sha256": h} for set_name, (n, h) in observed.items()},
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
            print("mb9_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"mb9_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
