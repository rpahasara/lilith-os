"""15B2b-B1b-3e PR-3 P3-2: offline owner freshness workstation tooling.

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md (§22–§24).

A thin filesystem and CLI layer over the pure `owner_freshness` contract, for
the owner's workstation. It reads only the paths it is given. It has no
network, DEV, cloud, Git, or credential dependency. It holds no key and signs
nothing.

    python -m lilith_owner_memory.owner_freshness_tool <command> ...

Read-only: `inspect-chain`, `verify-replica`, `compare-replicas`, `classify`, `location-check`,
`check-independence`. Storage setup (P3-3): `probe-storage` (temporary probe files only),
`init-real-replica` (gated; creates an EMPTY replica).
Candidate producers (write only a new candidate file, never a record):
`propose-genesis`, `propose-accept`, `propose-reject`.
The one record writer: `append` (owner ceremony; §24 of the record).

    candidate generated != record accepted
    owner confirmation != authority beyond the owner-only replica it lands in (D1, D2, D6)
    file mtime / Git metadata != freshness

`append` requires the owner to repeat the candidate's record digest
(`--confirm-digest`). It re-derives the candidate from the replicas, the
authentic chain, and the genesis pin, and writes only a byte-identical
record. So a stale, conflicting, non-authentic, rejected-lineage, or
hand-edited candidate can never be written, and an `AHEAD_UNACCEPTED` world
is never accepted without that explicit owner step. The confirmation
protects against mistakes, not against a hostile process running as the
owner. That protection is custody (D6): replicas live where no agent or
automation can write.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from lilith_memory.owner_proof import OwnerProofError

from . import authority_contracts as A
from . import create_only_publish as COP
from . import owner_acceptance as OA
from . import owner_freshness as OF
from . import recovery_contracts as R
from . import rotation_contracts as RC
from . import witness_readiness as WR
from .contracts import ContractViolation

# ------------------------------------------------------------- file formats ---

REPLICA_TYPE = "LILITH_OWNER_FRESHNESS_REPLICA"
REPLICA_FIELDS = frozenset({"replicaType", "schemaVersion", "replicaId", "environment", "authorityProfile"})
MANIFEST = "REPLICA.json"
RECORDS = "records"
RECORD_NAME = re.compile(r"(\d{6})-([0-9a-f]{64})\.json\Z")
PENDING_PREFIX = ".pending-"
REPLICA_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
MAX_RECORD_VERSION = 999_999

CANDIDATE_TYPE = "LILITH_OWNER_FRESHNESS_CANDIDATE"
CANDIDATE_FIELDS = frozenset({"candidateType", "schemaVersion", "accepted", "decision", "recordDigest", "record"})
TRUST_TYPE = "LILITH_OWNER_FRESHNESS_TRUST_INPUTS"
TRUST_FIELDS = frozenset({"trustType", "schemaVersion", "environment", "witnessAnchor", "registryRoot", "registries"})

MAX_INPUT_BYTES = 8 << 20
MINIMUM_REPLICAS = 2          # D6


class ToolRefusal(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _refuse(reason: str, detail: str | None = None) -> ToolRefusal:
    return ToolRefusal(reason, detail)


def _read_regular(path: Path, reason: str) -> bytes:
    """Read one regular, non-symlink file. The mtime is never consulted."""
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise _refuse(reason, f"MISSING:{path.name}") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
        raise _refuse(reason, f"NOT_A_REGULAR_FILE:{path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    try:
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _input_json(path: Path, reason: str) -> Any:
    """An owner-supplied input: any strict JSON (no duplicate keys)."""
    try:
        return WR._json(_read_regular(Path(path), reason))
    except OwnerProofError as exc:
        raise _refuse(reason, "MALFORMED_JSON") from exc


def _canonical_json(raw: bytes, reason: str) -> dict[str, Any]:
    try:
        return OF.parse_record_bytes(raw)
    except OwnerProofError as exc:
        raise _refuse(reason, "NOT_CANONICAL") from exc


# ----------------------------------------------------------------- replicas ---

@dataclass(frozen=True)
class ReplicaV1:
    path: Path
    replica_id: str
    environment: str
    authority_profile: str
    records: tuple[dict[str, Any], ...]

    @property
    def digests(self) -> tuple[str, ...]:
        return tuple(OF.record_digest(r) for r in self.records)


def _manifest(replica_id: str, environment: str, profile: str) -> dict[str, Any]:
    return {"replicaType": REPLICA_TYPE, "schemaVersion": 1, "replicaId": replica_id,
            "environment": environment, "authorityProfile": profile}


def _fsync_directory(path: Path) -> str:
    """POSIX directories can be fsynced; Windows cannot (recorded, P3-3 review item)."""
    if os.name != "posix":
        return "UNSUPPORTED_PLATFORM"
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return "PERFORMED"


def _write_new_file(path: Path, data: bytes) -> None:
    """Create-only write with a file fsync. Never replaces anything."""
    COP.write_new_file(path, data)


def init_replica(path: Any, *, replica_id: str, environment: str, authority_profile: str) -> dict[str, Any]:
    """Create an empty replica in a directory that does not exist yet.

    It never adopts, cleans, or reuses an existing directory. A replica holds
    no record until the owner appends record 1 (after the V2 genesis commit).
    """
    path = Path(path)
    if not (isinstance(replica_id, str) and REPLICA_ID.fullmatch(replica_id)):
        raise _refuse("REPLICA_ID_INVALID")
    if OF.PROFILE_ENVIRONMENTS.get(authority_profile) != environment:
        raise _refuse("PROFILE_MISMATCH")
    if os.path.lexists(path):
        raise _refuse("REPLICA_PATH_EXISTS")
    os.mkdir(path, 0o700)
    _write_new_file(path / MANIFEST, OF.record_bytes(_manifest(replica_id, environment, authority_profile)))
    os.mkdir(path / RECORDS, 0o700)
    fsync = [_fsync_directory(path / RECORDS), _fsync_directory(path)]
    if path.parent != path:
        fsync.append(_fsync_directory(path.parent))
    return {"status": "REPLICA_INITIALIZED", "replicaId": replica_id, "environment": environment,
            "authorityProfile": authority_profile, "directoryFsync": fsync[-1]}


def load_replica(path: Any) -> ReplicaV1:
    """Strict read of one replica. Anything unexpected refuses; nothing is repaired.

    Order comes only from each record's own `recordVersion` and chain link:
    never from file order, mtime, or any Git metadata.
    """
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise _refuse("REPLICA_MISSING", str(path)) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise _refuse("REPLICA_NOT_A_DIRECTORY")
    entries = set(os.listdir(path))
    if entries != {MANIFEST, RECORDS}:
        raise _refuse("REPLICA_UNEXPECTED_ENTRY", ",".join(sorted(entries ^ {MANIFEST, RECORDS})))
    manifest = _canonical_json(_read_regular(path / MANIFEST, "REPLICA_MANIFEST_INVALID"), "REPLICA_MANIFEST_INVALID")
    if set(manifest) != REPLICA_FIELDS or manifest["replicaType"] != REPLICA_TYPE \
            or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1 \
            or not (isinstance(manifest["replicaId"], str) and REPLICA_ID.fullmatch(manifest["replicaId"])) \
            or OF.PROFILE_ENVIRONMENTS.get(manifest["authorityProfile"]) != manifest["environment"]:
        raise _refuse("REPLICA_MANIFEST_INVALID")
    records_dir = path / RECORDS
    if os.path.islink(records_dir) or not records_dir.is_dir():
        raise _refuse("REPLICA_UNEXPECTED_ENTRY", RECORDS)
    by_version: dict[int, tuple[str, str]] = {}
    for name in sorted(os.listdir(records_dir)):
        if name.startswith(PENDING_PREFIX):
            raise _refuse("REPLICA_PENDING_WRITE", name)
        match = RECORD_NAME.fullmatch(name)
        if match is None:
            raise _refuse("REPLICA_UNEXPECTED_ENTRY", name)
        version = int(match.group(1))
        if version in by_version:
            raise _refuse("RECORD_VERSION_DUPLICATED", str(version))
        by_version[version] = (name, match.group(2))
    if sorted(by_version) != list(range(1, len(by_version) + 1)):
        raise _refuse("RECORD_VERSION_GAP", ",".join(str(v) for v in sorted(by_version)))
    records = []
    for version in sorted(by_version):
        name, digest = by_version[version]
        raw = _read_regular(records_dir / name, "RECORD_MALFORMED")
        if not raw:                      # interrupted create (DIRECT_O_EXCL crash): never accepted, never removed
            raise _refuse("RECORD_ZERO_BYTES", name)
        record = _canonical_json(raw, "RECORD_MALFORMED")
        try:
            parsed = OF.OwnerFreshnessRecordV1.from_dict(record)
        except (OwnerProofError, TypeError) as exc:
            raise _refuse("RECORD_MALFORMED", name) from exc
        if parsed.digest != digest or parsed.record_version != version:
            raise _refuse("RECORD_NAME_MISMATCH", name)
        if parsed.environment != manifest["environment"] or parsed.authority_profile != manifest["authorityProfile"]:
            raise _refuse("RECORD_PROFILE_MISMATCH", name)
        records.append(record)
    if records:
        result = OF.verify_owner_register(records)
        if not result.verified:
            raise _refuse(result.reason, result.detail)
    return ReplicaV1(path, manifest["replicaId"], manifest["environment"], manifest["authorityProfile"],
                     tuple(records))


def _distinct(replicas: Sequence[ReplicaV1]) -> None:
    ids = [r.replica_id for r in replicas]
    if len(set(ids)) != len(ids):
        raise _refuse("REPLICA_ID_DUPLICATED")
    for index, left in enumerate(replicas):
        for right in replicas[index + 1:]:
            if os.path.samefile(left.path, right.path):
                raise _refuse("REPLICA_SAME_LOCATION")
            if (left.environment, left.authority_profile) != (right.environment, right.authority_profile):
                raise _refuse("REPLICA_PROFILE_MISMATCH")


def load_register(paths: Sequence[Any]) -> tuple[OF.OwnerRegisterResultV1, tuple[ReplicaV1, ...]]:
    """The owner register from its replicas, never raising: any failure is a
    non-verified register, which classifies FRESHNESS_UNKNOWN (D7, D8)."""
    try:
        replicas = tuple(load_replica(p) for p in paths)
        _distinct(replicas)
    except ToolRefusal as refusal:
        return OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, refusal.reason, refusal.detail), ()
    if len(replicas) < MINIMUM_REPLICAS:
        return OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "REPLICA_QUORUM_UNMET", str(len(replicas))), \
            replicas
    if all(not r.records for r in replicas):
        return OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "OWNER_REGISTER_EMPTY"), replicas
    empty = [index for index, r in enumerate(replicas) if not r.records]
    if empty:                          # some copies empty, others not: one is behind
        return OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "REPLICAS_DIVERGENT",
                                        f"replica{empty[0]}:PREFIX"), replicas
    return OF.reconcile_owner_replicas([list(r.records) for r in replicas], minimum_replicas=MINIMUM_REPLICAS), \
        replicas


def compare_replicas(paths: Sequence[Any]) -> dict[str, Any]:
    register, replicas = load_register(paths)
    return {"status": register.status, "reason": register.reason, "detail": register.detail,
            "replicas": [{"replicaId": r.replica_id, "records": len(r.records),
                          "headDigest": r.digests[-1] if r.records else None} for r in replicas],
            "latestAcceptedRecordVersion": register.facts.latest.record_version if register.verified else None}


# ---------------------------------------------------------- trust and chain ---

@dataclass(frozen=True)
class TrustInputsV1:
    environment: str
    anchor: R.TrustedWitnessAnchorV1
    registry_root: A.TrustedRegistryRootV1
    authority_public_keys: frozenset[bytes]


def load_trust(path: Any) -> TrustInputsV1:
    """Pinned verification inputs the owner holds: the K-WIT anchor, the
    registry root, and the registries whose keys must never sign a witness."""
    value = _input_json(Path(path), "TRUST_INPUTS_INVALID")
    if not isinstance(value, dict) or set(value) != TRUST_FIELDS or value["trustType"] != TRUST_TYPE \
            or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 \
            or not isinstance(value["registries"], list):
        raise _refuse("TRUST_INPUTS_INVALID")
    try:
        anchor = R.TrustedWitnessAnchorV1.from_dict(value["witnessAnchor"])
        root = A.TrustedRegistryRootV1.from_dict(value["registryRoot"])
    except (OwnerProofError, TypeError) as exc:
        raise _refuse("TRUST_INPUTS_INVALID", str(exc)) from exc
    if not (value["environment"] == anchor.environment == root.environment):
        raise _refuse("TRUST_INPUTS_ENVIRONMENT_MISMATCH")
    return TrustInputsV1(value["environment"], anchor, root, RC._authority_keys(*value["registries"]))


def verify_chain(trust: TrustInputsV1, chain_path: Any, environment: str) -> RC.ChainResultV1:
    """K-WIT verification of an exported witness chain (a JSON array of V2
    witness documents, genesis first). This is the whole authenticity check."""
    documents = _input_json(Path(chain_path), "CHAIN_INPUT_INVALID")
    if not isinstance(documents, list):
        raise _refuse("CHAIN_INPUT_INVALID")
    if trust.environment != environment:
        raise _refuse("TRUST_INPUTS_ENVIRONMENT_MISMATCH")
    return RC.verify_witness_v2_chain(anchor=trust.anchor, chain=documents, environment=environment,
                                      registry_root=trust.registry_root,
                                      authority_public_keys=trust.authority_public_keys)


def load_pin(path: Any) -> WR.OwnerGenesisPinV1:
    try:
        return WR.OwnerGenesisPinV1.from_dict(_input_json(Path(path), "GENESIS_PIN_INVALID"))
    except (OwnerProofError, TypeError) as exc:
        raise _refuse("GENESIS_PIN_INVALID") from exc


def inspect_chain(trust: TrustInputsV1, chain_path: Any, environment: str) -> dict[str, Any]:
    chain = verify_chain(trust, chain_path, environment)
    if not chain.verified:
        return {"authenticity": OF.NOT_AUTHENTIC, "reason": chain.reason, "detail": chain.detail}
    head = chain.facts.head
    return {"authenticity": OF.AUTHENTIC, "environment": head.environment, "entries": len(chain.facts.witnesses),
            "genesisWitnessDigest": chain.facts.witnesses[0].digest, "headWitnessVersion": head.witness_version,
            "headWitnessDigest": head.digest, "recoveryEpoch": head.current_recovery_epoch.to_dict(),
            "registryVersion": head.registry_version, "registryDigest": head.registry_digest,
            "ledgerSequence": head.ledger_sequence, "witnessKeyId": head.witness_key_id,
            "consumedAuthorizationIds": sorted(chain.facts.consumed_authorization_ids),
            "note": "authentic != current; compare against the owner register (classify)"}


# -------------------------------------------------------------- classification ---

def _result(result: OF.FreshnessResultV1) -> dict[str, Any]:
    return {"authenticity": result.authenticity, "freshness": result.freshness, "reason": result.reason,
            "detail": result.detail, "facts": dict(result.facts)}


def classify(replica_paths: Sequence[Any], trust: TrustInputsV1, chain_path: Any, *, environment: str,
             authority_profile: str) -> dict[str, Any]:
    register, _ = load_register(replica_paths)
    chain = verify_chain(trust, chain_path, environment)
    result = OF.classify_presented_world(register=register, chain=chain, environment=environment,
                                         authority_profile=authority_profile)
    return _result(result) | {"gates": {op: OF.freshness_gate(result, op).status
                                        for op in sorted(OF.GATED_OPERATIONS)}}


# ------------------------------------------------------------------ candidates ---

def _candidate_document(candidate: OF.OwnerRecordCandidateV1) -> dict[str, Any]:
    return {"candidateType": CANDIDATE_TYPE, "schemaVersion": 1, "accepted": False,
            "decision": candidate.record["decision"], "recordDigest": candidate.record_digest,
            "record": dict(candidate.record)}


def _write_candidate(out: Any, candidate: OF.OwnerRecordCandidateV1) -> dict[str, Any]:
    if not candidate.proposed:
        raise _refuse("CANDIDATE_NOT_PROPOSED", candidate.reason)
    document = _candidate_document(candidate)
    try:
        _write_new_file(Path(out), json.dumps(document, indent=1, sort_keys=True).encode("utf-8") + b"\n")
    except FileExistsError as exc:
        raise _refuse("CANDIDATE_FILE_EXISTS") from exc
    return {"status": "CANDIDATE_WRITTEN", "accepted": False, "decision": document["decision"],
            "recordVersion": document["record"]["recordVersion"], "recordDigest": document["recordDigest"],
            "note": "candidate != acceptance; nothing was appended to any replica"}


def _pin_binds(pin: WR.OwnerGenesisPinV1, environment: str, genesis_digest: str) -> None:
    if pin.environment != environment:
        raise _refuse("GENESIS_PIN_ENVIRONMENT_MISMATCH")
    if pin.genesis_witness_digest != genesis_digest:
        raise _refuse("GENESIS_PIN_MISMATCH")


def _genesis_candidate(trust, chain_path, pin, environment, profile) -> OF.OwnerRecordCandidateV1:
    candidate = OF.propose_genesis_record(chain=verify_chain(trust, chain_path, environment),
                                          environment=environment, authority_profile=profile)
    if candidate.proposed:
        _pin_binds(pin, environment, candidate.record["genesisWitnessDigest"])
    return candidate


def _successor_candidate(decision, register, trust, chain_path, pin, environment, profile) -> OF.OwnerRecordCandidateV1:
    if not register.verified:
        raise _refuse("OWNER_REGISTER_NOT_VERIFIED", register.reason)
    _pin_binds(pin, environment, register.facts.genesis_witness_digest)
    propose = OF.propose_acceptance if decision == OF.ACCEPT_CURRENT else OF.propose_rejection
    return propose(register=register, chain=verify_chain(trust, chain_path, environment), environment=environment,
                   authority_profile=profile)


def propose_genesis(trust, chain_path, pin_path, out, *, environment, authority_profile) -> dict[str, Any]:
    return _write_candidate(out, _genesis_candidate(trust, chain_path, load_pin(pin_path), environment,
                                                    authority_profile))


def propose(decision: str, replica_paths, trust, chain_path, pin_path, out, *, environment,
            authority_profile) -> dict[str, Any]:
    register, _ = load_register(replica_paths)
    return _write_candidate(out, _successor_candidate(decision, register, trust, chain_path, load_pin(pin_path),
                                                      environment, authority_profile))


def load_candidate(path: Any) -> tuple[dict[str, Any], str]:
    value = _input_json(Path(path), "CANDIDATE_MALFORMED")
    if not isinstance(value, dict) or set(value) != CANDIDATE_FIELDS or value["candidateType"] != CANDIDATE_TYPE \
            or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 \
            or value["accepted"] is not False:
        raise _refuse("CANDIDATE_MALFORMED")
    try:
        parsed = OF.OwnerFreshnessRecordV1.from_dict(value["record"])
    except (OwnerProofError, TypeError) as exc:
        raise _refuse("CANDIDATE_MALFORMED", "RECORD") from exc
    if parsed.digest != value["recordDigest"] or parsed.decision != value["decision"]:
        raise _refuse("CANDIDATE_MALFORMED", "DIGEST_OR_DECISION")
    return dict(value["record"]), parsed.digest


# ------------------------------------------------------------------- append ---

def append(target_path, peer_path, candidate_path, trust, chain_path, pin_path, *, environment: str,
           authority_profile: str, confirm_digest: Any) -> dict[str, Any]:
    """The owner ceremony write (D1): append one record to ONE replica.

    Preconditions, all re-derived here rather than trusted from the candidate:

    1. the owner repeats the candidate's record digest (`confirm_digest`);
    2. target and peer are distinct, clean, identical replicas, or the peer
       is exactly one record ahead with this same record (the second half of
       the ceremony). Anything else refuses; the tool never copies between
       replicas;
    3. the presented chain is authentic, and the genesis pin binds the lineage (D12);
    4. re-proposing from the target replica's register and the chain yields a
       byte-identical record. Therefore only `AHEAD_UNACCEPTED` can be
       accepted, and only `AHEAD_UNACCEPTED` or `CONFLICTING` can be rejected.
    """
    block = OA.real_acceptance_block(authority_profile)
    if block is not None:                               # P3-6: no real acceptance while P3-3 is incomplete
        raise _refuse("REAL_ACCEPTANCE_DISABLED", block)
    record, digest = load_candidate(candidate_path)
    if not isinstance(confirm_digest, str) or not confirm_digest:
        raise _refuse("OWNER_CONFIRMATION_REQUIRED")
    if confirm_digest != digest:
        raise _refuse("OWNER_CONFIRMATION_MISMATCH")
    pin = load_pin(pin_path)
    target, peer = load_replica(target_path), load_replica(peer_path)
    _distinct((target, peer))
    if (target.environment, target.authority_profile) != (environment, authority_profile):
        raise _refuse("PROFILE_MISMATCH")
    if peer.digests == target.digests:
        replication = "PEER_PENDING"
    elif peer.digests == target.digests + (digest,):
        replication = "REPLICAS_IDENTICAL"
    else:
        raise _refuse("REPLICAS_NOT_APPENDABLE", "target and peer are neither identical nor peer = target + candidate")
    if not target.records:
        expected = _genesis_candidate(trust, chain_path, pin, environment, authority_profile)
    else:
        register = OF.verify_owner_register(list(target.records))
        expected = _successor_candidate(record["decision"], register, trust, chain_path, pin, environment,
                                        authority_profile)
    if not expected.proposed:
        raise _refuse("CANDIDATE_NOT_ACCEPTABLE", expected.reason)
    if dict(expected.record) != record:
        raise _refuse("CANDIDATE_NOT_ACCEPTABLE", "CANDIDATE_DIFFERS_FROM_DERIVED_RECORD")
    written = _write_record(target, record, digest)
    after = load_replica(target.path)
    if after.digests != target.digests + (digest,):
        raise _refuse("POST_WRITE_VERIFICATION_FAILED")
    return {"status": "RECORD_APPENDED", "replicaId": target.replica_id, "recordVersion": record["recordVersion"],
            "decision": record["decision"], "recordDigest": digest, "replication": replication,
            "directoryFsync": written["directoryFsync"], "publicationBackend": written["backend"]}


def admitted_backend(directory: Path) -> str:
    """The create-only backend for this filesystem, from a fresh probe of the
    directory's parent (P3-3A). Refuses when no reviewed backend is admitted."""
    probe = probe_storage(Path(directory).parent)
    if probe["result"] != P3_STORAGE_CAPABLE:
        raise _refuse(P3_STORAGE_INCAPABLE, probe["failure"] or probe["admittedBackend"])
    return probe["admittedBackend"]


