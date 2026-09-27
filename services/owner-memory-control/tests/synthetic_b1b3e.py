"""TEST_ONLY synthetic fixtures for 15B2b-B1b-3e (rotation / revocation / restore).

Everything is in-process:

- the B1b-3a synthetic registry root (K-ROOT stand-in) and registry v3 at the
  B1b-3a epoch, with `actor.current-2` as the single current Actor key;
- registry v4: the ordinary rotation `actor.current-2` -> `actor.b1b3e-successor-1`
  (`SUPERSEDED`), plus a same-version fork of v4 and a staged v4 variants;
- registry v5: an epoch advance to epoch 3 with a fresh Actor key;
- a TEST_ONLY RecoveryWitnessV2 key, distinct from the root and every
  authority key;
- the authority recovery ledger (`AuthorityLedgerStateV1`) with seeded
  history: `c1` consumed and its evidence issued, `c2` PREPARED.

History seeding uses a TEST-only readiness token (`seeded_ready`). B1b-3c
readiness is bound to RecoveryWitnessV1; the fixture uses the token only to
build pre-existing ledger history, never to model issuance under V2.

No key is read from or written to disk, the environment, or a credential
store. No real owner, memory, registry, witness, or authority exists.

Run `python synthetic_b1b3e.py --write-golden` only to regenerate the golden
file deliberately; tests compare against the committed file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import synthetic_authority as SA
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_authority_signer import synthetic_recovery_ledger as RL
from lilith_authority_signer import synthetic_witness_v2 as W2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory.contracts import _canonical

GOLDEN_PATH = Path(__file__).with_name("b1b3e_golden.json")

ENV = SA.ENV
POLICY = SA.POLICY
E2 = SA.EPOCH                                   # the B1b-3a epoch (counter 2)
E3 = A.RecoveryEpochV1(3, SA._label_hex("TEST_ONLY B1b-3e recovery epoch 3"))
E3_FORK = A.RecoveryEpochV1(3, SA._label_hex("TEST_ONLY B1b-3e recovery epoch 3 divergent"))
E4_REUSING_E2_RANDOM = A.RecoveryEpochV1(4, E2.random)

PREDECESSOR = "actor.current-2"
SUCCESSOR = "actor.b1b3e-successor-1"
EPOCH3_KEY = "actor.b1b3e-epoch3-1"
T_CUT = "2026-09-27T09:00:00Z"
RECOVERY_AT = "2026-09-27T12:00:00Z"

WITNESS_KEY_ID = "test-only.witness.b1b3e-v2-1"
SEEDS = {
    "witness": hashlib.sha256(b"TEST_ONLY B1b-3e recovery witness v2 key 1").digest(),
    "rogue-witness": hashlib.sha256(b"TEST_ONLY B1b-3e rogue witness v2 key").digest(),
    "successor": hashlib.sha256(b"TEST_ONLY B1b-3e successor actor key 1").digest(),
    "epoch3": hashlib.sha256(b"TEST_ONLY B1b-3e epoch 3 actor key 1").digest(),
    "second-current": hashlib.sha256(b"TEST_ONLY B1b-3e second current actor key").digest(),
    "other": hashlib.sha256(b"TEST_ONLY B1b-3e unrelated actor key").digest(),
}
SUCCESSOR_BLOB_SHA256 = hashlib.sha256(b"TEST_ONLY B1b-3e successor encrypted credential blob").hexdigest()
BASE_TIME = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)


def private(name: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(SEEDS[name])


def raw_public(name: str) -> bytes:
    return private(name).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def public_b64(name: str) -> str:
    return SA.b64(raw_public(name))


def stamp(minutes: int) -> str:
    return (BASE_TIME + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(label: str) -> str:
    return hashlib.sha256(("TEST_ONLY " + label).encode()).hexdigest()


def nonce(label: str) -> str:
    return SA._label_hex("TEST_ONLY B1b-3e nonce " + label)


# ------------------------------------------------------------ registries ---

def _keys(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["keyId"]: dict(record) for record in registry["keys"]}


def successor_record(**overrides: Any) -> dict[str, Any]:
    value = dict(publicKey=public_b64("successor"), createdAt=T_CUT, notBefore=T_CUT, registryVersion=4)
    value.update(overrides)
    return SA.key_record(SUCCESSOR, seed_name=PREDECESSOR, **value)


def registry_from(keys: dict[str, dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return SA.registry(keys=[keys[k] for k in sorted(keys)], **overrides)


def v3() -> dict[str, Any]:
    """The B1b-3a registry: `actor.current-2` is the single current Actor key."""
    return SA.registry()


def v4_keys(*, predecessor_reason: str | None = "SUPERSEDED") -> dict[str, dict[str, Any]]:
    keys = _keys(v3())
    if predecessor_reason is not None:
        keys[PREDECESSOR].update(revokedAt=T_CUT, revocationReason=predecessor_reason)
    keys[SUCCESSOR] = successor_record()
    return keys


def v4(*, issued_at: str = "2026-09-27T09:30:00Z", keys: dict[str, dict[str, Any]] | None = None,
       **overrides: Any) -> dict[str, Any]:
    """Ordinary rotation: predecessor SUPERSEDED at t_cut, successor current."""
    overrides.setdefault("registryVersion", 4)
    return registry_from(v4_keys() if keys is None else keys, issuedAt=issued_at, **overrides)


def v4_fork() -> dict[str, Any]:
    """Same version, different canonical content (a same-version fork)."""
    return v4(issued_at="2026-09-27T09:31:00Z")


def v5(*, epoch: A.RecoveryEpochV1 = E3, version: int = 5) -> dict[str, Any]:
    """Epoch advance to epoch 3: every epoch-2 current key retired at the
    recovery instant (B1b-3c semantics, RR-10a), one fresh epoch-3 Actor key."""
    keys = _keys(v4())
    for record in keys.values():
        if record["retiredAt"] is None and record["revokedAt"] is None:
            record["retiredAt"] = RECOVERY_AT
    keys[EPOCH3_KEY] = SA.key_record(EPOCH3_KEY, seed_name=PREDECESSOR, publicKey=public_b64("epoch3"),
                                     createdAt=RECOVERY_AT, notBefore=RECOVERY_AT, recoveryEpoch=epoch.to_dict(),
                                     registryVersion=version)
    return registry_from(keys, registryVersion=version, recoveryEpoch=epoch.to_dict(),
                         issuedAt="2026-09-27T12:10:00Z")


def root() -> A.TrustedRegistryRootV1:
    return SA.trusted_root()


def anchor(name: str = "witness", key_id: str = WITNESS_KEY_ID) -> R.TrustedWitnessAnchorV1:
    return R.TrustedWitnessAnchorV1.from_dict({"schemaVersion": 1, "witnessKeyId": key_id, "environment": ENV,
                                               "algorithm": "Ed25519", "publicKey": public_b64(name)})


# -------------------------------------------------------- authorizations ---

def head_authorization_unsigned(prior: dict[str, Any], target: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    p, t = RC.registry_head(prior), RC.registry_head(target)
    value = {
        "protocol": RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_PROTOCOL,
        "schemaVersion": RC.AUTHORIZATION_SCHEMA_VERSION,
        "authorizationId": "rhaa.b1b3e-rotation-1",
        "nonce": nonce("head advance 1"),
        "environment": ENV,
        "reason": "SUCCESSOR_ROTATION",
        "recoveryEpoch": E2.to_dict(),
        "priorRegistryVersion": p.version,
        "priorRegistryDigest": p.digest,
        "targetRegistryVersion": t.version,
        "targetRegistryDigest": t.digest,
        "registryRootKeyId": SA.ROOT_KEY_ID,
        "issuedAt": "2026-09-27T07:00:00Z",
        "notAfter": "2026-09-28T07:00:00Z",
    }
    value.update(overrides)
    return value


def sign(unsigned: dict[str, Any], separator: bytes, signer: str = "root") -> dict[str, Any]:
    """Sign as the B1b-3a synthetic registry root (K-ROOT stand-in)."""
    return {**unsigned, "signature": SA.b64(SA.private(signer).sign(separator + _canonical(unsigned)))}


def head_authorization(prior: dict[str, Any] | None = None, target: dict[str, Any] | None = None, *,
                       signer: str = "root", separator: bytes = RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
                       **overrides: Any) -> dict[str, Any]:
    unsigned = head_authorization_unsigned(prior or v3(), target or v4(), **overrides)
    return sign(unsigned, separator, signer)


def epoch_authorization_unsigned(witness: RC.RecoveryWitnessV2, target: dict[str, Any],
                                 **overrides: Any) -> dict[str, Any]:
    t = RC.registry_head(target)
    value = {
        "protocol": RC.EPOCH_ADVANCE_AUTHORIZATION_PROTOCOL,
        "schemaVersion": RC.AUTHORIZATION_SCHEMA_VERSION,
        "authorizationId": "eaa.b1b3e-recovery-1",
        "nonce": nonce("epoch advance 1"),
        "environment": ENV,
        "reason": "OPERATOR_RECOVERY",
        "priorRecoveryEpoch": witness.current_recovery_epoch.to_dict(),
        "successorRecoveryEpoch": E3.to_dict(),
        "targetRegistryVersion": t.version,
        "targetRegistryDigest": t.digest,
        "expectedPriorWitnessVersion": witness.witness_version,
        "expectedPriorWitnessDigest": witness.digest,
        "registryRootKeyId": SA.ROOT_KEY_ID,
        "issuedAt": "2026-09-27T07:30:00Z",
        "notAfter": "2026-09-28T07:30:00Z",
    }
    value.update(overrides)
    return value


def epoch_authorization(witness: RC.RecoveryWitnessV2, target: dict[str, Any] | None = None, *,
                        signer: str = "root", separator: bytes = RC.EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR,
                        **overrides: Any) -> dict[str, Any]:
    return sign(epoch_authorization_unsigned(witness, target or v5(), **overrides), separator, signer)


# ---------------------------------------------------- publication / health ---

def publication(name: str = "successor", key_id: str = SUCCESSOR, *, blob_sha256: str = SUCCESSOR_BLOB_SHA256,
                environment: str = ENV, public_key_sha256: str | None = None) -> dict[str, Any]:
    """B3, in the exact B1b-3d L2 keygen publication shape."""
    raw = raw_public(name)
    return {
        "publicationType": RC.KEY_PUBLICATION_TYPE,
        "schemaVersion": RC.KEY_PUBLICATION_SCHEMA_VERSION,
        "profile": "DEV_SYNTHETIC",
        "publicVerificationMaterial": {
            "keyId": key_id, "signingDomain": A.OWNER_ACTOR, "evidenceTypes": [A.OWNER_MEMORY_OPERATION],
            "environment": environment, "algorithm": "Ed25519", "publicKey": SA.b64(raw),
            "publicKeySha256": public_key_sha256 or hashlib.sha256(raw).hexdigest(),
        },
        "custodyEvidence": {
            "credentialName": "owner-actor-signing-key",
            "credentialPath": "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred",
            "withKey": "host", "machineId": "0" * 32, "blobByteSize": 128, "blobSha256": blob_sha256,
        },
    }


def health(name: str = "successor", **overrides: Any) -> dict[str, Any]:
    """B4, in the exact B1b-3d L1 `DevAuthoritySignerCoreV1.health()` shape."""
    value = {
        "profile": "DEV_SYNTHETIC", "signingDomain": A.OWNER_ACTOR, "foundation": "B1B3D_L1_SOURCE_FOUNDATION",
        "service": "SERVICE_AVAILABLE", "credential": RC.HEALTH_CREDENTIAL_PRESENT,
        "publicKeySha256": hashlib.sha256(raw_public(name)).hexdigest(), "signing": "SIGNING_NOT_AVAILABLE",
        "readiness": "NOT_READY", "reasons": [],
    }
    value.update(overrides)
    return value


# --------------------------------------------------------------- ledger ---

def seeded_ready(state: RL.AuthorityLedgerStateV1) -> RL.ReadinessResultV1:
    """TEST-only token that lets the fixture seed pre-existing ledger history."""
    return RL.ReadinessResultV1(RL.RESTORE_READY, facts={"ledgerSequence": state.sequence, "ledgerHead": state.head})


def seeded_ledger() -> RL.AuthorityLedgerStateV1:
    state = RL.AuthorityLedgerStateV1.genesis(environment=ENV, recovery_epoch=E2, policy_version=POLICY,
                                              registry_version=3, signing_key_ids=(PREDECESSOR,))
    lep = R.ledger_epoch_id(E2, ENV)
    state = state.prepare("c1", lep, ready=seeded_ready(state))
    state = state.consume("c1", ready=seeded_ready(state))
    state = state.issue("c1", "aev.c1", digest("evidence aev.c1"), ready=seeded_ready(state))
    state = state.prepare("c2", lep, ready=seeded_ready(state))
    return state


def witness_writer(name: str = "witness") -> W2.SyntheticWitnessV2SignerV1:
    return W2.SyntheticWitnessV2SignerV1(signing_key=private(name), witness_key_id=WITNESS_KEY_ID, environment=ENV)


# -------------------------------------------------------------- scenario ---

@dataclass
class Scenario:
    """One synthetic authority host driven through rotation and recovery."""

    ledger: RL.AuthorityLedgerStateV1 = field(default_factory=seeded_ledger)
    writer: W2.SyntheticWitnessV2SignerV1 = field(default_factory=witness_writer)
    ticks: int = 0
    hold_present: bool = False
    owner_intent: bool = False
    publication: dict[str, Any] | None = None
    candidate: dict[str, Any] | None = None
    authorization: dict[str, Any] | None = None
    signer_health: dict[str, Any] | None = None
    observed_blob: str | None = None

    def __post_init__(self) -> None:
        self.registry = v3()
        self.writer.genesis(registry=self.registry, registry_root=root(), ledger=self.ledger, updated_at=self.tick())

    def tick(self) -> str:
        self.ticks += 1
        return stamp(self.ticks)

    @property
    def witness(self) -> RC.RecoveryWitnessV2:
        return RC.RecoveryWitnessV2.from_verified_dict(self.writer.witness)

    def commit(self, transition) -> RL.AuthorityLedgerStateV1:
        self.ledger = transition(self.ledger)
        self.writer.record_ledger_advance(ledger=self.ledger, updated_at=self.tick())
        return self.ledger

    # rotation steps (design §7.4)
    def propose(self) -> None:
        self.owner_intent, self.hold_present = True, True

    def prepare(self) -> None:
        self.publication = publication()

    def authorize(self, candidate: dict[str, Any] | None = None, authorization: dict[str, Any] | None = None) -> None:
        self.candidate = candidate or v4()
        self.authorization = authorization or head_authorization(v3(), self.candidate)

    def publish(self) -> dict[str, Any]:
        signed = self.writer.execute_registry_head_advance(
            authorization=self.authorization, prior_registry=v3(), target_registry=self.candidate,
            registry_root=root(), updated_at=self.tick())
        self.registry = self.candidate
        return signed

    def activate(self) -> None:
        self.observed_blob = SUCCESSOR_BLOB_SHA256  # root-observed hash of the unit-slot blob (B2)
        self.signer_health = health()
        self.commit(lambda s: s.record_registry(self.candidate["registryVersion"], (SUCCESSOR,), POLICY))

    def release_hold(self) -> None:
        self.hold_present = False

    def evidence(self, **overrides: Any) -> RC.RotationEvidenceV1:
        value = dict(
            environment=ENV, signing_domain=A.OWNER_ACTOR, evidence_type=A.OWNER_MEMORY_OPERATION,
            predecessor_key_id=PREDECESSOR, successor_key_id=SUCCESSOR, registry_root=root(),
            witness_anchor=anchor(), witness_chain=self.writer.chain, prior_registry=v3(),
            owner_intent_recorded=self.owner_intent, hold_present=self.hold_present,
            successor_publication=self.publication, candidate_registry=self.candidate,
            head_authorization=self.authorization, signer_health=self.signer_health,
            ledger_observation=W2.observe_authority_recovery_ledger(self.ledger),
            observed_blob_sha256=self.observed_blob)
        value.update(overrides)
        return RC.RotationEvidenceV1(**value)

    def to_current(self) -> Scenario:
        self.propose()
        self.prepare()
        self.authorize()
        self.publish()
        self.activate()
        self.release_hold()
        return self

    # recovery (C-4 order)
    def epoch_advance(self, *, target: dict[str, Any] | None = None, authorization: dict[str, Any] | None = None,
                      stop_after: str | None = None) -> dict[str, Any]:
        target = target or v5()
        prior = self.registry
        authorization = authorization or epoch_authorization(self.witness, target)
        # 1. authority recovery ledger adoption (pre-witness, destroy/narrow-only)
        self.ledger = W2.adopt_authorized_epoch(self.ledger, authorization=authorization, witness=self.witness,
                                                target_registry=target, registry_root=root())
        if stop_after == "adoption":
            return {}
        # 2. witness execution over the post-journal head (point of no return)
        executed = self.writer.execute_epoch_advance(authorization=authorization, prior_registry=prior,
                                                     target_registry=target, registry_root=root(),
                                                     ledger=self.ledger, updated_at=self.tick())
        self.registry = target
        if stop_after == "execution":
            return executed
        # 3. quarantine (B1b-3c), then 4. witness again if anything was voided or quarantined
        quarantined = RL.quarantine_pre_recovery(self.ledger)
        if quarantined.sequence != self.ledger.sequence:
            self.commit(lambda _: quarantined)
        return executed

    def snapshot(self) -> tuple[RL.AuthorityLedgerStateV1, tuple[dict[str, Any], ...], dict[str, Any]]:
        return self.ledger, self.writer.chain, copy.deepcopy(self.registry)


def two_current_registry() -> dict[str, Any]:
    keys = v4_keys()
    keys["actor.b1b3e-second-current"] = SA.key_record(
        "actor.b1b3e-second-current", seed_name=PREDECESSOR, publicKey=public_b64("second-current"),
        createdAt=T_CUT, notBefore=T_CUT, registryVersion=4)
    return v4(keys=keys)


# ---------------------------------------------------------------- golden ---

def golden_document() -> dict[str, Any]:
    scenario = Scenario().to_current()
    rotation = RC.evaluate_rotation(scenario.evidence())
    rotation_chain = scenario.writer.chain
    head_auth = scenario.authorization
    epoch_auth = epoch_authorization(scenario.witness)
    scenario.epoch_advance(authorization=epoch_auth)
    ledger_ops = [op["op"] for op in scenario.ledger.log]
    return {
        "note": "TEST_ONLY synthetic vectors for 15B2b-B1b-3e. No real key, owner, registry, witness, or authority.",
        "domainSeparators": {
            "epochAdvanceAuthorization": RC.EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR.decode("ascii"),
            "registryHeadAdvanceAuthorization": RC.REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR.decode("ascii"),
            "recoveryWitnessV2": RC.WITNESS_V2_DOMAIN_SEPARATOR.decode("ascii"),
        },
        "registryDigestDefinition": "sha256(LILITH_AUTHORITY_REGISTRY_V1\\0 || JCS(all registry fields except signature))",
        "registryDigests": {"v3": RC.registry_digest(v3()), "v4": RC.registry_digest(v4()),
                            "v4Fork": RC.registry_digest(v4_fork()), "v5": RC.registry_digest(v5())},
        "publicKeys": {"root": SA.public_b64("root"), "witnessV2": public_b64("witness"),
                       "successor": public_b64("successor"), "epoch3": public_b64("epoch3")},
        "registryV4": v4(),
        "registryV5": v5(),
        "registryHeadAdvanceAuthorization": head_auth,
        "registryHeadAdvanceAuthorizationSigningDigest": hashlib.sha256(
            RC.registry_head_advance_authorization_signing_bytes(
                {k: v for k, v in head_auth.items() if k != "signature"})).hexdigest(),
        "epochAdvanceAuthorization": epoch_auth,
        "epochAdvanceAuthorizationSigningDigest": hashlib.sha256(
            RC.epoch_advance_authorization_signing_bytes(
                {k: v for k, v in epoch_auth.items() if k != "signature"})).hexdigest(),
        "successorPublication": publication(),
        "rotationWitnessChain": list(rotation_chain),
        "rotationOutcome": {"state": rotation.state, "issuanceReady": rotation.issuance_ready,
                            "predecessorState": rotation.facts["predecessorState"]},
        "recoveryWitnessChain": list(scenario.writer.chain),
        "authorityRecoveryLedgerOps": ledger_ops,
        "authorityRecoveryLedgerHead": scenario.ledger.head,
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-golden"]:
        raise SystemExit("usage: synthetic_b1b3e.py --write-golden")
    with GOLDEN_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(golden_document(), indent=2, sort_keys=True) + "\n")
