"""The fixed root ceremony CLIs of the reviewed release (PR-1S, S-9, S-11).

Installed by the upgrade `cli` stage as `/usr/local/sbin/<name>` (`root:root
0755`); each is a thin wrapper that calls `main(<name>, argv)`. Closed argument
forms only; no path, environment, key, or JSON-to-write argument, except the
one closed owner input document the verifier and the release read. Every
command prints one JSON object on stdout; a refusal prints
`<name>: REFUSED <reason>` on stderr and exits 2.

| CLI | forms |
| --- | --- |
| `lilith-authority-ledger-dev` | `provision <registryVersion>`, `observe` (root); `provision-as-signer <registryVersion>` (signer uid, via runuser) |
| `lilith-authority-hold-dev` | `observe`, `create-initial-held`, `release-initial <approvedPackageDigest> <inputs.json>`, `create-successor-held <ROTATION\\|KEY_COMPROMISE_RECOVERY> <N>`, `create-maintenance-held <authorizationId> <targetRegistryVersion>`, `create-custody-debt-held <N>`, `release-ceremony <ceremonyId> <approvedReadinessDigest> <successor-inputs.json>` |
| `lilith-authority-verify-dev` | `eligibility <inputs.json>`, `full <inputs.json>`, `genesis-candidate <registryVersion> <updatedAt>` |
| `lilith-recovery-witness-owner-dev` | `health`, `read`, `bootstrap <registryVersion> <updatedAt>`, `execute-head-advance <authorization.json> <targetRegistryVersion>`, `execute-epoch-advance <authorization.json> <targetRegistryVersion>` |
| `lilith-authority-recovery-dev` | `advance-epoch <authorization.json>`, `void-challenges`, `quarantine-uses` |

Nothing here starts, enables, or reloads a unit, and nothing signs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from lilith_authority_dev import protocol as AP
from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_authority_host.store_observer import observe_witness_state, read_regular
from lilith_owner_memory import authority_ledger_journal as J
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR
from lilith_recovery_witness import protocol as WP

from . import clients, genesis, ledger_tool, verifier
from .hold_store import HoldStoreError, HoldStoreV1

ENVIRONMENT = "dev"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
MAX_INPUT = 256 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[1-9][0-9]{0,15}\Z")
_ORDINAL = re.compile(r"[1-9][0-9]{0,3}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_AUTHORIZATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_CEREMONY_ID = _AUTHORIZATION_ID


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Refused("INPUT_DUPLICATE_KEY")
        value[key] = item
    return value


def _document(path: str) -> Any:
    try:
        raw = read_regular(path, limit=MAX_INPUT)
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Refused("INPUT_DOCUMENT_UNREADABLE") from exc


def _arg(pattern: re.Pattern[str], value: str, reason: str) -> str:
    if not isinstance(value, str) or not value.isascii() or pattern.fullmatch(value) is None:
        raise Refused(reason)
    return value


def _require_root(euid: int) -> None:
    if euid != 0:
        raise Refused("NOT_ROOT")


def _host_view() -> tuple[HI.HostInputsV1, WR.WitnessStoreObservationV1, WR.WitnessStoreContextV1]:
    inputs = HI.read_host_inputs(environment=ENVIRONMENT)
    if inputs.registry_root is None or inputs.witness_anchor is None:
        raise Refused("HOST_INPUTS_INCOMPLETE:" + ",".join(inputs.reasons))
    context = inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))
    return inputs, observe_witness_state(P.WITNESS_STATE), context


def _signer_ids() -> tuple[int, int]:
    import pwd

    entry = pwd.getpwnam(P.AUTHORITY_USER)
    return entry.pw_uid, entry.pw_gid


# ------------------------------------------------------------- commands ---

def _ledger(argv: list[str], euid: int) -> dict[str, Any]:
    if argv[:1] == ["provision-as-signer"] and len(argv) == 2:
        uid, _gid = _signer_ids()
        observed = ledger_tool.provision_as_signer(environment=ENVIRONMENT,
                                                   registry_version=int(_arg(_VERSION, argv[1], "VERSION_INVALID")),
                                                   euid=euid, signer_uid=uid)
        return {"ledgerSequence": observed.sequence, "ledgerHead": observed.head, "authorityGranted": False}
    _require_root(euid)
    if argv[:1] == ["provision"] and len(argv) == 2:
        version = int(_arg(_VERSION, argv[1], "VERSION_INVALID"))
        uid, gid = _signer_ids()

        def run_as_signer(registry_version: int) -> int:
            return subprocess.run(["/usr/sbin/runuser", "-u", P.AUTHORITY_USER, "--", P.LEDGER_CLI,
                                   "provision-as-signer", str(registry_version)], env=FIXED_ENV, check=False,
                                  timeout=120).returncode

        return ledger_tool.provision(environment=ENVIRONMENT, registry_version=version, euid=euid, signer_uid=uid,
                                     signer_gid=gid, run_as_signer=run_as_signer)
    if argv == ["observe"]:
        from lilith_authority_dev.ledger import observe_copy

        observed = observe_copy(P.AUTHORITY_LEDGER, environment=ENVIRONMENT)
        return {"ledgerSequence": observed.sequence, "ledgerHead": observed.head,
                "registryView": observed.registry_view, "rowsConsistent": observed.rows_consistent,
                "terminalReopened": observed.terminal_reopened, "authorityGranted": False}
    raise Refused("USAGE")


def _verify_run(mode: str, path: str, hold=None) -> Any:
    owner = verifier.parse_verifier_inputs(_document(path))
    return verifier.evaluate(mode, owner, health=clients.signer_health, hold=hold)


def _hold(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    store = HoldStoreV1(environment=ENVIRONMENT)
    if argv == ["observe"]:
        observed = store.observe()
        return {"listingDigest": observed.listing_digest, "snapshot": dict(observed.snapshot),
                "authorityGranted": False}
    inputs, witness_store, context = _host_view()
    if argv == ["create-initial-held"]:
        return {"record": store.create_initial_held(witness_store=witness_store, context=context)}
    if argv[:1] == ["release-initial"] and len(argv) == 3:
        approved = _arg(_DIGEST, argv[1], "APPROVED_DIGEST_INVALID")
        record = store.release_initial(
            approved_package_digest=approved,
            rerun=lambda held: _verify_run(SR.HOLD_RELEASE_ELIGIBILITY, argv[2], hold=held),
            witness_store=witness_store, context=context)
        return {"record": record}
    if argv[:1] == ["create-successor-held"] and len(argv) == 3:
        if argv[1] not in (SC.ROTATION, SC.KEY_COMPROMISE_RECOVERY):
            raise Refused("KIND_INVALID")
        return {"record": store.create_successor_held(kind=argv[1],
                                                      ordinal=int(_arg(_ORDINAL, argv[2], "ORDINAL_INVALID")),
                                                      witness_store=witness_store, context=context,
                                                      registries=inputs.registries)}
    if argv[:1] == ["create-maintenance-held"] and len(argv) == 3:
        version = int(_arg(_VERSION, argv[2], "VERSION_INVALID"))
        target = next((r for r in inputs.registries if r.get("registryVersion") == version), None)
        if target is None:
            raise Refused("REGISTRY_NOT_INSTALLED")
        return {"record": store.create_maintenance_held(
            authorization_id=_arg(_AUTHORIZATION_ID, argv[1], "AUTHORIZATION_ID_INVALID"), target_registry=target,
            witness_store=witness_store, context=context, registries=inputs.registries)}
    if argv[:1] == ["create-custody-debt-held"] and len(argv) == 2:
        return {"record": store.create_custody_debt_held(ordinal=int(_arg(_ORDINAL, argv[1], "ORDINAL_INVALID")),
                                                         witness_store=witness_store, context=context)}
    if argv[:1] == ["release-ceremony"] and len(argv) == 4:
        ceremony = _arg(_CEREMONY_ID, argv[1], "CEREMONY_ID_INVALID")
        approved = _arg(_DIGEST, argv[2], "APPROVED_DIGEST_INVALID")
        document = _document(argv[3])
        record = store.release_with_readiness(
            ceremony_id=ceremony, approved_readiness_digest=approved,
            rerun=lambda held: verifier.successor_readiness(document, hold=held, health=clients.signer_health),
            witness_store=witness_store, context=context)
        return {"record": record}
    raise Refused("USAGE")


def _verify(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    if argv[:1] in (["eligibility"], ["full"]) and len(argv) == 2:
        mode = SR.HOLD_RELEASE_ELIGIBILITY if argv[0] == "eligibility" else SR.FULL_READINESS
        return verifier.report(_verify_run(mode, argv[1]))
    if argv[:1] == ["genesis-candidate"] and len(argv) == 3:
        built, _inputs, _ledger = genesis.candidate(environment=ENVIRONMENT,
                                                    registry_version=int(_arg(_VERSION, argv[1], "VERSION_INVALID")),
                                                    updated_at=_arg(_INSTANT, argv[2], "UPDATED_AT_INVALID"))
        return genesis.candidate_report(built)
    raise Refused("USAGE")


def _witness(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    if argv == ["health"]:
        return dict(clients.witness_owner(WP.HEALTH, {}))
    if argv == ["read"]:
        return dict(clients.witness_owner(WP.READ_WITNESS, {}))
    if argv[:1] == ["bootstrap"] and len(argv) == 3:
        return genesis.bootstrap(environment=ENVIRONMENT,
                                 registry_version=int(_arg(_VERSION, argv[1], "VERSION_INVALID")),
                                 updated_at=_arg(_INSTANT, argv[2], "UPDATED_AT_INVALID"),
                                 witness_owner=clients.witness_owner)
    if argv[:1] in (["execute-head-advance"], ["execute-epoch-advance"]) and len(argv) == 3:
        authorization = _document(argv[1])
        version = int(_arg(_VERSION, argv[2], "VERSION_INVALID"))
        snapshot = dict(HoldStoreV1(environment=ENVIRONMENT).observe().snapshot)
        if argv[0] == "execute-head-advance":
            return dict(clients.witness_owner(WP.EXECUTE_REGISTRY_HEAD_ADVANCE, {
                "authorization": authorization, "targetRegistryVersion": version, "holdStore": snapshot}))
        from lilith_authority_dev.ledger import journal_copy, observe_copy

        observed = observe_copy(P.AUTHORITY_LEDGER, environment=ENVIRONMENT)
        journal = journal_copy(P.AUTHORITY_LEDGER, environment=ENVIRONMENT)
        adoption = journal[-1] if journal else None
        if not isinstance(adoption, dict) or adoption.get("op") != J.ADVANCE_EPOCH:
            raise Refused("ADOPTION_NOT_JOURNALLED")
        return dict(clients.witness_owner(WP.EXECUTE_EPOCH_ADVANCE, {
            "authorization": authorization, "targetRegistryVersion": version, "adoptionRecord": adoption,
            "ledgerSequence": observed.sequence, "ledgerHead": observed.head, "holdStore": snapshot}))
    raise Refused("USAGE")


def _recovery(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    snapshot = dict(HoldStoreV1(environment=ENVIRONMENT).observe().snapshot)
    if argv[:1] == ["advance-epoch"] and len(argv) == 2:
        return dict(clients.signer_recovery(AP.RECOVERY_ADVANCE_EPOCH, hold_snapshot=snapshot,
                                            epoch_authorization=_document(argv[1])))
    if argv == ["void-challenges"]:
        return dict(clients.signer_recovery(AP.RECOVERY_VOID_CHALLENGE, hold_snapshot=snapshot))
    if argv == ["quarantine-uses"]:
        return dict(clients.signer_recovery(AP.RECOVERY_QUARANTINE_USE, hold_snapshot=snapshot))
    raise Refused("USAGE")


COMMANDS: dict[str, Callable[[list[str], int], dict[str, Any]]] = {
    "lilith-authority-ledger-dev": _ledger,
    "lilith-authority-hold-dev": _hold,
    "lilith-authority-verify-dev": _verify,
    "lilith-recovery-witness-owner-dev": _witness,
    "lilith-authority-recovery-dev": _recovery,
}


def main(name: str, argv: list[str], *, euid: int | None = None) -> int:
    handler = COMMANDS.get(name)
    if handler is None:
        print(f"{name}: REFUSED UNKNOWN_CLI", file=sys.stderr)
        return 2
    try:
        result = handler(list(argv), os.geteuid() if euid is None else euid)
    except Refused as exc:
        print(f"{name}: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (HoldStoreError, ledger_tool.LedgerToolError, genesis.GenesisToolError) as exc:
        print(f"{name}: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (verifier.VerifierInputError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"{name}: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0