def _publish(directory: Path, final_name: str, data: bytes, *, exists_reason: str, owner: Path) -> dict[str, str]:
    backend = admitted_backend(owner)
    try:
        fsync = COP.publish(directory, final_name, data, backend=backend)
    except COP.PublishRefused as refused:
        raise _refuse(exists_reason if refused.reason == "FINAL_EXISTS" else refused.reason, final_name) from refused
    return {"directoryFsync": fsync, "backend": backend}


def _write_record(replica: ReplicaV1, record: dict[str, Any], digest: str) -> dict[str, str]:
    """Create-only publication of one record file through the admitted
    backend (P3-3A). The final name is never replaced: any existing file of
    the same version refuses first, and the primitive refuses a racing one.
    A crash can leave a `.pending-*` file behind; the next read then refuses
    with REPLICA_PENDING_WRITE, and the owner resolves it by hand (no silent
    repair).
    """
    version = record["recordVersion"]
    if version > MAX_RECORD_VERSION:
        raise _refuse("RECORD_VERSION_OUT_OF_RANGE")
    records_dir = replica.path / RECORDS
    for existing in os.listdir(records_dir):
        match = RECORD_NAME.fullmatch(existing)
        if match and int(match.group(1)) == version:
            raise _refuse("RECORD_EXISTS", existing)
    return _publish(records_dir, f"{version:06d}-{digest}.json", OF.record_bytes(record),
                    exists_reason="RECORD_EXISTS", owner=replica.path)


