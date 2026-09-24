#!/usr/bin/env python3
"""Trusted-main, observation-only broker lifecycle gate for pinned DEV.

The selected lifecycle is a protected-main constant, never a candidate input.
The command emits a deterministic snapshot for comparison before and after
transient candidate validation. It does not create files or start services.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

try:  # Pure-policy regressions also run on Windows.
    import grp
    import pwd
except ImportError:  # pragma: no cover
    grp = None
    pwd = None


PRE_B1B2B = "PRE_B1B2B"
POST_STAGE_I = "POST_STAGE_I"
POST_STAGE_II = "POST_STAGE_II"  # Reserved; not accepted or selectable.
POST_STAGE_II_FAILED_INERT_V1 = "POST_STAGE_II_FAILED_INERT_V1"
TRUSTED_DEV_PROFILE = POST_STAGE_II_FAILED_INERT_V1

PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
DEV_INSTANCE = "lilith-dev-01"
DEV_INSTANCE_ID = "7687007163730582258"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
DEV_HOSTNAME = f"{DEV_INSTANCE}.{ZONE}.c.{PROJECT}.internal"
RELEASE_SHA = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
MANIFEST_SHA = "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614"
OWNER_SCHEMA = "8074e95c1a1b1de6081cc686efc10159793f7c4768f362b64e9e6a34705eb314"
EVIDENCE_SCHEMA = "c18c904a9f2b4f1c48fa3aeafb3f587a33f59f35219c872f7c33d972d996e718"

ROOT = Path("/opt/lilith-memory-broker")
CONFIG = Path("/etc/lilith-memory-broker")
STATE = Path("/var/lib/lilith-memory-broker")
RUNTIME = Path("/run/lilith-memory")
API_ROOT = Path("/home/lilith/.hermes/lilith-os-dev")
OWNER_DB = STATE / "owner-control/owner_control.db"
EVIDENCE_DB = STATE / "state/synthetic_evidence.db"
SERVICE = "lilith-memory-broker.service"
SOCKET = "lilith-memory-broker.socket"

FILE_CONTRACT = {
    str(CONFIG / "dev.json"): ("c1787b34e5f1969fe98a0d3499c7913fde01a6eba7f2ee04f427a39cd02f27fb", 0, 987, 0o640),
    str(CONFIG / "identities.json"): ("e1c808901bea374d7a0d16d49140125d8572012497905a690d634373a2070d23", 0, 0, 0o600),
    str(CONFIG / "b1b2b-authorization.used.json"): ("2c9975086f7bc41aec872ae0bdeb9e5f9da7d312495ab193e46879de5302274b", 0, 0, 0o600),
    "/etc/systemd/system/lilith-memory-broker.service": ("6a9dca54b9051cc7788587a0f37601f67e16fc07de043cbc5d64e7123ed35689", 0, 0, 0o644),
    "/etc/systemd/system/lilith-memory-broker.socket": ("d9f21223b837fd4be98d3c67eb95625b00c8a0ee6922d06eb79605edb382e793", 0, 0, 0o644),
    "/etc/tmpfiles.d/lilith-memory-broker.conf": ("e6139f16b001a3c36e9ff3db733f19a3a7ce06b1d0fbc923591bc17b2d4df86e", 0, 0, 0o644),
    str(OWNER_DB): ("8c0c8a617b199b60eddb10d5b6123f6ec9a511646fe4d754ac1ce23881f4e69d", 999, 987, 0o600),
    str(EVIDENCE_DB): ("b8f619e5e6ede9dc9ea8a721150ea52d7082f5eb95543b0d11453efcb9581654", 999, 987, 0o600),
    str(API_ROOT / "current/app.py"): ("bb0a4139641c0a81607263b07fa854deb34241b5fcfcdcab965c6a82dd8826d3", 1001, 1002, 0o640),
    "/etc/systemd/system/lilith-os-api-dev.service": ("bacfbac4b0f9502ebfe0a745cd2a9ff691f6a16bad9a8706f03085d588c21243", 0, 0, 0o644),
}
POST_ABSENT = (
    str(RUNTIME), str(RUNTIME / "owner.sock"),
    str(CONFIG / "b1b2b-authorization.json"),
    str(CONFIG / "b1b2b-stage2-authorization.json"),
    str(CONFIG / "b1b2b-stage2-authorization.used.json"),
    "/tmp/lilith-memory-broker-stage2-host-marker",
)
OWNER_COUNTS = {
    "broker_schema_v1": 1,
    "owner_identity_v1": 1,
    "owner_access_identity_v1": 1,
    "owner_credential_v1": 1,  # Public synthetic credential only.
    "owner_proof_challenge_v1": 0,
    "owner_request_v1": 0,
    "synthetic_claim_v1": 0,
}
EVIDENCE_COUNTS = {"synthetic_schema_v1": 1, "synthetic_evidence_v1": 0}
FAILED_OWNER_DB_SHA = "16a4645c4833367df83bad257d59e5d4cb78d0e6dca5b32e55233cbc43ab3dee"
FAILED_EVIDENCE_DB_SHA = "b1435ec257ddcad3fec97c53fcd15c8656db8dc8e93f585f72f3c673c487ab68"
FAILED_USED_MARKER_SHA = "d75394b18906546095650851b0c18aac3208ac3fb04bde43655c80482602ef51"
FAILED_AUTHORIZATION_ID = "4006ead71ca04c219b3b41e6818010f2"
FAILED_CONSUMED_CHALLENGE = "och.ce2cc7d68c6f41ed89e176e4360e474e"
FAILED_EXPIRED_CHALLENGE = "och.abb1596f820c49ff80832e386fbfaa91"
FAILED_EVIDENCE_ID = "se.68b647fc14aeea4fb32bdd7d0fada54d8f4af7c272ec6784f5d22c4c8980e7b5"
FAILED_REQUEST_DIGEST = "03cc4a128cef589f6268b66ba2294521688a916e46bfdda8a5abe1dea951b73d"
FAILED_ACTION_DIGEST = "edb9a1ff061722e0c83a72689b2135c5f333526146c3a3a0f344a4202dcb8bf0"
FAILED_CHALLENGES = {
    "och.0a8e46578c2a4c87b0919d24f0552d9b": "CANCELLED",
    "och.17449e78f4164137a6624529688b335f": "CANCELLED",
    "och.52ed36f8bdce415c9c14bcb33e11c59b": "CANCELLED",
    "och.6f2a37eefb75465f8d2e4e683266baa3": "CANCELLED",
    "och.6f71a276fef74e4b9dae9460e8e25466": "CANCELLED",
    "och.873aa7d86d91472ebd8892490ea05e3e": "CANCELLED",
    "och.922cd4c2951c461aa72dcb74f8e78102": "CANCELLED",
    FAILED_EXPIRED_CHALLENGE: "EXPIRED",
    FAILED_CONSUMED_CHALLENGE: "CONSUMED",
    "och.d4cbf6f8cede404e9ed741a541aa6819": "CANCELLED",
    "och.d5329ab29d2f43e582d539829d18fdf9": "CANCELLED",
    "och.e36d313a6234428a9fb16adf8eebf133": "CANCELLED",
}
FAILED_REQUESTS = {
    "och.0a8e46578c2a4c87b0919d24f0552d9b": "e4a7bd8c0c6ccfe0d04d9741a19a6348213fc9845940715294e4f0d1acaf0bac",
    "och.17449e78f4164137a6624529688b335f": "55bf674b8b819c08d995a93c633775b2e9d27f8163c20894cdf948dad309d767",
    "och.52ed36f8bdce415c9c14bcb33e11c59b": "69d440618af91d328a2b1614b7a7b3c1af7c35ea4e9b108d7df16d4441814872",
    "och.6f2a37eefb75465f8d2e4e683266baa3": "b965b5a91d32af7ab55be2f42b9cc7d475f7d4de4a6a359c9ac55348fe0650f8",
    "och.6f71a276fef74e4b9dae9460e8e25466": "8973bb2bfd96251140b687f016c45f971998b1fddb02288e652f119c75858a66",
    "och.873aa7d86d91472ebd8892490ea05e3e": "0d409fb7056e8f9fa3d4837d1d8f058a1110a7d524ab20008747b3ee450f1ec3",
    "och.922cd4c2951c461aa72dcb74f8e78102": "f67f13fe3cb822215f215543da7e5634f5874e3290d7599d8e9833f5251fe7bc",
    FAILED_EXPIRED_CHALLENGE: "2162ae2d36922cc524138e8358644e651ec931e7992c072a37af6e8ee4f7d8a7",
    FAILED_CONSUMED_CHALLENGE: FAILED_REQUEST_DIGEST,
    "och.d4cbf6f8cede404e9ed741a541aa6819": "7bb65961c5bfb1810c450c87c88ab972726bb227798e0ac1f879b8747e6276ba",
    "och.d5329ab29d2f43e582d539829d18fdf9": "2c9318d9663f7a93ac990d533429ad547fdc2a35452982194f5d83f084cedf55",
    "och.e36d313a6234428a9fb16adf8eebf133": "bfb4fa3b532309ede325008dd5e100599cf93a5c47400fc9ac27fbf9aae47ab0",
}
FAILED_OWNER_COUNTS = {**OWNER_COUNTS, "owner_proof_challenge_v1": 12,
                       "owner_request_v1": 12, "synthetic_claim_v1": 1}
FAILED_EVIDENCE_COUNTS = {**EVIDENCE_COUNTS, "synthetic_evidence_v1": 1}
FAILED_FILES = {
    **FILE_CONTRACT,
    str(OWNER_DB): (FAILED_OWNER_DB_SHA, 999, 987, 0o600),
    str(EVIDENCE_DB): (FAILED_EVIDENCE_DB_SHA, 999, 987, 0o600),
    str(CONFIG / "b1b2b-stage2-authorization.used.json"):
        (FAILED_USED_MARKER_SHA, 0, 0, 0o600),
}
FAILED_ABSENT = tuple(path for path in POST_ABSENT if path not in
                      (str(RUNTIME), str(CONFIG / "b1b2b-stage2-authorization.used.json")))


class LifecycleError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LifecycleError(code)


def validate_pre(snapshot: dict) -> None:
    """Historical absence contract, retained for a genuinely pre-install DEV."""
    require(snapshot.get("profile") == PRE_B1B2B, "PRE_PROFILE_MISMATCH")
    require(snapshot.get("host") == expected_host(), "HOST_MISMATCH")
    require(snapshot.get("accounts") == {"broker": None, "relay": None, "ipc": None}, "PRE_ACCOUNT_PRESENT")
    require(snapshot.get("groups") == {"broker": None, "relay": None}, "PRE_GROUP_PRESENT")
    require(all(value is False for value in snapshot.get("persistent_paths", {}).values())
            and set(snapshot.get("persistent_paths", {})) == set(pre_absent_paths()), "PRE_BROKER_FOOTPRINT")
    for name in (SERVICE, SOCKET):
        unit = snapshot.get("units", {}).get(name, {})
        require(unit.get("LoadState") == "not-found" and unit.get("ActiveState") == "inactive", "PRE_UNIT_PRESENT")
    require(snapshot.get("broker_processes") == [], "PRE_BROKER_PROCESS")


def expected_host() -> dict[str, str]:
    return {
        "hostname": DEV_HOSTNAME,
        "machineId": DEV_MACHINE_ID,
        "projectId": PROJECT,
        "zone": f"projects/763184673487/zones/{ZONE}",
        "instanceId": DEV_INSTANCE_ID,
        "instanceName": DEV_INSTANCE,
    }


def pre_absent_paths() -> tuple[str, ...]:
    return (
        str(ROOT), str(CONFIG), str(STATE), str(RUNTIME),
        "/etc/systemd/system/lilith-memory-broker.service",
        "/etc/systemd/system/lilith-memory-broker.socket",
        "/etc/tmpfiles.d/lilith-memory-broker.conf",
        str(API_ROOT / "data/owner_control.db"),
    )


def _validate_stage_i_static(snapshot: dict, file_contract: dict) -> None:
    """Common immutable provisioning contract; runtime history is profile-specific."""
    require(snapshot.get("host") == expected_host(), "HOST_MISMATCH")
    expected_accounts = {
        "broker": {"uid": 999, "gid": 987, "home": "/nonexistent", "shell": "/usr/sbin/nologin", "groups": [987]},
        "relay": {"uid": 997, "gid": 986, "home": "/nonexistent", "shell": "/usr/sbin/nologin", "groups": [986, 988]},
        "ipc": {"gid": 988, "members": ["lilith-memory-relay"]},
    }
    require(snapshot.get("accounts") == expected_accounts, "STAGE_I_ACCOUNTS_CHANGED")
    require(snapshot.get("groups") == {"broker": 987, "relay": 986}, "STAGE_I_GROUPS_CHANGED")
    require(snapshot.get("directories") == {
        str(ROOT): [0, 0, 0o755], str(ROOT / "releases"): [0, 0, 0o755],
        str(CONFIG): [0, 0, 0o755], str(STATE): [999, 987, 0o700],
        str(STATE / "owner-control"): [999, 987, 0o700],
        str(STATE / "state"): [999, 987, 0o700],
    }, "STAGE_I_DIRECTORY_CHANGED")
    release = snapshot.get("release", {})
    require(release.get("target") == f"releases/{RELEASE_SHA}", "STAGE_I_RELEASE_POINTER")
    require(release.get("manifestSha256") == MANIFEST_SHA, "STAGE_I_RELEASE_HASH")
    require(release.get("candidateSha") == RELEASE_SHA and release.get("deploymentEnvironment") == "dev"
            and release.get("ownerSchemaFingerprint") == OWNER_SCHEMA
            and release.get("evidenceSchemaFingerprint") == EVIDENCE_SCHEMA, "STAGE_I_MANIFEST_CONTRACT")
    files = release.get("manifestFiles", {})
    payloads = release.get("payloads", {})
    require(len(files) == 23 and set(files) == set(payloads), "STAGE_I_PAYLOAD_SET")
    for path, expected in files.items():
        require(isinstance(expected, dict) and payloads.get(path) == expected, "STAGE_I_PAYLOAD_HASH")
    actual_files = snapshot.get("files", {})
    require(set(actual_files) == set(file_contract), "STAGE_I_FILE_SET")
    for path, (digest, uid, gid, mode) in file_contract.items():
        require(actual_files[path] == {"sha256": digest, "uid": uid, "gid": gid, "mode": mode},
                "STAGE_I_FILE_DRIFT:" + path)


def validate_post(snapshot: dict) -> None:
    """Pristine Stage I remains strict, including zero history and no sidecars."""
    require(snapshot.get("profile") == POST_STAGE_I, "POST_PROFILE_MISMATCH")
    _validate_stage_i_static(snapshot, FILE_CONTRACT)
    owner = snapshot.get("databases", {}).get("owner", {})
    evidence = snapshot.get("databases", {}).get("evidence", {})
    require(owner.get("integrity") == "ok" and owner.get("foreignKeyViolations") == 0
            and owner.get("fingerprint") == OWNER_SCHEMA and owner.get("version") == 2
            and owner.get("mode") == "B1B2_SYNTHETIC_DEV_V1"
            and owner.get("counts") == OWNER_COUNTS
            and owner.get("accessIdentity") == ["owner.ravindu.v1", "user:synthetic-owner@example.invalid", "ACTIVE"]
            and owner.get("credentialCount") == 1, "STAGE_I_OWNER_DB_DRIFT")
    require(evidence.get("integrity") == "ok" and evidence.get("foreignKeyViolations") == 0
            and evidence.get("fingerprint") == EVIDENCE_SCHEMA
            and evidence.get("profile") == "B1B2_SYNTHETIC_EVIDENCE_V1"
            and evidence.get("releaseSha") == RELEASE_SHA
            and evidence.get("counts") == EVIDENCE_COUNTS, "STAGE_I_EVIDENCE_DB_DRIFT")
    units = snapshot.get("units", {})
    service = units.get(SERVICE, {})
    broker_socket = units.get(SOCKET, {})
    require(all(service.get(key) == value for key, value in {
        "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
        "MainPID": "0", "UnitFileState": "static", "NRestarts": "0",
        "ExecMainStartTimestamp": "",
    }.items()), "BROKER_SERVICE_ACTIVE_OR_CHANGED")
    require(all(broker_socket.get(key) == value for key, value in {
        "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
        "UnitFileState": "disabled",
    }.items()), "BROKER_SOCKET_ACTIVE_OR_ENABLED")
    require(snapshot.get("absent") == {path: True for path in POST_ABSENT}, "STAGE_II_RUNTIME_OR_MARKER_PRESENT")
    require(snapshot.get("broker_processes") == [], "BROKER_PROCESS_PRESENT")
    api = snapshot.get("api", {})
    require(api.get("ActiveState") == "active" and api.get("NRestarts") == "0"
            and str(api.get("MainPID", "")).isdigit() and int(api["MainPID"]) > 0
            and api.get("ExecMainStartTimestamp"), "DEV_API_UNHEALTHY")
    require(api.get("health") == {"status": "ok", "database": True}, "DEV_API_HEALTH_MISMATCH")
    require(set(api.get("custody", {})) == {
        str(API_ROOT / "data/lilith-dev.db"), str(API_ROOT / "data/canonical-runtime.json"),
    }, "DEV_API_CUSTODY_MISSING")


def historical_baseline(owner: dict, evidence: dict, used: dict) -> dict:
    """Stable read-only historical state for a later, separately authorized delta check."""
    core = {
        "schemaVersion": 1,
        "profile": POST_STAGE_II_FAILED_INERT_V1,
        "authorizationId": used["authorizationId"],
        "usedMarkerSha256": used["sha256"],
        "ownerDbSha256": FAILED_OWNER_DB_SHA,
        "evidenceDbSha256": FAILED_EVIDENCE_DB_SHA,
        "ownerSchemaFingerprint": owner["fingerprint"],
        "evidenceSchemaFingerprint": evidence["fingerprint"],
        "ownerCounts": owner["counts"],
        "evidenceCounts": evidence["counts"],
        "challengeStates": owner["challengeStates"],
        "requestDigests": owner["requestDigests"],
        "claims": owner["claims"],
        "evidenceRows": evidence["evidenceRows"],
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**core, "stateDigestSha256": hashlib.sha256(encoded).hexdigest()}


def validate_failed_inert(snapshot: dict) -> None:
    """Only the exact, terminal evidence from failed run 35924789001 is admitted."""
    require(snapshot.get("profile") == POST_STAGE_II_FAILED_INERT_V1, "FAILED_PROFILE_MISMATCH")
    _validate_stage_i_static(snapshot, FAILED_FILES)
    owner = snapshot.get("databases", {}).get("owner", {})
    evidence = snapshot.get("databases", {}).get("evidence", {})
    require(owner.get("integrity") == "ok" and owner.get("foreignKeyViolations") == 0
            and owner.get("fingerprint") == OWNER_SCHEMA and owner.get("version") == 2
            and owner.get("mode") == "B1B2_SYNTHETIC_DEV_V1"
            and owner.get("counts") == FAILED_OWNER_COUNTS
            and owner.get("accessIdentity") == ["owner.ravindu.v1", "user:synthetic-owner@example.invalid", "ACTIVE"]
            and owner.get("credentialCount") == 1, "FAILED_OWNER_DB_DRIFT")
    require(evidence.get("integrity") == "ok" and evidence.get("foreignKeyViolations") == 0
            and evidence.get("fingerprint") == EVIDENCE_SCHEMA
            and evidence.get("profile") == "B1B2_SYNTHETIC_EVIDENCE_V1"
            and evidence.get("releaseSha") == RELEASE_SHA
            and evidence.get("counts") == FAILED_EVIDENCE_COUNTS, "FAILED_EVIDENCE_DB_DRIFT")
    expected_sidecars = {
        "-wal": {"sha256": hashlib.sha256(b"").hexdigest(), "uid": 999, "gid": 987,
                 "mode": 0o600, "size": 0},
        "-shm": {"sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb",
                 "uid": 999, "gid": 987, "mode": 0o600, "size": 32768},
    }
    require(owner.get("sidecars") == expected_sidecars and
            evidence.get("sidecars") == expected_sidecars, "FAILED_DATABASE_SIDECAR_DRIFT")
    require(owner.get("challengeStates") == FAILED_CHALLENGES and
            owner.get("requestDigests") == FAILED_REQUESTS and
            owner.get("consumedCredential") == [FAILED_CONSUMED_CHALLENGE, "ocred.synthetic",
                                                 "2026-09-23T21:54:26Z"],
            "FAILED_CHALLENGE_OR_REQUEST_DRIFT")
    expected_claim = [[FAILED_CONSUMED_CHALLENGE, FAILED_REQUEST_DIGEST,
                       FAILED_ACTION_DIGEST, "ocred.synthetic",
                       "SYNTHETIC_EVIDENCE_COMMITTED", FAILED_EVIDENCE_ID]]
    expected_evidence = [[FAILED_CONSUMED_CHALLENGE, FAILED_EVIDENCE_ID,
                          FAILED_REQUEST_DIGEST, FAILED_ACTION_DIGEST,
                          "owner.ravindu.v1", "ocred.synthetic",
                          "fixture.b1b1.synthetic-codename.v1", "SYNTHETIC_COMMITTED"]]
    require(owner.get("claims") == expected_claim and
            evidence.get("evidenceRows") == expected_evidence,
            "FAILED_SYNTHETIC_LINKAGE_DRIFT")
    used = snapshot.get("usedAuthorization", {})
    require(used.get("sha256") == FAILED_USED_MARKER_SHA and
            used.get("authorizationId") == FAILED_AUTHORIZATION_ID and
            used.get("schemaVersion") == 2 and
            used.get("stage") == "B1B2B_II / ACTIVATE_AND_ISOLATION_TEST" and
            used.get("authorityMode") == "SYNTHETIC_ONLY" and
            used.get("canonicalCapability") == "DISABLED" and
            used.get("releaseSha") == RELEASE_SHA and
            used.get("ownerActor") == "rpahasara" and
            used.get("apiBaselineDigest") ==
            "0fbed57b7746be3051e3de623990c6402daaa1f88197e614d60499419e1cdbd5",
            "FAILED_USED_AUTHORIZATION_DRIFT")
    require(snapshot.get("historicalBaseline") == historical_baseline(owner, evidence, used),
            "FAILED_HISTORICAL_BASELINE_DRIFT")
    service = snapshot.get("units", {}).get(SERVICE, {})
    broker_socket = snapshot.get("units", {}).get(SOCKET, {})
    require(all(service.get(k) == v for k, v in {
        "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
        "MainPID": "0", "UnitFileState": "static", "NRestarts": "0",
        "ExecMainStartTimestamp": "",
    }.items()), "FAILED_BROKER_NOT_INERT")
    require(all(broker_socket.get(k) == v for k, v in {
        "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
        "UnitFileState": "disabled",
    }.items()), "FAILED_SOCKET_NOT_INERT")
    require(snapshot.get("absent") == {path: True for path in FAILED_ABSENT},
            "FAILED_UNCONSUMED_MARKER_OR_SOCKET_PRESENT")
    require(snapshot.get("runtimeDirectory") == {"uid": 0, "gid": 988, "mode": 0o710,
                                                 "children": []}, "FAILED_RUNTIME_DIRECTORY_DRIFT")
    require(snapshot.get("broker_processes") == [] and snapshot.get("broker_uid_processes") == [],
            "FAILED_BROKER_PROCESS_PRESENT")
    api = snapshot.get("api", {})
    require(api.get("ActiveState") == "active" and api.get("NRestarts") == "0"
            and str(api.get("MainPID", "")).isdigit() and int(api["MainPID"]) > 0
            and api.get("ExecMainStartTimestamp") and
            api.get("health") == {"status": "ok", "database": True}
            and api.get("custody", {}).get(str(API_ROOT / "data/lilith-dev.db"), {}).get("sha256") ==
            "e4080d47ac782dc5578c4537b8aab277e73b27546e704ee2fff6fda506f67e6c"
            and api.get("custody", {}).get(str(API_ROOT / "data/canonical-runtime.json"), {}).get("sha256") ==
            "65ac5077486cfe25665fc8f5815661b1653878182492a0309ec974e9394c08e7",
            "FAILED_API_OR_CANONICAL_DRIFT")


def validate(snapshot: dict) -> None:
    if TRUSTED_DEV_PROFILE == PRE_B1B2B:
        validate_pre(snapshot)
    elif TRUSTED_DEV_PROFILE == POST_STAGE_I:
        validate_post(snapshot)
    elif TRUSTED_DEV_PROFILE == POST_STAGE_II_FAILED_INERT_V1:
        validate_failed_inert(snapshot)
    else:
        raise LifecycleError("UNACCEPTED_LIFECYCLE_PROFILE")


def _command(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=15).stdout.strip()


def _metadata(key: str) -> str:
    request = Request("http://169.254.169.254/computeMetadata/v1/" + key,
                      headers={"Metadata-Flavor": "Google"})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        require(response.headers.get("Metadata-Flavor") == "Google", "UNTRUSTED_HOST_METADATA")
        return response.read(256).decode("ascii", "strict").strip()


def _host() -> dict[str, str]:
    return {
        "hostname": socket.getfqdn(),
        "machineId": Path("/etc/machine-id").read_text(encoding="ascii").strip(),
        "projectId": _metadata("project/project-id"),
        "zone": _metadata("instance/zone"),
        "instanceId": _metadata("instance/id"),
        "instanceName": _metadata("instance/name"),
    }


def _directory(path: Path) -> list[int]:
    meta = path.lstat()
    require(stat.S_ISDIR(meta.st_mode), "EXPECTED_DIRECTORY:" + str(path))
    return [meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)]


def _read_regular(path: Path) -> tuple[bytes, os.stat_result]:
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), "EXPECTED_REGULAR_FILE:" + str(path))
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "FILE_REPLACED:" + str(path))
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read()
    finally:
        os.close(fd)
    require(len(data) == opened.st_size, "FILE_SIZE_CHANGED:" + str(path))
    return data, opened


def _file(path: Path) -> dict:
    data, meta = _read_regular(path)
    return {"sha256": hashlib.sha256(data).hexdigest(), "uid": meta.st_uid,
            "gid": meta.st_gid, "mode": stat.S_IMODE(meta.st_mode)}


def _account(name: str) -> dict | None:
    try:
        user = pwd.getpwnam(name)
    except KeyError:
        return None
    local = [line for line in Path("/etc/passwd").read_text(encoding="utf-8").splitlines()
             if line.startswith(name + ":")]
    shadow = [line.split(":", 2)[1] for line in Path("/etc/shadow").read_text(encoding="utf-8").splitlines()
              if line.startswith(name + ":")]
    require(len(local) == 1 and len(shadow) == 1 and shadow[0].startswith(("!", "*")),
            "ACCOUNT_NOT_LOCAL_OR_LOCKED:" + name)
    require(not Path("/home", name).exists() and not Path("/etc/ssh/authorized_keys", name).exists(),
            "ACCOUNT_HOME_OR_SSH_PRESENT:" + name)
    sudo = subprocess.run(("/usr/bin/sudo", "-n", "-l", "-U", name),
                          capture_output=True, text=True, timeout=10)
    require(sudo.stdout.strip() == f"User {name} is not allowed to run sudo on {DEV_INSTANCE}."
            and not sudo.stderr.strip(), "ACCOUNT_SUDO_PRIVILEGE:" + name)
    return {"uid": user.pw_uid, "gid": user.pw_gid, "home": user.pw_dir,
            "shell": user.pw_shell, "groups": sorted(set(os.getgrouplist(name, user.pw_gid)))}


def _accounts() -> dict:
    ipc = None
    try:
        group = grp.getgrnam("lilith-memory-ipc")
        ipc = {"gid": group.gr_gid, "members": sorted(group.gr_mem)}
    except KeyError:
        pass
    return {"broker": _account("lilith-memory-broker"),
            "relay": _account("lilith-memory-relay"), "ipc": ipc}


def _groups() -> dict:
    found = {}
    for name in ("lilith-memory-broker", "lilith-memory-relay"):
        try:
            found["broker" if name.endswith("broker") else "relay"] = grp.getgrnam(name).gr_gid
        except KeyError:
            found["broker" if name.endswith("broker") else "relay"] = None
    return found


def _unit(name: str) -> dict[str, str]:
    properties = "LoadState,ActiveState,SubState,MainPID,UnitFileState,NRestarts,ExecMainStartTimestamp,FragmentPath,DropInPaths"
    output = _command("/usr/bin/systemctl", "show", name, "--property=" + properties, "--no-pager")
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def _broker_processes() -> list[int]:
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if b"lilith_memory_broker.server" in cmdline or b"/opt/lilith-memory-broker/current/venv/bin/python" in cmdline:
            found.append(int(entry.name))
    return sorted(found)


def _broker_uid_processes() -> list[int]:
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid == 999:
                found.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return sorted(found)


def _release() -> dict:
    current = ROOT / "current"
    link = current.lstat()
    require(stat.S_ISLNK(link.st_mode) and link.st_uid == 0 and link.st_gid == 0,
            "STAGE_I_POINTER_TYPE")
    target = os.readlink(current)
    require(target == f"releases/{RELEASE_SHA}", "STAGE_I_POINTER_TARGET")
    release_dir = ROOT / target
    require(_directory(release_dir) == [0, 0, 0o755], "STAGE_I_RELEASE_DIRECTORY")
    manifest_bytes, manifest_meta = _read_regular(release_dir / "release-manifest.json")
    require((manifest_meta.st_uid, manifest_meta.st_gid, stat.S_IMODE(manifest_meta.st_mode)) == (0, 0, 0o644),
            "STAGE_I_MANIFEST_OWNERSHIP")
    manifest = json.loads(manifest_bytes)
    manifest_files = {}
    payloads = {}
    for item in manifest["files"]:
        name = item["path"]
        require(isinstance(name, str) and name and not name.startswith("/")
                and all(part not in ("", ".", "..") for part in name.split("/"))
                and name not in manifest_files, "STAGE_I_MANIFEST_PATH")
        path = release_dir
        for part in name.split("/")[:-1]:
            path = path / part
            require(stat.S_ISDIR(path.lstat().st_mode), "STAGE_I_PAYLOAD_PARENT")
        payload_path = release_dir / name
        data, meta = _read_regular(payload_path)
        require((meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (0, 0, 0o644),
                "STAGE_I_PAYLOAD_OWNERSHIP")
        manifest_files[name] = {"sha256": item["sha256"], "byteSize": item["byteSize"]}
        payloads[name] = {"sha256": hashlib.sha256(data).hexdigest(), "byteSize": len(data)}
    return {
        "target": target, "manifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "candidateSha": manifest.get("candidateSha"),
        "deploymentEnvironment": manifest.get("deploymentEnvironment"),
        "ownerSchemaFingerprint": manifest.get("ownerSchemaFingerprint"),
        "evidenceSchemaFingerprint": manifest.get("evidenceSchemaFingerprint"),
        "manifestFiles": manifest_files, "payloads": payloads,
    }


def _database(path: Path, tables: dict[str, int], *, historical: bool = False) -> tuple[sqlite3.Connection, dict]:
    sidecars = {}
    for suffix in ("-wal", "-shm"):
        side = Path(str(path) + suffix)
        if historical:
            data, meta = _read_regular(side)
            sidecars[suffix] = {"sha256": hashlib.sha256(data).hexdigest(),
                                "uid": meta.st_uid, "gid": meta.st_gid,
                                "mode": stat.S_IMODE(meta.st_mode), "size": meta.st_size}
        else:
            require(not os.path.lexists(side), "STAGE_I_DATABASE_SIDECAR")
    conn = sqlite3.connect("file:" + path.as_posix() + "?mode=ro&immutable=1", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        require(conn.execute("PRAGMA query_only").fetchone()[0] == 1, "DATABASE_NOT_QUERY_ONLY")
        found = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(found == set(tables), "STAGE_I_DATABASE_TABLE_SET")
        counts = {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in tables}
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        result = {"counts": counts, "integrity": integrity, "foreignKeyViolations": fk}
        if historical:
            result["sidecars"] = sidecars
        return conn, result
    except Exception:
        conn.close()
        raise


def _owner_database(*, historical: bool = False) -> dict:
    conn, result = _database(OWNER_DB, OWNER_COUNTS, historical=historical)
    try:
        rows = conn.execute("SELECT version,fingerprint,mode FROM broker_schema_v1").fetchall()
        require(len(rows) == 1, "OWNER_SCHEMA_ROWS")
        schema_rows = conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall()
        source = "\n".join(f"{kind}:{name}:{' '.join(sql.split())}" for kind, name, sql in schema_rows)
        calculated = hashlib.sha256(source.encode("utf-8")).hexdigest()
        require(rows[0][1] == calculated, "OWNER_SCHEMA_FINGERPRINT")
        access = conn.execute("SELECT owner_id,access_identity,status FROM owner_access_identity_v1").fetchall()
        credential_count = conn.execute("SELECT COUNT(*) FROM owner_credential_v1").fetchone()[0]
        result = {**result, "version": rows[0][0], "fingerprint": calculated,
                  "mode": rows[0][2], "accessIdentity": list(access[0]) if len(access) == 1 else [],
                  "credentialCount": credential_count}
        if historical:
            result["challengeStates"] = dict(conn.execute(
                "SELECT challenge_id,state FROM owner_proof_challenge_v1").fetchall())
            result["requestDigests"] = dict(conn.execute(
                "SELECT challenge_id,request_digest FROM owner_request_v1").fetchall())
            consumed = conn.execute(
                "SELECT challenge_id,consumed_credential_record_id,consumed_at "
                "FROM owner_proof_challenge_v1 WHERE state='CONSUMED'").fetchall()
            result["consumedCredential"] = list(consumed[0]) if len(consumed) == 1 else []
            result["claims"] = [list(row) for row in conn.execute(
                "SELECT challenge_id,request_digest,action_digest,synthetic_credential_record_id,"
                "status,synthetic_evidence_id FROM synthetic_claim_v1 ORDER BY challenge_id")]
        return result
    finally:
        conn.close()


def _evidence_database(*, historical: bool = False) -> dict:
    conn, result = _database(EVIDENCE_DB, EVIDENCE_COUNTS, historical=historical)
    try:
        rows = conn.execute("SELECT profile,release_sha FROM synthetic_schema_v1").fetchall()
        require(len(rows) == 1, "SYNTHETIC_SCHEMA_ROWS")
        ddl = [row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY rowid")]
        calculated = hashlib.sha256("\n".join(ddl).encode()).hexdigest()
        result = {**result, "profile": rows[0][0], "releaseSha": rows[0][1], "fingerprint": calculated}
        if historical:
            result["evidenceRows"] = [list(row) for row in conn.execute(
                "SELECT challenge_id,synthetic_evidence_id,request_digest,action_digest,"
                "logical_owner_id,synthetic_credential_record_id,fixture_marker,state "
                "FROM synthetic_evidence_v1 ORDER BY challenge_id")]
        return result
    finally:
        conn.close()


def _api() -> dict:
    unit = _unit("lilith-os-api-dev.service")
    request = Request("http://127.0.0.1:8765/health")
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        health = json.load(response)
    custody = {}
    for path in (API_ROOT / "data/lilith-dev.db", API_ROOT / "data/canonical-runtime.json"):
        custody[str(path)] = _file(path)
    return {key: unit.get(key) for key in ("ActiveState", "MainPID", "NRestarts", "ExecMainStartTimestamp")} | {
        "health": {"status": health.get("status"), "database": health.get("database")},
        "custody": custody,
    }


def _used_authorization() -> dict:
    path = CONFIG / "b1b2b-stage2-authorization.used.json"
    data, meta = _read_regular(path)
    require((meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (0, 0, 0o600),
            "FAILED_USED_MARKER_OWNERSHIP")
    value = json.loads(data)
    require(isinstance(value, dict), "FAILED_USED_MARKER_FORMAT")
    return {"sha256": hashlib.sha256(data).hexdigest(),
            **{key: value.get(key) for key in (
                "authorizationId", "schemaVersion", "stage", "authorityMode",
                "canonicalCapability", "releaseSha", "ownerActor", "apiBaselineDigest")}}


def _runtime_directory() -> dict:
    meta = RUNTIME.lstat()
    require(stat.S_ISDIR(meta.st_mode), "FAILED_RUNTIME_DIRECTORY_TYPE")
    return {"uid": meta.st_uid, "gid": meta.st_gid,
            "mode": stat.S_IMODE(meta.st_mode),
            "children": sorted(item.name for item in RUNTIME.iterdir())}


def collect_post() -> dict:
    snapshot = {
        "profile": POST_STAGE_I,
        "host": _host(),
        "accounts": _accounts(),
        "groups": _groups(),
        "directories": {str(path): _directory(path) for path in (ROOT, ROOT / "releases", CONFIG, STATE,
                          STATE / "owner-control", STATE / "state")},
        "release": _release(),
        "files": {path: _file(Path(path)) for path in FILE_CONTRACT},
        "databases": {"owner": _owner_database(), "evidence": _evidence_database()},
        "units": {name: _unit(name) for name in (SERVICE, SOCKET)},
        "absent": {path: not os.path.lexists(path) for path in POST_ABSENT},
        "broker_processes": _broker_processes(),
        "api": _api(),
    }
    validate_post(snapshot)
    return snapshot


def collect_failed_inert() -> dict:
    """Read only. Never rewrite, checkpoint, remove, or normalize historical data."""
    owner = _owner_database(historical=True)
    evidence = _evidence_database(historical=True)
    used = _used_authorization()
    snapshot = {
        "profile": POST_STAGE_II_FAILED_INERT_V1,
        "host": _host(),
        "accounts": _accounts(),
        "groups": _groups(),
        "directories": {str(path): _directory(path) for path in (ROOT, ROOT / "releases", CONFIG, STATE,
                          STATE / "owner-control", STATE / "state")},
        "release": _release(),
        "files": {path: _file(Path(path)) for path in FAILED_FILES},
        "databases": {"owner": owner, "evidence": evidence},
        "usedAuthorization": used,
        "historicalBaseline": historical_baseline(owner, evidence, used),
        "units": {name: _unit(name) for name in (SERVICE, SOCKET)},
        "absent": {path: not os.path.lexists(path) for path in FAILED_ABSENT},
        "runtimeDirectory": _runtime_directory(),
        "broker_processes": _broker_processes(),
        "broker_uid_processes": _broker_uid_processes(),
        "api": _api(),
    }
    validate_failed_inert(snapshot)
    return snapshot


def collect_pre() -> dict:
    snapshot = {
        "profile": PRE_B1B2B,
        "host": _host(),
        "accounts": _accounts(),
        "groups": _groups(),
        "persistent_paths": {path: os.path.lexists(path) for path in pre_absent_paths()},
        "units": {name: _unit(name) for name in (SERVICE, SOCKET)},
        "broker_processes": _broker_processes(),
    }
    validate_pre(snapshot)
    return snapshot


def main() -> int:
    require(sys.argv[1:] == ["snapshot"], "FIXED_SNAPSHOT_COMMAND_ONLY")
    require(os.name == "posix" and os.geteuid() == 0 and pwd is not None and grp is not None,
            "ROOT_LINUX_REQUIRED")
    if TRUSTED_DEV_PROFILE == POST_STAGE_I:
        snapshot = collect_post()
    elif TRUSTED_DEV_PROFILE == POST_STAGE_II_FAILED_INERT_V1:
        snapshot = collect_failed_inert()
    elif TRUSTED_DEV_PROFILE == PRE_B1B2B:
        snapshot = collect_pre()
    else:
        raise LifecycleError("UNACCEPTED_LIFECYCLE_PROFILE")
    print(json.dumps(snapshot, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LifecycleError, OSError, KeyError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"LIFECYCLE_VALIDATION_FAILED:{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
