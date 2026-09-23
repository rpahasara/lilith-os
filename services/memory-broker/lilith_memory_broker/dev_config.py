"""Closed, pinned configuration for a synthetic DEV process only."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from lilith_memory import owner_proof as P

from .request import LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, SYNTHETIC_FIXTURE_ID


DEV_HOST = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
DEV_CREDENTIAL_FINGERPRINT = "d030138a32a4470f7f7945e35cf67cbd9532639d8ab03075aff7c53285785e69"
PROFILE = "B1B2_SYNTHETIC_DEV_V1"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MACHINE = re.compile(r"[0-9a-f]{32}\Z")
_FIELDS = frozenset({
    "deploymentEnvironment", "authorityMode", "stateProfile", "canonicalCapability",
    "expectedHost", "machineId", "releaseSha", "logicalOwnerId", "accessIdentity",
    "fixtureId", "fixtureFingerprint", "credentialFingerprint", "rpId", "origin",
    "ownerSchemaFingerprint", "evidenceSchemaFingerprint", "custody",
})
_CUSTODY = frozenset({"cognitiveDb", "privacyDb", "actorKey", "privacyKey", "containmentKey"})


class DevConfigError(ValueError):
    pass


def fixture_fingerprint() -> str:
    data = {
        "accessIdentity": SYNTHETIC_ACCESS_IDENTITY,
        "fixtureId": SYNTHETIC_FIXTURE_ID,
        "logicalOwnerId": LOGICAL_OWNER_ID,
        "origin": P.SYNTHETIC_ORIGIN,
        "rpId": P.SYNTHETIC_RP_ID,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def credential_fingerprint(credential: P.OwnerCredentialV1) -> str:
    """Hash immutable public fields; the durable sign counter may advance."""
    value = credential.to_dict()
    immutable = {key: value[key] for key in (
        "recordId", "ownerPrincipal", "credentialId", "publicKeyCose",
        "algorithm", "rpId", "createdAt",
    )}
    return hashlib.sha256(json.dumps(immutable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class DevConfig:
    machine_id: str
    release_sha: str
    credential_fingerprint: str
    owner_schema_fingerprint: str
    evidence_schema_fingerprint: str

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> DevConfig:
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise DevConfigError("CONFIG_FIELDS")
        expected = {
            "deploymentEnvironment": "dev", "authorityMode": "SYNTHETIC_ONLY",
            "stateProfile": PROFILE, "canonicalCapability": "DISABLED",
            "expectedHost": DEV_HOST, "logicalOwnerId": LOGICAL_OWNER_ID,
            "accessIdentity": SYNTHETIC_ACCESS_IDENTITY,
            "fixtureId": SYNTHETIC_FIXTURE_ID,
            "fixtureFingerprint": fixture_fingerprint(),
            "credentialFingerprint": DEV_CREDENTIAL_FINGERPRINT,
            "rpId": P.SYNTHETIC_RP_ID, "origin": P.SYNTHETIC_ORIGIN,
        }
        if any(value.get(key) != item for key, item in expected.items()):
            raise DevConfigError("CONFIG_NOT_SYNTHETIC_DEV")
        custody = value["custody"]
        if not isinstance(custody, dict) or set(custody) != _CUSTODY or any(item != "ABSENT" for item in custody.values()):
            raise DevConfigError("CUSTODY_NOT_ABSENT")
        if not isinstance(value["machineId"], str) or not _MACHINE.fullmatch(value["machineId"]) or value["machineId"] != DEV_MACHINE_ID:
            raise DevConfigError("MACHINE_ID")
        if not isinstance(value["releaseSha"], str) or not _SHA.fullmatch(value["releaseSha"]):
            raise DevConfigError("RELEASE_SHA")
        for key in ("credentialFingerprint", "ownerSchemaFingerprint", "evidenceSchemaFingerprint"):
            if not isinstance(value[key], str) or not _HEX.fullmatch(value[key]):
                raise DevConfigError("INVALID_FINGERPRINT")
        return cls(value["machineId"], value["releaseSha"], value["credentialFingerprint"], value["ownerSchemaFingerprint"], value["evidenceSchemaFingerprint"])

    @classmethod
    def from_file(cls, path: Path) -> DevConfig:
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise DevConfigError("CONFIG_FILE_INVALID")
        if os.name != "nt":
            metadata = path.stat()
            if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o640:
                raise DevConfigError("CONFIG_OWNERSHIP_INVALID")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def validate_runtime(self, *, hostname: str, machine_id: str, release_sha: str) -> None:
        if os.environ.get("LILITH_ENV") != "dev" or hostname.split(".", 1)[0] != DEV_HOST:
            raise DevConfigError("DEV_HOST_REQUIRED")
        if machine_id != self.machine_id or release_sha != self.release_sha:
            raise DevConfigError("HOST_OR_RELEASE_MISMATCH")
