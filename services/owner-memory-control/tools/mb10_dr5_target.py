#!/usr/bin/env python3
"""15B2b-B1b-3e M-B10 (WRITE_HELD): OFF-HOST phase-bound DR-5 targets for the post-HELD phases.

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §4 (rule:
`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`, unchanged; ADR-0015 dependency-bound invalidation).

Owner workstation, stdlib only. It reads local files, writes nothing and contacts nothing.

The accepted W9 targets (`mb9_dr5_target.py`, pinned, UNCHANGED) are derived from the accepted post-M-B6 texts. This
tool derives the post-HELD targets from exactly those derived texts, with a delta it PROVES from the pinned DR-5
script (`scripts/deployer_authority_boundary_proof.sh`) instead of assuming it:

- the hold store `/var/lib/lilith-authority-custody/holds` appears in the script only as one
  `AB_PR1_UNOBSERVABLE` leaf beneath the root-only (0700) `/var/lib/lilith-authority-custody`, so the routine
  deployer prints `UNOBSERVABLE_BY_DESIGN: ... (beneath root-only ...)` both before and after M-B10;
- no ladder, prerequisite, later-state, parent or root-file entry of the script lies at or beneath the hold store or
  its parent's scratch, and the parent's own ladder row judges kind, owner and mode only (never a time or size);
- M-B10 writes beneath that parent only (a scratch file in the parent, renamed into the store).

So M-B10 adds and removes NO DR-5 line: the derived delta is EMPTY. The post-HELD targets are new, phase-specific
names whose texts equal the W9 RUNNING / STOPPED texts; the W9 targets and their phase mapping are not touched, and
a W9 phase is never accepted here.

| Form | Effect |
| --- | --- |
| `derive <result-set> <dr5-block> <predeploy-block> <dr5-script>` | the accepted post-M-B6 texts (via the pinned W9 derivation) and the pinned script; the empty delta is proven; each derived target must equal its pin |
| `compare <verified-w10-phase> <deploy-log>` | the target for the INDEPENDENTLY verified W10 host phase (`mb10_held_verifier.py`); anything else is `NO_BASELINE_STOP`. `EQUAL` only on byte equality of all three sets |

    DR-5 EQUAL != HELD present (the deployer cannot observe the hold store);  HELD proof = the root W10 verifier
    derived target != accepted baseline;  EQUAL != owner acceptance;  phase argument != phase proof
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb9_dr5_target as T9  # noqa: E402  (pinned; reused unchanged)

TargetError = T9.TargetError
_need = T9._need
SETS = T9.SETS
MB9_DR5_TARGET_SHA256 = "d176864a2f15cd9a64462c1ffc0bb46364428e97d3ec64b5fd547bb380ef1675"
DR5_SCRIPT = "scripts/deployer_authority_boundary_proof.sh"
DR5_SCRIPT_SHA256 = "9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43"
HOLD_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE = HOLD_PARENT + "/holds"
UNOBSERVABLE_LINE = f"UNOBSERVABLE_BY_DESIGN: {HOLD_STORE} (beneath root-only {HOLD_PARENT}; checked only by root tooling)"
PATH_LISTS = ("AB_PARENTS", "AB_ROOT_FILES", "AB_LADDER", "AB_PR1_LADDER", "AB_PR1_UNOBSERVABLE", "AB_HOST_PREREQS",
              "AB_LATER", "AB_PR1_CLIS")

RUNNING_HELD = "WITNESS_RUNNING_HELD"
STOPPED_HELD = "WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD"
SOURCE = {RUNNING_HELD: T9.RUNNING, STOPPED_HELD: T9.STOPPED}
# The derived post-HELD targets (PROPOSED; not owner-accepted). Their texts equal the W9 sources (empty delta).
TARGETS = {RUNNING_HELD: dict(T9.TARGETS[T9.RUNNING]), STOPPED_HELD: dict(T9.TARGETS[T9.STOPPED])}
# W10 host phase (independently verified by `mb10_held_verifier.py`) -> comparison target. Every other phase,
# including every W9 phase, has no post-HELD baseline.
PHASE_TARGETS = {"W10_1_HELD_EXACT": RUNNING_HELD, "W10_1S_HELD_EXACT_WITNESS_STOPPED": STOPPED_HELD}


def _check_base_tool() -> None:
    _need(hashlib.sha256(Path(T9.__file__).read_bytes()).hexdigest() == MB9_DR5_TARGET_SHA256,
          "MB9_DR5_TARGET_PIN_MISMATCH")


def script_lists(script: bytes) -> dict[str, list[str]]:
    """Each `readonly AB_*="..."` list of the DR-5 script as its whitespace / line items (no shell evaluation)."""
    _need(hashlib.sha256(script).hexdigest() == DR5_SCRIPT_SHA256, "DR5_SCRIPT_PIN_MISMATCH")
    text = script.decode("utf-8")
    out: dict[str, list[str]] = {}
    for name in PATH_LISTS:
        found = re.findall(rf'^readonly {name}="(.*?)"$', text, flags=re.MULTILINE | re.DOTALL)
        _need(len(found) == 1, "DR5_SCRIPT_LIST_NOT_EXACTLY_ONCE:" + name)
        body = found[0]
        out[name] = [line for line in body.split("\n") if line.strip()] if "\n" in body else body.split()
    return out


def _paths(name: str, items: list[str]) -> list[str]:
    if name in ("AB_LADDER", "AB_PR1_LADDER"):
        return [item.split("|")[1] for item in items]
    if name == "AB_PR1_UNOBSERVABLE":
        return [part for item in items for part in item.split("|")]
    if name == "AB_HOST_PREREQS":
        return [item.split("|")[0] for item in items]
    return items


def prove_hold_unobservable(script: bytes) -> dict:
    """The empty delta, proven from the pinned script text (record §4.2)."""
    lists = script_lists(script)
    unobservable = [tuple(item.split("|")) for item in lists["AB_PR1_UNOBSERVABLE"]]
    _need(unobservable.count((HOLD_PARENT, HOLD_STORE)) == 1, "HOLD_STORE_NOT_AN_UNOBSERVABLE_LEAF")
    ladder = [item.split("|") for item in lists["AB_PR1_LADDER"]]
    parent_rows = [row for row in ladder if row[1] == HOLD_PARENT]
    _need(parent_rows == [["P1A-9", HOLD_PARENT, "directory", "700", "-r -x"]], "HOLD_PARENT_ROW_NOT_ROOT_ONLY")
    for name, items in lists.items():
        for path in _paths(name, items):
            beneath = path == HOLD_STORE or path.startswith(HOLD_STORE + "/") or path.startswith(HOLD_PARENT + "/.")
            if beneath and not (name == "AB_PR1_UNOBSERVABLE" and path == HOLD_STORE):
                raise TargetError("HOLD_PATH_OBSERVED_BY_SCRIPT:" + name)
    return {"holdStoreUnobservable": True, "parentRow": parent_rows[0], "unobservableLine": UNOBSERVABLE_LINE}


def derive(base: dict[str, bytes], script: bytes, *, base_pins: dict = T9.BASE, w9_pins: dict | None = T9.TARGETS,
           target_pins: dict | None = TARGETS) -> dict:
    """The post-HELD targets: the pinned W9 derivation, then the proven EMPTY substitution set. `w9_pins=None` and
    `target_pins=None` skip the pinned equalities (TEST seams for synthetic baselines)."""
    _check_base_tool()
    proof = prove_hold_unobservable(script)
    w9 = T9.derive(base, base_pins=base_pins, target_pins=w9_pins)
    out = {}
    for target, source in SOURCE.items():
        texts = w9["targets"][source]["texts"]
        derived = {name: list(texts[name]) for name in SETS}                 # the empty, proven delta
        sets = {}
        for name in SETS:
            T9._invariants(name, derived[name])
            if name != "predeploy-block":
                _need(derived[name].count(UNOBSERVABLE_LINE) == 1, "UNOBSERVABLE_LINE_NOT_EXACTLY_ONCE:" + name)
            sets[name] = {"lines": len(derived[name]), "sha256": T9.digest(derived[name]),
                          "counts": T9.counts(derived[name]), "sourceTarget": source, "added": [], "removed": []}
            if target_pins is not None:
                _need((sets[name]["lines"], sets[name]["sha256"]) == target_pins[target][name],
                      "TARGET_NOT_PINNED:" + target + ":" + name)
        out[target] = {"sets": sets, "texts": derived}
    return {"resultType": "LILITH_MB10_DR5_TARGETS", "schemaVersion": 1,
            "rule": "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA", "delta": "EMPTY_PROVEN_FROM_PINNED_SCRIPT",
            "proof": proof, "targets": out, "accepted": False, "derived": True, "w9TargetsUnchanged": True,
            "dr5EqualIsNotHeldEvidence": True}


def target_for(phase: str) -> tuple[str, dict]:
    name = PHASE_TARGETS.get(phase)
    if name is None:
        raise TargetError("NO_BASELINE_STOP:" + phase)
    return name, TARGETS[name]


def compare(phase: str, log: str) -> dict:
    _check_base_tool()
    name, target = target_for(phase)
    sets = T9.extract(log)
    observed = {set_name: (len(lines), T9.digest(lines)) for set_name, lines in sets.items()}
    unequal = [set_name for set_name in SETS if observed[set_name] != target[set_name]]
    kinds = T9.counts(sets["result-set"])
    return {"resultType": "LILITH_MB10_DR5_PHASE_COMPARISON", "phase": phase, "target": name, "targetAccepted": False,
            "observed": {set_name: {"lines": n, "sha256": h} for set_name, (n, h) in observed.items()},
            "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "unequal": unequal,
            "result": "EQUAL" if not unequal and kinds["ALLOWED"] == 0 else "DRIFT", "accepted": False,
            "note": "DR-5 cannot observe the hold store: EQUAL is not evidence of HELD"}


def _read(path: str) -> bytes:
    data = Path(path).read_bytes()
    _need(len(data) <= T9.MAX_INPUT, "INPUT_TOO_LARGE")
    return data


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 5 and argv[0] == "derive":
            result = derive(dict(zip(SETS, (_read(path) for path in argv[1:4]))), _read(argv[4]))
            out = {k: v for k, v in result.items() if k != "targets"}
            out["targets"] = {name: target["sets"] for name, target in result["targets"].items()}
        elif len(argv) == 3 and argv[0] == "compare":
            out = compare(argv[1], _read(argv[2]).decode("utf-8", "replace"))
        else:
            print("mb10_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"mb10_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
