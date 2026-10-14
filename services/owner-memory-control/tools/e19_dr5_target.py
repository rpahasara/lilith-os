#!/usr/bin/env python3
"""15B2b-B1b-3e E-19 completion: OFF-HOST phase-bound DR-5 comparison for the post-U5 (NEW-release) phases.

Record: docs/architecture/slice-15b2b-b1b3e-e19-completion-record.md (rule:
`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`, unchanged; ADR-0015 dependency-bound invalidation).

Owner workstation, stdlib only. It reads local files, writes nothing and contacts nothing.

The targets are the merged contract's `NEW_DR5_TARGETS` (`e19_p1b10_upgrade.py`, PR #194): the accepted W10_1 texts
(`mb10_dr5_target.derive`, which re-checks every W9 / W10 pin over the accepted post-M-B6 fixture and the pinned DR-5
script) with exactly the release lines moved by `derive_release_swap(<OLD>, <NEW>)`. This tool adds no target value:
`derive` re-derives them and requires equality with the merged pins; `compare` maps an INDEPENDENTLY verified
post-U5 host result to a target. The historical W10_1 targets and their phase map (`mb10_dr5_target`) are untouched.

| Form | Effect |
| --- | --- |
| `derive <result-set> <dr5-block> <predeploy-block> <dr5-script>` | re-derive both E-19 targets; each must equal its merged pin |
| `compare <host-u5-dir> <deploy-log>` | the target for the verified `e19_operator host U5` result in `<host-u5-dir>` (HOST_RESULT.json + w10verifier.out); `EQUAL` only on byte equality of all three sets |

Fail closed: a missing or unparseable file, a host result that is not the exact U5 PASS for the NEW release, a W10
phase outside the map, a W10 report bound to any identity other than the completion record's accepted replacement,
a missing DR-5 set, an `ALLOWED` line, or a log that names the retired OLD release is `NO_BASELINE_STOP` / refused,
never EQUAL.

    derived target != accepted target;  EQUAL != owner completion acceptance;  a local test is never DR-5 EQUAL
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e19_p1b10_upgrade as E  # noqa: E402  (the merged contract: NEW_DR5_TARGETS, derive_release_swap)
import mb10_dr5_target as T10  # noqa: E402  (pinned; reused unchanged)
import mb9_dr5_target as T9  # noqa: E402  (pinned; reused unchanged)

TargetError = T9.TargetError
_need = T9._need
SETS = T9.SETS
E19_CONTRACT_SHA256 = "e8c8f6037ef51d4e2f7de7ac546f034bdf4893a717ef3bcb450d9fe52cb12cc2"
MB10_DR5_TARGET_SHA256 = "29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0"
COMPLETION_RECORD = HERE / "e19_completion_record.json"
COMPLETION_RECORD_SHA256 = "31bc707ebc9b58b376d233a30594eaa0e1f4d3b32444b172c741dbaeec66b3b8"

RUNNING_HELD_E19 = "WITNESS_RUNNING_HELD_E19"
STOPPED_HELD_E19 = "WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19"
# The independently verified W10 phase of a post-U5 host read -> its E-19 target. Every other phase has no baseline.
PHASE_TARGETS = {"W10_1_HELD_EXACT": RUNNING_HELD_E19, "W10_1S_HELD_EXACT_WITNESS_STOPPED": STOPPED_HELD_E19}
HOST_U5_PASS = f"E19_HOST_{E.U5}_PASS"
HOST_CODES = frozenset({"identity", "custody", "readiness", "preservation", "observer", "w5verifier", "mb6verifier",
                        "w8verifier", "e19status", "w9verifier", "w10verifier"})
TARGET_STATUS = E.NEW_DR5_TARGETS_STATUS            # DERIVED_PINNED_NOT_ACCEPTED until the owner's completion


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_pins() -> None:
    _need(_sha(Path(E.__file__).read_bytes()) == E19_CONTRACT_SHA256, "E19_CONTRACT_PIN_MISMATCH")
    _need(_sha(Path(T10.__file__).read_bytes()) == MB10_DR5_TARGET_SHA256, "MB10_DR5_TARGET_PIN_MISMATCH")


def accepted_replacement() -> tuple[str, str]:
    """The owner-accepted replacement identity, from the pinned completion record only."""
    raw = COMPLETION_RECORD.read_bytes()
    _need(_sha(raw) == COMPLETION_RECORD_SHA256, "COMPLETION_RECORD_PIN_MISMATCH")
    record = json.loads(raw)
    identity = record["witness"]["acceptedReplacement"]
    _need(isinstance(identity, list) and len(identity) == 2 and all(isinstance(x, str) and x for x in identity),
          "COMPLETION_RECORD_IDENTITY")
    return identity[0], identity[1]


def derive(base: dict[str, bytes], script: bytes) -> dict:
    """Both E-19 targets re-derived from the accepted W10_1 texts; each must equal the merged contract pin."""
    _check_pins()
    w10 = T10.derive(base, script)
    out = {}
    for target, source in E.NEW_DR5_SOURCES.items():
        swapped = E.derive_release_swap(w10["targets"][source]["texts"], old=E.OLD_RELEASE, new=E.NEW_RELEASE)
        sets = {}
        for name in SETS:
            T9._invariants(name, swapped[name])
            sets[name] = {"lines": len(swapped[name]), "sha256": T9.digest(swapped[name])}
            _need((sets[name]["lines"], sets[name]["sha256"]) == tuple(E.NEW_DR5_TARGETS[target][name]),
                  "TARGET_NOT_PINNED:" + target + ":" + name)
        out[target] = {"sets": sets, "sourceTarget": source}
    return {"resultType": "LILITH_E19_DR5_TARGETS", "schemaVersion": 1, "targets": out, "status": TARGET_STATUS,
            "accepted": False, "derived": True, "historicalW10TargetsUnchanged": True}


def _json_file(path: Path, name: str) -> Any:
    _need(path.is_file() and not path.is_symlink(), "HOST_EVIDENCE_MISSING:" + name)
    raw = path.read_bytes()
    _need(len(raw) <= T9.MAX_INPUT, "INPUT_TOO_LARGE:" + name)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TargetError("HOST_EVIDENCE_UNPARSEABLE:" + name) from exc


def verified_phase(host_dir: Path) -> tuple[str, dict]:
    """The W10 phase of an `e19_operator host U5` PASS for the NEW release, bound to the accepted replacement."""
    host_dir = Path(host_dir)
    result = _json_file(host_dir / "HOST_RESULT.json", "HOST_RESULT")
    _need(isinstance(result, Mapping) and result.get("result") == HOST_U5_PASS and result.get("phase") == E.U5,
          "NO_BASELINE_STOP:HOST_NOT_U5_PASS")
    _need(result.get("selectedRelease") == E.NEW_RELEASE, "NO_BASELINE_STOP:RELEASE_MISMATCH")
    _need(result.get("e19State") == "E19_OLD_RETIRED" and result.get("readinessExact") is True
          and result.get("tmpResidue") == [], "NO_BASELINE_STOP:HOST_STATE")
    codes = result.get("codes")
    _need(isinstance(codes, Mapping) and set(codes) == HOST_CODES and all(v == 0 for v in codes.values()),
          "NO_BASELINE_STOP:HOST_CODES")
    _need((host_dir / "w10verifier.rc").is_file() and (host_dir / "w10verifier.rc").read_text().strip() == "0",
          "NO_BASELINE_STOP:W10_RC")
    w10 = _json_file(host_dir / "w10verifier.out", "w10verifier")
    _need(isinstance(w10, Mapping) and w10.get("failures") == [], "NO_BASELINE_STOP:W10_FAILURES")
    phase = w10.get("phase")
    _need(phase in PHASE_TARGETS, "NO_BASELINE_STOP:" + str(phase))
    _need(w10.get("authorityActive") is False and w10.get("registryEffective") is False
          and w10.get("issuanceAuthority") == "NONE", "NO_BASELINE_STOP:AUTHORITY")
    if PHASE_TARGETS[phase] == RUNNING_HELD_E19:
        identity = (w10.get("witnessInvocationId"), str(w10.get("witnessMainPid")))
        _need(identity == accepted_replacement() and str(w10.get("witnessNRestarts")) == "0",
              "NO_BASELINE_STOP:WITNESS_NOT_ACCEPTED_REPLACEMENT")
    return phase, {"hostResultSha256": _sha((host_dir / "HOST_RESULT.json").read_bytes()),
                   "w10OutputSha256": _sha((host_dir / "w10verifier.out").read_bytes())}


def compare(host_dir: Path, log: str) -> dict:
    _check_pins()
    phase, bound = verified_phase(host_dir)
    name = PHASE_TARGETS[phase]
    target = E.NEW_DR5_TARGETS[name]
    sets = T9.extract(log)
    _need(isinstance(sets, Mapping) and set(sets) == set(SETS) and all(sets[name] for name in SETS),
          "DR5_SETS_MISSING")
    old_lines = sum(1 for lines in sets.values() for line in lines if E.OLD_RELEASE in line)
    observed = {set_name: (len(lines), T9.digest(lines)) for set_name, lines in sets.items()}
    unequal = [set_name for set_name in SETS if observed[set_name] != tuple(target[set_name])]
    kinds = T9.counts(sets["result-set"])
    equal = not unequal and kinds["ALLOWED"] == 0 and old_lines == 0
    return {"resultType": "LILITH_E19_DR5_PHASE_COMPARISON", "phase": phase, "target": name,
            "targetStatus": TARGET_STATUS, "targetAccepted": False, "hostEvidence": bound,
            "observed": {set_name: {"lines": n, "sha256": h} for set_name, (n, h) in observed.items()},
            "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "oldReleaseLines": old_lines, "unequal": unequal,
            "result": "EQUAL" if equal else "DRIFT", "accepted": False,
            "note": "DR-5 EQUAL is deployment-boundary evidence only; the owner's completion acceptance is separate"}


def _read(path: str) -> bytes:
    data = Path(path).read_bytes()
    _need(len(data) <= T9.MAX_INPUT, "INPUT_TOO_LARGE")
    return data


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 5 and argv[0] == "derive":
            out = derive(dict(zip(SETS, (_read(path) for path in argv[1:4]))), _read(argv[4]))
        elif len(argv) == 3 and argv[0] == "compare":
            out = compare(Path(argv[1]), _read(argv[2]).decode("utf-8", "replace"))
        else:
            print("e19_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"e19_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
