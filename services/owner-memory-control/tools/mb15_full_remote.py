#!/usr/bin/env python3
"""15B2b-B1b-3e M-B15 (EVALUATE_FULL_READINESS) W14: the READ-ONLY host side of `mb15_operator.py`.

Record: docs/architecture/slice-15b2b-b1b3e-mb15-w14-full-readiness-package.md. SOURCE ONLY: running it on DEV needs
the operator and a separate owner authorization.

It runs as root under the release interpreter in the reviewed mb6 BOOT stdin bundle, after the UNCHANGED W10 chain,
the UNCHANGED W11 verifier (`mb11_signer_verifier`), the UNCHANGED M-B11 host tail and the UNCHANGED E-22 host tail
(`e22_transition_remote`). The owner-side inputs arrive as one generated data module, `mb15_full_evidence` (`DOC`),
never as a host file or a free argument; `main` refuses before any host read unless the argv digest equals the
canonical digest of `DOC`.

    full    ONE HEALTH frame bound to one exact RUNNING incarnation (the E-22 `package_report` capture, unchanged),
            then the release verifier's own `evaluate` in BOTH modes over that frame and ONE complete hold
            observation (`verifier.report` for each, the W11 `_summary` of each, the hold listing digest); plus the
            W11 signer observation (units, credentials names, owner socket, process), the effective restart boundary
            and the ledger directory bytes

Nothing here judges: W14 is `mb15_operator.judge`, off-host. It never starts, stops, enables or reloads a unit, never
reads a credential and never writes. It never connects to the owner socket unless the service and socket are an exact
RUNNING pair (the M-B11 guard).

    root FULL_READINESS READY != M-B15 (freshness, preservation, owner reproduction) != activation != First Memory
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

import e22_transition_remote as Q  # noqa: E402  (BOOT bundle member; the E-22 host tail, unchanged)

REMOTE_TYPE = "LILITH_MB15_FULL_REMOTE"
EVIDENCE_MODULE = "mb15_full_evidence"
FORMS = ("full",)
_FIELDS = frozenset({"form", "ownerInputs"})

Refused = Q.Refused
canonical = Q.canonical
evidence_digest = Q.evidence_digest
evidence_module_source = Q.evidence_module_source


def check_evidence(doc: Any, form: str) -> Mapping[str, Any]:
    if form not in FORMS or not isinstance(doc, Mapping) or set(doc) != _FIELDS or doc.get("form") != form:
        raise Refused("EVIDENCE_NOT_EXACT")
    if not isinstance(doc["ownerInputs"], Mapping):
        raise Refused("EVIDENCE_OWNER_INPUTS_INVALID")
    return doc


def both_modes(root: Any, *, owner_uid: int = 0, owner_gid: int = 0, run: Callable | None = None
               ) -> Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]:
    """The release verifier in BOTH modes over the SAME HEALTH frame and ONE complete hold observation.
    `owner_uid`, `owner_gid`, `run` are TEST seams (root and the real systemctl runner on DEV)."""
    def evaluate(document: Mapping[str, Any], frame: Mapping[str, Any]) -> dict[str, Any]:
        import mb11_signer_verifier as W  # noqa: N811
        from lilith_authority_root import observers as O
        from lilith_authority_root import verifier as RV
        from lilith_authority_root.hold_store import HoldStoreV1
        from lilith_owner_memory import successor_readiness as SR

        owner = RV.parse_verifier_inputs(document)
        hold = HoldStoreV1(environment=owner.environment, root=Path(root), owner_uid=owner_uid,
                           owner_gid=owner_gid).observe()
        out: dict[str, Any] = {"holdListingDigest": hold.listing_digest}
        for name, mode in (("full", SR.FULL_READINESS), ("eligibility", SR.HOLD_RELEASE_ELIGIBILITY)):
            result = RV.evaluate(mode, owner, root=Path(root), owner_uid=owner_uid, owner_gid=owner_gid,
                                 health=lambda: dict(frame), run=run or O.default_runner, hold=hold)
            out[name] = dict(RV.report(result))
            out[name + "Summary"] = W._summary(result)
        return out

    return evaluate


def run_form(doc: Mapping[str, Any], *, root: Any = "/", W: Any = None, units: Callable | None = None,
             health: Callable | None = None, evaluate: Callable | None = None, process: Callable | None = None,
             restart_boundary: Callable | None = None, ledger: Callable | None = None) -> dict[str, Any]:
    """The one read-only form. Every keyword argument is a TEST seam."""
    if W is None:
        import mb11_signer_verifier as W  # noqa: N811
    out: dict[str, Any] = {"remoteType": REMOTE_TYPE, "schemaVersion": 1, "form": doc["form"],
                           "evidenceSha256": evidence_digest(doc), "authorityGranted": False}
    report = Q.package_report(doc["ownerInputs"], root=root, W=W, units=units, health=health,
                              evaluate=evaluate or both_modes(root))
    out["healthCapture"] = report["healthCapture"]
    out["readiness"] = report["report"]
    signer = W.observe_signer(Path(root), units=units, process=process)
    out["signer"] = signer
    try:
        out["restartBoundary"] = (restart_boundary or W._restart_boundary)(Path(root), units)
    except Exception as exc:  # noqa: BLE001 - an unreadable boundary is UNKNOWN, never success
        out["restartBoundary"] = {"error": type(exc).__name__}
    out["ledger"] = (ledger or W.observe_ledger_bytes)(Path(root))
    return out


def main(argv: list[str]) -> int:
    try:
        if len(argv) != 2 or argv[0] not in FORMS:
            raise Refused("USAGE")
        module = sys.modules.get(EVIDENCE_MODULE)
        doc = check_evidence(getattr(module, "DOC", None), argv[0])
        if evidence_digest(doc) != argv[1]:
            raise Refused("EVIDENCE_DIGEST_MISMATCH")
        import mb6_ledger_verifier as V6

        V6.require_dev_root()
        if V6.RELEASE_TREE not in sys.path:
            sys.path.insert(0, V6.RELEASE_TREE)
        result = run_form(doc)
    except Refused as exc:
        print(f"mb15_full_remote: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - e.g. mb6_ledger_verifier.Refused (NOT_ROOT / NOT_DEV_HOST)
        print(f"mb15_full_remote: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