# ------------------------------------------- P3-3 real-replica storage gate ---
#
# Generic inspection keeps the P3-2 behaviour (directory fsync reported, not
# required). Admission of a REAL owner replica is stricter:
# - directory fsync is REQUIRED (P3-3);
# - at least one reviewed create-only backend must pass (P3-3A, which
#   replaces the P3-3 "hard links required" rule). There is never a
#   fallback to an overwriting rename;
# - the location must pass the policy checks below.

P3_STORAGE_CAPABLE = "P3_STORAGE_CAPABLE"
P3_STORAGE_INCAPABLE = "P3_STORAGE_INCAPABLE"
PROBE_PREFIX = ".lilith-p3-probe-"
# Required on every admitted filesystem, whatever the backend.
PROBE_CHECKS = ("exclusiveCreate", "fileFsync", "directoryFsync", "symlinkDetection", "canonicalReread", "cleanup")
BACKEND_CHECK_NAMES = {COP.HARDLINK_PUBLISH_V1: "hardlinkPublish", COP.RENAME_NOREPLACE_V1: "renameNoReplace",
                       COP.DIRECT_O_EXCL_V1: "directExclusiveFinal"}
PASS, FAIL, UNAVAILABLE = "PASS", "FAIL", "UNAVAILABLE"
# Path components of known automatically synchronized roots (case-insensitive).
AUTO_SYNC_COMPONENTS = re.compile(r"(onedrive.*|dropbox.*|google ?drive|my ?drive|icloud.*|box|box sync|nextcloud|"
                                  r"owncloud|pcloud.*|mega|megasync|sync|syncthing|resilio sync)\Z", re.IGNORECASE)


