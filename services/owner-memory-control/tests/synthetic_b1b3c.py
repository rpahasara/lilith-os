"""TEST_ONLY synthetic fixtures for 15B2b-B1b-3c (recovery epoch / witness).

Everything is in-process or inside a temporary directory:

- epochs E1 (the B1b-3a/B1b-3b epoch), E2, a divergent E2, and E3;
- a TEST_ONLY witness key, distinct from the registry root and from every
  authority key;
- authority registries at E1 and E2, signed by the B1b-3a synthetic root;
- `Host`: the pure authority-side ledger plus its witness, with explicit
  snapshot/restore of either or both (restore = reuse an older value);
- `RecoveryFlow`: the real, unchanged L04 V2 store behind the B1b-3b signer
  and adapter, wrapped by the B1b-3c recovery-bound gate.

No key is read from or written to disk, the environment, or a credential
store. No real owner, memory, registry, witness, or authority exists.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import synthetic_authority as SA
import synthetic_b1b3b as T
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from lilith_authority_signer import synthetic_broker as B
from lilith_authority_signer import synthetic_evidence_ledger as EL
from lilith_authority_signer import synthetic_recovery_ledger as RL
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import l04_v2_adapter as AD
from lilith_owner_memory import recovery_admission as RA
from lilith_owner_memory import recovery_contracts as R

GOLDEN_PATH = Path(__file__).with_name("b1b3c_golden.json")

ENV = "test"
E1 = SA.EPOCH
E2 = A.RecoveryEpochV1(3, SA._label_hex("TEST_ONLY recovery epoch 3"))
E2_FORK = A.RecoveryEpochV1(3, SA._label_hex("TEST_ONLY recovery epoch 3 divergent ceremony"))
E3 = A.RecoveryEpochV1(4, SA._label_hex("TEST_ONLY recovery epoch 4"))
LEP1 = R.ledger_epoch_id(E1, ENV)
LEP2 = R.ledger_epoch_id(E2, ENV)

RECOVERY_AT = "2026-09-26T13:00:00Z"
WITNESS_KEY_ID = "test-only.witness.recovery-1"
TEST_ONLY_WITNESS_SEED = hashlib.sha256(b"TEST_ONLY B1b-3c recovery witness key 1").digest()
TEST_ONLY_ROGUE_WITNESS_SEED = hashlib.sha256(b"TEST_ONLY B1b-3c rogue witness key").digest()
E2_KEY_ID = "actor.b1b3c-broker-e2"
TEST_ONLY_E2_SEED = hashlib.sha256(b"TEST_ONLY B1b-3c broker owner-actor signing key epoch 3").digest()
E2_CHALLENGE_ISSUED = datetime(2026, 9, 26, 13, 30, 0, tzinfo=timezone.utc)


def witness_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(TEST_ONLY_WITNESS_SEED)


def anchor(seed: bytes = TEST_ONLY_WITNESS_SEED, key_id: str = WITNESS_KEY_ID,
           environment: str = ENV) -> R.TrustedWitnessAnchorV1:
    return R.TrustedWitnessAnchorV1.from_dict({
        "schemaVersion": 1, "witnessKeyId": key_id, "environment": environment, "algorithm": "Ed25519",
        "publicKey": T.public_b64(seed)})


def witness_signer(seed: bytes = TEST_ONLY_WITNESS_SEED) -> RL.SyntheticWitnessSignerV1:
    return RL.SyntheticWitnessSignerV1(signing_key=Ed25519PrivateKey.from_private_bytes(seed),
                                       witness_key_id=WITNESS_KEY_ID, environment=ENV)


def privacy(status: str = R.PRIVACY_AT_OR_AFTER_REQUIRED) -> R.PrivacyBoundaryObservationV1:
    return R.PrivacyBoundaryObservationV1(status)


# ------------------------------------------------------------ registries ---

def e1_registry(version: int = SA.REGISTRY_VERSION, **broker: Any) -> dict[str, Any]:
    """The B1b-3b registry at E1 (the B1b-3b broker key is current)."""
    return T.registry(version=version, keys=T.registry_keys(broker=T.broker_key_record(**broker)))


def e2_key_record(**overrides: Any) -> dict[str, Any]:
    value = dict(publicKey=T.public_b64(TEST_ONLY_E2_SEED), createdAt=RECOVERY_AT, notBefore=RECOVERY_AT,
                 recoveryEpoch=E2.to_dict(), registryVersion=4)
    value.update(overrides)
    return SA.key_record(E2_KEY_ID, seed_name="actor.current-2", **value)


def e2_registry(version: int = 4, *, epoch: A.RecoveryEpochV1 = E2, broker: dict[str, Any] | None = None,
                e2_key: dict[str, Any] | None = None, issued_at: str = RECOVERY_AT) -> dict[str, Any]:
    """Recovery to `epoch`: every E1 key that was current is retired at the
    recovery instant (a key belongs to exactly one epoch), and a new broker
    key is published in the new epoch."""
    keys = []
    for record in SA.default_keys():
        if record["retiredAt"] is None and record["revokedAt"] is None:
            record = {**record, "retiredAt": RECOVERY_AT}
        keys.append(record)
    keys.append(broker or T.broker_key_record(retiredAt=RECOVERY_AT))
    # The E2 key's registryVersion is its first publication (4) and never changes.
    keys.append(e2_key or e2_key_record(recoveryEpoch=epoch.to_dict(), registryVersion=min(version, 4)))
    return SA.registry(keys=sorted(keys, key=lambda r: r["keyId"]), registryVersion=version,
                       recoveryEpoch=epoch.to_dict(), issuedAt=issued_at)


def compromised_broker(revoked_at: str = "2026-09-26T13:10:00Z") -> dict[str, Any]:
    return T.broker_key_record(retiredAt=RECOVERY_AT, revokedAt=revoked_at, revocationReason="COMPROMISED",
                               compromisedSince="2026-09-26T12:00:00Z")


# ----------------------------------------------------------------- host ---

def _stamp(n: int) -> str:
    return (datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(label: str) -> str:
    return hashlib.sha256(("TEST_ONLY " + label).encode()).hexdigest()


class Host:
    """One synthetic authority host: the pure ledger, its witness, and the
    registry the broker uses. `snapshot()` / `restore_*()` model backups."""

    def __init__(self, *, registry: dict[str, Any] | None = None, environment: str = ENV,
                 epoch: A.RecoveryEpochV1 = E1, key_ids: tuple[str, ...] = (T.BROKER_KEY_ID,)) -> None:
        self.environment = environment
        self.registry = e1_registry() if registry is None else registry
        self.state = RL.AuthorityLedgerStateV1.genesis(
            environment=environment, recovery_epoch=epoch, policy_version=SA.POLICY,
            registry_version=self.registry["registryVersion"], signing_key_ids=key_ids)
        self.signer = witness_signer()
        self.ticks = 0
        self.witness = self.sign()

    def sign(self) -> dict[str, Any]:
        self.ticks += 1
        self.witness = self.signer.sign_state(self.state, updated_at=_stamp(self.ticks))
        return self.witness

    def witness_view(self) -> R.RecoveryWitnessV1:
        return R.RecoveryWitnessV1.from_verified_dict(self.witness)

    def readiness(self, *, state: Any = "current", witness: Any = "current", registry: Any = "current",
                  privacy_status: str = R.PRIVACY_AT_OR_AFTER_REQUIRED, witness_anchor=None,
                  environment: str | None = None) -> RL.ReadinessResultV1:
        return RL.evaluate_restore_readiness(
            state=self.state if state == "current" else state,
            witness=self.witness if witness == "current" else witness,
            witness_anchor=witness_anchor or anchor(), registry=self.registry if registry == "current" else registry,
            registry_root=SA.trusted_root(), environment=environment or self.environment,
            privacy=privacy(privacy_status))

    def commit(self, transition, *, witness: bool = True):
        """Apply one ledger transition, then update the witness (the witness is
        written after the ledger commit and before the effect is acknowledged)."""
        self.state = transition(self.state)
        if witness:
            self.sign()
        return self.state

    def ready(self) -> RL.ReadinessResultV1:
        result = self.readiness()
        assert result.ready, result
        return result

    # Authority-creating steps each need a fresh RESTORE_READY bound to the state.
    def prepare(self, challenge_id: str, ledger_epoch: str | None = None):
        ready = self.ready()
        return self.commit(lambda s: s.prepare(challenge_id, ledger_epoch or s.ledger_epoch, ready=ready))

    def consume(self, challenge_id: str):
        ready = self.ready()
        return self.commit(lambda s: s.consume(challenge_id, ready=ready))

    def issue(self, challenge_id: str, evidence_id: str | None = None):
        ready = self.ready()
        evidence_id = evidence_id or "aev." + challenge_id
        return self.commit(lambda s: s.issue(challenge_id, evidence_id, digest("evidence " + evidence_id),
                                             ready=ready))

    def reserve(self, evidence_id: str, proposal: str, epoch: A.RecoveryEpochV1 | None = None):
        ready = self.ready()
        return self.commit(lambda s: s.reserve(evidence_id, digest("evidence " + evidence_id),
                                               epoch or s.recovery_epoch, proposal, ready=ready))

    def confirm(self, evidence_id: str, admission: str = "adm.synthetic", revision: str = "rev.synthetic"):
        ready = self.ready()
        return self.commit(lambda s: s.confirm(evidence_id, admission, revision, ready=ready))

    def full_admission(self, challenge_id: str, proposal: str | None = None):
        self.prepare(challenge_id)
        self.consume(challenge_id)
        self.issue(challenge_id)
        self.reserve("aev." + challenge_id, proposal or "prop." + challenge_id)
        return self.confirm("aev." + challenge_id, "adm." + challenge_id, "rev." + challenge_id)

    def publish_registry(self, registry: dict[str, Any], key_ids: tuple[str, ...] | None = None):
        self.registry = registry
        keys = key_ids or tuple(self.state.replayed().signing_key_ids)
        return self.commit(lambda s: s.record_registry(registry["registryVersion"], keys, registry["policyVersion"]))

    def snapshot(self) -> tuple[RL.AuthorityLedgerStateV1, dict[str, Any], dict[str, Any]]:
        return self.state, dict(self.witness), dict(self.registry)

    def recover(self, *, new_random: str = E2.random, registry: dict[str, Any] | None = None,
                reason: str = "LEDGER_RESTORE_DETECTED", crash_after_advance: bool = False) -> dict[str, Any]:
        """The TEST ceremony: advance the ledger, witness the new epoch (point
        of no return), quarantine pre-recovery work, witness again."""
        previous = self.witness_view()
        before = self.state
        # Recovery starts from the journal, never from edited rows.
        self.state = RL.AuthorityLedgerStateV1.from_log(self.state.log)
        registry = e2_registry() if registry is None else registry
        self.state = RL.begin_recovery(self.state, witness=previous, new_random=new_random, registry=registry,
                                       registry_root=SA.trusted_root(), reason=reason)
        self.registry = registry
        self.sign()
        if crash_after_advance:
            return {}
        self.state = RL.quarantine_pre_recovery(self.state)
        self.sign()
        return RL.recovery_transition_record(before, self.state, previous_witness=previous,
                                             new_witness=self.witness_view())


def next_key_record(**overrides: Any) -> dict[str, Any]:
    value = dict(publicKey=T.public_b64(T.TEST_ONLY_NEXT_SEED), createdAt="2026-09-26T12:30:00Z",
                 notBefore="2026-09-26T12:30:00Z", registryVersion=4)
    value.update(overrides)
    return SA.key_record(T.NEXT_KEY_ID, seed_name="actor.current-2", **value)


def rotated_e1_registry(version: int = 4, *, compromised: bool = False) -> dict[str, Any]:
    """Same epoch, next registry version: the B1b-3b broker key is routinely
    retired, or compromised, and a next key is published."""
    broker = (dict(retiredAt="2026-09-26T12:30:00Z", revokedAt="2026-09-26T12:40:00Z",
                   revocationReason="COMPROMISED", compromisedSince="2026-09-26T11:00:00Z")
              if compromised else dict(retiredAt="2026-09-26T12:30:00Z"))
    return T.registry(version=version, issued_at="2026-09-26T12:45:00Z",
                      keys=T.registry_keys(next_key_record(), broker=T.broker_key_record(**broker)))


def tamper_rows(ledger: RL.AuthorityLedgerStateV1, table: str, key: str, **values: Any) -> RL.AuthorityLedgerStateV1:
    """A direct write to the authority DB rows, bypassing the journal."""
    rows = {"challenges": {k: dict(v) for k, v in ledger.rows["challenges"].items()},
            "uses": {k: dict(v) for k, v in ledger.rows["uses"].items()}}
    rows[table][key].update(values)
    return RL.AuthorityLedgerStateV1(ledger.log, rows)


def base_host() -> tuple[Host, tuple]:
    """c1 fully admitted; snapshot S with c2 PREPARED; then c2 consumed and
    its evidence issued (unreserved) after the snapshot."""
    host = Host()
    host.full_admission("c1")
    host.prepare("c2")
    snap = host.snapshot()
    host.consume("c2")
    host.issue("c2")
    return host, snap


def _row(number: int, name: str, result: RL.ReadinessResultV1, *, operation: str | None = None,
         detected: bool = True, unresolved: str | None = None) -> dict[str, Any]:
    return {
        "scenario": number, "name": name, "readiness": result.status, "reason": result.reason,
        "detail": result.detail, "operationRefusal": operation,
        "authorityIssuanceBlocked": (not result.ready) or operation is not None,
        "historicalReadsAllowed": result.facts["historicalReadsAllowed"],
        "detected": detected, "unresolved": unresolved,
        "wholeHostRollbackProtected": result.facts["wholeHostRollbackProtected"],
    }


def _refusal(fn) -> str | None:
    try:
        fn()
    except RL.LedgerRefusal as refused:
        return refused.reason
    return None


def restore_matrix() -> list[dict[str, Any]]:
    """The fifteen deterministic snapshot / restore scenarios (section 13)."""
    rows = []
    host, snap = base_host()
    rows.append(_row(1, "clean-restart-no-restore", host.readiness()))
    rows.append(_row(2, "broker-ledger-restored-witness-current", host.readiness(state=snap[0])))
    rows.append(_row(3, "witness-restored-broker-current", host.readiness(witness=snap[1])))
    rows.append(_row(4, "both-restored-together", host.readiness(state=snap[0], witness=snap[1]), detected=False,
                     unresolved="WHOLE_HOST_OR_WHOLE_DISK_ROLLBACK: a same-host witness rolled back with the "
                                "ledger matches it; needs an off-host or independently monotonic anchor"))

    registry_host = Host()
    before_update = registry_host.snapshot()
    registry_host.publish_registry(e1_registry(4))
    rows.append(_row(5, "old-registry-current-witness", registry_host.readiness(registry=e1_registry(3))))
    rows.append(_row(6, "current-registry-old-ledger", registry_host.readiness(state=before_update[0])))

    reopened = tamper_rows(host.state, "challenges", "c1", state=RL.PREPARED)
    rows.append(_row(7, "consumed-challenge-reopened-by-stale-db", host.readiness(state=reopened)))

    recovered, recovered_snap = base_host()
    pre_recovery_witness = recovered.witness_view()
    pre_recovery_state = recovered.state
    recovered.recover()
    rows.append(_row(8, "prepared-challenge-resurrected-after-recovery",
                     recovered.readiness(state=recovered_snap[0])))

    retired = Host()
    retired.publish_registry(rotated_e1_registry(), key_ids=(T.NEXT_KEY_ID,))
    rows.append(_row(9, "retired-key-resurrected", retired.readiness(registry=e1_registry(3))))
    compromised = Host()
    compromised.publish_registry(rotated_e1_registry(compromised=True), key_ids=(T.NEXT_KEY_ID,))
    rows.append(_row(10, "compromised-key-state-rolled-back", compromised.readiness(registry=e1_registry(3))))

    replay_e1 = _refusal(lambda: recovered.reserve("aev.c2", "prop.replay", epoch=E1))
    rows.append(_row(11, "old-authority-evidence-replayed-after-e2", recovered.readiness(), operation=replay_e1))
    stale_app = _refusal(lambda: host.reserve("aev.c1", "prop.stale-app"))
    rows.append(_row(12, "stale-application-db-current-broker", host.readiness(), operation=stale_app))
    rows.append(_row(13, "stale-broker-current-application-db", host.readiness(state=snap[0])))

    fork = RL.begin_recovery(RL.AuthorityLedgerStateV1.from_log(pre_recovery_state.log),
                             witness=pre_recovery_witness, new_random=E2_FORK.random, registry=e2_registry(epoch=E2_FORK),
                             registry_root=SA.trusted_root(), reason="LEDGER_RESTORE_DETECTED")
    rows.append(_row(14, "duplicate-epoch-counter-different-nonce", recovered.readiness(state=fork)))

    other_env = RL.AuthorityLedgerStateV1.genesis(environment="dev", recovery_epoch=E1, policy_version=SA.POLICY,
                                                  registry_version=3, signing_key_ids=(T.BROKER_KEY_ID,))
    rows.append(_row(15, "same-epoch-object-wrong-environment", host.readiness(state=other_env)))
    return rows


# ---------------------------------------------------------- L04 flow ---

class RecoveryFlow:
    """The B1b-3b V2 path over a real temporary L04, bound to a witness."""

    def __init__(self) -> None:
        self.l04 = T.L04Harness()
        self.host = Host()
        self.registry_doc = self.host.registry
        self.links = AD.AdmissionLinkStoreV1()
        self.ledger = EL.SyntheticEvidenceUseLedgerV1()
        self.clock = T.Clock(T.CHALLENGE_ISSUED + timedelta(seconds=20))
        self.brokers: dict[str, B.SyntheticBrokerAuthorityV1] = {}
        self.configure(E1)

    def close(self) -> None:
        self.l04.close()

    @property
    def witness_doc(self) -> dict[str, Any]:
        return self.host.witness

    def owner_context(self, epoch: A.RecoveryEpochV1):
        return T.owner_context(ledger_epoch=R.ledger_epoch_id(epoch, ENV))

    def configure(self, epoch: A.RecoveryEpochV1) -> None:
        """A broker, adapter, and gate configured for `epoch` (from the witness)."""
        witness = self.host.witness_view()
        owner = self.owner_context(epoch)
        authority = R.witness_authority_context(witness, registry_root=SA.trusted_root(), purpose=A.NEW_ADMISSION)
        if epoch == E1:
            key, config = T.broker_private(), T.signer_config()
        else:
            key = Ed25519PrivateKey.from_private_bytes(TEST_ONLY_E2_SEED)
            config = T.signer_config(key_id=E2_KEY_ID, registry_version=witness.minimum_registry_version,
                                     recovery_epoch=epoch)
        self.epoch = epoch
        self.broker = self.brokers.setdefault(
            epoch.random, B.SyntheticBrokerAuthorityV1(signing_key=key, config=config, owner_context=owner,
                                                       now_fn=self.clock))
        self.adapter = AD.L04V2AdmissionAdapter(
            AD.v2_admission_store(self.l04.store()), owner_context=owner, authority_context=authority,
            registry_provider=lambda: self.registry_doc, link_store=self.links, evidence_use_ledger=self.ledger)
        self.gate = self.make_gate(self.adapter)

    def make_gate(self, adapter: AD.L04V2AdmissionAdapter) -> RA.RecoveryBoundAdmissionGateV1:
        return RA.RecoveryBoundAdmissionGateV1(adapter, witness_provider=lambda: self.witness_doc,
                                               witness_anchor=anchor(), registry_root=SA.trusted_root())

    def recover(self, **kwargs: Any) -> dict[str, Any]:
        ack = self.host.recover(**kwargs)
        self.registry_doc = self.host.registry
        return ack

    def proof(self, action, nonce: str, *, epoch: A.RecoveryEpochV1 | None = None, memory_item_id=None):
        epoch = epoch or self.epoch
        times = {} if epoch == E1 else {"issuedAt": "2026-09-26T13:30:00Z", "expiresAt": "2026-09-26T13:31:00Z"}
        return T.owner_proof(action, "och." + nonce, memory_item_id=memory_item_id,
                             ledgerEpoch=R.ledger_epoch_id(epoch, ENV), **times)

    def signed(self, proof: T.OwnerProof) -> dict[str, Any]:
        base = T.CHALLENGE_ISSUED if self.epoch == E1 else E2_CHALLENGE_ISSUED
        assert self.broker.prepare_challenge(proof.challenge_json).status == B.PREPARED
        self.clock.value = base + timedelta(seconds=20)
        consumed = self.broker.consume_owner_proof(proof.challenge["challengeId"], action=proof.action,
                                                   assertion=proof.assertion, owner_credential=proof.credential)
        assert consumed.status == B.CONSUMED, consumed
        self.clock.value = base + timedelta(seconds=21)
        issued = self.broker.issue_owner_evidence(B.OwnerEvidenceRequestV1(
            proof.challenge["challengeId"], proof.action, proof.assertion, proof.credential))
        assert issued.status == B.ISSUED, issued
        return dict(issued.evidence)

    def broker_for(self, epoch: A.RecoveryEpochV1) -> B.SyntheticBrokerAuthorityV1:
        return self.brokers[epoch.random]

    def request(self, proposal_ref_id: str, proof: T.OwnerProof, evidence: Any, *, epoch=None, **replace: Any):
        broker = self.broker_for(epoch or self.epoch)
        value = dict(proposal_ref_id=proposal_ref_id, evidence=evidence, challenge_json=proof.challenge_json,
                     challenge_record=broker.ledger_record(proof.challenge["challengeId"]),
                     assertion=proof.assertion, owner_credential=proof.credential)
        value.update(replace)
        return AD.V2AdmissionRequestV1(**value)

    def create(self, value: str, nonce: str):
        action, encoded = self.l04.action(value)
        proposal = self.l04.proposal(action, encoded, nonce=nonce)
        proof = self.proof(action, nonce)
        return action, proposal, proof, self.signed(proof)

    def historical(self, proof: T.OwnerProof, evidence: dict[str, Any], proposal: str, *,
                   epoch: A.RecoveryEpochV1, **replace: Any):
        broker = self.broker_for(epoch)
        value = dict(action=proof.action, challenge_json=proof.challenge_json,
                     challenge_record=broker.ledger_record(proof.challenge["challengeId"]),
                     assertion=proof.assertion, owner_credential=proof.credential, registry=self.registry_doc,
                     evidence=evidence, admission=AD.read_l04_admission_view(self.l04.db, proposal, proof.action),
                     link=self.links.get(proposal), evidence_use=self.ledger.lookup(evidence.get("evidenceId")))
        value.update(replace)
        witness = value.pop("witness", self.witness_doc)
        return RA.verify_historical_accepted_memory(witness=witness, witness_anchor=anchor(),
                                                    registry_root=SA.trusted_root(),
                                                    owner_context=self.owner_context(self.epoch), **value)


# ---------------------------------------------------------------- golden ---

def golden_document() -> dict[str, Any]:
    host = Host()
    return {
        "note": "TEST_ONLY synthetic vectors for 15B2b-B1b-3c. No real key, owner, registry, witness, or authority.",
        "domainSeparators": {
            "recoveryEpoch": R.RECOVERY_EPOCH_DOMAIN_SEPARATOR.decode("ascii"),
            "witness": R.WITNESS_DOMAIN_SEPARATOR.decode("ascii"),
            "ledgerHead": RL.LEDGER_HEAD_DOMAIN_SEPARATOR.decode("ascii"),
        },
        "epochs": {
            name: {
                "epoch": epoch.to_dict(),
                "canonical": R.epoch_canonical_bytes(epoch).decode("ascii"),
                "digestTest": R.epoch_digest(epoch, "test"),
                "digestDev": R.epoch_digest(epoch, "dev"),
                "ledgerEpochTest": R.ledger_epoch_id(epoch, "test"),
                "ledgerEpochDev": R.ledger_epoch_id(epoch, "dev"),
            }
            for name, epoch in (("E1", E1), ("E2", E2), ("E2_FORK", E2_FORK), ("E3", E3))
        },
        "witnessPublicKey": T.public_b64(TEST_ONLY_WITNESS_SEED),
        "genesisLedger": {"sequence": host.state.sequence, "head": host.state.head, "log": list(host.state.log)},
        "genesisWitness": host.witness,
        "genesisWitnessDigest": R.witness_digest(host.witness),
        "restoreMatrix": restore_matrix(),
        "fieldSemantics": {
            "ledgerEpoch": "lep1. + sha256(RECOVERY_EPOCH_V1 separator || JCS{counter, environment, random})",
            "recoveryEpoch": "B1b-3a (counter, random), unchanged; equality exact on both parts",
            "witness": "freshness / monotonic-state evidence only; never authority",
            "registryTupleVersion": "memory tuple registry version; owner-bound via the challenge",
            "registryVersion": "authority key registry version; signer-bound via OwnerEvidenceV2, floor from witness",
        },
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-golden"]:
        raise SystemExit("usage: synthetic_b1b3c.py --write-golden")
    with GOLDEN_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(golden_document(), indent=2, sort_keys=True) + "\n")
