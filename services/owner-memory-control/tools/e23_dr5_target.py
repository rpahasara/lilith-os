#!/usr/bin/env python3
"""Track B E-23 completion: OFF-HOST phase-bound DR-5 comparison for the post-E8 (E-23 NEW release) state.

Record: docs/architecture/trackb-e23-completion.md. Owner workstation, stdlib only: it reads local files, writes nothing
and contacts nothing. It is the accepted E-22 procedure (`e22_dr5_target.py`, unchanged) moved one release on:

    target = derive_release_swap(E-22 post-V7 texts, OLD = 129f2be, NEW = 57bff671)

where the E-22 post-V7 texts are themselves the M-B11 running-signer texts (`mb11_dr5_target.derive`) moved by the same
E-19 contract procedure (`derive_release_swap`, unchanged). Only the release lines move; every other line keeps its
text and order. The target is DERIVED and PINNED, never observed: until one real post-E8 deploy proof compares EQUAL
(`compare`), nothing here claims EQUAL.

| Form | Effect |
| --- | --- |
| `derive <result-set> <dr5-block> <predeploy-block> <dr5-script>` | re-derive the E-23 target; it must equal its pin |
| `compare <e23-workdir> <deploy-log>` | the target for the workdir's consumed RETIRE that reached E8, its VERIFIED signer and both owner acceptances; `EQUAL` only on byte equality of all three sets |

Fail closed: no E8 retire, no verified signer, a missing acceptance or DR-5 set, an `ALLOWED` line, or a log naming
a retired release is `NO_BASELINE_STOP` / DRIFT, never EQUAL.

    derived target != observed EQUAL != accepted;  DR-5 cannot observe HEALTH, the keys, the anchor or the hold store
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

import e22_dr5_target as D22  # noqa: E402  (the accepted E-22 procedure; reused unchanged)
import e23_privacy_anchor_upgrade as E23  # noqa: E402  (the merged, pinned E-23 contract)

T9, D11, J, E19 = D22.T9, D22.D11, D22.J, D22.E19
TargetError = T9.TargetError
_need = T9._need
SETS = T9.SETS
TARGET = "SIGNER_RUNNING_WITNESS_RUNNING_HELD_E23"
SOURCE = D22.TARGET                                       # SIGNER_RUNNING_WITNESS_RUNNING_HELD_E22 (merged, pinned)
STATUS = "DERIVED_PINNED_NOT_ACCEPTED"
E8 = "E8_OLD_RETIRED"
RETIRED = (J.OLD_RELEASE, E23.OLD_RELEASE)                # ba943e1 (E-22 OLD), 129f2be (E-23 OLD)
TARGET_SETS: Mapping[str, tuple[int, str]] = {
    "result-set": (194, "94d38f47f25004e409ac4a7a717c6cd751ed44aa20f249548821054999c913ac"),
    "dr5-block": (155, "402633cde5be1c660613c1a6f64a57ca4f9116ecafa59571d043feb4d16404b0"),
    "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"),   # no release line
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def texts(base: Mapping[str, bytes], script: bytes, *, mb11_pins: Any = D11.TARGETS) -> dict[str, list[str]]:
    """The E-23 target texts: the E-22 derivation (re-checked against its merged pin), then one more release swap."""
    D22.derive(base, script, mb11_pins=mb11_pins)                                     # E-22 target == its pin
    mb11 = D11.derive(base, script, target_pins=mb11_pins)["targets"][D22.SOURCE]["texts"]
    e22 = E19.derive_release_swap(mb11, old=J.OLD_RELEASE, new=J.NEW_RELEASE)
    _need(J.NEW_RELEASE == E23.OLD_RELEASE, "E23_OLD_NOT_THE_E22_NEW")
    return E19.derive_release_swap(e22, old=E23.OLD_RELEASE, new=E23.NEW_RELEASE)


def derive(base: Mapping[str, bytes], script: bytes, *, mb11_pins: Any = D11.TARGETS) -> dict:
    swapped = texts(base, script, mb11_pins=mb11_pins)
    sets = {}
    for name in SETS:
        T9._invariants(name, swapped[name])
        sets[name] = {"lines": len(swapped[name]), "sha256": T9.digest(swapped[name])}
        _need((sets[name]["lines"], sets[name]["sha256"]) == tuple(TARGET_SETS[name]), "E23_TARGET_NOT_PINNED:" + name)
    return {"resultType": "LILITH_E23_DR5_TARGET", "schemaVersion": 1, "target": TARGET, "source": SOURCE,
            "release": E23.NEW_RELEASE, "sets": sets, "status": STATUS, "accepted": False}


def _json(path: Path, name: str) -> Any:
    _need(path.is_file() and not path.is_symlink(), "E23_EVIDENCE_MISSING:" + name)
    raw = path.read_bytes()
    _need(len(raw) <= T9.MAX_INPUT, "INPUT_TOO_LARGE:" + name)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TargetError("E23_EVIDENCE_UNPARSEABLE:" + name) from exc


def verified_e8(workdir: Path) -> dict:
    """The consumed RETIRE that reached E8, the VERIFIED replacement signer on NEW and both owner acceptances."""
    workdir = Path(workdir)
    steps = sorted((workdir / "steps").glob("*-RETIRE")) if (workdir / "steps").is_dir() else []
    _need(len(steps) == 1 and (workdir / "attempts" / "e23-retire.json").is_file(), "NO_BASELINE_STOP:NO_RETIRE")
    step = _json(steps[0] / "STEP.json", "RETIRE")
    _need(step.get("result") == "E23_RETIRE_REACHED_" + E8, "NO_BASELINE_STOP:NOT_E8")
    runs = sorted((workdir / "verify").glob("*-SIGNER")) if (workdir / "verify").is_dir() else []
    _need(bool(runs), "NO_BASELINE_STOP:NO_SIGNER_VERIFY")
    verify = _json(runs[-1] / "VERIFY.json", "VERIFY")
    _need(verify.get("result") == "E23_SIGNER_VERIFIED" and verify.get("release") == E23.NEW_RELEASE,
          "NO_BASELINE_STOP:SIGNER_NOT_VERIFIED")
    _need((workdir / "acceptance" / "SIGNER_ACCEPTANCE.json").is_file()
          and (workdir / "acceptance" / "WITNESS_ACCEPTANCE.json").is_file(), "NO_BASELINE_STOP:NOT_ACCEPTED")
    return {"retireStepSha256": _sha((steps[0] / "STEP.json").read_bytes()),
            "signerVerifySha256": _sha((runs[-1] / "VERIFY.json").read_bytes()),
            "signer": [verify.get("invocationId"), verify.get("mainPid")]}


def compare(workdir: Path, log: str) -> dict:
    bound = verified_e8(workdir)
    sets = T9.extract(log)
    _need(isinstance(sets, Mapping) and set(sets) == set(SETS) and all(sets[name] for name in SETS),
          "DR5_SETS_MISSING")
    retired_lines = sum(1 for lines in sets.values() for line in lines if any(old in line for old in RETIRED))
    observed = {name: (len(lines), T9.digest(lines)) for name, lines in sets.items()}
    unequal = [name for name in SETS if observed[name] != tuple(TARGET_SETS[name])]
    kinds = T9.counts(sets["result-set"])
    equal = not unequal and kinds["ALLOWED"] == 0 and retired_lines == 0
    return {"resultType": "LILITH_E23_DR5_PHASE_COMPARISON", "phase": E8, "target": TARGET, "targetStatus": STATUS,
            "targetAccepted": False, "evidence": bound,
            "observed": {name: {"lines": n, "sha256": h} for name, (n, h) in observed.items()},
            "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "retiredReleaseLines": retired_lines,
            "unequal": unequal, "result": "EQUAL" if equal else "DRIFT", "accepted": False,
            "note": "DR-5 EQUAL is deployment-boundary evidence only; it cannot observe HEALTH, the keys or the hold"}


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
            print("e23_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"e23_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
