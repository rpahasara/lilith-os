#!/usr/bin/env python3
"""First Memory DEV host: one owner-run runtime connection from a conversation turn to canonical L04 and back.

A narrow, separate runtime (never the `/os/conversation` relay, never Hermes, never the Next.js UI). It composes the
accepted `first_memory_conversation.FirstMemoryConversationV1` with real DEV components only:

- the ONE authoritative Privacy DB (F9c2 `f9-drill/privacy_governance.f9drill.db`) behind the current-boot
  `PrivacyFreshnessGate` (`PrivacyBindingV1`: the stale Core API path, a changed boot, an older store or a pending
  FORGET refuse explicitly);
- the F9c2 cognitive (L04) DB with the durable admission link (`first_memory_l04_migration.py`);
- the governed project-codename tuple (`GOVERNED_TUPLE`; never the suppressed First Interaction identity) and the
  server-owned canonical config (`lilith_memory.config.load`): memory creation stays DISABLED until the owner sets
  `canonicalLtmEnabled` and the codename capability in that root-owned file;
- the root-installed owner registration (`/etc/lilith-owner-proof-dev/owner-registration.json`) for the owner
  principal, RP, settings and registered PUBLIC credentials;
- the installed K-ROOT trust anchor and registry (`/etc/lilith-authority-dev`) for the L04 V2 authority contexts;
- the real authority signer over its root owner socket (`lilith_authority_root.clients`): governed
  `ISSUE_OWNER_EVIDENCE` and the evidence-use transport, each write with the complete root hold-store snapshot.

Identity: started by root (the owner's host-root ceremony), it immediately runs with the L04 / Privacy owner's
effective uid (`lilith`) and regains uid 0 only for the signer socket exchange and the root hold-store read
(`RootPrivilegeV1`). Every database file it touches is therefore written as `lilith`.

Closed forms (one turn per invocation; text on stdin, one JSON object per line on stdout):

    remember <session>    stdin: the utterance, then (after the printed offer) the owner's assertion JSON
    recall   <session>    stdin: the utterance

Nothing here signs, holds a key, chooses a signed digest, or reads a private key. A refusal is explicit.

    owner-run host != authority;  admitted != true;  recall reads canonical storage only
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional, Protocol

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", ROOT / "services/authority-dev",
              ROOT / "services/recovery-witness"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from lilith_authority_dev import profile as SIGNER_PROFILE  # noqa: E402
from lilith_authority_dev import protocol as AP  # noqa: E402
from lilith_authority_host import inputs as HI  # noqa: E402
from lilith_memory import canonical_authority as CA  # noqa: E402
from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import canonical_store  # noqa: E402
from lilith_memory import config as CONFIG  # noqa: E402
from lilith_memory import learning_v2  # noqa: E402
from lilith_memory import memory_v2  # noqa: E402
from lilith_memory import owner_proof as OP  # noqa: E402
from lilith_memory import privacy_freshness as F  # noqa: E402
from lilith_memory import privacy_governance as PG  # noqa: E402
from lilith_owner_memory import accepted_read_v2 as AR  # noqa: E402
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import contracts as K  # noqa: E402
from lilith_owner_memory import first_memory_conversation as FMC  # noqa: E402
from lilith_owner_memory import l04_v2_adapter as AD  # noqa: E402
from lilith_owner_memory import recovery_contracts as R  # noqa: E402

ENVIRONMENT = "dev"
SERVICE_USER = "lilith"
DRILL = Path("/home/lilith/.hermes/lilith-os-dev/f9-drill")
# The governed DEV_SYNTHETIC project-codename tuple: the one identity the signer, L04 and the accepted read compose.
GOVERNED_TUPLE = memory_v2.MemoryTuplePolicyV1(
    memory_class="SYNTHETIC_PROJECT_CODENAME_FACT", subject_namespace="project.synthetic", subject_key="codename",
    value_schema=learning_v2.VALUE_SCHEMA, capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
    read_allowed=True, write_allowed=True)


@dataclass(frozen=True)
class HostPathsV1:
    """Every fixed path. The defaults are DEV; TEST passes temporary ones (and the matching stale/authoritative)."""

    privacy_db: Path = FMC.AUTHORITATIVE_PRIVACY_DB
    authoritative_privacy_db: Path = FMC.AUTHORITATIVE_PRIVACY_DB    # PrivacyBindingV1 refuses any other DB
    stale_privacy_db: Path = FMC.STALE_PRIVACY_DB
    cognitive_db: Path = DRILL / "cognitive_memory.f9drill.db"
    actor_secret: Path = DRILL / "actor-authority.f9drill.key"
    privacy_secret: Path = DRILL / "privacy-authority.f9drill.key"
    canonical_config: Path = Path("/etc/lilith-first-memory-dev/canonical-config.json")
    host_root: Path = Path("/")          # where /etc/lilith-authority-dev and /etc/lilith-owner-proof-dev live
    host_owner_uid: int = 0


DEV_PATHS = HostPathsV1()


class HostRefused(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise HostRefused(code)


# ------------------------------------------------------------------------------------------------- identity ---

class RootPrivilegeV1:
    """Run as the L04 / Privacy owner; regain uid 0 only around a signer or hold-store exchange (Linux)."""

    def __init__(self, user: str = SERVICE_USER):
        import pwd

        entry = pwd.getpwnam(user)
        self._uid, self._gid = entry.pw_uid, entry.pw_gid
        _need(os.getuid() == 0, "HOST_MUST_BE_STARTED_BY_ROOT")
        os.setgroups([])
        os.setegid(self._gid)
        os.seteuid(self._uid)

    @contextlib.contextmanager
    def as_root(self) -> Iterator[None]:
        os.seteuid(0)
        os.setegid(0)
        try:
            yield
        finally:
            os.setegid(self._gid)
            os.seteuid(self._uid)


class NoPrivilegeV1:
    """TEST seam: the same calls, no identity change."""

    @contextlib.contextmanager
    def as_root(self) -> Iterator[None]:
        yield


# ------------------------------------------------------------------------------------------------- signer ---

class SignerTransportV1(Protocol):
    def hold_snapshot(self) -> dict[str, Any]: ...

    def issue(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def use(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class RootSignerTransportV1:
    """The real signer owner socket and root hold store, reached only with uid 0."""

    def __init__(self, privilege: Any):
        self._privilege = privilege

    def hold_snapshot(self) -> dict[str, Any]:
        from lilith_authority_root.hold_store import HoldStoreV1

        with self._privilege.as_root():
            return dict(HoldStoreV1(environment=ENVIRONMENT).observe().snapshot)

    def issue(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        from lilith_authority_root import clients

        with self._privilege.as_root():
            return clients.signer_issue(payload)

    def use(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        from lilith_authority_root import clients

        with self._privilege.as_root():
            return clients.signer_use(operation, payload)


def action_dict(action: C.FrozenMemoryActionV1) -> dict[str, Any]:
    return {"schemaVersion": action.schema_version, "actorRefId": action.actor_ref_id, "operation": action.operation,
            "memoryClass": action.memory_class, "subjectNamespace": action.subject_namespace,
            "subjectKey": action.subject_key, "valueSchema": action.value_schema,
            "payloadDigest": action.payload_digest, "expectedActiveRevisionId": action.expected_active_revision_id,
            "restoreRevisionId": action.restore_revision_id, "purpose": action.purpose}


class SignerIssuerV1:
    """`first_memory_conversation.OwnerEvidenceIssuerV1` on the governed signer: it journals PREPARE/CONSUME/ISSUE
    itself at issue time (single use), so `prepare` only keeps the exact challenge for the issue request."""

    def __init__(self, transport: SignerTransportV1):
        self._transport = transport
        self._challenges: dict[str, dict[str, Any]] = {}

    def prepare(self, challenge_json: bytes) -> None:
        challenge = json.loads(challenge_json)
        self._challenges[challenge["challengeId"]] = challenge

    def issue(self, challenge_id: str, action: C.FrozenMemoryActionV1, assertion: Mapping[str, Any],
              credential: Mapping[str, Any]) -> FMC.IssuedEvidenceV1:
        challenge = self._challenges.pop(challenge_id, None)
        if challenge is None:
            raise FMC.FirstMemoryRefused("CHALLENGE_NOT_PREPARED")
        try:
            result = self._transport.issue({
                "challengeId": challenge_id, "action": action_dict(action), "assertion": dict(assertion),
                "ownerCredential": dict(credential), "challenge": challenge,
                "holdStore": self._transport.hold_snapshot()})
        except (OSError, ValueError) as exc:
            raise FMC.FirstMemoryRefused("SIGNER_UNREACHABLE:" + type(exc).__name__) from exc
        if not isinstance(result, Mapping) or result.get("status") != "ISSUED":
            value = result if isinstance(result, Mapping) else {}
            reason = str(value.get("reason") or value.get("status") or "SIGNER_REFUSED")
            detail = value.get("detail")                                    # a closed reason code, never a value
            raise FMC.FirstMemoryRefused(reason if not isinstance(detail, str) else f"{reason}:{detail}")
        return FMC.IssuedEvidenceV1(dict(result["evidence"]), dict(result["challengeRecord"]))


@dataclass(frozen=True)
class UseResultV1:
    status: str
    reason: Optional[str] = None
    record: Optional[Mapping[str, Any]] = None


class SignerEvidenceUseLedgerV1:
    """The authority-side evidence-use ledger the L04 V2 adapter and accepted read need (reserve, confirm, abandon,
    lookup), served by the signer's durable, witness-backed ledger."""

    def __init__(self, transport: SignerTransportV1):
        self._transport = transport

    def _write(self, operation: str, expected: str, **fields: Any) -> UseResultV1:
        try:
            result = self._transport.use(operation, {**fields, "holdStore": self._transport.hold_snapshot()})
        except (OSError, ValueError) as exc:
            return UseResultV1("REFUSED", "SIGNER_UNREACHABLE:" + type(exc).__name__)
        if not isinstance(result, Mapping) or result.get("status") != expected:
            return UseResultV1("REFUSED", str((result or {}).get("reason") or (result or {}).get("status")))
        return UseResultV1(expected, None, result.get("record"))

    def reserve(self, *, evidence_id: str, evidence_digest: str, challenge_id: str, proposal_ref_id: str,
                action_digest: str) -> UseResultV1:
        return self._write(AP.RESERVE_EVIDENCE_USE, "RESERVED", evidenceId=evidence_id, evidenceDigest=evidence_digest,
                           challengeId=challenge_id, proposalRefId=proposal_ref_id, actionDigest=action_digest)

    def confirm(self, *, evidence_id: str, proposal_ref_id: str, admission_id: str, revision_id: str) -> UseResultV1:
        return self._write(AP.CONFIRM_EVIDENCE_USE, "CONSUMED", evidenceId=evidence_id, proposalRefId=proposal_ref_id,
                           admissionId=admission_id, revisionId=revision_id)

    def abandon(self, *, evidence_id: str, proposal_ref_id: str) -> UseResultV1:
        return self._write(AP.ABANDON_EVIDENCE_USE, "ABANDONED", evidenceId=evidence_id, proposalRefId=proposal_ref_id)

    def lookup(self, evidence_id: Any) -> Mapping[str, Any] | None:
        if not isinstance(evidence_id, str):
            return None
        try:
            result = self._transport.use(AP.LOOKUP_EVIDENCE_USE, {"evidenceId": evidence_id})
        except (OSError, ValueError):
            return None                                                     # fail closed: no use record
        if not isinstance(result, Mapping) or result.get("status") != "OK" or result.get("use") is None:
            return None
        return dict(result["use"])


