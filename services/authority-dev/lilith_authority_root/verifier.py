"""The independent root PR-1 readiness verifier (PR-1S, S-11, RR-38 A).

Read-only. It gathers every root observation itself (public on-host inputs,
the witness store, a private copy of the ledger, CURRENT, the credential
inventory, the installed unit's credential directives, the installed
release tree, unit states, the complete hold store), takes the signer's
HEALTH (B4, a signer claim), and takes the owner-supplied inputs from one
closed input document (release attestation digests, the accepted CURRENT
pin, the first-preflight CURRENT observation, the exact K-ACT and K-WIT
publication bytes, the proof transcript digests, the activation line, and
the PR-2 / PR-3 results, which are ABSENT until those PRs exist).

It invokes the accepted pure evaluators (Source Prep B readiness in
`HOLD_RELEASE_ELIGIBILITY` or `FULL_READINESS`, and the PR-1 package) and
returns structured reasons, the canonical package, and its digest. It never
writes RELEASED, generates a credential, signs, or alters the ledger.

    on-host PASS != owner acceptance
"""

from __future__ import annotations

import base64
import dataclasses
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from lilith_authority_dev.ledger import LedgerError, observe_copy
from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_authority_host.store_observer import observe_witness_state
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import pr1_bootstrap as B
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR

from . import observers as O
from .hold_store import CompleteHoldObservationV1, HoldStoreV1

INPUT_TYPE = "LILITH_PR1_VERIFIER_INPUTS"
INPUT_SCHEMA_VERSION = 1
INPUT_FIELDS = frozenset({
    "inputType", "schemaVersion", "environment", "releaseSha", "attestedManifestSha256", "reviewedRuntimeDigests",
    "pinnedCurrentSha256", "firstPreflightCurrent", "kActPublication", "kWitPublication", "proofs", "activation",
    "snapshotInventory", "offHostMaterial",
})
_CURRENT_FIELDS = frozenset({"path", "kind", "uid", "gid", "mode", "device", "inode", "size", "mtimeNs", "ctimeNs",
                             "sha256"})
_PROOF_FIELDS = frozenset({"result", "transcriptSha256", "detail"})
_SNAPSHOT_FIELDS = frozenset({"status", "recordSha256", "artefactClasses", "namedDebts"})
_OFFHOST_FIELDS = frozenset({"status", "registerSha256", "genesisPinDigest", "kRootPublicKeySha256",
                             "kWitPublicKeySha256", "kActPublicationSha256", "registryHead", "releaseSha",
                             "releaseManifestSha256", "authorizationIds", "burnedOrdinals"})
UNITS = PA.SIGNER_UNITS + PA.WITNESS_UNITS


class VerifierInputError(ValueError):
    pass


@dataclass(frozen=True)
class VerifierInputsV1:
    environment: str
    release_sha: str
    attested_manifest_sha256: str
    reviewed_runtime_digests: Mapping[str, str] | None
    pinned_current_sha256: str
    first_preflight_current: PA.CurrentBlobObservationV1
    k_act_publication_bytes: bytes
    k_wit_publication_bytes: bytes
    proofs: Mapping[str, PA.ExternalProofV1]
    activation: PA.ActivationObservationV1
    snapshot_inventory: PA.SnapshotInventoryResultV1 | None
    offhost_material: PA.OwnerOffHostMaterialV1 | None


