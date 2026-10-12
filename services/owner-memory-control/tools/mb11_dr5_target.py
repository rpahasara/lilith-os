#!/usr/bin/env python3
"""15B2b-B1b-3e M-B11 (START_SIGNER): OFF-HOST phase-bound DR-5 targets for the post-start signer phases.

Record: docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-design.md §8 (rule:
`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`, unchanged; ADR-0015 dependency-bound invalidation).

Owner workstation, stdlib only. It reads local files, writes nothing and contacts nothing.

The post-HELD targets (`mb10_dr5_target.py`, pinned, UNCHANGED) are derived from the accepted post-M-B6 texts. This
tool derives the post-start targets from exactly those derived texts, with a delta it PROVES from the pinned DR-5
script (`scripts/deployer_authority_boundary_proof.sh`) instead of assuming it:

- `/run/credentials/lilith-authority-dev.service` is one `AB_LATER` item: while absent the routine deployer prints
  one `DEFERRED_UNTIL_OBJECT_EXISTS: <path> (later step)` line; once present, `DENIED: test -w`, `-r`, `-x` in that
  order (`ab_check_later_state`, `/run/*`). systemd creates it on every signer service start and removes it on stop;
- `/run/lilith-authority-dev` (tmpfiles, since the pre-PR-1B reboot) is already present in the source texts as its
  three `DENIED` lines, and the owner socket beneath it is named by no list, so the signer start changes neither;
- no other list of the script names a path at or beneath either path.

So a RUNNING signer replaces exactly one line by three (+2 lines in the result set and the DR-5 block; the pre-deploy
block is unchanged). A signer STOPPED after its first K-ACT load leaves no deployer-visible trace: its text equals the
post-HELD running-witness text, under a distinct target name. These are derived, PROPOSED targets: no live W11
deployment observation exists yet.

| Form | Effect |
| --- | --- |
| `derive <result-set> <dr5-block> <predeploy-block> <dr5-script>` | the accepted post-M-B6 texts (via the pinned W9 and W10 derivations) and the pinned script; the delta is proven; each derived target must equal its pin |
| `compare <verified-w11-phase> <deploy-log>` | the target for the INDEPENDENTLY verified W11 host phase (`mb11_signer_verifier.py`); anything else, every W9 and W10 phase included, is `NO_BASELINE_STOP`. `EQUAL` only on byte equality of all three sets |

    DR-5 EQUAL != signer verified (the deployer cannot observe HEALTH, the key or the hold store)
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

import mb10_dr5_target as T10  # noqa: E402  (pinned; reused unchanged)
import mb9_dr5_target as T9  # noqa: E402  (pinned; reused unchanged)

TargetError = T9.TargetError
_need = T9._need
SETS = T9.SETS
MB10_DR5_TARGET_SHA256 = "29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0"
DR5_SCRIPT = T10.DR5_SCRIPT
DR5_SCRIPT_SHA256 = T10.DR5_SCRIPT_SHA256
SIGNER_RUNTIME = "/run/lilith-authority-dev"
SIGNER_OWNER_SOCKET = SIGNER_RUNTIME + "/owner.sock"
SIGNER_CREDENTIALS = "/run/credentials/lilith-authority-dev.service"
SIGNER_STATE = "/var/lib/lilith-authority-dev"
DEFERRED_LINE = f"DEFERRED_UNTIL_OBJECT_EXISTS: {SIGNER_CREDENTIALS} (later step)"
DENIED_LINES = tuple(f"DENIED: test {op} {SIGNER_CREDENTIALS}" for op in ("-w", "-r", "-x"))
PRESENT_BEFORE = tuple(f"DENIED: test {op} {path}" for path in (SIGNER_RUNTIME, SIGNER_STATE)
                       for op in ("-w", "-r", "-x"))
LATER_STATE_FUNCTION = (
    'ab_check_later_state() {\n'
    '  local path\n'
    '  for path in ${AB_LATER}; do\n'
    '    if [ -n "$(ab_stat "${path}")" ]; then\n'
    '      ab_deny -w "${path}"\n'
    '      case "${path}" in\n'
    '        /var/lib/*|/run/*) ab_deny -r "${path}"; ab_deny -x "${path}" ;;\n'
    '      esac\n'
    '    else\n'
    '      ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${path} (later step)"\n'
    '    fi\n'
    '  done\n'
    '}\n')

RUNNING_SIGNER_HELD = "SIGNER_RUNNING_WITNESS_RUNNING_HELD"
STOPPED_AFTER_LOAD_HELD = "SIGNER_STOPPED_AFTER_FIRST_LOAD_WITNESS_RUNNING_HELD"
SOURCE = {RUNNING_SIGNER_HELD: T10.RUNNING_HELD, STOPPED_AFTER_LOAD_HELD: T10.RUNNING_HELD}
SUBSTITUTIONS = {RUNNING_SIGNER_HELD: ((DEFERRED_LINE, DENIED_LINES),), STOPPED_AFTER_LOAD_HELD: ()}
# The derived post-start targets (PROPOSED; not owner-accepted; no live W11 observation yet). Tests re-derive them.
TARGETS = {
    RUNNING_SIGNER_HELD: {
        "result-set": (194, "8c8b6eacb144e1d3587a9e6ea1694ff122c0c219ac6e9b90f1f2addd9b41ce93"),
        "dr5-block": (155, "ba39512d64bbc0966dca4125ab1d390adf2d3b41718a279d57e5a4aa4e6d1e59"),
        "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),
    },
    STOPPED_AFTER_LOAD_HELD: dict(T10.TARGETS[T10.RUNNING_HELD]),
}
# W11 host phase (independently verified by `mb11_signer_verifier.py`) -> comparison target. Every other phase,
# including every W9 and W10 phase, has no post-start baseline.
PHASE_TARGETS = {"W11_1_SIGNER_STARTED_EXACT": RUNNING_SIGNER_HELD,
                 "W11_1S_STOPPED_AFTER_FIRST_LOAD": STOPPED_AFTER_LOAD_HELD}


def _check_base_tool() -> None:
    _need(hashlib.sha256(Path(T10.__file__).read_bytes()).hexdigest() == MB10_DR5_TARGET_SHA256,
          "MB10_DR5_TARGET_PIN_MISMATCH")


def prove_signer_delta(script: bytes) -> dict:
    """The one-line delta, proven from the pinned script text (record §8)."""
    lists = T10.script_lists(script)                       # also checks the script pin
    later = lists["AB_LATER"]
    _need(later.count(SIGNER_CREDENTIALS) == 1, "SIGNER_CREDENTIALS_NOT_ONE_LATER_ITEM")
    _need(later.count(SIGNER_RUNTIME) == 1 and later.count(SIGNER_STATE) == 1, "SIGNER_RUNTIME_OR_STATE_NOT_LATER")
    _need(script.decode("utf-8").count(LATER_STATE_FUNCTION) == 1, "LATER_STATE_FUNCTION_NOT_EXACT")
    for name, items in lists.items():
        for path in T10._paths(name, items):
            beneath = (path.startswith(SIGNER_CREDENTIALS + "/") or path == SIGNER_OWNER_SOCKET
                       or path.startswith(SIGNER_RUNTIME + "/"))
            if beneath or (path == SIGNER_CREDENTIALS and name != "AB_LATER") \
                    or (path == SIGNER_RUNTIME and name != "AB_LATER"):
                raise TargetError("SIGNER_PATH_OBSERVED_BY_SCRIPT:" + name)
    return {"credentialsDirectoryIsOneLaterItem": True, "runtimeAndStateAlreadyLater": True,
            "deferredLine": DEFERRED_LINE, "deniedLines": list(DENIED_LINES)}


def derive(base: dict[str, bytes], script: bytes, *, base_pins: dict = T9.BASE, w9_pins: dict | None = T9.TARGETS,
           w10_pins: dict | None = T10.TARGETS, target_pins: dict | None = TARGETS) -> dict:
    """The post-start targets: the pinned W10 derivation, then the proven substitution. `*_pins=None` skips the
    pinned equalities (TEST seams for synthetic baselines)."""
    _check_base_tool()
    proof = prove_signer_delta(script)
    w10 = T10.derive(base, script, base_pins=base_pins, w9_pins=w9_pins, target_pins=w10_pins)
    out = {}
    for target, source in SOURCE.items():
        texts = w10["targets"][source]["texts"]
        derived, sets = {}, {}
        for name in SETS:
            lines = list(texts[name])
            if name != "predeploy-block":
                _need(lines.count(DEFERRED_LINE) == 1, "SOURCE_DEFERRED_LINE_NOT_EXACTLY_ONCE:" + name)
                for line in PRESENT_BEFORE:
                    _need(lines.count(line) == 1, "SOURCE_SIGNER_RUNTIME_NOT_ALREADY_DENIED:" + name)
                derived[name] = T9.substitute(lines, SUBSTITUTIONS[target])
            else:
                _need(not any(SIGNER_CREDENTIALS in line for line in lines), "PREDEPLOY_NAMES_SIGNER_CREDENTIALS")
                derived[name] = lines
            T9._invariants(name, derived[name])
            added = [line for line in derived[name] if line not in lines]
            removed = [line for line in lines if line not in derived[name]]
            sets[name] = {"lines": len(derived[name]), "sha256": T9.digest(derived[name]),
                          "counts": T9.counts(derived[name]), "sourceTarget": source, "added": added,
                          "removed": removed}
            if target_pins is not None:
                _need((sets[name]["lines"], sets[name]["sha256"]) == target_pins[target][name],
                      "TARGET_NOT_PINNED:" + target + ":" + name)
        out[target] = {"sets": sets, "texts": derived}
    return {"resultType": "LILITH_MB11_DR5_TARGETS", "schemaVersion": 1,
            "rule": "PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA", "delta": "ONE_LATER_LINE_PROVEN_FROM_PINNED_SCRIPT",
            "proof": proof, "targets": out, "accepted": False, "derived": True, "liveW11ObservationExists": False,
            "w9AndW10TargetsUnchanged": True, "dr5EqualIsNotSignerEvidence": True}


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
    return {"resultType": "LILITH_MB11_DR5_PHASE_COMPARISON", "phase": phase, "target": name, "targetAccepted": False,
            "observed": {set_name: {"lines": n, "sha256": h} for set_name, (n, h) in observed.items()},
            "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "unequal": unequal,
            "result": "EQUAL" if not unequal and kinds["ALLOWED"] == 0 else "DRIFT", "accepted": False,
            "note": "DR-5 cannot observe HEALTH, the loaded key or the hold store: EQUAL is not signer evidence"}


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
            print("mb11_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"mb11_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