# --------------------------------------------------------------------------------------------- composition ---

@dataclass(frozen=True)
class ComposedV1:
    conversation: FMC.FirstMemoryConversationV1
    creation_enabled: bool                                 # the root-owned canonical config, read for this turn
    registered_credentials: tuple[Mapping[str, Any], ...]  # the registered owner PUBLIC credentials


class FirstMemoryDevHostV1:
    """Builds a FRESH composition per `compose()` from fixed inputs; holds no memory or session state itself."""

    def __init__(self, *, transport: SignerTransportV1, paths: HostPathsV1 = DEV_PATHS,
                 freshness: Optional[F.PrivacyFreshnessGate] = None,
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._transport, self._paths, self._freshness, self._now = transport, paths, freshness, now_fn

    # inputs, re-read per composition ------------------------------------------------------------------------

    def _registration(self) -> HI.OwnerRegistrationV1:
        registration, reason = HI.read_owner_registration(environment=ENVIRONMENT, root=self._paths.host_root,
                                                          owner_uid=self._paths.host_owner_uid)
        _need(registration is not None, str(reason))
        return registration

    def _authority(self) -> tuple[A.TrustedRegistryRootV1, dict[str, Any], A.RecoveryEpochV1]:
        inputs = HI.read_host_inputs(environment=ENVIRONMENT, root=self._paths.host_root,
                                     owner_uid=self._paths.host_owner_uid)
        _need(inputs.registry_root is not None and inputs.registries, "AUTHORITY_INPUTS_INCOMPLETE")
        head = max(inputs.registries, key=lambda registry: registry["registryVersion"])
        return inputs.registry_root, head, A.RecoveryEpochV1.from_dict(head["recoveryEpoch"])

    def _config(self) -> CONFIG.RuntimeConfig:
        return CONFIG.load(self._paths.canonical_config)

    def compose(self) -> ComposedV1:
        paths = self._paths
        _need(paths.cognitive_db.is_file(), "COGNITIVE_DB_UNAVAILABLE")
        registration = self._registration()
        registry_root, head, epoch = self._authority()
        settings = self._config()
        actor = CA.LocalOwnerAuthority(paths.cognitive_db, paths.actor_secret.read_bytes())
        privacy_store = PG.PrivacyGovernanceStore(paths.privacy_db, paths.privacy_secret.read_bytes(), actor)
        binding = FMC.PrivacyBindingV1(paths.privacy_db, privacy_store, paths.cognitive_db,
                                       authoritative=paths.authoritative_privacy_db, stale=paths.stale_privacy_db,
                                       freshness=self._freshness)
        capabilities = frozenset({GOVERNED_TUPLE.capability}) & settings.active_capabilities
        policy = CA.MemoryPolicyStore(paths.cognitive_db, actor, active_capabilities=capabilities)
        consent = CA.ConsentStore(paths.cognitive_db, actor, policy_store=policy)
        rollback = CA.RollbackAuthority(paths.cognitive_db, actor, consent)
        learning = learning_v2.LearningV2Store(
            paths.cognitive_db, privacy_hold_resolver=binding.resolver,
            containment_ready=lambda: settings.canonical_ltm_config_valid, actor_authority=actor,
            policy_store=policy, consent_store=consent)
        tuples = memory_v2.CanonicalTupleRegistry((GOVERNED_TUPLE,))
        links = AD.L04AdmissionLinkStoreV1(paths.cognitive_db)
        uses = SignerEvidenceUseLedgerV1(self._transport)
        ledger_epoch = R.ledger_epoch_id(epoch, ENVIRONMENT)
        owner_context = K.AcceptanceContextV1(
            deployment_environment=ENVIRONMENT, authority_domain=SIGNER_PROFILE.DEV_AUTHORITY_DOMAIN,
            logical_owner_id=SIGNER_PROFILE.DEV_LOGICAL_OWNER, owner_principal=registration.owner_principal,
            rp_id=registration.rp_id, origin=registration.origin, policy_version=SIGNER_PROFILE.DEV_POLICY_VERSION,
            registry_tuple_version=registration.registry_tuple_version, ledger_epoch=ledger_epoch,
            privacy_notice_version=registration.privacy_notice_version,
            broker_releases=frozenset(registration.broker_releases))

        def authority_context(purpose: str) -> A.AuthorityVerificationContextV1:
            return A.AuthorityVerificationContextV1(
                environment=ENVIRONMENT, purpose=purpose, registry_root=registry_root,
                trusted_minimum_registry_version=head["registryVersion"], expected_recovery_epoch=epoch,
                policy_version=SIGNER_PROFILE.DEV_POLICY_VERSION)

        def store(**overrides: Any) -> canonical_store.CanonicalMemoryStoreV2:
            values = dict(
                enabled_provider=lambda: settings.canonical_ltm_enabled,
                capability_provider=settings.capability_active,
                family_registry=memory_v2.ProposalFamilyRegistry(
                    (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY)),
                memory_registry=tuples, containment_ready=lambda identity: identity == GOVERNED_TUPLE.identity,
                actor_authority=actor, policy_store=policy, consent_store=consent, rollback_authority=rollback,
                privacy_hold_resolver=binding.resolver)
            values.update(overrides)
            return canonical_store.CanonicalMemoryStoreV2(paths.cognitive_db, learning, **values)

        def adapter() -> AD.L04V2AdmissionAdapter:
            return AD.L04V2AdmissionAdapter(
                AD.v2_admission_store(store()), owner_context=owner_context,
                authority_context=authority_context(A.NEW_ADMISSION), registry_provider=lambda: head,
                link_store=links, evidence_use_ledger=uses)

        def reader() -> AR.AcceptedMemoryReadFacadeV2:
            facade = memory_v2.CanonicalMemoryReadFacade(
                store(), registry=tuples, consent_store=consent, privacy_hold_resolver=binding.resolver,
                actor_resolver=lambda candidate: candidate == actor.ACTOR)
            return AR.AcceptedMemoryReadFacadeV2(
                facade, store(), owner_context=owner_context,
                authority_context=authority_context(A.HISTORICAL_VERIFICATION), registry_provider=lambda: head,
                challenge_record_provider=links.challenge_record, link_store=links, evidence_use_ledger=uses)

        challenge_context = {
            "protocol": OP.PROTOCOL, "schemaVersion": K.CHALLENGE_V2_SCHEMA_VERSION,
            "ownerPrincipal": registration.owner_principal,
            "privacyNoticeVersion": registration.privacy_notice_version, "rpId": registration.rp_id,
            "deploymentEnvironment": ENVIRONMENT, "authorityDomain": SIGNER_PROFILE.DEV_AUTHORITY_DOMAIN,
            "logicalOwnerId": SIGNER_PROFILE.DEV_LOGICAL_OWNER, "policyVersion": SIGNER_PROFILE.DEV_POLICY_VERSION,
            "registryTupleVersion": registration.registry_tuple_version, "ledgerEpoch": ledger_epoch}
        conversation = FMC.FirstMemoryConversationV1(
            privacy=binding, l04=FMC.L04ComponentsV1(actor, policy, consent, learning), adapter=adapter,
            reader=reader, issuer=SignerIssuerV1(self._transport), tuple_policy=GOVERNED_TUPLE,
            challenge_context=challenge_context, now_fn=self._now)
        return ComposedV1(conversation, settings.canonical_ltm_enabled
                          and settings.capability_active(GOVERNED_TUPLE.capability), tuple(registration.credentials))


# ---------------------------------------------------------------------------------------------- the turn ---

def remember(host: FirstMemoryDevHostV1, session: str, text: str,
             owner_assertion: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
    """One "remember my project codename is X" turn: offer -> the owner's assertion over the printed challenge ->
    governed admission. Memory creation stays refused while the canonical config does not enable it."""
    composed = host.compose()
    _need(composed.creation_enabled, "MEMORY_CREATION_NOT_AUTHORIZED")
    conversation = composed.conversation
    offer = conversation.offer(session, text)
    if offer.status != FMC.OFFERED:
        return {"status": offer.status}
    answer = owner_assertion({"status": offer.status, "offerId": offer.offer_id, "codename": offer.codename,
                              "webauthnChallenge": offer.webauthn_challenge.hex()})
    _need(isinstance(answer, Mapping) and set(answer) == {"assertion", "credentialRecordId"}, "OWNER_ANSWER_INVALID")
    credential = next((c for c in composed.registered_credentials
                       if c["recordId"] == answer["credentialRecordId"]), None)
    _need(credential is not None, "OWNER_CREDENTIAL_NOT_REGISTERED")
    result = conversation.consent(offer.offer_id, session, dict(answer["assertion"]), credential)
    return {"status": result.status, "reason": result.reason, "proposalRefId": result.proposal_ref_id}


def recall(host: FirstMemoryDevHostV1, session: str, text: str) -> dict[str, Any]:
    """One "what is my project codename" turn on a fresh composition: canonical storage only."""
    result = host.compose().conversation.recall(session, text)
    return {"status": result.status, "codename": result.codename, "reason": result.reason}


def main(argv: list[str]) -> int:
    def emit(value: Mapping[str, Any]) -> None:
        sys.stdout.write(json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    try:
        if len(argv) != 2 or argv[0] not in ("remember", "recall"):
            raise HostRefused("USAGE")
        privilege = RootPrivilegeV1()
        host = FirstMemoryDevHostV1(transport=RootSignerTransportV1(privilege))
        text = sys.stdin.readline().rstrip("\n")
        if argv[0] == "recall":
            emit(recall(host, argv[1], text))
            return 0

        def owner_assertion(offer: Mapping[str, Any]) -> Mapping[str, Any]:
            emit(offer)
            return json.loads(sys.stdin.readline())

        emit(remember(host, argv[1], text, owner_assertion))
        return 0
    except (HostRefused, FMC.FirstMemoryRefused) as exc:
        print(f"first-memory-dev-host: REFUSED {exc.code}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"first-memory-dev-host: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