def _b64u(value: Any) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise VerifierInputError("publication bytes must be base64url")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _exact(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise VerifierInputError(f"{name} fields")
    return value


def _decimal(value: Any) -> int | None:
    try:
        return PA.parse_decimal(value)
    except ValueError as exc:
        raise VerifierInputError("firstPreflightCurrent identity") from exc


def parse_verifier_inputs(document: Any) -> VerifierInputsV1:
    """The closed owner input document. Nothing is defaulted; PR-2 / PR-3 are
    explicit `null` until they exist (-> NOT_READY)."""
    doc = _exact(document, INPUT_FIELDS, "input")
    if doc["inputType"] != INPUT_TYPE or doc["schemaVersion"] != INPUT_SCHEMA_VERSION:
        raise VerifierInputError("input type")
    current = _exact(doc["firstPreflightCurrent"], _CURRENT_FIELDS, "firstPreflightCurrent")
    mode = current["mode"]
    first = PA.CurrentBlobObservationV1(
        current["path"], current["kind"], current["uid"], current["gid"],
        None if mode is None else int(mode, 8), _decimal(current["device"]), _decimal(current["inode"]),
        current["size"], _decimal(current["mtimeNs"]), _decimal(current["ctimeNs"]), current["sha256"])
    proofs = {}
    if not isinstance(doc["proofs"], Mapping):
        raise VerifierInputError("proofs")
    for name, value in doc["proofs"].items():
        value = _exact(value, _PROOF_FIELDS, f"proof {name}")
        proofs[name] = PA.ExternalProofV1(name, value["result"], value["transcriptSha256"], value["detail"])
    activation = _exact(doc["activation"], frozenset({"line", "b1cUnchanged"}), "activation")
    snapshot = None
    if doc["snapshotInventory"] is not None:
        item = _exact(doc["snapshotInventory"], _SNAPSHOT_FIELDS, "snapshotInventory")
        snapshot = PA.SnapshotInventoryResultV1(item["status"], item["recordSha256"],
                                                tuple(item["artefactClasses"]), tuple(item["namedDebts"]))
    material = None
    if doc["offHostMaterial"] is not None:
        item = _exact(doc["offHostMaterial"], _OFFHOST_FIELDS, "offHostMaterial")
        head = _exact(item["registryHead"], frozenset({"registryVersion", "registryDigest"}), "registryHead")
        material = PA.OwnerOffHostMaterialV1(
            item["status"], item["registerSha256"], item["genesisPinDigest"], item["kRootPublicKeySha256"],
            item["kWitPublicKeySha256"], item["kActPublicationSha256"],
            RC.RegistryHeadV1(head["registryVersion"], head["registryDigest"]), item["releaseSha"],
            item["releaseManifestSha256"], tuple(item["authorizationIds"]), tuple(item["burnedOrdinals"]))
    return VerifierInputsV1(
        doc["environment"], doc["releaseSha"], doc["attestedManifestSha256"], doc["reviewedRuntimeDigests"],
        doc["pinnedCurrentSha256"], first, _b64u(doc["kActPublication"]), _b64u(doc["kWitPublication"]), proofs,
        PA.ActivationObservationV1(activation["line"], activation["b1cUnchanged"]), snapshot, material)


def evaluate(mode: str, owner: VerifierInputsV1, *, root: Path | str = Path("/"), owner_uid: int = 0,
             owner_gid: int = 0, health: Callable[[], Mapping[str, Any]], run: O.Runner = O.default_runner,
             hold: CompleteHoldObservationV1 | None = None) -> PA.Pr1AcceptanceResultV1:
    """One read-only re-run over current observations. `hold`, when given, is
    the complete observation the hold writer took under its exclusive lock
    (RR-38: the release re-run judges exactly that store)."""
    root = Path(root)
    environment = owner.environment
    host = HI.read_host_inputs(environment=environment, root=root, owner_uid=owner_uid)
    try:
        ledger = observe_copy(root / P.AUTHORITY_LEDGER.lstrip("/"), environment=environment)
    except LedgerError:
        ledger = None
    if hold is None:
        hold = HoldStoreV1(environment=environment, root=root, owner_uid=owner_uid, owner_gid=owner_gid).observe()
    current = O.observe_current_blob(root)
    try:
        signer_health = dict(health())
    except (OSError, ValueError):
        signer_health = None
    readiness = None
    if host.registry_root is not None and host.witness_anchor is not None:
        try:
            publication = B.parse_publication_document(owner.k_act_publication_bytes)
        except Exception:  # noqa: BLE001 - malformed owner input fails closed below
            publication = None
        base = WR.WitnessReadinessInputsV1(
            environment=environment, signing_domain=A.OWNER_ACTOR, evidence_type=A.OWNER_MEMORY_OPERATION,
            store=host.store_context(authority_public_keys=HI.authority_public_keys(host)),
            witness_store=observe_witness_state(root / P.WITNESS_STATE.lstrip("/")),
            head_registries=host.registries, ledger_observation=ledger, observed_blob_sha256=current.sha256,
            publication=publication, health=signer_health,
            unit_credentials=O.observe_unit_credentials(root), credential_inventory=O.observe_credential_inventory(root),
            inventory_phase=WR.STEADY, hold_present=None, slot_contract=_slot_contract(owner_uid, owner_gid))
        readiness = SR.SuccessorReadinessInputsV1(base, hold.observation, owner.k_act_publication_bytes, None,
                                                  owner.release_sha, None, SC.custody_profile(environment))
    try:
        witness_publication = B.parse_publication_document(owner.k_wit_publication_bytes)
    except Exception:  # noqa: BLE001
        witness_publication = None
    anchor = None
    raw_anchor = host.documents.get(P.WITNESS_ANCHOR)
    if raw_anchor is not None:
        anchor = WR.parse_document_bytes(raw_anchor)
    inputs = PA.Pr1AcceptanceInputsV1(
        environment=environment, readiness=readiness, release_sha=owner.release_sha,
        installed_release=O.observe_installed_release(root, release_sha=owner.release_sha,
                                                      host_targets=tuple(P.RELEASE_HOST_TARGETS.values())),
        attested_manifest_sha256=owner.attested_manifest_sha256,
        host_targets={target: member for member, target in P.RELEASE_HOST_TARGETS.items()},
        reviewed_runtime_digests=owner.reviewed_runtime_digests, current_first_preflight=owner.first_preflight_current,
        current_now=current, pinned_current_sha256=owner.pinned_current_sha256,
        unit_states=O.observe_units(UNITS, run=run, root=root), witness_publication=witness_publication,
        witness_anchor=anchor, proofs=owner.proofs, activation=owner.activation,
        snapshot_inventory=owner.snapshot_inventory, offhost_material=owner.offhost_material,
        profile=SC.custody_profile(environment), witness_profile=B.witness_profile(environment),
        owner_ids=(owner_uid, owner_gid))
    return PA.evaluate_pr1_acceptance(inputs, mode=mode)


def _slot_contract(owner_uid: int, owner_gid: int) -> WR.CredentialSlotContractV1:
    """The fixed DEV_SYNTHETIC slot contract (root-owned; `owner_*` are TEST seams)."""
    return dataclasses.replace(WR.DEV_SYNTHETIC_SLOT_CONTRACT, owner_uid=owner_uid, owner_gid=owner_gid)


SUCCESSOR_INPUT_TYPE = "LILITH_SUCCESSOR_RELEASE_INPUTS"
SUCCESSOR_INPUT_FIELDS = frozenset({"inputType", "schemaVersion", "environment", "publication", "ceremonyRecord",
                                    "ceremonyRegister", "reviewedReleaseSha", "inventoryPhase"})


def successor_readiness(document: Any, *, hold: CompleteHoldObservationV1,
                        health: Callable[[], Mapping[str, Any]], root: Path | str = Path("/"),
                        owner_uid: int = 0, owner_gid: int = 0) -> SR.SuccessorReadinessResultV1:
    """HOLD_RELEASE_ELIGIBILITY re-run for a successor / maintenance / custody-
    debt ceremony (B1b-3e rehearsal; never run in PR-1), over exactly the
    hold store the writer observed under its lock."""
    doc = _exact(document, SUCCESSOR_INPUT_FIELDS, "successor input")
    if doc["inputType"] != SUCCESSOR_INPUT_TYPE or doc["schemaVersion"] != 1             or doc["inventoryPhase"] not in WR.INVENTORY_PHASES:
        raise VerifierInputError("successor input type")
    root = Path(root)
    environment = doc["environment"]
    host = HI.read_host_inputs(environment=environment, root=root, owner_uid=owner_uid)
    if host.registry_root is None or host.witness_anchor is None:
        raise VerifierInputError("host inputs incomplete")
    publication_bytes = _b64u(doc["publication"])
    try:
        ledger = observe_copy(root / P.AUTHORITY_LEDGER.lstrip("/"), environment=environment)
    except LedgerError:
        ledger = None
    try:
        signer_health = dict(health())
    except (OSError, ValueError):
        signer_health = None
    current = O.observe_current_blob(root)
    base = WR.WitnessReadinessInputsV1(
        environment=environment, signing_domain=A.OWNER_ACTOR, evidence_type=A.OWNER_MEMORY_OPERATION,
        store=host.store_context(authority_public_keys=HI.authority_public_keys(host)),
        witness_store=observe_witness_state(root / P.WITNESS_STATE.lstrip("/")), head_registries=host.registries,
        ledger_observation=ledger, observed_blob_sha256=current.sha256,
        publication=B.parse_publication_document(publication_bytes), health=signer_health,
        unit_credentials=O.observe_unit_credentials(root), credential_inventory=O.observe_credential_inventory(root),
        inventory_phase=doc["inventoryPhase"], hold_present=None, slot_contract=_slot_contract(owner_uid, owner_gid))
    inputs = SR.SuccessorReadinessInputsV1(base, hold.observation, publication_bytes, doc["ceremonyRecord"],
                                           doc["reviewedReleaseSha"], doc["ceremonyRegister"],
                                           SC.custody_profile(environment))
    return SR.evaluate_successor_readiness(inputs, mode=SR.HOLD_RELEASE_ELIGIBILITY)


def report(result: PA.Pr1AcceptanceResultV1) -> dict[str, Any]:
    return {"mode": result.mode, "status": result.status, "reasons": list(result.reasons),
            "packageDigest": result.package_digest, "package": result.package, "authorityGranted": False}
