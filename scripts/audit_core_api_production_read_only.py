#!/usr/bin/env python3
"""Trusted, observation-only production darkness audit.

The workflow executes this source in memory on the pinned production VM. It
does not install a file, open a writable database, or change a service.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sqlite3
import stat
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

try:
    import pwd
except ImportError:  # Windows local control tests.
    pwd = None


PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
INSTANCE = "lilith-01"
INSTANCE_ID = "1332996232081478576"
HOSTNAME = f"{INSTANCE}.{ZONE}.c.{PROJECT}.internal"
SERVICE = "lilith-os-api.service"
SERVICE_FRAGMENT = f"/etc/systemd/system/{SERVICE}"
PRODUCTION_ROOT = Path("/home/lilith/.hermes/lilith-os")
DATA_DIR = PRODUCTION_ROOT / "data"
ROUTER_CONFIG = Path("/home/lilith/.hermes/lilith_router/router.yaml")
COGNITIVE_DB = DATA_DIR / "cognitive_memory.db"
PRIVACY_DB = DATA_DIR / "privacy_governance.db"
CONTAINMENT_REGISTRY = DATA_DIR / "legacy_containment_registry.json"
RUNTIME_CONFIG = DATA_DIR / "canonical-runtime.json"
DEV_ROOT = Path("/home/lilith/.hermes/lilith-os-dev")
METADATA_ROOT = "http://metadata.google.internal/computeMetadata/v1/"
CANONICAL_TABLES = {
    "registry": ("memory_registry_entry",),
    "learningV2": (
        "learning_memory_intent_v2",
        "learning_candidate_v2",
        "learning_project_codename_candidate_v1",
        "learning_candidate_source_v2",
        "learning_assessment_v2",
        "learning_proposal_ref",
        "learning_proposal_v2",
    ),
    "actor": ("actor_evidence_ref", "actor_evidence_consumption"),
    "consent": ("consent_grant", "consent_revocation"),
    "policy": ("policy_decision",),
    "rollback": ("rollback_authorization", "rollback_consumption"),
    "canonicalMemory": (
        "memory_item",
        "memory_revision",
        "memory_revision_source",
        "memory_active_revision",
        "memory_admission",
        "memory_apply_audit",
    ),
}
PRIVACY_TABLES = (
    "privacy_forget_request",
    "privacy_hold",
    "privacy_erasure_authorization",
    "privacy_erasure_authorization_owner",
    "privacy_erasure_execution",
    "privacy_restore_suppression_manifest",
    "privacy_completion_receipt",
    "privacy_completion_owner_result",
)


class AuditError(RuntimeError):
    """A required production safety fact could not be established."""


def _metadata(key: str) -> str:
    request = Request(
        METADATA_ROOT + key,
        headers={"Metadata-Flavor": "Google"},
    )
    with urlopen(request, timeout=5) as response:
        if response.headers.get("Metadata-Flavor") != "Google":
            raise AuditError("untrusted metadata response")
        return response.read(256).decode("ascii", "strict").strip()


def _service_state() -> dict[str, str]:
    process = subprocess.run(
        [
            "systemctl",
            "show",
            SERVICE,
            "--property=LoadState,ActiveState,SubState,FragmentPath,MainPID,ActiveEnterTimestamp",
            "--no-pager",
        ],
        check=True,
        text=True,
        capture_output=True,
        timeout=10,
    )
    return dict(
        line.split("=", 1)
        for line in process.stdout.splitlines()
        if "=" in line
    )


def validate_host(
    *,
    metadata=_metadata,
    hostname=socket.gethostname,
    service_state=_service_state,
    effective_uid=None,
) -> dict:
    """Establish VM, project, service, and user identity before any file read."""
    expected = {
        "instanceName": INSTANCE,
        "instanceId": INSTANCE_ID,
        "projectId": PROJECT,
        "zone": f"projects/763184673487/zones/{ZONE}",
    }
    observed = {
        "instanceName": metadata("instance/name"),
        "instanceId": metadata("instance/id"),
        "projectId": metadata("project/project-id"),
        "zone": metadata("instance/zone"),
    }
    if observed != expected or hostname() != HOSTNAME:
        raise AuditError("production VM identity mismatch")
    user_id = os.geteuid() if effective_uid is None else effective_uid
    if pwd is None or user_id != pwd.getpwnam("lilith").pw_uid:
        raise AuditError("production audit must run as the lilith read owner")
    service = service_state()
    expected_service = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "FragmentPath": SERVICE_FRAGMENT,
    }
    if any(service.get(key) != value for key, value in expected_service.items()):
        raise AuditError("production service identity or state mismatch")
    if not service.get("MainPID", "").isdigit() or int(service["MainPID"]) <= 0:
        raise AuditError("production service has no active PID")
    return {**observed, "hostname": HOSTNAME, "service": service}


def _regular_file(path: Path, *, root: Path) -> dict:
    if not path.is_absolute() or not path.is_relative_to(root):
        raise AuditError("production audit path escaped its fixed root")
    current = root
    if root.is_symlink():
        raise AuditError("production audit root is a symlink")
    for component in path.relative_to(root).parts:
        current = current / component
        if current.is_symlink():
            raise AuditError("production audit path traverses a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise AuditError("production audit path resolves outside fixed root")
    details = path.stat()
    if not stat.S_ISREG(details.st_mode):
        raise AuditError("production audit target is not a regular file")
    if details.st_uid != pwd.getpwnam("lilith").pw_uid:
        raise AuditError("production audit target owner differs")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "identity": f"{details.st_dev}:{details.st_ino}",
        "sha256": digest,
        "byteSize": details.st_size,
        "mode": format(stat.S_IMODE(details.st_mode), "04o"),
        "owner": "lilith",
    }


def _database(path: Path, tables: tuple[str, ...]) -> dict:
    metadata = _regular_file(path, root=PRODUCTION_ROOT)
    if metadata["mode"] != "0600":
        raise AuditError("production database mode is not 0600")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise AuditError("SQLite query-only mode is inactive")
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not set(tables).issubset(existing):
            raise AuditError("required production tables are absent")
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        if integrity != "ok" or foreign_keys or any(counts.values()):
            raise AuditError("production database integrity or zero-row check failed")
        return {
            **metadata,
            "accessMode": "SQLITE_READ_ONLY_QUERY_ONLY",
            "counts": counts,
            "integrityCheck": integrity,
            "foreignKeyViolations": foreign_keys,
        }
    finally:
        connection.close()


def audit() -> dict:
    identity = validate_host()
    if PRODUCTION_ROOT.resolve(strict=True) == DEV_ROOT.resolve(strict=False):
        raise AuditError("production root aliases DEV root")
    if DATA_DIR.resolve(strict=True) == (DEV_ROOT / "data").resolve(strict=False):
        raise AuditError("production data directory aliases DEV")
    if any(path.exists() or path.is_symlink() for path in (CONTAINMENT_REGISTRY, RUNTIME_CONFIG)):
        raise AuditError("production containment registry or runtime activation file exists")
    if not ROUTER_CONFIG.is_relative_to(Path("/home/lilith/.hermes/lilith_router")):
        raise AuditError("production router config path mismatch")
    config = _regular_file(
        ROUTER_CONFIG, root=Path("/home/lilith/.hermes/lilith_router")
    )
    switch = re.findall(
        r"^canonical_ltm_enabled:\s*(\S+)\s*$",
        ROUTER_CONFIG.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if switch != ["false"]:
        raise AuditError("production canonical switch is not explicitly false")
    cognitive_tables = tuple(
        table for group in CANONICAL_TABLES.values() for table in group
    )
    cognitive = _database(COGNITIVE_DB, cognitive_tables)
    privacy = _database(PRIVACY_DB, PRIVACY_TABLES)
    service_after = _service_state()
    if service_after != identity["service"]:
        raise AuditError("production service state changed during read-only audit")
    return {
        "phase": "production-read-only-audit",
        "host": identity,
        "serviceUnchangedDuringAudit": True,
        "configuration": {
            **config,
            "canonicalLtmEnabled": False,
            "canonicalCapabilityActive": False,
        },
        "cognitiveDatabase": cognitive,
        "privacyDatabase": privacy,
        "containmentRegistry": {"path": str(CONTAINMENT_REGISTRY), "absent": True},
        "runtimeActivationFile": {"path": str(RUNTIME_CONFIG), "absent": True},
        "registryAndContainmentActive": False,
        "productionRowsRemainZero": True,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
