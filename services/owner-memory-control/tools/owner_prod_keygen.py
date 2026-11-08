#!/usr/bin/python3 -IB
"""OWNER_PROD host key ceremony (P3): K-ACT and K-WIT for the production owner. SOURCE ONLY; never installed.

    python3 -I -B owner_prod_keygen.py actor
    python3 -I -B owner_prod_keygen.py witness

The production twin of `lilith-authority-keygen-dev` (`actor` and `witness` forms only; no successor). It is a separate
tool, so the DEV keygen stays byte-identical. It reuses that tool's validated mechanics (in-memory generation, the
systemd-creds pipe, exclusive `O_EXCL` writes, the CURRENT-unchanged proof) and changes exactly three things:

- the host: `lilith-01` whose machine ID hashes to `PROD_MACHINE_ID_SHA256`, and the root-installed `deployment.json` naming OWNER_PROD. The DEV
  machine ID is refused even if both were equal. `PROD_MACHINE_ID_SHA256` is unpinned (None) in source: a reviewed commit pins
  the digest from a read-only PROD observation, so until then both forms refuse with PROD_MACHINE_ID_NOT_PINNED;
- the key IDs: `prod.owner-prod.actor.1` (K-ACT) and `prod.witness.owner-prod.1` (K-WIT), matching the runtime
  OWNER_PROD profiles; a test pins them;
- the publications: profile `OWNER_PROD`, environment `prod`.

Slot, credential and unit names are the DEV ones (documented naming debt). Run once per key, as root, by the owner,
inside a separately approved PROD ceremony step. It prints one canonical public publication; nothing private leaves it.
"""

from __future__ import annotations

import hashlib
import re
import os
import sys
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CEREMONY = ROOT / "services/authority-dev/ceremony"
if str(CEREMONY) not in sys.path:
    sys.path.insert(0, str(CEREMONY))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import lilith_authority_keygen_dev as G  # noqa: E402  (the DEV keygen's mechanics, unchanged)

PROFILE = "OWNER_PROD"
ENVIRONMENT = "prod"
KEY_ID = "prod.owner-prod.actor.1"
WITNESS_KEY_ID = "prod.witness.owner-prod.1"
HOSTNAME = "lilith-01"
# D-9 (digest pin): SHA-256 of the exact bytes of lilith-01's /etc/machine-id (32 lowercase hex + "\n"), as the
# COMPLETE read-only audit run 2 (2026-11-05) recorded it. The raw ID is never a committed constant: the host's own
# file is read at run time, must hash to this pin, and then (as before) goes into the custody evidence the keygen
# prints on the host. Pinned by the owner's D-9 approval (2026-11-05); value from the sealed run-2 audit evidence.
PROD_MACHINE_ID_SHA256: str | None = "1b1d67880b40565fda61c2944d20c9e9d90c650846e10cac3eb900e6a9ac1001"
_MACHINE_ID_BYTES = re.compile(rb"[0-9a-f]{32}\n\Z")
DEPLOYMENT_PATH = "/etc/lilith-authority-dev/deployment.json"
DEPLOYMENT = b'{"environment":"prod","profile":"OWNER_PROD","schemaVersion":1}'
ACTOR, WITNESS = "actor", "witness"
Refused, Failed, Host = G.Refused, G.Failed, G.Host


def deployment_is_prod(host: Host) -> bool:
    """True only for the exact root-owned OWNER_PROD selection; anything present but different refuses."""
    path = host.path(DEPLOYMENT_PATH)
    if not os.path.lexists(path):
        return False
    G._root_owned(host, path, kind="file", mode=0o644, missing="DEPLOYMENT_INVALID", bad="DEPLOYMENT_INVALID")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise Refused("DEPLOYMENT_INVALID") from exc
    if data.rstrip(b"\n") != DEPLOYMENT:
        raise Refused("DEPLOYMENT_INVALID")
    return True


def machine_digest_pin(machine_pin: str | None = None, machine_digest: str | None = None) -> str | None:
    """The pinned digest: the committed `PROD_MACHINE_ID_SHA256`, or a TEST seam (a digest, or a raw test ID hashed
    exactly as the host file is: ID + "\n")."""
    if machine_digest is not None:
        return machine_digest
    if machine_pin is not None:
        return hashlib.sha256((machine_pin + "\n").encode("ascii")).hexdigest()
    return PROD_MACHINE_ID_SHA256


