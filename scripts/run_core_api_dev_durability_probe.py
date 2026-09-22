#!/usr/bin/env python3
"""Trusted persistent-DEV durability probe for the exact deployed candidate.

This control intentionally contains no canonical runtime implementation.  It
loads the exact installed candidate package, creates synthetic state only in
the isolated DEV paths, proves a new process can read that state after the
sanctioned service restart, and then tears the dedicated probe state down.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Optional

try:
    import grp
    import pwd
except ImportError:  # Windows-only local control tests.
    grp = None
    pwd = None


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_SCHEMA_FINGERPRINT = (
    "ceadab225a2ef8ecb713f5e0d78a303161713af223b26480775c56ec1544d229"
)
APP_ROOT = Path("/home/lilith/.hermes/lilith-os-dev")
DEV_HERMES_ROOT = Path("/home/lilith/.hermes-dev")
DATA_DIR = APP_ROOT / "data"
COGNITIVE_DB = DATA_DIR / "cognitive_memory.dev.db"
PRIVACY_DB = DATA_DIR / "privacy_governance.dev.db"
DEFAULT_CONFIG_PATH = DATA_DIR / "canonical-runtime.json"
PRODUCTION_COGNITIVE_DB = Path(
    "/home/lilith/.hermes/lilith-os/data/cognitive_memory.db"
)
PRODUCTION_PRIVACY_DB = Path(
    "/home/lilith/.hermes/lilith-os/data/privacy_governance.db"
)
PROBE_DIR = DATA_DIR / "canonical-durability-probe"
MARKER_PATH = PROBE_DIR / "owned-probe.json"
STATE_PATH = PROBE_DIR / "pre-restart-state.json"
PROBE_CONFIG_PATH = PROBE_DIR / "canonical-runtime.probe.json"
CONTAINMENT_PATH = PROBE_DIR / "legacy-containment.probe.json"
ACTOR_SECRET_PATH = PROBE_DIR / "actor-authority.probe.key"
PRIVACY_SECRET_PATH = PROBE_DIR / "privacy-authority.probe.key"
CONTAINMENT_SECRET_PATH = PROBE_DIR / "containment.probe.key"
BACKUP_DIR = PROBE_DIR / "backups"

TEST_CLASS = "SYNTHETIC_PROJECT_CODENAME_FACT"
TEST_NAMESPACE = "project.synthetic"
TEST_KEY = "codename"
EXPECTED_OWNER = "lilith"
EXPECTED_GROUP = "lilith"

CANONICAL_TABLES = (
    "learning_memory_intent_v2",
    "learning_candidate_v2",
    "learning_project_codename_candidate_v1",
    "learning_candidate_source_v2",
    "learning_assessment_v2",
    "learning_proposal_ref",
    "learning_proposal_v2",
    "memory_registry_entry",
    "memory_item",
    "memory_revision",
    "memory_revision_source",
    "memory_active_revision",
    "memory_admission",
    "memory_apply_audit",
    "actor_evidence_ref",
    "actor_evidence_consumption",
    "consent_grant",
    "consent_revocation",
    "policy_decision",
    "rollback_authorization",
    "rollback_consumption",
)

LEGACY_TARGETS = {
    "memory": (
        DEV_HERMES_ROOT / "MEMORY.md",
        DEV_HERMES_ROOT / "memories" / "MEMORY.md",
    ),
    "user": (
        DEV_HERMES_ROOT / "USER.md",
        DEV_HERMES_ROOT / "memories" / "USER.md",
    ),
    "skills": (DEV_HERMES_ROOT / "skills",),
    "pending": (
        DEV_HERMES_ROOT / "pending",
        DEV_HERMES_ROOT / "memories" / "pending",
    ),
    "backgroundReview": (
        DEV_HERMES_ROOT / "background-review",
        DEV_HERMES_ROOT / "background_review",
    ),
    "world": (DEV_HERMES_ROOT / "world",),
    "goals": (DEV_HERMES_ROOT / "goals",),
    "soul": (DEV_HERMES_ROOT / "SOUL.md",),
    "personalization": (DEV_HERMES_ROOT / "personalization",),
    "promptContext": (
        DEV_HERMES_ROOT / "prompts",
        DEV_HERMES_ROOT / "context",
    ),
}


class ProbeError(RuntimeError):
    """Fail-closed durability-probe error."""


@dataclass(frozen=True)
class ProbePaths:
    app_root: Path
    data_dir: Path
    cognitive_db: Path
    privacy_db: Path
    production_cognitive_db: Path
    production_privacy_db: Path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _reject_symlink_chain(root: Path, target: Path) -> None:
    root_value = Path(os.path.abspath(root))
    target_value = Path(os.path.abspath(target))
    if not _is_relative_to(target_value, root_value):
        raise ProbeError("probe path is outside the isolated DEV root")
    for ancestor in (root_value, *root_value.parents):
        if ancestor.is_symlink():
            raise ProbeError(f"probe root traverses a symlink: {ancestor}")
    current = root_value
    for part in target_value.relative_to(root_value).parts:
        current = current / part
        if current.is_symlink():
            raise ProbeError(f"probe path may not traverse a symlink: {current}")


def _same_file(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and os.path.samefile(left, right)


def guard_probe_paths(
    app_root: Path,
    data_dir: Path,
    cognitive_db: Path,
    privacy_db: Path,
    production_cognitive_db: Path,
    production_privacy_db: Path,
) -> ProbePaths:
    """Resolve and reject production, external, symlinked, or aliased paths."""

    for candidate in (data_dir, cognitive_db, privacy_db):
        if Path(candidate) in (Path(production_cognitive_db), Path(production_privacy_db)):
            raise ProbeError("probe path resolves to a production database")
    for candidate in (data_dir, cognitive_db, privacy_db):
        _reject_symlink_chain(Path(app_root), Path(candidate))
    root = Path(app_root).resolve(strict=False)
    data = Path(data_dir).resolve(strict=False)
    cognitive = Path(cognitive_db).resolve(strict=False)
    privacy = Path(privacy_db).resolve(strict=False)
    production_cognitive = Path(production_cognitive_db).resolve(strict=False)
    production_privacy = Path(production_privacy_db).resolve(strict=False)
    if cognitive in {production_cognitive, production_privacy}:
        raise ProbeError("cognitive DEV database resolves to a production database")
    if privacy in {production_cognitive, production_privacy}:
        raise ProbeError("privacy DEV database resolves to a production database")
    if not _is_relative_to(data, root) or not _is_relative_to(cognitive, data):
        raise ProbeError("cognitive DEV database is outside the isolated DEV root")
    if not _is_relative_to(privacy, data):
        raise ProbeError("privacy DEV database is outside the isolated DEV root")
    if cognitive == privacy:
        raise ProbeError("cognitive and privacy databases must be physically separate")
    if _same_file(data, production_cognitive.parent) or _same_file(
        data, production_privacy.parent
    ):
        raise ProbeError("DEV data directory aliases the production data directory")
    for candidate in (cognitive, privacy):
        for production in (production_cognitive, production_privacy):
            if _same_file(candidate, production):
                raise ProbeError("DEV database aliases a production database")
    return ProbePaths(
        app_root=root,
        data_dir=data,
        cognitive_db=cognitive,
        privacy_db=privacy,
        production_cognitive_db=production_cognitive,
        production_privacy_db=production_privacy,
    )


def default_probe_paths() -> ProbePaths:
    return guard_probe_paths(
        APP_ROOT,
        DATA_DIR,
        COGNITIVE_DB,
        PRIVACY_DB,
        PRODUCTION_COGNITIVE_DB,
        PRODUCTION_PRIVACY_DB,
    )


def assert_clean_baseline(paths: ProbePaths, probe_dir: Path = PROBE_DIR) -> dict:
    unexpected = [
        str(path)
        for path in (paths.cognitive_db, paths.privacy_db, Path(probe_dir))
        if path.exists() or path.is_symlink()
    ]
    for database in (paths.cognitive_db, paths.privacy_db):
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(database) + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                unexpected.append(str(sidecar))
    if unexpected:
        raise ProbeError(
            "unexpected persistent DEV probe state exists: " + ", ".join(unexpected)
        )
    return {
        "cognitive": {"path": str(paths.cognitive_db), "exists": False},
        "privacy": {"path": str(paths.privacy_db), "exists": False},
        "probeDirectory": {"path": str(probe_dir), "exists": False},
    }


def _ensure_owner_only(path: Path, *, directory: bool = False) -> None:
    if path.is_symlink():
        raise ProbeError(f"owner-only probe path may not be a symlink: {path}")
    details = path.lstat()
    if directory and not stat.S_ISDIR(details.st_mode):
        raise ProbeError(f"owner-only probe directory is not a directory: {path}")
    if not directory and not stat.S_ISREG(details.st_mode):
        raise ProbeError(f"owner-only probe file is not a regular file: {path}")
    expected = 0o700 if directory else 0o600
    mode = stat.S_IMODE(details.st_mode)
    if os.name != "nt" and mode != expected:
        raise ProbeError(f"unsafe permissions for {path}: {oct(mode)}")
    if hasattr(os, "geteuid") and details.st_uid != os.geteuid():
        raise ProbeError(f"unexpected owner for {path}")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    _ensure_owner_only(path)


def _load_json(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ProbeError(f"JSON document is not an object: {path}")
    return raw


def _file_metadata(path: Path) -> dict:
    details = path.stat()
    try:
        owner = pwd.getpwuid(details.st_uid).pw_name if pwd is not None else None
    except (KeyError, AttributeError):
        owner = None
    try:
        group = grp.getgrgid(details.st_gid).gr_name if grp is not None else None
    except (KeyError, AttributeError):
        group = None
    return {
        "path": str(path),
        "exists": True,
        "identity": f"{details.st_dev}:{details.st_ino}",
        "sha256": _sha256_file(path),
        "byteSize": details.st_size,
        "uid": getattr(details, "st_uid", None),
        "gid": getattr(details, "st_gid", None),
        "owner": owner,
        "group": group,
        "mode": format(stat.S_IMODE(details.st_mode), "04o"),
    }


def _sqlite_evidence(path: Path, tables: Iterable[str]) -> dict:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        existing = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        counts = {
            name: int(
                connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            )
            if name in existing
            else None
            for name in tables
        }
        return {
            **_file_metadata(path),
            "integrityCheck": str(
                connection.execute("PRAGMA integrity_check").fetchone()[0]
            ),
            "foreignKeyViolations": len(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            ),
            "counts": counts,
        }
    finally:
        connection.close()


def _checkpoint(path: Path) -> None:
    connection = sqlite3.connect(str(path), timeout=5.0)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()


def _default_config_evidence() -> dict:
    if not DEFAULT_CONFIG_PATH.is_file() or DEFAULT_CONFIG_PATH.is_symlink():
        raise ProbeError("default DEV canonical configuration is unavailable or unsafe")
    raw = _load_json(DEFAULT_CONFIG_PATH)
    expected = {
        "schemaVersion": 1,
        "canonicalLtmEnabled": False,
        "activeCapabilities": [],
    }
    if raw != expected:
        raise ProbeError("default DEV canonical configuration is not dark")
    evidence = _file_metadata(DEFAULT_CONFIG_PATH)
    if os.name != "nt" and evidence["mode"] != "0600":
        raise ProbeError("default DEV canonical configuration is not mode 0600")
    return evidence


def _service_process_evidence(pid: int, release: Path) -> dict:
    process = Path("/proc") / str(pid)
    if not process.is_dir():
        raise ProbeError("post-restart DEV service process is unavailable")
    environment = {}
    for item in (process / "environ").read_bytes().split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        if key.decode("utf-8", "strict") in {
            "LILITH_ENV",
            "LILITH_COGNITIVE_DB_PATH",
            "LILITH_PRIVACY_DB_PATH",
            "LILITH_CANONICAL_CONFIG_FILE",
        }:
            environment[key.decode("utf-8")] = value.decode("utf-8", "strict")
    expected = {
        "LILITH_ENV": "dev",
        "LILITH_COGNITIVE_DB_PATH": str(COGNITIVE_DB),
        "LILITH_PRIVACY_DB_PATH": str(PRIVACY_DB),
        "LILITH_CANONICAL_CONFIG_FILE": str(DEFAULT_CONFIG_PATH),
    }
    if environment != expected:
        raise ProbeError("post-restart DEV service database/config environment changed")
    cwd = Path(os.readlink(process / "cwd")).resolve(strict=True)
    if cwd != release:
        raise ProbeError("post-restart DEV service is not running from the candidate release")
    return {"pid": pid, "workingDirectory": str(cwd), "environment": environment}


def _runtime(candidate_sha: str) -> SimpleNamespace:
    if not SHA_RE.fullmatch(candidate_sha):
        raise ProbeError("candidate SHA is invalid")
    current = APP_ROOT / "current"
    if not current.is_symlink():
        raise ProbeError("DEV current release is not an atomic symlink")
    release = current.resolve(strict=True)
    expected_release = (APP_ROOT / "releases" / candidate_sha).resolve(strict=False)
    if release != expected_release:
        raise ProbeError("DEV current release does not match the candidate SHA")
    manifest_path = release / "deployment-manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("candidateSha") != candidate_sha:
        raise ProbeError("deployment manifest candidate SHA mismatch")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ProbeError("deployment manifest file list is unavailable")
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "byteSize"}:
            raise ProbeError("deployment manifest file record is malformed")
        unresolved = release / str(item["path"])
        if unresolved.is_symlink():
            raise ProbeError("deployed manifest path is a symlink")
        target = unresolved.resolve(strict=True)
        if not _is_relative_to(target, release):
            raise ProbeError("deployed manifest path is unsafe")
        if target.stat().st_size != item["byteSize"] or _sha256_file(target) != item[
            "sha256"
        ]:
            raise ProbeError(f"deployed file digest mismatch: {item['path']}")
    sys.path.insert(0, str(release))
    from lilith_memory import backup
    from lilith_memory import canonical_authority as authority
    from lilith_memory import canonical_contracts as contracts
    from lilith_memory import canonical_migration
    from lilith_memory import canonical_store
    from lilith_memory import config
    from lilith_memory import learning_v2
    from lilith_memory import memory_store
    from lilith_memory import memory_v2
    from lilith_memory import privacy_governance
    from lilith_memory import registry_loader
    from lilith_memory import slice15b2a_migration

    modules = (
        backup,
        authority,
        contracts,
        canonical_migration,
        canonical_store,
        config,
        learning_v2,
        memory_store,
        memory_v2,
        privacy_governance,
        registry_loader,
        slice15b2a_migration,
    )
    if any(
        not _is_relative_to(Path(module.__file__).resolve(strict=True), release)
        for module in modules
    ):
        raise ProbeError("durability probe imported code outside the exact release")
    return SimpleNamespace(
        release=release,
        manifest=manifest,
        backup=backup,
        authority=authority,
        contracts=contracts,
        canonical_migration=canonical_migration,
        canonical_store=canonical_store,
        config=config,
        learning_v2=learning_v2,
        memory_store=memory_store,
        memory_v2=memory_v2,
        privacy_governance=privacy_governance,
        registry_loader=registry_loader,
        slice15b2a_migration=slice15b2a_migration,
    )


def _target_record(path: Path, synthetic_token: bytes) -> dict:
    if not path.exists() and not path.is_symlink():
        return {"path": str(path), "exists": False, "tokenFound": False}
    if path.is_symlink():
        return {
            "path": str(path),
            "exists": True,
            "kind": "symlink",
            "target": os.readlink(path),
            "tokenFound": False,
        }
    digest = hashlib.sha256()
    token_found = False
    file_count = 0
    values = [path] if path.is_file() else sorted(
        value for value in path.rglob("*") if value.is_file() or value.is_symlink()
    )
    for value in values:
        relative = value.name if path.is_file() else value.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        if value.is_symlink():
            digest.update(b"SYMLINK\0" + os.readlink(value).encode("utf-8"))
            continue
        content = value.read_bytes()
        file_count += 1
        digest.update(content)
        token_found = token_found or synthetic_token in content
    return {
        "path": str(path),
        "exists": True,
        "kind": "file" if path.is_file() else "directory",
        "treeSha256": digest.hexdigest(),
        "fileCount": file_count,
        "tokenFound": token_found,
    }


def legacy_snapshot(synthetic_value: str) -> dict:
    token = synthetic_value.encode("utf-8")
    categories = {
        name: [_target_record(path, token) for path in paths]
        for name, paths in LEGACY_TARGETS.items()
    }
    return {
        "root": str(DEV_HERMES_ROOT),
        "categories": categories,
        "tokenFound": any(
            item["tokenFound"]
            for records in categories.values()
            for item in records
        ),
    }


def _legacy_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("categories") == right.get("categories")


def _create_secret(runtime: SimpleNamespace, path: Path) -> None:
    runtime.authority.create_owner_only_secret(path)
    _ensure_owner_only(path)


def _policy(runtime: SimpleNamespace) -> Any:
    return runtime.memory_v2.MemoryTuplePolicyV1(
        memory_class=TEST_CLASS,
        subject_namespace=TEST_NAMESPACE,
        subject_key=TEST_KEY,
        value_schema=runtime.learning_v2.VALUE_SCHEMA,
        capability=runtime.contracts.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
        read_allowed=True,
        write_allowed=True,
    )


def _install_registry(runtime: SimpleNamespace, database: Path, policy: Any) -> None:
    connection = sqlite3.connect(str(database), timeout=5.0)
    try:
        connection.execute(
            "INSERT INTO memory_registry_entry VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "registry.dev.durability.v1",
                1,
                policy.memory_class,
                policy.subject_namespace,
                policy.subject_key,
                policy.value_schema,
                policy.capability,
                1,
                1,
                1,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _authorities(runtime: SimpleNamespace) -> SimpleNamespace:
    loaded_config = runtime.config.load(PROBE_CONFIG_PATH)
    if not loaded_config.canonical_ltm_enabled or not loaded_config.capability_active(
        runtime.contracts.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE
    ):
        raise ProbeError("synthetic DEV probe configuration did not activate exactly")
    policy = _policy(runtime)
    registry = runtime.registry_loader.GovernedRegistryLoader(
        COGNITIVE_DB,
        approved_policies=(policy,),
        allowed_memory_classes=frozenset({TEST_CLASS}),
    ).load()
    containment_secret = runtime.authority.load_owner_only_secret(
        CONTAINMENT_SECRET_PATH
    )
    containment = runtime.registry_loader.load_containment(
        CONTAINMENT_PATH,
        secret=containment_secret,
        canonical_registry=registry,
    )
    actor = runtime.authority.LocalOwnerAuthority.from_secret_file(
        COGNITIVE_DB, ACTOR_SECRET_PATH
    )
    policy_store = runtime.authority.MemoryPolicyStore(
        COGNITIVE_DB,
        actor,
        active_capabilities=loaded_config.active_capabilities,
    )
    consent = runtime.authority.ConsentStore(
        COGNITIVE_DB, actor, policy_store=policy_store
    )
    rollback = runtime.authority.RollbackAuthority(
        COGNITIVE_DB, actor, consent
    )
    privacy = runtime.privacy_governance.PrivacyGovernanceStore.from_secret_file(
        PRIVACY_DB, PRIVACY_SECRET_PATH, actor
    )
    learning = runtime.learning_v2.LearningV2Store(
        COGNITIVE_DB,
        privacy_hold_resolver=privacy,
        containment_ready=lambda: containment.ready_for(
            (TEST_CLASS, TEST_NAMESPACE, TEST_KEY)
        ),
        actor_authority=actor,
        policy_store=policy_store,
        consent_store=consent,
    )
    store = runtime.canonical_store.CanonicalMemoryStoreV2(
        COGNITIVE_DB,
        learning,
        enabled_provider=lambda: loaded_config.canonical_ltm_enabled,
        capability_provider=loaded_config.capability_active,
        family_registry=runtime.memory_v2.ProposalFamilyRegistry(
            (
                runtime.learning_v2.V2_PROPOSAL_FAMILY,
                runtime.learning_v2.V1_PROPOSAL_FAMILY,
            )
        ),
        memory_registry=registry,
        containment_ready=containment.ready_for,
        actor_authority=actor,
        policy_store=policy_store,
        consent_store=consent,
        rollback_authority=rollback,
        privacy_hold_resolver=privacy,
    )
    facade = runtime.memory_v2.CanonicalMemoryReadFacade(
        store,
        registry=registry,
        consent_store=consent,
        privacy_hold_resolver=privacy,
        actor_resolver=lambda selected: selected == actor.ACTOR,
    )
    return SimpleNamespace(
        config=loaded_config,
        registry=registry,
        containment=containment,
        actor=actor,
        policy=policy_store,
        consent=consent,
        rollback=rollback,
        privacy=privacy,
        learning=learning,
        store=store,
        facade=facade,
    )


def _action(runtime: SimpleNamespace, authority: SimpleNamespace, value: str, *,
            operation: Optional[str] = None, expected: Optional[str] = None) -> tuple[Any, str]:
    selected_operation = operation or runtime.contracts.CREATE
    normalized, payload_digest = runtime.learning_v2.normalize_project_codename(
        {"codename": value}
    )
    action = runtime.contracts.FrozenMemoryActionV1(
        schema_version=1,
        actor_ref_id=authority.actor.ACTOR.actor_ref_id,
        operation=selected_operation,
        memory_class=TEST_CLASS,
        subject_namespace=TEST_NAMESPACE,
        subject_key=TEST_KEY,
        value_schema=runtime.learning_v2.VALUE_SCHEMA,
        payload_digest=payload_digest,
        expected_active_revision_id=expected,
        restore_revision_id=None,
        purpose=runtime.contracts.LONG_TERM_PERSONAL_PROJECT_RECALL,
    )
    return action, normalized


def _proposal(
    runtime: SimpleNamespace,
    authority: SimpleNamespace,
    action: Any,
    normalized: str,
    *,
    nonce: str,
) -> dict:
    evidence = authority.actor.issue(
        action=action,
        request_digest=_digest_text("request:" + nonce),
        nonce=nonce,
    )
    decision = authority.policy.decide(
        action=action,
        actor_evidence_ref_id=evidence.actor_evidence_ref_id,
        capability=runtime.contracts.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
    )
    challenge = authority.consent.create_challenge(
        action=action,
        actor_evidence_ref_id=evidence.actor_evidence_ref_id,
        policy_decision_ref_id=decision.decision_ref_id,
    )
    intent_ref_id = "intent." + nonce
    consent = authority.consent.confirm(
        challenge.challenge_id,
        action=action,
        issuer_ref="synthetic-dev-durability-probe",
        intent_ref_id=intent_ref_id,
        privacy_notice_version="privacy-v1",
    )
    intent = authority.learning.create_intent(
        action=action,
        actor_evidence_ref_id=evidence.actor_evidence_ref_id,
        normalized_value_json=normalized,
        intent_ref_id=intent_ref_id,
    )
    candidate = authority.learning.create_candidate(
        action=action,
        actor_evidence_ref_id=evidence.actor_evidence_ref_id,
        intent_ref_id=intent.intent_ref_id,
        policy_decision_ref_id=decision.decision_ref_id,
        consent_ref_id=consent.consent_id,
    )
    outcome = authority.learning.assess(candidate.candidate_id)
    if outcome != runtime.learning_v2.REAL_ELIGIBLE:
        raise ProbeError(f"synthetic candidate was not eligible: {outcome}")
    proposal, proposal_ref = authority.learning.create_proposal(
        candidate_id=candidate.candidate_id,
        action=action,
    )
    return {
        "evidence": evidence,
        "decision": decision,
        "consent": consent,
        "intent": intent,
        "candidate": candidate,
        "proposal": proposal,
        "proposalRef": proposal_ref,
    }


def _facade_read(authority: SimpleNamespace) -> dict:
    row = authority.facade.read_exact(
        actor=authority.actor.ACTOR,
        memory_class=TEST_CLASS,
        subject_namespace=TEST_NAMESPACE,
        subject_key=TEST_KEY,
    )
    if row is None:
        raise ProbeError("canonical facade returned a miss")
    return dict(row)


def _canonical_lineage(database: Path) -> dict:
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT i.memory_item_id,i.memory_class,i.subject_namespace,i.subject_key,"
            "a.revision_id,r.normalized_value_json,r.value_digest,r.epistemic_basis,"
            "r.consent_ref_id,r.verification_outcome_ref_id,r.created_from_proposal_ref_id,"
            "p.policy_decision_ref_id,p.actor_evidence_ref_id,p.candidate_id,"
            "s.source_owner,s.source_stream,s.source_record_id,s.source_schema_version,"
            "s.source_digest,s.occurred_at,s.subject_ref,"
            "m.admission_id,m.outcome AS admission_outcome,"
            "x.operation_id,x.operation,x.resulting_active_revision_id "
            "FROM memory_item i "
            "JOIN memory_active_revision a ON a.memory_item_id=i.memory_item_id "
            "JOIN memory_revision r ON r.revision_id=a.revision_id "
            "JOIN learning_proposal_ref q ON q.proposal_ref_id=r.created_from_proposal_ref_id "
            "JOIN learning_proposal_v2 p ON p.proposal_id=q.family_proposal_id "
            "JOIN memory_revision_source s ON s.revision_id=r.revision_id "
            "JOIN memory_admission m ON m.proposal_ref_id=q.proposal_ref_id "
            "JOIN memory_apply_audit x ON x.proposal_ref_id=q.proposal_ref_id "
            "WHERE i.memory_class=? AND i.subject_namespace=? AND i.subject_key=?",
            (TEST_CLASS, TEST_NAMESPACE, TEST_KEY),
        ).fetchone()
        if row is None:
            raise ProbeError("canonical SQLite lineage is unavailable")
        return dict(row)
    finally:
        connection.close()


def _assert_read_matches(read: Mapping[str, Any], lineage: Mapping[str, Any]) -> None:
    pairs = (
        ("memory_item_id", "memory_item_id"),
        ("revision_id", "revision_id"),
        ("normalized_value_json", "normalized_value_json"),
        ("value_digest", "value_digest"),
        ("consent_ref_id", "consent_ref_id"),
    )
    if any(str(read[left]) != str(lineage[right]) for left, right in pairs):
        raise ProbeError("facade output disagrees with SQLite lineage")
    if lineage.get("epistemic_basis") != "USER_ASSERTED":
        raise ProbeError("synthetic memory epistemic basis changed")
    if str(lineage.get("verification_outcome_ref_id")) != str(
        lineage.get("policy_decision_ref_id")
    ):
        raise ProbeError("revision authority reference is not the exact Policy decision")


def _marker(candidate_sha: str) -> dict:
    return {
        "schemaVersion": 1,
        "role": "lilith-core-api-dev-canonical-durability-probe",
        "candidateSha": candidate_sha,
        "cognitiveDatabase": str(COGNITIVE_DB),
        "privacyDatabase": str(PRIVACY_DB),
    }


def validate_marker(candidate_sha: str, marker_path: Optional[Path] = None) -> dict:
    selected = Path(marker_path) if marker_path is not None else MARKER_PATH
    if selected.is_symlink():
        raise ProbeError("probe ownership marker may not be a symlink")
    marker = _load_json(selected)
    if marker != _marker(candidate_sha):
        raise ProbeError("probe ownership marker does not match this candidate")
    return marker


def _mount_targets() -> set[Path]:
    mountinfo = Path("/proc/self/mountinfo")
    if not mountinfo.exists():
        return set()
    targets = set()
    for line in mountinfo.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 5:
            mountpoint = fields[4]
            for escaped, plain in (
                ("\\040", " "),
                ("\\011", "\t"),
                ("\\012", "\n"),
                ("\\134", "\\"),
            ):
                mountpoint = mountpoint.replace(escaped, plain)
            targets.add(Path(mountpoint))
    return targets


def _cleanup_inventory(paths: ProbePaths) -> list[Path]:
    """Inventory only the owned synthetic files before any deletion."""
    targets = [
        Path(str(database) + suffix)
        for database in (paths.cognitive_db, paths.privacy_db)
        for suffix in ("", "-wal", "-shm", "-journal")
    ]
    if PROBE_DIR.is_symlink():
        raise ProbeError("probe directory may not be a symlink")
    if PROBE_DIR.exists():
        _ensure_owner_only(PROBE_DIR, directory=True)
        allowed = {
            MARKER_PATH.name,
            STATE_PATH.name,
            PROBE_CONFIG_PATH.name,
            CONTAINMENT_PATH.name,
            ACTOR_SECRET_PATH.name,
            PRIVACY_SECRET_PATH.name,
            CONTAINMENT_SECRET_PATH.name,
            BACKUP_DIR.name,
        }
        if any(child.name not in allowed for child in PROBE_DIR.iterdir()):
            raise ProbeError("probe directory contains an unrelated entry")
        targets.append(PROBE_DIR)
        targets.extend(PROBE_DIR.rglob("*"))
    mounts = _mount_targets()
    if any(
        mount == paths.data_dir or _is_relative_to(mount, paths.data_dir)
        for mount in mounts
    ):
        raise ProbeError("isolated DEV probe path is a mount or bind alias")
    for target in targets:
        if target.is_symlink():
            raise ProbeError(f"synthetic cleanup target is a symlink: {target}")
        if target.exists():
            _reject_symlink_chain(paths.app_root, target)
            details = target.lstat()
            if not (stat.S_ISDIR(details.st_mode) or stat.S_ISREG(details.st_mode)):
                raise ProbeError(f"synthetic cleanup target has an unsafe type: {target}")
            if stat.S_ISREG(details.st_mode) and details.st_nlink != 1:
                raise ProbeError(f"synthetic cleanup target has an external hardlink: {target}")
            _ensure_owner_only(target, directory=stat.S_ISDIR(details.st_mode))
    return targets


def _cleanup_generated(candidate_sha: str, *, require_marker: bool) -> dict:
    if not SHA_RE.fullmatch(candidate_sha):
        raise ProbeError("candidate SHA is invalid")
    paths = default_probe_paths()
    targets = _cleanup_inventory(paths)
    existing = [target for target in targets if target.exists() or target.is_symlink()]
    if not existing:
        return {
            "phase": "cleanup",
            "status": "CLEANUP_ALREADY_COMPLETE",
            "candidateSha": candidate_sha,
            "teardownSemantics": "DEV_ENVIRONMENT_TEARDOWN_NOT_PRIVACY_ERASURE",
            "cognitiveDatabaseAbsent": True,
            "privacyDatabaseAbsent": True,
            "probeDirectoryAbsent": True,
            "unrelatedDevStateRemoved": False,
        }
    if not MARKER_PATH.is_file():
        raise ProbeError("existing synthetic DEV state lacks its ownership marker")
    _ensure_owner_only(MARKER_PATH)
    validate_marker(candidate_sha)
    for database in (paths.cognitive_db, paths.privacy_db):
        for suffix in ("", "-wal", "-shm", "-journal"):
            target = Path(str(database) + suffix)
            if target.exists():
                target.unlink()
    if PROBE_DIR.exists():
        shutil.rmtree(PROBE_DIR)
    result = {
        "phase": "cleanup",
        "status": "CLEANUP_COMPLETE",
        "candidateSha": candidate_sha,
        "teardownSemantics": "DEV_ENVIRONMENT_TEARDOWN_NOT_PRIVACY_ERASURE",
        "cognitiveDatabaseAbsent": not paths.cognitive_db.exists(),
        "privacyDatabaseAbsent": not paths.privacy_db.exists(),
        "probeDirectoryAbsent": not PROBE_DIR.exists(),
        "unrelatedDevStateRemoved": False,
    }
    if not all(
        result[key]
        for key in (
            "cognitiveDatabaseAbsent",
            "privacyDatabaseAbsent",
            "probeDirectoryAbsent",
        )
    ):
        raise ProbeError("DEV durability probe cleanup was incomplete")
    return result


def prepare(candidate_sha: str, pre_restart_pid: int) -> dict:
    paths = default_probe_paths()
    baseline = assert_clean_baseline(paths)
    default_config = _default_config_evidence()
    if pre_restart_pid <= 0:
        raise ProbeError("DEV service had no pre-restart PID")
    runtime = _runtime(candidate_sha)
    directory_created = False
    marker_created = False
    try:
        PROBE_DIR.mkdir(parents=True, mode=0o700)
        directory_created = True
        os.chmod(PROBE_DIR, 0o700)
        BACKUP_DIR.mkdir(mode=0o700)
        os.chmod(BACKUP_DIR, 0o700)
        _ensure_owner_only(PROBE_DIR, directory=True)
        _ensure_owner_only(BACKUP_DIR, directory=True)
        _atomic_json(MARKER_PATH, _marker(candidate_sha))
        marker_created = True

        runtime.memory_store.assert_isolated_test_database(
            paths.cognitive_db, paths.production_cognitive_db
        )
        runtime.config.assert_nonproduction_database(
            paths.cognitive_db,
            production_path=paths.production_cognitive_db,
            environment="dev",
        )
        runtime.config.assert_nonproduction_database(
            paths.privacy_db,
            production_path=paths.production_privacy_db,
            environment="dev",
        )

        legacy_before = legacy_snapshot("SYNTHETIC-DEV-DURABILITY")
        runtime.memory_store.migrate(
            paths.cognitive_db,
            production_path=paths.production_cognitive_db,
        )
        os.chmod(paths.cognitive_db, 0o600)
        pre_b2a = runtime.memory_store.create_verified_backup(
            paths.cognitive_db, BACKUP_DIR / "cognitive.pre-15b2a.db"
        )
        runtime.slice15b2a_migration.migrate_cognitive(
            paths.cognitive_db,
            verified_backup=pre_b2a,
            production_path=paths.cognitive_db,
        )
        cognitive_backup = runtime.backup.create_backup(
            paths.cognitive_db,
            BACKUP_DIR / "cognitive.pre-v2.db",
            BACKUP_DIR / "cognitive.pre-v2.manifest.json",
            role="cognitive",
        )
        runtime.backup.verify_backup(
            paths.cognitive_db, cognitive_backup, expected_role="cognitive"
        )
        migration_version, migration_fingerprint = runtime.canonical_migration.migrate(
            paths.cognitive_db, backup_manifest=cognitive_backup
        )
        if (
            migration_version != 2
            or migration_fingerprint != EXPECTED_SCHEMA_FINGERPRINT
        ):
            raise ProbeError("canonical migration version/fingerprint mismatch")
        repeat_backup = runtime.backup.create_backup(
            paths.cognitive_db,
            BACKUP_DIR / "cognitive.repeat-v2.db",
            BACKUP_DIR / "cognitive.repeat-v2.manifest.json",
            role="cognitive",
        )
        repeat = runtime.canonical_migration.migrate(
            paths.cognitive_db, backup_manifest=repeat_backup
        )
        if repeat != (migration_version, migration_fingerprint):
            raise ProbeError("canonical migration repeat was not idempotent")

        paths.privacy_db.touch(mode=0o600)
        os.chmod(paths.privacy_db, 0o600)
        privacy_backup = runtime.backup.create_backup(
            paths.privacy_db,
            BACKUP_DIR / "privacy.pre-migration.db",
            BACKUP_DIR / "privacy.pre-migration.manifest.json",
            role="privacy",
        )
        runtime.backup.verify_backup(
            paths.privacy_db, privacy_backup, expected_role="privacy"
        )
        privacy_schema, privacy_complete = runtime.slice15b2a_migration.migrate_privacy(
            paths.privacy_db
        )
        for path in (paths.cognitive_db, paths.privacy_db):
            os.chmod(path, 0o600)
            _ensure_owner_only(path)

        policy = _policy(runtime)
        _install_registry(runtime, paths.cognitive_db, policy)
        _atomic_json(
            PROBE_CONFIG_PATH,
            {
                "schemaVersion": 1,
                "canonicalLtmEnabled": True,
                "activeCapabilities": [policy.capability],
            },
        )
        synthetic_value = f"SYNTHETIC-DEV-DURABILITY-{candidate_sha[:12]}"
        normalized_value, value_digest = runtime.learning_v2.normalize_project_codename(
            {"codename": synthetic_value}
        )
        _atomic_json(
            CONTAINMENT_PATH,
            {
                "schemaVersion": 1,
                "protectedTuples": [
                    {
                        "schemaVersion": 1,
                        "memoryClass": TEST_CLASS,
                        "subjectNamespace": TEST_NAMESPACE,
                        "subjectKey": TEST_KEY,
                        "valueFingerprints": [value_digest],
                        "actionDigests": [],
                    }
                ],
            },
        )
        for secret in (
            ACTOR_SECRET_PATH,
            PRIVACY_SECRET_PATH,
            CONTAINMENT_SECRET_PATH,
        ):
            _create_secret(runtime, secret)

        authority = _authorities(runtime)
        action, normalized = _action(runtime, authority, synthetic_value)
        created_refs = _proposal(
            runtime,
            authority,
            action,
            normalized,
            nonce="durability.create." + candidate_sha[:12],
        )
        applied = authority.store.apply(
            created_refs["proposalRef"].proposal_ref_id
        )
        if applied.outcome != runtime.canonical_store.ACCEPTED:
            raise ProbeError(f"synthetic canonical CREATE failed: {applied}")
        pre_read = _facade_read(authority)
        lineage = _canonical_lineage(paths.cognitive_db)
        _assert_read_matches(pre_read, lineage)
        if pre_read["normalized_value_json"] != normalized_value:
            raise ProbeError("pre-restart canonical value mismatch")
        legacy_pre_restart = legacy_snapshot(synthetic_value)
        if (
            legacy_before["tokenFound"]
            or legacy_pre_restart["tokenFound"]
            or not _legacy_equal(legacy_before, legacy_pre_restart)
        ):
            raise ProbeError("synthetic canonical value reached a legacy DEV store")
        _checkpoint(paths.cognitive_db)
        _checkpoint(paths.privacy_db)
        cognitive_evidence = _sqlite_evidence(paths.cognitive_db, CANONICAL_TABLES)
        privacy_evidence = _sqlite_evidence(
            paths.privacy_db, runtime.privacy_governance.PRIVACY_TABLES
        )
        for evidence in (cognitive_evidence, privacy_evidence):
            if os.name != "nt" and (
                evidence["owner"] != EXPECTED_OWNER
                or evidence["group"] != EXPECTED_GROUP
                or evidence["mode"] != "0600"
            ):
                raise ProbeError("persistent DEV database owner/group/mode is unsafe")
        if (
            cognitive_evidence["integrityCheck"] != "ok"
            or cognitive_evidence["foreignKeyViolations"] != 0
            or privacy_evidence["integrityCheck"] != "ok"
            or privacy_evidence["foreignKeyViolations"] != 0
        ):
            raise ProbeError("persistent DEV database validation failed")
        state = {
            "schemaVersion": 1,
            "candidateSha": candidate_sha,
            "releasePath": str(runtime.release),
            "preRestartPid": pre_restart_pid,
            "syntheticValue": synthetic_value,
            "subjectTuple": [TEST_CLASS, TEST_NAMESPACE, TEST_KEY],
            "migration": {
                "version": migration_version,
                "schemaFingerprint": migration_fingerprint,
                "repeat": list(repeat),
                "privacySchemaFingerprint": privacy_schema,
                "privacyCompleteFingerprint": privacy_complete,
                "cognitiveBackup": asdict(cognitive_backup),
                "privacyBackup": asdict(privacy_backup),
            },
            "baseline": baseline,
            "defaultDevConfig": default_config,
            "create": {
                "memoryItemId": applied.memory_item_id,
                "activeRevisionId": applied.active_revision_id,
                "proposalRefId": created_refs["proposalRef"].proposal_ref_id,
                "revisionDigest": _digest_text(
                    str(lineage["revision_id"]) + ":" + str(lineage["value_digest"])
                ),
                "normalizedValueDigest": lineage["value_digest"],
                "actorEvidenceRefId": created_refs[
                    "evidence"
                ].actor_evidence_ref_id,
                "policyDecisionRefId": created_refs["decision"].decision_ref_id,
                "consentRefId": created_refs["consent"].consent_id,
                "admissionId": lineage["admission_id"],
                "operationId": lineage["operation_id"],
                "epistemicBasis": lineage["epistemic_basis"],
            },
            "preRestartFacadeRead": pre_read,
            "preRestartLineage": lineage,
            "cognitiveDatabase": cognitive_evidence,
            "privacyDatabase": privacy_evidence,
            "legacyBaseline": legacy_before,
            "legacyPreRestart": legacy_pre_restart,
            "facadeExplanation": {
                "boundary": "CanonicalMemoryReadFacade.read_exact",
                "source": "persistent SQLite active revision and exact Consent",
                "legacyFallback": False,
                "worldLookup": False,
                "promptOrContextFallback": False,
            },
        }
        _atomic_json(STATE_PATH, state)
        result = {
            "phase": "pre-restart",
            "candidateSha": candidate_sha,
            "releasePath": str(runtime.release),
            "preRestartPid": pre_restart_pid,
            "databasePaths": [str(paths.cognitive_db), str(paths.privacy_db)],
            "migration": state["migration"],
            "create": state["create"],
            "facadeRead": pre_read,
            "lineage": lineage,
            "legacyStoresUnchanged": True,
            "truthOwnership": "USER_ASSERTED",
        }
        print(json.dumps(result, sort_keys=True))
        return result
    except Exception:
        if marker_created:
            try:
                _cleanup_generated(candidate_sha, require_marker=True)
            except Exception as cleanup_error:
                print(
                    json.dumps(
                        {"phase": "failed-cleanup", "error": str(cleanup_error)},
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
        elif directory_created:
            for database in (paths.cognitive_db, paths.privacy_db):
                for suffix in ("", "-wal", "-shm", "-journal"):
                    generated = Path(str(database) + suffix)
                    if generated.exists() and not generated.is_symlink():
                        generated.unlink()
            if PROBE_DIR.exists() and not PROBE_DIR.is_symlink():
                shutil.rmtree(PROBE_DIR)
        raise


def verify(candidate_sha: str, post_restart_pid: int) -> dict:
    validate_marker(candidate_sha)
    state = _load_json(STATE_PATH)
    if state.get("candidateSha") != candidate_sha:
        raise ProbeError("pre-restart evidence belongs to another candidate")
    pre_restart_pid = int(state.get("preRestartPid") or 0)
    if post_restart_pid <= 0 or post_restart_pid == pre_restart_pid:
        raise ProbeError("sanctioned DEV service restart did not create a new PID")
    runtime = _runtime(candidate_sha)
    service_process = _service_process_evidence(post_restart_pid, runtime.release)
    current_default_config = _default_config_evidence()
    if current_default_config["sha256"] != state["defaultDevConfig"]["sha256"]:
        raise ProbeError("default disabled DEV canonical configuration changed")
    authority = _authorities(runtime)
    post_read = _facade_read(authority)
    lineage = _canonical_lineage(COGNITIVE_DB)
    _assert_read_matches(post_read, lineage)
    pre_read = state["preRestartFacadeRead"]
    pre_lineage = state["preRestartLineage"]
    for field in (
        "memory_item_id",
        "revision_id",
        "normalized_value_json",
        "value_digest",
        "consent_ref_id",
    ):
        if str(post_read[field]) != str(pre_read[field]):
            raise ProbeError(f"post-restart facade field changed: {field}")
    for field in (
        "memory_item_id",
        "revision_id",
        "normalized_value_json",
        "value_digest",
        "epistemic_basis",
        "consent_ref_id",
        "policy_decision_ref_id",
        "actor_evidence_ref_id",
        "created_from_proposal_ref_id",
        "source_owner",
        "source_stream",
        "source_digest",
        "admission_id",
        "operation_id",
    ):
        if str(lineage[field]) != str(pre_lineage[field]):
            raise ProbeError(f"post-restart SQLite lineage changed: {field}")
    cognitive_before_hold = _sqlite_evidence(COGNITIVE_DB, CANONICAL_TABLES)
    if (
        cognitive_before_hold["integrityCheck"] != "ok"
        or cognitive_before_hold["foreignKeyViolations"] != 0
    ):
        raise ProbeError("post-restart cognitive SQLite cross-check failed")

    synthetic_value = str(state["syntheticValue"])
    legacy_post_restart = legacy_snapshot(synthetic_value)
    if (
        legacy_post_restart["tokenFound"]
        or not _legacy_equal(state["legacyBaseline"], legacy_post_restart)
    ):
        raise ProbeError("legacy DEV stores changed or contain the synthetic value")

    next_value = synthetic_value + "-BLOCKED"
    supersede_action, normalized = _action(
        runtime,
        authority,
        next_value,
        operation=runtime.contracts.SUPERSEDE,
        expected=str(lineage["revision_id"]),
    )
    blocked_refs = _proposal(
        runtime,
        authority,
        supersede_action,
        normalized,
        nonce="durability.blocked." + candidate_sha[:12],
    )
    forget_action = runtime.contracts.FrozenMemoryActionV1(
        schema_version=1,
        actor_ref_id=authority.actor.ACTOR.actor_ref_id,
        operation=runtime.contracts.FORGET,
        memory_class=TEST_CLASS,
        subject_namespace=TEST_NAMESPACE,
        subject_key=TEST_KEY,
        value_schema=None,
        payload_digest=str(lineage["value_digest"]),
        expected_active_revision_id=None,
        restore_revision_id=None,
        purpose=runtime.contracts.LONG_TERM_PERSONAL_PROJECT_RECALL,
    )
    forget_evidence = authority.actor.issue(
        action=forget_action,
        request_digest=_digest_text("request:durability.privacy." + candidate_sha),
        nonce="durability.privacy." + candidate_sha[:12],
    )
    forget_request, erasure_authorization, suppression_ref = authority.privacy.begin_forget(
        action=forget_action,
        actor_evidence_ref_id=forget_evidence.actor_evidence_ref_id,
        intent_ref_id="intent.durability.privacy." + candidate_sha[:12],
        memory_item_id=str(lineage["memory_item_id"]),
        resource_owners=("L04",),
        confirmation_event_ref="confirm.durability.privacy." + candidate_sha[:12],
    )
    if not authority.privacy.is_held(TEST_CLASS, TEST_NAMESPACE, TEST_KEY):
        raise ProbeError("synthetic privacy hold did not become active")
    suppressed = authority.facade.read_exact(
        actor=authority.actor.ACTOR,
        memory_class=TEST_CLASS,
        subject_namespace=TEST_NAMESPACE,
        subject_key=TEST_KEY,
    )
    if suppressed is not None:
        raise ProbeError("privacy hold did not suppress canonical read")
    before_blocked_lineage = _canonical_lineage(COGNITIVE_DB)
    blocked = authority.store.apply(blocked_refs["proposalRef"].proposal_ref_id)
    if blocked.failure_code != "PRIVACY_HOLD_ACTIVE":
        raise ProbeError(f"privacy hold did not block mutation: {blocked}")
    after_blocked_lineage = _canonical_lineage(COGNITIVE_DB)
    for field in (
        "memory_item_id",
        "revision_id",
        "normalized_value_json",
        "value_digest",
        "operation_id",
    ):
        if str(after_blocked_lineage[field]) != str(before_blocked_lineage[field]):
            raise ProbeError("privacy hold allowed canonical mutation")
    final_legacy = legacy_snapshot(synthetic_value)
    if final_legacy["tokenFound"] or not _legacy_equal(
        state["legacyBaseline"], final_legacy
    ):
        raise ProbeError("privacy suppression introduced a legacy fallback")
    _checkpoint(COGNITIVE_DB)
    _checkpoint(PRIVACY_DB)
    cognitive_final = _sqlite_evidence(COGNITIVE_DB, CANONICAL_TABLES)
    privacy_final = _sqlite_evidence(
        PRIVACY_DB, runtime.privacy_governance.PRIVACY_TABLES
    )
    final_default_config = _default_config_evidence()
    if final_default_config["sha256"] != state["defaultDevConfig"]["sha256"]:
        raise ProbeError("default disabled DEV configuration changed during the probe")
    if (
        cognitive_final["integrityCheck"] != "ok"
        or cognitive_final["foreignKeyViolations"] != 0
        or privacy_final["integrityCheck"] != "ok"
        or privacy_final["foreignKeyViolations"] != 0
    ):
        raise ProbeError("post-restart database integrity validation failed")
    result = {
        "phase": "post-restart",
        "candidateSha": candidate_sha,
        "releasePath": str(runtime.release),
        "preRestartPid": pre_restart_pid,
        "postRestartPid": post_restart_pid,
        "newProcessContext": True,
        "serviceProcess": service_process,
        "facadeRead": post_read,
        "sqliteLineage": lineage,
        "sqliteAgreement": True,
        "legacyStoresUnchanged": True,
        "truthOwnership": lineage["epistemic_basis"],
        "verifiedOutcomePromotion": lineage["epistemic_basis"] == "VERIFIED_OUTCOME",
        "revisionPolicyDecisionRefId": lineage["policy_decision_ref_id"],
        "privacyHold": {
            "requestId": forget_request.request_id,
            "authorizationRefId": erasure_authorization.authorization_ref_id,
            "suppressionRef": suppression_ref,
            "readSuppressed": True,
            "mutationFailureCode": blocked.failure_code,
            "legacyFallback": False,
        },
        "cognitiveDatabase": cognitive_final,
        "privacyDatabase": privacy_final,
        "defaultDevConfig": final_default_config,
    }
    print(json.dumps(result, sort_keys=True))
    return result


def cleanup(candidate_sha: str) -> dict:
    result = _cleanup_generated(candidate_sha, require_marker=True)
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="phase", required=True)
    for name in ("prepare", "verify", "cleanup"):
        selected = subparsers.add_parser(name)
        selected.add_argument("--candidate-sha", required=True)
        if name == "prepare":
            selected.add_argument("--pre-restart-pid", required=True, type=int)
        elif name == "verify":
            selected.add_argument("--post-restart-pid", required=True, type=int)
    args = parser.parse_args()
    if not SHA_RE.fullmatch(args.candidate_sha):
        raise ProbeError("candidate SHA is invalid")
    if args.phase == "prepare":
        prepare(args.candidate_sha, args.pre_restart_pid)
    elif args.phase == "verify":
        verify(args.candidate_sha, args.post_restart_pid)
    else:
        cleanup(args.candidate_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