def _directory_fsync_strict(path: Path) -> None:
    """Directory fsync or an exception. No platform exemption."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _inside_replica(path: Path) -> bool:
    for ancestor in (path, *path.parents):
        if os.path.lexists(ancestor / MANIFEST) and os.path.isdir(ancestor / RECORDS):
            return True
    return False


def _probe_backend(root: Path, backend: str, payload: bytes) -> str:
    """The abstract create-only contract, for one backend: publish once, the
    re-read equals the bytes, a second publish at the same final name is
    refused, a racing primitive call is refused by the primitive itself, and
    the existing final stays untouched."""
    directory = root / f"backend-{BACKEND_CHECK_NAMES[backend]}"
    os.mkdir(directory, 0o700)
    final = directory / "000001-probe.json"
    try:
        COP.publish(directory, final.name, payload, backend=backend)
    except COP.BackendUnavailable:
        return UNAVAILABLE
    except Exception:                                     # noqa: BLE001 - contained per backend
        return FAIL
    try:
        if _read_regular(final, "PROBE") != payload:
            return FAIL
        try:
            COP.publish(directory, final.name, payload + b" ", backend=backend)
            return FAIL                                   # replaced or duplicated: contract broken
        except COP.PublishRefused as refused:
            if refused.reason != "FINAL_EXISTS":
                return FAIL
        racing = directory / f"{COP.PENDING_PREFIX}race.tmp"
        COP.write_new_file(racing, payload + b"  ")
        try:
            if backend == COP.RENAME_NOREPLACE_V1:
                COP.rename_noreplace(racing, final)
            elif backend == COP.HARDLINK_PUBLISH_V1:
                getattr(os, "link")(racing, final)
            else:
                COP.write_new_file(final, payload + b"  ")
            return FAIL
        except FileExistsError:
            pass
        if _read_regular(final, "PROBE") != payload:
            return FAIL
        return PASS if set(os.listdir(directory)) == {final.name, racing.name} else FAIL
    except Exception:                                     # noqa: BLE001 - contained per backend
        return FAIL


def probe_storage(probe_parent: Any) -> dict[str, Any]:
    """Capability probe on the filesystem of `probe_parent`, an existing
    directory the owner selected. It creates and removes only a fresh
    `.lilith-p3-probe-<random>` directory and the files inside it, and it
    refuses to run inside an initialized replica.

    `P3_STORAGE_CAPABLE` requires every common check and at least one
    ADMITTED create-only backend. Each backend is reported separately; the
    admitted one is chosen deterministically (`COP.ADMITTED_PREFERENCE`)."""
    parent = Path(probe_parent)
    if not parent.is_dir() or os.path.islink(parent):
        raise _refuse("PROBE_PARENT_INVALID")
    if _inside_replica(parent.resolve()):
        raise _refuse("PROBE_INSIDE_REPLICA")
    root = parent / f"{PROBE_PREFIX}{os.urandom(8).hex()}"
    checks: dict[str, Any] = dict.fromkeys(PROBE_CHECKS, False)
    backends = dict.fromkeys(COP.BACKENDS, UNAVAILABLE)
    failure = None
    os.mkdir(root, 0o700)
    try:
        a, s = root / "a.json", root / "s.json"
        payload = OF.record_bytes({"probe": "LILITH_P3_STORAGE_PROBE", "n": 1})
        _write_new_file(a, payload)                                        # O_EXCL + file fsync
        try:
            _write_new_file(a, payload)
            raise _refuse("PROBE_EXCLUSIVE_CREATE_REPLACED")
        except FileExistsError:
            checks["exclusiveCreate"] = True
        checks["fileFsync"] = True
        _directory_fsync_strict(root)
        checks["directoryFsync"] = True
        symlink = getattr(os, "symlink", None)
        if symlink is not None:
            symlink(a, s)
            try:
                _read_regular(s, "PROBE_SYMLINK")
            except ToolRefusal:
                checks["symlinkDetection"] = stat.S_ISLNK(os.lstat(s).st_mode)
        checks["canonicalReread"] = _canonical_json(_read_regular(a, "PROBE"), "PROBE") == \
            {"probe": "LILITH_P3_STORAGE_PROBE", "n": 1}
        for backend in COP.BACKENDS:
            backends[backend] = _probe_backend(root, backend, payload)
    except ToolRefusal as refusal:
        failure = refusal.reason
    except OSError as exc:
        failure = f"{type(exc).__name__}:{getattr(exc, 'errno', None)}"
    finally:
        for current, directories, files in os.walk(root, topdown=False):
            for name in files:
                os.unlink(Path(current) / name)
            for name in directories:
                path = Path(current) / name
                if os.path.islink(path):
                    os.unlink(path)
                else:
                    os.rmdir(path)
        os.rmdir(root)
        try:
            _directory_fsync_strict(parent)
        except OSError:
            pass
        checks["cleanup"] = not os.path.lexists(root)
    admitted = COP.select_backend({b: backends[b] == PASS for b in COP.BACKENDS})
    info = os.stat(parent)
    capable = failure is None and all(checks[name] is True for name in PROBE_CHECKS) and admitted != COP.NONE
    return {"result": P3_STORAGE_CAPABLE if capable else P3_STORAGE_INCAPABLE, "failure": failure,
            "checks": checks, "backends": {BACKEND_CHECK_NAMES[b]: backends[b] for b in COP.BACKENDS},
            "admittedBackend": admitted, "evaluatedNotAdmitted": [COP.DIRECT_O_EXCL_V1],
            "device": info.st_dev, "platform": os.name}


def location_policy(path: Any) -> dict[str, Any]:
    """Refuse locations that cannot be an independent owner replica: inside a
    Git working tree (any ancestor holds `.git`), or under a known
    automatically synchronized root. Unknown sync or backup mechanisms cannot
    be excluded by code; that remains owner evidence."""
    target = Path(os.path.abspath(path))
    for ancestor in (target, *target.parents):
        if os.path.lexists(ancestor / ".git"):
            raise _refuse("LOCATION_IN_GIT_WORKTREE", str(ancestor))
    for part in target.parts:
        if AUTO_SYNC_COMPONENTS.fullmatch(part.strip("/\\")):
            raise _refuse("LOCATION_AUTO_SYNC_ROOT", part)
    for name, value in os.environ.items():
        if name.upper().startswith(("ONEDRIVE", "DROPBOX")) and value:
            root = os.path.abspath(value)
            if os.path.commonpath([root, str(target)]) == root:
                raise _refuse("LOCATION_AUTO_SYNC_ROOT", name)
    return {"path": str(target), "gitWorkTree": False, "knownAutoSyncRoot": False}


def check_independence(first: Any, second: Any) -> dict[str, Any]:
    """Refuse two replicas that are observably one location or one device.
    Distinct devices are necessary evidence, not sufficient: two partitions of
    one disk, or two directories inside one virtual disk, still roll back together."""
    left, right = load_replica(first), load_replica(second)
    _distinct((left, right))
    dev_left, dev_right = os.stat(left.path).st_dev, os.stat(right.path).st_dev
    if dev_left == dev_right:
        raise _refuse("REPLICA_SAME_DEVICE", str(dev_left))
    return {"status": "DISTINCT_DEVICES_OBSERVED", "devices": [dev_left, dev_right],
            "note": "distinct st_dev != independent rollback domain; owner evidence required"}


def init_real_replica(path: Any, *, replica_id: str, environment: str, authority_profile: str,
                      other_replica: Any = None) -> dict[str, Any]:
    """P3-3 admission + initialization of one REAL owner replica. Every gate
    must pass before anything is created; nothing is appended."""
    path = Path(os.path.abspath(path))
    if OF.PROFILE_ENVIRONMENTS.get(authority_profile) != environment:
        raise _refuse("PROFILE_MISMATCH")
    if not (isinstance(replica_id, str) and REPLICA_ID.fullmatch(replica_id)):
        raise _refuse("REPLICA_ID_INVALID")
    policy = location_policy(path)
    if os.path.lexists(path):
        raise _refuse("REPLICA_PATH_EXISTS")
    if other_replica is not None:
        other = load_replica(other_replica)
        if other.replica_id == replica_id:
            raise _refuse("REPLICA_ID_DUPLICATED")
        if os.stat(path.parent).st_dev == os.stat(other.path).st_dev:
            raise _refuse("REPLICA_SAME_DEVICE")
    probe = probe_storage(path.parent)
    if probe["result"] != P3_STORAGE_CAPABLE:
        raise _refuse(P3_STORAGE_INCAPABLE, probe["failure"] or ",".join(k for k, v in probe["checks"].items()
                                                                           if v is not True))
    created = init_replica(path, replica_id=replica_id, environment=environment, authority_profile=authority_profile)
    if created["directoryFsync"] != "PERFORMED":
        raise _refuse("DIRECTORY_FSYNC_NOT_PERFORMED")
    replica = load_replica(path)
    if replica.records or sorted(os.listdir(path / RECORDS)):
        raise _refuse("REPLICA_NOT_EMPTY")
    info = os.stat(path)
    return {"status": "REAL_REPLICA_INITIALIZED_EMPTY", "replicaId": replica_id, "environment": environment,
            "authorityProfile": authority_profile, "records": 0, "location": policy, "probe": probe,
            "mode": oct(stat.S_IMODE(info.st_mode)),
            "recordsMode": oct(stat.S_IMODE(os.stat(path / RECORDS).st_mode)), "device": info.st_dev}


# -------------------------------------------- P3-6 acceptance-evidence store ---
#
# A sibling owner-custody structure, one per replica. It is never inside the
# strict replica root, which admits only REPLICA.json and records/:
#
#   <acceptance store>/
#     ACCEPTANCE.json                          manifest: custodyCopyId = the paired replica's replicaId
#     envelopes/NNNNNN-<envelopeDigest>.json   JCS {"envelope": ..., "package": ...}, create-only
#
# Freshness records and acceptance evidence stay distinct but cross-bound:
# envelope N binds record N's digest, and the store binds its paired replica ID.

ACCEPTANCE_STORE_TYPE = "LILITH_OWNER_ACCEPTANCE_STORE"
ACCEPTANCE_STORE_FIELDS = frozenset({"storeType", "schemaVersion", "custodyCopyId", "environment",
                                     "authorityProfile"})
ACCEPTANCE_MANIFEST = "ACCEPTANCE.json"
ENVELOPES = "envelopes"
ENVELOPE_NAME = RECORD_NAME
ENVELOPE_CANDIDATE_TYPE = "LILITH_OWNER_ACCEPTANCE_ENVELOPE_CANDIDATE"
ENVELOPE_CANDIDATE_FIELDS = frozenset({"candidateType", "schemaVersion", "accepted", "envelopeDigest", "envelope",
                                       "package"})


@dataclass(frozen=True)
class AcceptanceStoreV1:
    path: Path
    custody_copy_id: str
    environment: str
    authority_profile: str
    bundles: tuple[dict[str, Any], ...]

    @property
    def digests(self) -> tuple[str, ...]:
        return tuple(OA.envelope_digest(b["envelope"]) for b in self.bundles)


def init_acceptance_store(path: Any, *, custody_copy_id: str, environment: str,
                          authority_profile: str) -> dict[str, Any]:
    path = Path(path)
    if not (isinstance(custody_copy_id, str) and REPLICA_ID.fullmatch(custody_copy_id)):
        raise _refuse("REPLICA_ID_INVALID")
    if OF.PROFILE_ENVIRONMENTS.get(authority_profile) != environment:
        raise _refuse("PROFILE_MISMATCH")
    if _inside_replica(Path(os.path.abspath(path))):
        raise _refuse("ACCEPTANCE_STORE_INSIDE_REPLICA")
    if os.path.lexists(path):
        raise _refuse("ACCEPTANCE_STORE_PATH_EXISTS")
    os.mkdir(path, 0o700)
    _write_new_file(path / ACCEPTANCE_MANIFEST, OF.record_bytes(
        {"storeType": ACCEPTANCE_STORE_TYPE, "schemaVersion": 1, "custodyCopyId": custody_copy_id,
         "environment": environment, "authorityProfile": authority_profile}))
    os.mkdir(path / ENVELOPES, 0o700)
    return {"status": "ACCEPTANCE_STORE_INITIALIZED", "custodyCopyId": custody_copy_id,
            "directoryFsync": [_fsync_directory(path / ENVELOPES), _fsync_directory(path)][-1]}


def load_acceptance_store(path: Any) -> AcceptanceStoreV1:
    """Strict read, like `load_replica`: exact entries, canonical names and
    bytes, contiguous versions, and no repair."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise _refuse("ACCEPTANCE_STORE_MISSING") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise _refuse("ACCEPTANCE_STORE_NOT_A_DIRECTORY")
    entries = set(os.listdir(path))
    if entries != {ACCEPTANCE_MANIFEST, ENVELOPES}:
        raise _refuse("ACCEPTANCE_STORE_UNEXPECTED_ENTRY", ",".join(sorted(entries ^ {ACCEPTANCE_MANIFEST, ENVELOPES})))
    manifest = _canonical_json(_read_regular(path / ACCEPTANCE_MANIFEST, "ACCEPTANCE_MANIFEST_INVALID"),
                               "ACCEPTANCE_MANIFEST_INVALID")
    if set(manifest) != ACCEPTANCE_STORE_FIELDS or manifest["storeType"] != ACCEPTANCE_STORE_TYPE \
            or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1 \
            or not (isinstance(manifest["custodyCopyId"], str) and REPLICA_ID.fullmatch(manifest["custodyCopyId"])) \
            or OF.PROFILE_ENVIRONMENTS.get(manifest["authorityProfile"]) != manifest["environment"]:
        raise _refuse("ACCEPTANCE_MANIFEST_INVALID")
    directory = path / ENVELOPES
    if os.path.islink(directory) or not directory.is_dir():
        raise _refuse("ACCEPTANCE_STORE_UNEXPECTED_ENTRY", ENVELOPES)
    by_version: dict[int, tuple[str, str]] = {}
    for name in sorted(os.listdir(directory)):
        if name.startswith(PENDING_PREFIX):
            raise _refuse("ACCEPTANCE_PENDING_WRITE", name)
        match = ENVELOPE_NAME.fullmatch(name)
        if match is None:
            raise _refuse("ACCEPTANCE_STORE_UNEXPECTED_ENTRY", name)
        version = int(match.group(1))
        if version in by_version:
            raise _refuse("ENVELOPE_VERSION_DUPLICATED", str(version))
        by_version[version] = (name, match.group(2))
    if sorted(by_version) != list(range(1, len(by_version) + 1)):
        raise _refuse("ENVELOPE_VERSION_GAP", ",".join(str(v) for v in sorted(by_version)))
    bundles = []
    for version in sorted(by_version):
        name, digest = by_version[version]
        raw = _read_regular(directory / name, "ENVELOPE_MALFORMED")
        if not raw:
            raise _refuse("ENVELOPE_ZERO_BYTES", name)
        bundle = _canonical_json(raw, "ENVELOPE_MALFORMED")
        try:
            if set(bundle) != OA.BUNDLE_FIELDS:
                raise ContractViolation("INVALID_BUNDLE")
            parsed = OA.OwnerFreshnessAcceptanceEnvelopeV1.from_dict(bundle["envelope"])
        except (OwnerProofError, TypeError) as exc:
            raise _refuse("ENVELOPE_MALFORMED", name) from exc
        if parsed.digest != digest or parsed.freshness_record_version != version:
            raise _refuse("ENVELOPE_NAME_MISMATCH", name)
        if (parsed.environment, parsed.authority_profile) != (manifest["environment"], manifest["authorityProfile"]):
            raise _refuse("ENVELOPE_PROFILE_MISMATCH", name)
        bundles.append(bundle)
    return AcceptanceStoreV1(path, manifest["custodyCopyId"], manifest["environment"], manifest["authorityProfile"],
                             tuple(bundles))