def read_prod_machine_id(host: Host, pin_sha256: str) -> str:
    """The host's raw machine ID, only if its file is exactly one ID line hashing to the pin and is not the DEV ID."""
    try:
        raw = host.path("/etc/machine-id").read_bytes()
    except OSError as exc:
        raise Refused("NOT_PROD_HOST") from exc
    if not _MACHINE_ID_BYTES.fullmatch(raw) or hashlib.sha256(raw).hexdigest() != pin_sha256:
        raise Refused("NOT_PROD_HOST")
    machine_id = raw.decode("ascii").strip()
    if machine_id == G.DEV_MACHINE_ID:
        raise Refused("NOT_PROD_HOST")
    return machine_id


def host_preflight(host: Host, *, euid: int, isolated: bool, hostname: str, machine_pin: str | None = None,
                   machine_digest: str | None = None) -> str:
    """The PROD host checks, then the DEV keygen's own custody checks. Returns the machine ID."""
    pin = machine_digest_pin(machine_pin, machine_digest)
    if euid != 0:
        raise Refused("NOT_ROOT")
    if not isolated:
        raise Refused("INTERPRETER_NOT_ISOLATED")
    if pin is None:
        raise Refused("PROD_MACHINE_ID_NOT_PINNED")
    machine_id = read_prod_machine_id(host, pin)
    if hostname.split(".", 1)[0] != HOSTNAME:
        raise Refused("NOT_PROD_HOST")
    if not deployment_is_prod(host):
        raise Refused("DEPLOYMENT_NOT_OWNER_PROD")
    try:
        swaps = host.path("/proc/swaps").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise Refused("SWAP_STATE_UNKNOWN") from exc
    if not swaps or any(line.strip() for line in swaps[1:]):
        raise Refused("SWAP_ACTIVE")
    G._root_owned(host, host.path(G.HOST_KEY), kind="file", mode=0o400,
                  missing="HOST_CREDENTIAL_KEY_ABSENT", bad="HOST_CREDENTIAL_KEY_CUSTODY")
    G._root_owned(host, host.path(G.SYSTEMD_CREDS), kind="file", mode=0o755,
                  missing="SYSTEMD_CREDS_ABSENT", bad="SYSTEMD_CREDS_CUSTODY")
    G._root_owned(host, host.path(G.CREDSTORE), kind="dir", mode=0o700,
                  missing="CREDSTORE_ABSENT", bad="CREDSTORE_CUSTODY")
    return machine_id


def actor_preflight(host: Host, **facts) -> str:
    machine_id = host_preflight(host, **facts)
    if os.path.lexists(host.path(G.CREDENTIAL_PATH)):
        raise Refused("CREDENTIAL_ALREADY_PRESENT")
    if any(host.path(G.CREDSTORE).iterdir()):
        raise Refused("CREDSTORE_NOT_EMPTY")
    return machine_id


def witness_preflight(host: Host, **facts) -> tuple[str, G.CurrentFacts]:
    machine_id = host_preflight(host, **facts)
    if sorted(entry.name for entry in host.path(G.CREDSTORE).iterdir()) != [G.SLOT_NAME]:
        raise Refused("CREDSTORE_NOT_EXACTLY_CURRENT")
    G._root_owned(host, host.path(G.CREDENTIAL_PATH), kind="file", mode=0o600, missing="CURRENT_ABSENT",
                  bad="CURRENT_CUSTODY")
    G._root_owned(host, host.path(G.WITNESS_PARENT), kind="dir", mode=0o700, missing="WITNESS_PARENT_ABSENT",
                  bad="WITNESS_PARENT_CUSTODY")
    if sorted(entry.name for entry in host.path(G.WITNESS_PARENT).iterdir()) != ["credentials"]:
        raise Refused("WITNESS_PARENT_UNEXPECTED_ENTRY")
    G._root_owned(host, host.path(G.WITNESS_CREDENTIAL_DIR), kind="dir", mode=0o700,
                  missing="WITNESS_CREDENTIAL_DIR_ABSENT", bad="WITNESS_CREDENTIAL_DIR_CUSTODY")
    if any(host.path(G.WITNESS_CREDENTIAL_DIR).iterdir()):
        raise Refused("WITNESS_CREDENTIAL_ALREADY_PRESENT")
    try:
        return machine_id, G.current_facts(host)
    except OSError as exc:
        raise Refused("CURRENT_CUSTODY") from exc


