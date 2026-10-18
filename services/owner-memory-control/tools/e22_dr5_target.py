#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12 E-22 completion: OFF-HOST phase-bound DR-5 comparison for the post-V7 (NEW-release) state.

Record: docs/architecture/slice-15b2b-b1b3e-e22-completion.md (rule `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`,
unchanged). Owner workstation, stdlib only. It reads local files, writes nothing and contacts nothing.

The target is the merged contract's `NEW_DR5_TARGETS` (`e22_judge_upgrade.py`, PR #220): the M-B11 running-signer
texts (`mb11_dr5_target.derive`, which re-checks every W9 / W10 / W11 pin over the accepted post-M-B6 fixture and the
pinned DR-5 script) with exactly the release lines moved by the E-19 contract's `derive_release_swap(OLD, NEW)`. This
tool adds no target value: `derive` re-derives it and requires equality with the merged pin; `compare` maps the
INDEPENDENTLY verified post-V7 state (the E-22 operator workdir) to that target.

| Form | Effect |
| --- | --- |
| `derive <result-set> <dr5-block> <predeploy-block> <dr5-script>` | re-derive the E-22 target; it must equal its merged pin |
| `compare <e22-workdir> <deploy-log>` | the target for the workdir's consumed RETIRE that reached V7 and its VERIFIED signer POST; `EQUAL` only on byte equality of all three sets |

Fail closed: no V7 retire step, no verified signer POST, a missing DR-5 set, an `ALLOWED` line, or a log naming the
retired OLD release is `NO_BASELINE_STOP` / DRIFT, never EQUAL.

    derived target != accepted target;  EQUAL != owner acceptance;  DR-5 cannot observe HEALTH, the key or the hold store
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

import e22_judge_upgrade as J  # noqa: E402  (the merged contract: NEW_DR5_TARGETS)
import mb11_dr5_target as D11  # noqa: E402  (pinned; reused unchanged)

T9 = D11.T9
E19 = J.E19
TargetError = T9.TargetError
_need = T9._need
SETS = T9.SETS
TARGET, = J.NEW_DR5_TARGETS
SOURCE = J.NEW_DR5_SOURCES[TARGET]
W11_1 = "W11_1_SIGNER_STARTED_EXACT"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive(base: Mapping[str, bytes], script: bytes, *, mb11_pins: Any = D11.TARGETS) -> dict:
    """Re-derive the post-V7 target from the accepted texts and require equality with the merged pin."""
    _need(SOURCE == D11.RUNNING_SIGNER_HELD, "E22_SOURCE_NOT_MB11_RUNNING_SIGNER")
    texts = D11.derive(base, script, target_pins=mb11_pins)["targets"][SOURCE]["texts"]
    swapped = E19.derive_release_swap(texts, old=J.OLD_RELEASE, new=J.NEW_RELEASE)
    sets = {}
    for name in SETS:
        T9._invariants(name, swapped[name])
        sets[name] = {"lines": len(swapped[name]), "sha256": T9.digest(swapped[name])}
        _need((sets[name]["lines"], sets[name]["sha256"]) == tuple(J.NEW_DR5_TARGETS[TARGET][name]),
              "E22_TARGET_NOT_PINNED:" + name)
    return {"resultType": "LILITH_E22_DR5_TARGET", "schemaVersion": 1, "target": TARGET, "source": SOURCE,
            "release": J.NEW_RELEASE, "sets": sets, "status": J.NEW_DR5_TARGETS_STATUS, "accepted": False}


def _json(path: Path, name: str) -> Any:
    _need(path.is_file() and not path.is_symlink(), "E22_EVIDENCE_MISSING:" + name)
    raw = path.read_bytes()
    _need(len(raw) <= T9.MAX_INPUT, "INPUT_TOO_LARGE:" + name)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TargetError("E22_EVIDENCE_UNPARSEABLE:" + name) from exc


def verified_v7(workdir: Path) -> dict:
    """The consumed RETIRE that reached V7 and the VERIFIED replacement signer POST (W11_1, K-ACT load count 2)."""
    workdir = Path(workdir)
    steps = sorted((workdir / "steps").glob("*-RETIRE")) if (workdir / "steps").is_dir() else []
    _need(len(steps) == 1 and (workdir / "attempts" / "e22-retire.json").is_file(), "NO_BASELINE_STOP:NO_RETIRE")
    step = _json(steps[0] / "STEP.json", "RETIRE")
    _need(step.get("result") == "E22_RETIRE_REACHED_" + J.V7, "NO_BASELINE_STOP:NOT_V7")
    posts = sorted((workdir / "posts").glob("*-SIGNER")) if (workdir / "posts").is_dir() else []
    _need(bool(posts), "NO_BASELINE_STOP:NO_SIGNER_POST")
    post = _json(posts[-1] / "POST.json", "POST")
    _need(post.get("result") == "E22_SIGNER_POST_VERIFIED" and post.get("w11Phase") == W11_1
          and post.get("kActLoadCount") == J.KACT_LOAD_COUNT_AFTER and post.get("release") == J.NEW_RELEASE,
          "NO_BASELINE_STOP:SIGNER_POST_NOT_VERIFIED")
    _need((workdir / "acceptance" / "SIGNER_ACCEPTANCE.json").is_file()
          and (workdir / "acceptance" / "WITNESS_ACCEPTANCE.json").is_file(), "NO_BASELINE_STOP:NOT_ACCEPTED")
    return {"retireStepSha256": _sha((steps[0] / "STEP.json").read_bytes()),
            "signerPostSha256": _sha((posts[-1] / "POST.json").read_bytes()),
            "signer": [post.get("invocationId"), post.get("mainPid")]}


def compare(workdir: Path, log: str) -> dict:
    bound = verified_v7(workdir)
    target = J.NEW_DR5_TARGETS[TARGET]
    sets = T9.extract(log)
    _need(isinstance(sets, Mapping) and set(sets) == set(SETS) and all(sets[name] for name in SETS),
          "DR5_SETS_MISSING")
    old_lines = sum(1 for lines in sets.values() for line in lines if J.OLD_RELEASE in line)
    observed = {name: (len(lines), T9.digest(lines)) for name, lines in sets.items()}
    unequal = [name for name in SETS if observed[name] != tuple(target[name])]
    kinds = T9.counts(sets["result-set"])
    equal = not unequal and kinds["ALLOWED"] == 0 and old_lines == 0
    return {"resultType": "LILITH_E22_DR5_PHASE_COMPARISON", "phase": W11_1, "target": TARGET,
            "targetStatus": J.NEW_DR5_TARGETS_STATUS, "targetAccepted": False, "evidence": bound,
            "observed": {name: {"lines": n, "sha256": h} for name, (n, h) in observed.items()},
            "allowed": kinds["ALLOWED"], "fail": kinds["FAIL"], "oldReleaseLines": old_lines, "unequal": unequal,
            "result": "EQUAL" if equal else "DRIFT", "accepted": False,
            "note": "DR-5 EQUAL is deployment-boundary evidence only; it cannot observe HEALTH, the key or the hold"}


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
            print("e22_dr5_target: REFUSED USAGE", file=sys.stderr)
            return 2
    except TargetError as exc:
        print(f"e22_dr5_target: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0 if out.get("result", "EQUAL") == "EQUAL" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