def classify_acceptance_state(replica_paths: Sequence[Any], store_paths: Sequence[Any],
                              pin_path: Any) -> dict[str, Any]:
    """Acceptance-evidence state for the latest freshness record. Reported
    beside freshness, never merged into it."""
    register, replicas = load_register(replica_paths)
    try:
        stores = [load_acceptance_store(p) for p in store_paths]
        pin = _input_json(Path(pin_path), "GENESIS_PIN_INVALID")
    except ToolRefusal as refusal:
        return {"state": OA.ACCEPTANCE_UNKNOWN, "reason": refusal.reason, "detail": refusal.detail}
    if len(stores) != 2 or {s.custody_copy_id for s in stores} != {r.replica_id for r in replicas} \
            or len({s.custody_copy_id for s in stores}) != 2:
        return {"state": OA.ACCEPTANCE_UNKNOWN, "reason": "ACCEPTANCE_STORES_NOT_PAIRED_WITH_REPLICAS", "detail": None}
    result = OA.classify_acceptance(register=register, copies=[list(s.bundles) for s in stores],
                                    replica_ids=[r.replica_id for r in replicas], pin=pin)
    return {"state": result.state, "reason": result.reason, "detail": result.detail,
            "evidencedRecordVersion": result.evidenced_record_version}