def _custody(credential_name: str, credential_path: str, machine_id: str, ciphertext: bytes) -> dict:
    return {"credentialName": credential_name, "credentialPath": credential_path, "withKey": "host",
            "machineId": machine_id, "blobByteSize": len(ciphertext),
            "blobSha256": hashlib.sha256(ciphertext).hexdigest()}


def publication(public_key: bytes, ciphertext: bytes, machine_id: str) -> dict:
    """The K-ACT publication: the DEV v1 shape with the OWNER_PROD identity."""
    if not isinstance(public_key, bytes) or len(public_key) != 32 or not ciphertext:
        raise ValueError("public key or ciphertext invalid")
    return {"publicationType": G.PUBLICATION_TYPE, "schemaVersion": G.PUBLICATION_SCHEMA_VERSION, "profile": PROFILE,
            "publicVerificationMaterial": {"keyId": KEY_ID, "signingDomain": G.SIGNING_DOMAIN,
                                           "evidenceTypes": list(G.EVIDENCE_TYPES), "environment": ENVIRONMENT,
                                           "algorithm": G.ALGORITHM, "publicKey": G._b64u(public_key),
                                           "publicKeySha256": hashlib.sha256(public_key).hexdigest()},
            "custodyEvidence": _custody(G.CREDENTIAL_NAME, G.CREDENTIAL_PATH, machine_id, ciphertext)}


def witness_publication(public_key: bytes, ciphertext: bytes, machine_id: str) -> dict:
    if not isinstance(public_key, bytes) or len(public_key) != 32 or not ciphertext:
        raise ValueError("public key or ciphertext invalid")
    return {"publicationType": G.WITNESS_PUBLICATION_TYPE, "schemaVersion": G.PUBLICATION_SCHEMA_VERSION,
            "profile": PROFILE,
            "witnessKey": {"witnessKeyId": WITNESS_KEY_ID, "environment": ENVIRONMENT, "algorithm": G.ALGORITHM,
                           "publicKey": G._b64u(public_key), "publicKeySha256": hashlib.sha256(public_key).hexdigest()},
            "custodyEvidence": _custody(G.WITNESS_CREDENTIAL_NAME, G.WITNESS_BLOB_PATH, machine_id, ciphertext)}


def actor_ceremony(host: Host, machine_id: str, *,
                   key_factory: Callable[[], Ed25519PrivateKey] = Ed25519PrivateKey.generate,
                   encrypt: Callable[[bytes], bytes] = G.systemd_encrypt) -> dict:
    public, ciphertext = G._encrypted_key(key_factory, encrypt)
    G.write_blob(host, ciphertext)
    return publication(public, ciphertext, machine_id)


def witness_ceremony(host: Host, machine_id: str, before: G.CurrentFacts, *,
                     key_factory: Callable[[], Ed25519PrivateKey] = Ed25519PrivateKey.generate,
                     encrypt: Callable[[bytes], bytes] = G.witness_encrypt) -> dict:
    public, ciphertext = G._encrypted_key(key_factory, encrypt)
    G._require_current_unchanged(host, before)
    G.write_witness_blob(host, ciphertext)
    G._require_current_unchanged(host, before)
    return witness_publication(public, ciphertext, machine_id)


def main(argv: list[str] | None = None, *, host: Host = Host()) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv not in ([ACTOR], [WITNESS]):
            raise Refused("USAGE_ACTOR_OR_WITNESS")
        facts = dict(euid=os.geteuid(), isolated=bool(sys.flags.isolated), hostname=os.uname().nodename)
        if argv == [ACTOR]:
            machine_id, before = actor_preflight(host, **facts), None
        else:
            machine_id, before = witness_preflight(host, **facts)
        G.restrict_process()
    except Refused as refused:
        print(f"owner-prod-keygen: REFUSED {refused.reason}", file=sys.stderr)
        return G.EXIT_REFUSED
    try:
        result = actor_ceremony(host, machine_id) if argv == [ACTOR] else witness_ceremony(host, machine_id, before)
    except Failed as failed:
        print(f"owner-prod-keygen: FAILED {failed.reason}", file=sys.stderr)
        return G.EXIT_FAILED
    sys.stdout.buffer.write(G.canonical(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
