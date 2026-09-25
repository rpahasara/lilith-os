#!/usr/bin/python3 -IS
"""LILITH 15B2b-B1c-1A canonical activation acceptance verifier (DEV).

Accepted canonical LTM activation on DEV is defined as the result of THIS
program, owner-installed root:root 0755 at /usr/local/sbin/lilith-activation-verify
and never deployed by routine automation. It imports nothing from the
replaceable Core API, reads no environment or arguments, and accepts only:

  /etc/lilith-os-dev/activation/grant.json       owner activation grant
  /etc/lilith-os-dev/activation/grant.json.sig   SSH signature over it
  /etc/lilith-os-dev/activation/allowed-signers  pinned owner public key

each root-owned, not group/other-writable, beneath root-owned parents, with the
signature verified by /usr/bin/ssh-keygen under a dedicated namespace. The
owner private key never exists on the host, so neither `lilith`, the deployed
code, nor the routine deployer can mint an accepted activation.

canonical-runtime.json is advisory application configuration only: it is
reported, never trusted, and can never make activation accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path


AUTHORITY_DIR = Path("/etc/lilith-os-dev/activation")
ADVISORY_CONFIG = Path("/etc/lilith-os-dev/canonical-runtime.json")
MACHINE_ID = Path("/etc/machine-id")
SSH_KEYGEN = "/usr/bin/ssh-keygen"
GRANT = "grant.json"
SIGNATURE = "grant.json.sig"
SIGNERS = "allowed-signers"
NAMESPACE = "lilith-canonical-activation"
IDENTITY = "lilith-owner"
SCHEMA = "lilith.canonical-activation-grant.v1"
GRANT_KEYS = frozenset(
    {"schema", "environment", "hostMachineId", "capabilities", "grantId", "notBefore", "notAfter"}
)
ALLOWED_CAPABILITIES = frozenset({"canonical_memory.project_codename.mutate"})
GRANT_ID = re.compile(r"[0-9a-f]{32}\Z")
MAX_BYTES = 8192


class NotAccepted(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _trusted(path: Path, uid: int, directory: bool) -> None:
    try:
        details = os.lstat(path)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise NotAccepted("AUTHORITY_PATH_UNREADABLE") from exc
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(details.st_mode) or details.st_uid != uid or details.st_mode & 0o022:
        raise NotAccepted("UNTRUSTED_AUTHORITY_PATH")


def _read(path: Path, uid: int, absent: str) -> bytes:
    try:
        _trusted(path, uid, directory=False)
    except FileNotFoundError as exc:
        raise NotAccepted(absent) from exc
    data = path.read_bytes()
    if not data or len(data) > MAX_BYTES:
        raise NotAccepted("AUTHORITY_FILE_SIZE_INVALID")
    return data


def verify(
    authority_dir: Path = AUTHORITY_DIR,
    machine_id_path: Path = MACHINE_ID,
    *,
    uid: int = 0,
    now: int | None = None,
    ssh_keygen: str = SSH_KEYGEN,
) -> dict:
    """Return accepted-grant facts or raise NotAccepted; never trusts the caller."""
    for directory in (authority_dir.parent, authority_dir):
        try:
            _trusted(directory, uid, directory=True)
        except FileNotFoundError as exc:
            raise NotAccepted("AUTHORITY_DIRECTORY_ABSENT") from exc
    raw = _read(authority_dir / GRANT, uid, "GRANT_ABSENT")
    signature = authority_dir / SIGNATURE
    signers = authority_dir / SIGNERS
    _read(signature, uid, "SIGNATURE_ABSENT")
    _read(signers, uid, "OWNER_SIGNER_ABSENT")
    try:
        grant = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise NotAccepted("GRANT_MALFORMED") from exc
    if not isinstance(grant, dict) or set(grant) != GRANT_KEYS or grant["schema"] != SCHEMA:
        raise NotAccepted("GRANT_MALFORMED")
    if grant["environment"] != "dev":
        raise NotAccepted("GRANT_ENVIRONMENT_MISMATCH")
    if grant["hostMachineId"] != machine_id_path.read_text(encoding="ascii").strip():
        raise NotAccepted("GRANT_HOST_MISMATCH")
    capabilities = grant["capabilities"]
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(item, str) for item in capabilities)
        or len(set(capabilities)) != len(capabilities)
        or not set(capabilities) <= ALLOWED_CAPABILITIES
    ):
        raise NotAccepted("GRANT_CAPABILITY_INVALID")
    if not isinstance(grant["grantId"], str) or not GRANT_ID.match(grant["grantId"]):
        raise NotAccepted("GRANT_MALFORMED")
    window = (grant["notBefore"], grant["notAfter"])
    if any(isinstance(v, bool) or not isinstance(v, int) for v in window) or window[0] >= window[1]:
        raise NotAccepted("GRANT_MALFORMED")
    current = int(time.time()) if now is None else now
    if not window[0] <= current < window[1]:
        raise NotAccepted("GRANT_NOT_CURRENT")
    result = subprocess.run(
        [ssh_keygen, "-Y", "verify", "-f", str(signers), "-I", IDENTITY,
         "-n", NAMESPACE, "-s", str(signature)],
        input=raw, capture_output=True, timeout=10,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if result.returncode != 0:
        raise NotAccepted("SIGNATURE_INVALID")
    return {
        "grantId": grant["grantId"],
        "capabilities": sorted(capabilities),
        "notAfter": grant["notAfter"],
        "grantSha256": hashlib.sha256(raw).hexdigest(),
    }


def _advisory_enabled() -> str:
    try:
        return str(json.loads(ADVISORY_CONFIG.read_text(encoding="utf-8")).get("canonicalLtmEnabled") is True).lower()
    except (OSError, ValueError, AttributeError):
        return "unreadable"


def main() -> int:
    if sys.argv[1:]:
        print("usage: lilith-activation-verify", file=sys.stderr)
        return 2
    advisory = _advisory_enabled()
    try:
        accepted = verify()
    except NotAccepted as exc:
        print(f"ACTIVATION=NOT_ACCEPTED reason={exc.reason} advisoryConfigEnabled={advisory}")
        return 1
    print("ACTIVATION=ACCEPTED " + json.dumps(accepted, sort_keys=True)
          + f" advisoryConfigEnabled={advisory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