def build_package(replica_paths: Sequence[Any], trust_path: Any, chain_path: Any, pin_path: Any,
                  candidate_path: Any, out: Any, *, environment: str, authority_profile: str,
                  evidence: Mapping[str, str]) -> dict[str, Any]:
    """Ceremony step 1: build the review package BEFORE the append, from the
    replicas as they are now (the prior register)."""
    register, replicas = load_register(replica_paths)
    if not register.verified and register.reason != "OWNER_REGISTER_EMPTY":
        raise _refuse("OWNER_REGISTER_NOT_VERIFIED", register.reason)
    prior = [] if not register.verified else [r.to_dict() for r in register.facts.records]
    record, _ = load_candidate(candidate_path)
    trust = load_trust(trust_path)
    try:
        package = OA.build_review_package(
            prior_records=prior, chain=verify_chain(trust, chain_path, environment), candidate_record=record,
            trust_document=_input_json(Path(trust_path), "TRUST_INPUTS_INVALID"),
            pin=_input_json(Path(pin_path), "GENESIS_PIN_INVALID"), replica_ids=[r.replica_id for r in replicas],
            environment=environment, authority_profile=authority_profile, attached_evidence=evidence)
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise _refuse("PACKAGE_NOT_BUILDABLE", str(exc)) from exc
    try:
        _write_new_file(Path(out), OF.record_bytes(package))
    except FileExistsError as exc:
        raise _refuse("PACKAGE_FILE_EXISTS") from exc
    return {"status": "PACKAGE_WRITTEN", "packageDigest": OA.review_package_digest(package),
            "packageKind": package["packageKind"], "note": "a review package is not an acceptance"}


def _expected_envelope(stores: Sequence[AcceptanceStoreV1], register: OF.OwnerRegisterResultV1,
                       package: Mapping[str, Any]) -> dict[str, Any]:
    records = register.facts.records
    target = stores[0]
    if len(target.bundles) != len(records) - 1:
        raise _refuse("ENVELOPE_NOT_NEXT", f"{len(target.bundles)}/{len(records)}")
    previous = target.bundles[-1]["envelope"] if target.bundles else None
    try:
        return OA.build_envelope(record=records[-1].to_dict(), package=package, previous_envelope=previous)
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise _refuse("ENVELOPE_NOT_BUILDABLE", str(exc)) from exc


