"""The signer's own read-only view and readiness self-view (PR-1S, S-10).

The signer reads, from fixed paths only: the public on-host inputs
(`lilith_authority_host.inputs`), the witness chain through its
`ReadOnlyPaths` view of `/var/lib/lilith-recovery-witness`, and its own
ledger. It cannot observe the credential inventory (`InaccessiblePaths`,
PC-7) or the root `0700` hold store (RR-34), so its self-view is partial by
construction and ALWAYS reports NOT_READY with those two reasons plus
`ISSUANCE_UNWIRED` (RR-39). Independent readiness is the root verifier's.

    signer self-view != independent readiness
    signer HEALTH    != authority
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_authority_host.store_observer import observe_witness_state
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import witness_readiness as WR

from .ledger import DurableAuthorityLedgerV1, LedgerError
from .recovery import SignerViewV1

# Always present: what the signer can never establish about itself.
STRUCTURAL_SELF_VIEW_REASONS = ("CREDENTIAL_INVENTORY_UNOBSERVABLE_BY_SIGNER", "HOLD_STORE_UNOBSERVABLE_BY_SIGNER",
                                "ISSUANCE_UNWIRED")


def signer_view(*, environment: str, root: Path | str = Path("/"), owner_uid: int = 0) -> SignerViewV1:
    root = Path(root)
    inputs = HI.read_host_inputs(environment=environment, root=root, owner_uid=owner_uid)
    witness_store = observe_witness_state(root / P.WITNESS_STATE.lstrip("/"))
    context = None
    if inputs.registry_root is not None and inputs.witness_anchor is not None:
        context = inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))
    return SignerViewV1(context, inputs.registries, witness_store, inputs.reasons)


def self_view(view: SignerViewV1, open_ledger: Callable[[], DurableAuthorityLedgerV1]) -> dict[str, Any]:
    """Ordered NOT_READY reasons the signer can derive about itself. Never READY."""
    reasons: list[str] = list(view.incomplete)
    head = None
    if view.context is None:
        reasons.append("WITNESS_MISSING")
    else:
        scan = WR.classify_witness_store(observation=view.witness_store, context=view.context)
        if scan.classification == WR.UNINITIALIZED:
            reasons.append("WITNESS_MISSING")
        elif scan.classification != WR.CONSISTENT:
            reasons.append("WITNESS_" + scan.classification)
        else:
            head = scan.head
    try:
        ledger = open_ledger()
    except LedgerError as exc:
        reasons.append("AUTHORITY_STATE_MISSING" if exc.reason == "AUTHORITY_STATE_MISSING"
                       else "LEDGER_" + exc.reason)
    else:
        try:
            observation = ledger.observe()
            if head is not None:
                position = RC.authority_ledger_position_reason(observation, head)
                if position is not None:
                    reasons.append(position)
        except LedgerError as exc:
            reasons.append("LEDGER_" + exc.reason)
        finally:
            ledger.close()
    reasons.extend(STRUCTURAL_SELF_VIEW_REASONS)
    return {"readiness": "NOT_READY", "reasons": reasons, "independentReadiness": "ROOT_VERIFIER_ONLY",
            "authorityGranted": False}
