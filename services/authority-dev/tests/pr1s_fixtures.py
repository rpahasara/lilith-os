"""TEST_ONLY fixtures for 15B2b-B1b-3e PR-1S (runtime wiring), repository only.

`Pr1Host` is a synthetic PR-1B host tree under a TEMPORARY root, built only
through the live-capable PR-1S components (durable ledger, filesystem witness
store and writer, hold store writer, installer-shaped files) with the Source
Prep B TEST identities in the TEST environment `test`. It is never pointed
at `/`, never at DEV, and holds no real key, credential, witness, or
authority. Keys are the existing TEST_ONLY fixture seeds.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control",
             ROOT / "services/owner-memory-control/tests", ROOT / "services/authority-dev",
             ROOT / "services/authority-dev/ceremony", ROOT / "services/recovery-witness", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import synthetic_authority as SA  # noqa: E402
import synthetic_b1b3e as F  # noqa: E402
import synthetic_b1b3e_prep_b as PB  # noqa: E402
from lilith_authority_dev.ledger import DurableAuthorityLedgerV1  # noqa: E402
from lilith_authority_host import inputs as HI  # noqa: E402
from lilith_authority_host import paths as P  # noqa: E402
from lilith_authority_host.store_observer import observe_witness_state  # noqa: E402
from lilith_authority_root.hold_store import HoldStoreV1  # noqa: E402
from lilith_owner_memory import authority_ledger_journal as J  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402
from lilith_recovery_witness.credential import WitnessSigningKeyV1  # noqa: E402
from lilith_recovery_witness.storage import FilesystemWitnessStorageV1  # noqa: E402
from lilith_recovery_witness.writer import DevSyntheticWitnessWriterV1  # noqa: E402

ENV = "test"                          # the TEST fixtures' exact environment; nothing maps it onto dev
POSIX = os.name == "posix"
UID = os.getuid() if POSIX else 0
GID = os.getgid() if POSIX else 0
WITNESS_PROFILE = B.witness_profile(ENV)
CUSTODY_PROFILE = SC.custody_profile(ENV)
RELEASE_SHA = "c608fc0ffaeee41d7ebf007dc0a66321a1907d31"
P0 = PB.P0
T_GENESIS = "2026-09-26T07:00:00Z"
WITNESS_CIPHERTEXT = b"TEST_ONLY PR-1S stand-in K-WIT ciphertext (never a credential)"


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def root_anchor_document() -> dict[str, Any]:
    return {"schemaVersion": 1, "rootKeyId": SA.ROOT_KEY_ID, "environment": ENV, "algorithm": "Ed25519",
            "publicKey": SA.public_b64("root")}


def witness_anchor_document(name: str = "witness") -> dict[str, Any]:
    return {"schemaVersion": 1, "witnessKeyId": B.WITNESS_KEY_ID, "environment": ENV, "algorithm": "Ed25519",
            "publicKey": F.public_b64(name)}


def witness_publication(name: str = "witness", **custody: Any) -> dict[str, Any]:
    value = B.witness_publication(F.raw_public(name), WITNESS_CIPHERTEXT, PB.MACHINE_ID, profile=WITNESS_PROFILE)
    value["custodyEvidence"].update(custody)
    return value


def signing_key(name: str = "witness") -> WitnessSigningKeyV1:
    return WitnessSigningKeyV1(F.private(name))


def ledger_observation_initial(registry: dict[str, Any]) -> RC.AuthorityLedgerObservationV1:
    op = J.genesis_op(registry)
    sequence, head = J.initial_position(registry)
    return RC.AuthorityLedgerObservationV1(ENV, A_epoch(registry), sequence, head, registry["registryVersion"],
                                           tuple(op["signingKeyIds"]))


def A_epoch(registry: dict[str, Any]):
    from lilith_owner_memory import authority_contracts as A
    return A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"])


def _write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, mode)


def _dir(path: Path, mode: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    return path


class Pr1Host:
    """A synthetic PR-1B host under `root`: skeleton, custody, anchors,
    registry v1, ledger, pin, witness genesis, and the INITIAL_CUSTODY hold."""

    def __init__(self, directory: str | Path, *, registry: dict[str, Any] | None = None):
        self.root = Path(directory)
        self.registry = registry or PB.g1()
        for path in ("etc/systemd/system", "etc/tmpfiles.d", "usr/local/sbin", "var/lib/systemd", "opt"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        for absolute in (P.AUTHORITY_CONFIG, P.TRUST_DIR, P.REGISTRY_DIR, P.OWNER_INPUT_DIR):
            _dir(self.path(absolute), 0o755)
        for absolute in (P.CREDSTORE, P.CUSTODY_ROOT, P.PREPARED_DIR, P.RETIRED_DIR, P.WITNESS_CREDENTIAL_PARENT,
                         P.WITNESS_CREDENTIAL_ROOT, P.HOLD_STORE_PARENT, P.HOLD_STORE, P.AUTHORITY_STATE):
            _dir(self.path(absolute), 0o700)
        _dir(self.path(P.WITNESS_STATE), 0o750)
        # CURRENT: stand-in ciphertext whose SHA-256 is the Prep B K-ACT publication's blobSha256.
        _write(self.path(P.CURRENT_SLOT), b"TEST_ONLY Prep B encrypted blob " + P0.encode(), 0o600)
        _write(self.path(P.WITNESS_BLOB), WITNESS_CIPHERTEXT, 0o600)
        _write(self.path(f"{P.UNIT_DIR}/lilith-authority-dev.service"),
               (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_bytes(), 0o644)
        self.storage = FilesystemWitnessStorageV1(self.path(P.WITNESS_STATE))
        self.holds = HoldStoreV1(environment=ENV, root=self.root, owner_uid=UID, owner_gid=GID)

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def document(self, absolute: str, value: dict[str, Any]) -> None:
        _write(self.path(absolute), WR.document_bytes(value), 0o644)

    # --------------------------------------------------------- PR-1B steps ---
    def install_public(self) -> Pr1Host:
        self.document(P.REGISTRY_ROOT_ANCHOR, root_anchor_document())
        self.document(P.WITNESS_ANCHOR, witness_anchor_document())
        self.document(f"{P.REGISTRY_DIR}/{HI.registry_file_name(self.registry['registryVersion'])}", self.registry)
        return self

    def provision_ledger(self) -> RC.AuthorityLedgerObservationV1:
        return DurableAuthorityLedgerV1.provision(self.path(P.AUTHORITY_LEDGER), environment=ENV,
                                                  genesis=J.genesis_op(self.registry), expected_uid=UID)

    def ledger(self) -> DurableAuthorityLedgerV1:
        return DurableAuthorityLedgerV1.open_existing(self.path(P.AUTHORITY_LEDGER), environment=ENV,
                                                      expected_uid=UID)

    def ledger_observation(self) -> RC.AuthorityLedgerObservationV1:
        ledger = self.ledger()
        try:
            return ledger.observe()
        finally:
            ledger.close()

    def candidate(self, updated_at: str = T_GENESIS) -> B.GenesisCandidateV1:
        return B.build_genesis_candidate(registry=self.registry, registry_root=F.root(),
                                         ledger_observation=self.ledger_observation(), updated_at=updated_at,
                                         profile=WITNESS_PROFILE)

    def install_owner_inputs(self, pin_digest: str) -> Pr1Host:
        self.document(P.GENESIS_PIN_COPY, WR.OwnerGenesisPinV1(ENV, pin_digest).to_dict())
        self.document(P.AUTHORIZATION_REGISTER_COPY, {
            "registerType": WR.REGISTER_TYPE, "schemaVersion": WR.REGISTER_SCHEMA_VERSION, "environment": ENV,
            "authorizations": [], "headRegistries": [RC.registry_head(self.registry).to_dict()]})
        return self

    def inputs(self) -> HI.HostInputsV1:
        return HI.read_host_inputs(environment=ENV, root=self.root, owner_uid=UID)

    def context(self) -> WR.WitnessStoreContextV1:
        inputs = self.inputs()
        return inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))

    def writer(self, **overrides: Any) -> DevSyntheticWitnessWriterV1:
        value = dict(signing_key=signing_key(), storage=self.storage, profile=WITNESS_PROFILE)
        value.update(overrides)
        return DevSyntheticWitnessWriterV1(**value)

    def bootstrap(self, updated_at: str = T_GENESIS) -> dict[str, Any]:
        return self.writer().bootstrap(registry=self.registry, ledger_observation=self.ledger_observation(),
                                       context=self.context(), updated_at=updated_at)

    def witness_store(self) -> WR.WitnessStoreObservationV1:
        return observe_witness_state(self.path(P.WITNESS_STATE))

    def create_held(self) -> dict[str, Any]:
        return self.holds.create_initial_held(witness_store=self.witness_store(), context=self.context())

    def genesis_host(self) -> Pr1Host:
        """Everything through INITIAL_CUSTODY HELD (P1B-10)."""
        self.install_public()
        self.provision_ledger()
        self.install_owner_inputs(self.candidate().digest)
        self.bootstrap()
        self.create_held()
        return self


# ------------------------------------------------------ installed release ---

@contextlib.contextmanager
def stand_in_wheels():
    """Local stand-ins for the pinned wheel set (the L2 test convention)."""
    import install_authority_dev as I

    saved = (I.WHEEL_HASHES, I.LOCK, I.EXPECTED_PATHS)
    with tempfile.TemporaryDirectory() as directory:
        wheelhouse = Path(directory)
        hashes = {}
        for index, name in enumerate(saved[0]):
            data = f"stand-in wheel {index}".encode()
            (wheelhouse / name).write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        I.WHEEL_HASHES = hashes
        I.LOCK = "".join(f"x{i}==1 --hash=sha256:{h}\n" for i, h in enumerate(hashes.values())).encode()
        try:
            yield wheelhouse
        finally:
            I.WHEEL_HASHES, I.LOCK, I.EXPECTED_PATHS = saved


def release_payloads(wheelhouse: Path) -> dict[str, bytes]:
    import build_authority_dev_release as BR

    return BR.build_payloads(ROOT, wheelhouse)


def install_release(root: Path, sha: str, payloads: dict[str, bytes], *, host_copies: bool = True) -> dict:
    """Write `releases/<sha>` (+ manifest, a stand-in venv), `current`, and the
    host copies of every unit and CLI. Returns the manifest."""
    import install_authority_dev as I

    manifest = I.manifest_for(sha, payloads)
    top = root / f"opt/lilith-authority-dev/releases/{sha}"
    for relative, data in sorted({**payloads, I.MANIFEST: I.canonical(manifest)}.items()):
        target = top.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        os.chmod(target, 0o755 if relative.startswith("cli/") else 0o644)
    (top / "venv/bin").mkdir(parents=True, exist_ok=True)
    (top / "venv/bin/python").write_bytes(b"#!/bin/false\n")
    for directory, subdirs, _files in os.walk(top):
        for name in subdirs:
            os.chmod(Path(directory) / name, 0o755)
    os.chmod(top, 0o755)
    os.chmod(top.parent, 0o755)
    current = root / "opt/lilith-authority-dev/current"
    if current.is_symlink():
        current.unlink()
    os.symlink(f"releases/{sha}", current)
    if host_copies:
        for member, target in P.RELEASE_HOST_TARGETS.items():
            _write(root / target.lstrip("/"), payloads[member], 0o755 if member.startswith("cli/") else 0o644)
    return manifest


# ------------------------------------------------------ verifier owner inputs ---

def fake_systemctl(states: dict[str, dict[str, str]] | None = None):
    base = {unit: {"LoadState": "loaded", "ActiveState": "active", "UnitFileState": "static",
                   "NeedDaemonReload": "no"} for unit in PA.SIGNER_UNITS + PA.WITNESS_UNITS}
    for unit, values in (states or {}).items():
        base[unit].update(values)

    def run(argv):
        unit = argv[-1]
        out = "\n".join(f"{k}={v}" for k, v in base[unit].items())
        return subprocess.CompletedProcess(list(argv), 0, out, "")
    return run


def proof(name: str, detail: str | None = None) -> dict[str, Any]:
    return {"result": "PASS", "transcriptSha256": hashlib.sha256(f"TEST_ONLY transcript {name}".encode()).hexdigest(),
            "detail": detail}


def proofs() -> dict[str, dict[str, Any]]:
    return {name: proof(name, PA.REQUIRED_DEPLOYER_MATURITY if name == "DEPLOYER_DENIAL" else None)
            for name in PA.REQUIRED_PROOFS}


def current_document(host: Pr1Host) -> dict[str, Any]:
    from lilith_authority_root import observers as O

    observed = O.observe_current_blob(host.root)
    value = observed.to_dict()
    return value


def snapshot_inventory() -> dict[str, Any]:
    return {"status": "ACCEPTED", "recordSha256": hashlib.sha256(b"TEST_ONLY PR-2 record").hexdigest(),
            "artefactClasses": ["NO_SNAPSHOTS"], "namedDebts": []}


def offhost_material(host: Pr1Host, *, manifest_sha256: str, **overrides: Any) -> dict[str, Any]:
    pin = json.loads(host.path(P.GENESIS_PIN_COPY).read_bytes())
    value = {
        "status": "PRESENT", "registerSha256": hashlib.sha256(host.path(P.AUTHORIZATION_REGISTER_COPY).read_bytes())
        .hexdigest(), "genesisPinDigest": pin["genesisWitnessDigest"],
        "kRootPublicKeySha256": hashlib.sha256(F.root().public_key).hexdigest(),
        "kWitPublicKeySha256": hashlib.sha256(F.raw_public("witness")).hexdigest(),
        "kActPublicationSha256": hashlib.sha256(PB.publication_bytes(P0)).hexdigest(),
        "registryHead": RC.registry_head(host.registry).to_dict(), "releaseSha": RELEASE_SHA,
        "releaseManifestSha256": manifest_sha256, "authorizationIds": [], "burnedOrdinals": []}
    value.update(overrides)
    return value


def verifier_inputs(host: Pr1Host, *, manifest_sha256: str, first_current: dict[str, Any] | None = None,
                    with_pr2: bool = False, with_pr3: bool = False, **overrides: Any) -> dict[str, Any]:
    value = {
        "inputType": "LILITH_PR1_VERIFIER_INPUTS", "schemaVersion": 1, "environment": ENV,
        "releaseSha": RELEASE_SHA, "attestedManifestSha256": manifest_sha256, "reviewedRuntimeDigests": None,
        "pinnedCurrentSha256": PB.BLOB[P0],
        "firstPreflightCurrent": first_current or current_document(host),
        "kActPublication": b64u(PB.publication_bytes(P0)),
        "kWitPublication": b64u(SC.canonical_publication_bytes(witness_publication())),
        "proofs": proofs(), "activation": {"line": PA.ACTIVATION_DARK_LINE, "b1cUnchanged": True},
        "snapshotInventory": snapshot_inventory() if with_pr2 else None,
        "offHostMaterial": offhost_material(host, manifest_sha256=manifest_sha256) if with_pr3 else None,
    }
    value.update(overrides)
    return value


def health_p0() -> dict[str, Any]:
    return PB.health(P0)


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, symlinks=True)