def propose_envelope(replica_paths, store_paths, package_path, out) -> dict[str, Any]:
    """Ceremony step 11: construct the envelope for the latest record, after
    both replicas hold it. A candidate, never an acceptance."""
    register, _ = load_register(replica_paths)
    if not register.verified:
        raise _refuse("OWNER_REGISTER_NOT_VERIFIED", register.reason)
    stores = [load_acceptance_store(p) for p in store_paths]
    package = _canonical_json(_read_regular(Path(package_path), "PACKAGE_INVALID"), "PACKAGE_INVALID")
    envelope = _expected_envelope(stores, register, package)
    digest = OA.envelope_digest(envelope)
    document = {"candidateType": ENVELOPE_CANDIDATE_TYPE, "schemaVersion": 1, "accepted": False,
                "envelopeDigest": digest, "envelope": envelope, "package": package}
    try:
        _write_new_file(Path(out), json.dumps(document, indent=1, sort_keys=True).encode("utf-8") + b"\n")
    except FileExistsError as exc:
        raise _refuse("CANDIDATE_FILE_EXISTS") from exc
    return {"status": "ENVELOPE_CANDIDATE_WRITTEN", "accepted": False, "envelopeDigest": digest,
            "freshnessRecordVersion": envelope["freshnessRecordVersion"],
            "note": "envelope candidate != acceptance evidence"}


def append_envelope(target_path, peer_path, replica_paths, candidate_path, trust_path, chain_path, pin_path, *,
                    environment: str, authority_profile: str, confirm_digest: Any) -> dict[str, Any]:
    """Ceremony steps 12–13: the owner confirms the envelope digest, then it is
    written to ONE acceptance store. Everything is re-derived first:

    - both replicas are identical and hold the bound record as their head;
    - the package is rebuilt from the prior register, the authentic chain,
      the trust inputs, the pin, and the record, and must be identical;
    - for ACCEPT_CURRENT, the chain classifies AUTHENTIC + CURRENT now;
    - the envelope is rebuilt and must be identical.

    Real-profile writes are blocked while P3-3 is incomplete.
    """
    block = OA.real_acceptance_block(authority_profile)
    if block is not None:
        raise _refuse("REAL_ACCEPTANCE_DISABLED", block)
    value = _input_json(Path(candidate_path), "ENVELOPE_CANDIDATE_MALFORMED")
    if not isinstance(value, dict) or set(value) != ENVELOPE_CANDIDATE_FIELDS \
            or value["candidateType"] != ENVELOPE_CANDIDATE_TYPE or value["accepted"] is not False \
            or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise _refuse("ENVELOPE_CANDIDATE_MALFORMED")
    try:
        digest = OA.envelope_digest(value["envelope"])
    except (OwnerProofError, TypeError) as exc:
        raise _refuse("ENVELOPE_CANDIDATE_MALFORMED", "ENVELOPE") from exc
    if digest != value["envelopeDigest"]:
        raise _refuse("ENVELOPE_CANDIDATE_MALFORMED", "DIGEST")
    if not isinstance(confirm_digest, str) or not confirm_digest:
        raise _refuse("OWNER_CONFIRMATION_REQUIRED")
    if confirm_digest != digest:
        raise _refuse("OWNER_CONFIRMATION_MISMATCH")
    register, replicas = load_register(replica_paths)
    if not register.verified:
        raise _refuse("OWNER_REGISTER_NOT_VERIFIED", register.reason)
    if (register.facts.environment, register.facts.authority_profile) != (environment, authority_profile):
        raise _refuse("PROFILE_MISMATCH")
    target, peer = load_acceptance_store(target_path), load_acceptance_store(peer_path)
    if {target.custody_copy_id, peer.custody_copy_id} != {r.replica_id for r in replicas} \
            or target.custody_copy_id == peer.custody_copy_id:
        raise _refuse("ACCEPTANCE_STORES_NOT_PAIRED_WITH_REPLICAS")
    if os.path.samefile(target.path, peer.path):
        raise _refuse("ACCEPTANCE_STORE_SAME_LOCATION")
    if peer.digests == target.digests:
        replication = "PEER_PENDING"
    elif peer.digests == target.digests + (digest,):
        replication = "COPIES_IDENTICAL"
    else:
        raise _refuse("ACCEPTANCE_STORES_NOT_APPENDABLE")
    records = register.facts.records
    trust = load_trust(trust_path)
    chain = verify_chain(trust, chain_path, environment)
    try:
        package = OA.build_review_package(
            prior_records=[r.to_dict() for r in records[:-1]], chain=chain, candidate_record=records[-1].to_dict(),
            trust_document=_input_json(Path(trust_path), "TRUST_INPUTS_INVALID"),
            pin=_input_json(Path(pin_path), "GENESIS_PIN_INVALID"), replica_ids=[r.replica_id for r in replicas],
            environment=environment, authority_profile=authority_profile,
            attached_evidence=value["package"].get("attachedEvidence", {}) if isinstance(value["package"], dict)
            else {})
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise _refuse("PACKAGE_NOT_REPRODUCIBLE", str(exc)) from exc
    if package != value["package"]:
        raise _refuse("PACKAGE_NOT_REPRODUCIBLE", "PACKAGE_DIFFERS")
    if records[-1].decision == OF.ACCEPT_CURRENT:
        now = OF.classify_presented_world(register=register, chain=chain, environment=environment,
                                          authority_profile=authority_profile)
        if not now.current:
            raise _refuse("FRESHNESS_NOT_CURRENT", f"{now.freshness}:{now.reason}")
    if _expected_envelope([target], register, package) != value["envelope"]:
        raise _refuse("ENVELOPE_NOT_DERIVABLE")
    bundle = {"envelope": value["envelope"], "package": package}
    version = value["envelope"]["freshnessRecordVersion"]
    directory = target.path / ENVELOPES
    published = _publish(directory, f"{version:06d}-{digest}.json", OF.record_bytes(bundle),
                         exists_reason="ENVELOPE_EXISTS", owner=target.path)
    fsync = published["directoryFsync"]
    if load_acceptance_store(target.path).digests != target.digests + (digest,):
        raise _refuse("POST_WRITE_VERIFICATION_FAILED")
    return {"status": "ENVELOPE_APPENDED", "custodyCopyId": target.custody_copy_id, "freshnessRecordVersion": version,
            "envelopeDigest": digest, "replication": replication, "directoryFsync": fsync,
            "publicationBackend": published["backend"]}


# ---------------------------------------------------------------------- CLI ---

EXIT_OK, EXIT_USAGE, EXIT_REFUSED = 0, 2, 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="owner_freshness_tool", description="Offline owner freshness tooling "
                                     "(B1b-3e PR-3 P3-2). No network, DEV, cloud, Git, or key access.")
    sub = parser.add_subparsers(dest="command", required=True)

    def world(p, replicas=True, pin=False, out=False):
        if replicas:
            p.add_argument("--replica", action="append", required=True, help="owner replica directory (twice)")
        p.add_argument("--trust", required=True, help="pinned trust inputs JSON")
        p.add_argument("--chain", required=True, help="exported witness chain JSON array, genesis first")
        p.add_argument("--environment", required=True)
        p.add_argument("--profile", required=True, choices=sorted(OF.PROFILE_ENVIRONMENTS))
        if pin:
            p.add_argument("--pin", required=True, help="OwnerGenesisPinV1 JSON")
        if out:
            p.add_argument("--out", required=True, help="new candidate file (must not exist)")

    p = sub.add_parser("init-replica")
    p.add_argument("--replica", required=True)
    p.add_argument("--replica-id", required=True)
    p.add_argument("--environment", required=True)
    p.add_argument("--profile", required=True, choices=sorted(OF.PROFILE_ENVIRONMENTS))
    p = sub.add_parser("init-real-replica", help="P3-3 gated initialization of a REAL owner replica")
    p.add_argument("--replica", required=True)
    p.add_argument("--replica-id", required=True)
    p.add_argument("--environment", required=True)
    p.add_argument("--profile", required=True, choices=sorted(OF.PROFILE_ENVIRONMENTS))
    p.add_argument("--other-replica", help="the already-initialized other real replica, if any")
    p = sub.add_parser("probe-storage", help="P3-3 filesystem capability probe (temporary files only)")
    p.add_argument("--probe-parent", required=True)
    p = sub.add_parser("location-check")
    p.add_argument("--path", required=True)
    p = sub.add_parser("check-independence")
    p.add_argument("--replica", action="append", required=True)
    p = sub.add_parser("init-acceptance-store", help="P3-6 sibling acceptance-evidence store (empty)")
    p.add_argument("--store", required=True)
    p.add_argument("--custody-copy-id", required=True, help="the paired replica's replicaId")
    p.add_argument("--environment", required=True)
    p.add_argument("--profile", required=True, choices=sorted(OF.PROFILE_ENVIRONMENTS))
    p = sub.add_parser("verify-acceptance-store")
    p.add_argument("--store", required=True)
    p = sub.add_parser("build-review-package", help="P3-6 ceremony step 1 (before the append)")
    world(p, pin=True, out=True)
    p.add_argument("--candidate", required=True, help="the freshness record candidate")
    p.add_argument("--evidence", action="append", default=[], help="NAME=SHA256 of owner-held evidence")
    p = sub.add_parser("propose-envelope", help="P3-6 ceremony step 11 (after both replicas hold the record)")
    p.add_argument("--replica", action="append", required=True)
    p.add_argument("--store", action="append", required=True)
    p.add_argument("--package", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("append-envelope", help="P3-6 ceremony steps 12-13, into ONE store")
    world(p, replicas=True, pin=True)
    p.add_argument("--store", required=True, help="the ONE acceptance store to write")
    p.add_argument("--peer-store", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--confirm-digest", required=True, help="the envelopeDigest, repeated by the owner")
    p = sub.add_parser("classify-acceptance")
    p.add_argument("--replica", action="append", required=True)
    p.add_argument("--store", action="append", required=True)
    p.add_argument("--pin", required=True)
    p = sub.add_parser("inspect-chain")
    world(p, replicas=False)
    p = sub.add_parser("verify-replica")
    p.add_argument("--replica", required=True)
    p = sub.add_parser("compare-replicas")
    p.add_argument("--replica", action="append", required=True)
    world(sub.add_parser("classify"))
    world(sub.add_parser("propose-genesis"), replicas=False, pin=True, out=True)
    world(sub.add_parser("propose-accept"), pin=True, out=True)
    world(sub.add_parser("propose-reject"), pin=True, out=True)
    p = sub.add_parser("append")
    world(p, replicas=False, pin=True)
    p.add_argument("--replica", required=True, help="the ONE replica to write")
    p.add_argument("--peer", required=True, help="the other replica (read only)")
    p.add_argument("--candidate", required=True)
    p.add_argument("--confirm-digest", required=True, help="the candidate recordDigest, repeated by the owner")
    return parser


def run(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit:
        return EXIT_USAGE, {"status": "USAGE"}
    try:
        command = args.command
        if command == "init-replica":
            return EXIT_OK, init_replica(args.replica, replica_id=args.replica_id, environment=args.environment,
                                         authority_profile=args.profile)
        if command == "init-acceptance-store":
            return EXIT_OK, init_acceptance_store(args.store, custody_copy_id=args.custody_copy_id,
                                                  environment=args.environment, authority_profile=args.profile)
        if command == "verify-acceptance-store":
            store = load_acceptance_store(args.store)
            return EXIT_OK, {"status": "ACCEPTANCE_STORE_VERIFIED", "custodyCopyId": store.custody_copy_id,
                             "envelopes": len(store.bundles)}
        if command == "classify-acceptance":
            return EXIT_OK, classify_acceptance_state(args.replica, args.store, args.pin)
        if command == "propose-envelope":
            return EXIT_OK, propose_envelope(args.replica, args.store, args.package, args.out)
        if command == "build-review-package":
            evidence = {}
            for item in args.evidence:
                name, sep, value = item.partition("=")
                if not sep or name in evidence:
                    return EXIT_USAGE, {"status": "USAGE"}
                evidence[name] = value
            return EXIT_OK, build_package(args.replica, args.trust, args.chain, args.pin, args.candidate, args.out,
                                          environment=args.environment, authority_profile=args.profile,
                                          evidence=evidence)
        if command == "append-envelope":
            return EXIT_OK, append_envelope(args.store, args.peer_store, args.replica, args.candidate, args.trust,
                                            args.chain, args.pin, environment=args.environment,
                                            authority_profile=args.profile, confirm_digest=args.confirm_digest)
        if command == "init-real-replica":
            return EXIT_OK, init_real_replica(args.replica, replica_id=args.replica_id,
                                              environment=args.environment, authority_profile=args.profile,
                                              other_replica=args.other_replica)
        if command == "probe-storage":
            result = probe_storage(args.probe_parent)
            return (EXIT_OK if result["result"] == P3_STORAGE_CAPABLE else EXIT_REFUSED), result
        if command == "location-check":
            return EXIT_OK, location_policy(args.path)
        if command == "check-independence":
            if len(args.replica) != 2:
                return EXIT_USAGE, {"status": "USAGE"}
            return EXIT_OK, check_independence(*args.replica)
        if command == "verify-replica":
            replica = load_replica(args.replica)
            return EXIT_OK, {"status": "REPLICA_VERIFIED", "replicaId": replica.replica_id,
                             "records": len(replica.records),
                             "headDigest": replica.digests[-1] if replica.records else None}
        if command == "compare-replicas":
            result = compare_replicas(args.replica)
            return (EXIT_OK if result["status"] == OF.REGISTER_VERIFIED else EXIT_REFUSED), result
        trust = load_trust(args.trust)
        if command == "inspect-chain":
            result = inspect_chain(trust, args.chain, args.environment)
            return (EXIT_OK if result["authenticity"] == OF.AUTHENTIC else EXIT_REFUSED), result
        if command == "classify":
            return EXIT_OK, classify(args.replica, trust, args.chain, environment=args.environment,
                                     authority_profile=args.profile)
        if command == "propose-genesis":
            return EXIT_OK, propose_genesis(trust, args.chain, args.pin, args.out, environment=args.environment,
                                            authority_profile=args.profile)
        if command in ("propose-accept", "propose-reject"):
            decision = OF.ACCEPT_CURRENT if command == "propose-accept" else OF.REJECT_CANDIDATE
            return EXIT_OK, propose(decision, args.replica, trust, args.chain, args.pin, args.out,
                                    environment=args.environment, authority_profile=args.profile)
        if command == "append":
            return EXIT_OK, append(args.replica, args.peer, args.candidate, trust, args.chain, args.pin,
                                   environment=args.environment, authority_profile=args.profile,
                                   confirm_digest=args.confirm_digest)
    except ToolRefusal as refusal:
        return EXIT_REFUSED, {"status": "REFUSED", "reason": refusal.reason, "detail": refusal.detail}
    except (ContractViolation, OwnerProofError) as exc:
        return EXIT_REFUSED, {"status": "REFUSED", "reason": "CONTRACT_VIOLATION", "detail": str(exc)}
    except OSError as exc:
        return EXIT_REFUSED, {"status": "REFUSED", "reason": "IO_ERROR", "detail": type(exc).__name__}
    return EXIT_USAGE, {"status": "USAGE"}


def main(argv: Sequence[str] | None = None) -> int:
    code, result = run(sys.argv[1:] if argv is None else argv)
    sys.stdout.write(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
