"""15B2b-B1b-3e PR-1S: the PR-1 owner acceptance evidence package (pure).

Design: docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md
§17, §19, §23, §24 (RR-34, RR-38, RR-39, RR-40).
Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

Pure verifiers and a canonical package over caller-supplied observations.
Nothing here reads a file, the environment, a network, a database, or a
credential; nothing signs; nothing mutates.

- `hold_listing_digest` / `hold_snapshot_document` / `parse_hold_snapshot`
  (RR-34, §17): the complete root hold-store observation in its one wire
  form, bound by the listing digest SHA-256(JCS([[name, sha256(bytes)], ...]))
  sorted by name. The authority signer accepts only this form (C-4).
- `current_preservation_reason` (§24): CURRENT ciphertext identity before /
  after, compared without decryption.
- `verify_installed_release` (§23): the selected release tree against its
  attested manifest, plus host-installed unit and CLI bytes.
- `evaluate_pr1_acceptance` (§19): E-1 .. E-24 as closed checks over the
  Source Prep B readiness (`HOLD_RELEASE_ELIGIBILITY` or `FULL_READINESS`)
  and the PR-1 observations, producing ONE canonical package and its
  domain-separated digest. Missing PR-2 / PR-3 input is NOT_READY, never a
  default PASS.
- `release_decision` (RR-38): INITIAL_CUSTODY HELD -> RELEASED planning is
  permitted only when the owner-approved digest equals a current re-run.

Every result is non-authority:

    complete observation != authority
    on-host PASS         != owner acceptance
    owner acceptance     != activation
    RELEASED             != issuance permission
    package digest       != authority signature
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

import rfc8785
from lilith_memory.owner_proof import OwnerProofError, _digest

from . import authority_contracts as A
from . import pr1_bootstrap as B
from . import recovery_contracts as R
from . import rotation_contracts as RC
from . import successor_custody as SC
from . import successor_readiness as SR
from . import witness_readiness as WR

PASS = WR.PASS
FAIL = WR.FAIL
READY = WR.READY
NOT_READY = WR.NOT_READY

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jcs(value: Any) -> bytes:
    return rfc8785.dumps(value)


# ------------------------------------------------ hold store snapshot (RR-34) ---

HOLD_STORE_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE_DIRECTORY = HOLD_STORE_PARENT + "/holds"
HOLD_SNAPSHOT_TYPE = "LILITH_HOLD_STORE_SNAPSHOT"
HOLD_SNAPSHOT_SCHEMA_VERSION = 1
HOLD_SNAPSHOT_FIELDS = frozenset({"snapshotType", "schemaVersion", "environment", "directory", "entries",
                                  "listingDigest"})
_HOLD_ENTRY_FIELDS = frozenset({"name", "data"})
MAX_HOLD_RECORDS = 256
MAX_HOLD_RECORD_BYTES = 4096
_HOLD_NAME = re.compile(r"[0-9a-f]{64}\.json\Z")

HOLD_SNAPSHOT_REASONS = (
    "HOLD_SNAPSHOT_MISSING",
    "HOLD_SNAPSHOT_MALFORMED",
    "HOLD_SNAPSHOT_ENVIRONMENT_MISMATCH",
    "HOLD_SNAPSHOT_DIRECTORY_MISMATCH",
    "HOLD_SNAPSHOT_TOO_LARGE",
    "HOLD_SNAPSHOT_ENTRY_INVALID",
    "HOLD_SNAPSHOT_NOT_SORTED",
    "HOLD_SNAPSHOT_DIGEST_MISMATCH",
)


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64u_decode(value: Any) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]*", value):
        raise ValueError("not base64url")
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _b64u(raw) != value:
        raise ValueError("non-canonical base64url")
    return raw


def hold_listing_digest(observation: SC.HoldStoreObservationV1) -> str:
    """SHA-256 of the JCS list of `[name, sha256(bytes)]`, sorted by name (§17).

    Every entry is listed; a non-regular entry has no digest and is refused.
    Equal digests never mean the records are valid: each is still parsed.
    """
    if not isinstance(observation, SC.HoldStoreObservationV1):
        raise ValueError("not a hold-store observation")
    pairs = []
    for entry in observation.entries:
        if not isinstance(entry, WR.StoreEntryV1) or entry.kind != WR.REGULAR or not isinstance(entry.data, bytes):
            raise ValueError("hold-store entry is not a regular file with bytes")
        pairs.append([entry.name, _sha256(entry.data)])
    pairs.sort(key=lambda pair: pair[0])
    return _sha256(_jcs(pairs))


def hold_snapshot_document(observation: SC.HoldStoreObservationV1, *, environment: str) -> dict[str, Any]:
    """The complete root observation in its one wire form (sorted, unique names)."""
    entries = sorted(observation.entries, key=lambda entry: entry.name)
    names = [entry.name for entry in entries]
    if len(set(names)) != len(names) or len(entries) > MAX_HOLD_RECORDS:
        raise ValueError("hold-store listing is not a set of bounded unique names")
    return {"snapshotType": HOLD_SNAPSHOT_TYPE, "schemaVersion": HOLD_SNAPSHOT_SCHEMA_VERSION,
            "environment": environment, "directory": HOLD_STORE_DIRECTORY,
            "entries": [{"name": entry.name, "data": _b64u(entry.data)} for entry in entries],
            "listingDigest": hold_listing_digest(observation)}


def parse_hold_snapshot(document: Any, *, environment: str
                        ) -> tuple[SC.HoldStoreObservationV1 | None, str | None, str | None]:
    """(observation, None, None) or (None, reason, detail). Never a subset:
    a single hold record, an unsorted or duplicated listing, or a listing
    whose digest does not equal its own entries is refused before any hold
    is judged. Completeness is the root observer's property (§17); this
    checks that the form is the observer's."""
    if document is None:
        return None, "HOLD_SNAPSHOT_MISSING", None
    if not isinstance(document, Mapping) or set(document) != HOLD_SNAPSHOT_FIELDS \
            or document.get("snapshotType") != HOLD_SNAPSHOT_TYPE \
            or type(document.get("schemaVersion")) is not int \
            or document.get("schemaVersion") != HOLD_SNAPSHOT_SCHEMA_VERSION \
            or not isinstance(document.get("entries"), list):
        return None, "HOLD_SNAPSHOT_MALFORMED", None
    if document["environment"] != environment:
        return None, "HOLD_SNAPSHOT_ENVIRONMENT_MISMATCH", str(document["environment"])
    if document["directory"] != HOLD_STORE_DIRECTORY:
        return None, "HOLD_SNAPSHOT_DIRECTORY_MISMATCH", None
    if len(document["entries"]) > MAX_HOLD_RECORDS:
        return None, "HOLD_SNAPSHOT_TOO_LARGE", None
    entries = []
    for item in document["entries"]:
        if not isinstance(item, Mapping) or set(item) != _HOLD_ENTRY_FIELDS \
                or not isinstance(item["name"], str) or _HOLD_NAME.fullmatch(item["name"]) is None:
            return None, "HOLD_SNAPSHOT_ENTRY_INVALID", None
        try:
            data = _b64u_decode(item["data"])
        except ValueError:
            return None, "HOLD_SNAPSHOT_ENTRY_INVALID", item["name"]
        if not data or len(data) > MAX_HOLD_RECORD_BYTES:
            return None, "HOLD_SNAPSHOT_ENTRY_INVALID", item["name"]
        entries.append(WR.StoreEntryV1(item["name"], WR.REGULAR, data))
    names = [entry.name for entry in entries]
    if names != sorted(set(names)):
        return None, "HOLD_SNAPSHOT_NOT_SORTED", None
    observation = SC.HoldStoreObservationV1(tuple(entries))
    listed = document["listingDigest"]
    if not isinstance(listed, str) or not hmac.compare_digest(listed, hold_listing_digest(observation)):
        return None, "HOLD_SNAPSHOT_DIGEST_MISMATCH", None
    return observation, None, None


# --------------------------------------------- CURRENT preservation (§24) ---

ABSENT = WR.ABSENT


@dataclass(frozen=True)
class CurrentBlobObservationV1:
    """Root `lstat` + ciphertext SHA-256 of CURRENT. Never decrypted."""

    path: str
    kind: str
    uid: int | None = None
    gid: int | None = None
    mode: int | None = None
    device: int | None = None
    inode: int | None = None
    size: int | None = None
    mtime_ns: int | None = None
    ctime_ns: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Device, inode and nanosecond times exceed the JCS safe-integer domain: decimal strings.
        return {"path": self.path, "kind": self.kind, "uid": self.uid, "gid": self.gid,
                "mode": None if self.mode is None else format(self.mode, "04o"), "device": _decimal(self.device),
                "inode": _decimal(self.inode), "size": self.size, "mtimeNs": _decimal(self.mtime_ns),
                "ctimeNs": _decimal(self.ctime_ns), "sha256": self.sha256}


def _decimal(value: int | None) -> str | None:
    return None if value is None else str(value)


def parse_decimal(value: Any) -> int | None:
    """Inverse of the decimal-string encoding: canonical non-negative decimal or `None`."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or (len(value) > 1 and value[0] == "0"):
        raise ValueError("not a canonical decimal string")
    return int(value)


# Closed, ordered preservation taxonomy.
CURRENT_PRESERVATION_REASONS = (
    "CURRENT_UNOBSERVED_BEFORE",
    "CURRENT_UNOBSERVED_AFTER",
    "CURRENT_PATH_MISMATCH",
    "CURRENT_MISSING",
    "CURRENT_NOT_REGULAR",
    "CURRENT_OWNER_MISMATCH",
    "CURRENT_MODE_MISMATCH",
    "CURRENT_HASH_UNOBSERVED",
    "CURRENT_SHA256_NOT_PINNED",
    "CURRENT_DEVICE_CHANGED",
    "CURRENT_INODE_CHANGED",
    "CURRENT_SIZE_CHANGED",
    "CURRENT_MTIME_CHANGED",
    "CURRENT_CTIME_CHANGED",
    "CURRENT_SHA256_CHANGED",
)


def current_preservation_reason(before: CurrentBlobObservationV1 | None, after: CurrentBlobObservationV1 | None,
                                *, pinned_sha256: str | None = None, expected_path: str = SC.CURRENT_PATH,
                                owner: tuple[int, int] = (0, 0)) -> str | None:
    """None when CURRENT is the same root 0600 regular file, byte-identical,
    before and after. Identity (`st_dev`, `st_ino`, size) and times
    (`mtime`, `ctime`: a chmod, chown, or rewrite changes `ctime`) must not
    change; a pinned SHA-256 (the accepted `6a61c350…`) must match both."""
    if not isinstance(before, CurrentBlobObservationV1):
        return "CURRENT_UNOBSERVED_BEFORE"
    if not isinstance(after, CurrentBlobObservationV1):
        return "CURRENT_UNOBSERVED_AFTER"
    for observed in (before, after):
        if observed.path != expected_path:
            return "CURRENT_PATH_MISMATCH"
        if observed.kind == ABSENT:
            return "CURRENT_MISSING"
        if observed.kind != WR.REGULAR:
            return "CURRENT_NOT_REGULAR"
        if (observed.uid, observed.gid) != tuple(owner):
            return "CURRENT_OWNER_MISMATCH"
        if observed.mode != 0o600:
            return "CURRENT_MODE_MISMATCH"
        if not isinstance(observed.sha256, str) or _HEX64.fullmatch(observed.sha256) is None:
            return "CURRENT_HASH_UNOBSERVED"
        if pinned_sha256 is not None and observed.sha256 != pinned_sha256:
            return "CURRENT_SHA256_NOT_PINNED"
    for name, reason in (("device", "CURRENT_DEVICE_CHANGED"), ("inode", "CURRENT_INODE_CHANGED"),
                         ("size", "CURRENT_SIZE_CHANGED"), ("mtime_ns", "CURRENT_MTIME_CHANGED"),
                         ("ctime_ns", "CURRENT_CTIME_CHANGED"), ("sha256", "CURRENT_SHA256_CHANGED")):
        if getattr(before, name) is None or getattr(before, name) != getattr(after, name):
            return reason
    return None


# ------------------------------------------------ installed release (§23) ---

@dataclass(frozen=True)
class ReleaseTreeEntryV1:
    """One entry of `releases/<sha>` (excluding `venv/`), `lstat`-observed."""

    path: str
    kind: str
    uid: int
    gid: int
    mode: int
    sha256: str | None = None


@dataclass(frozen=True)
class InstalledReleaseObservationV1:
    """Root read-only observation of the installed release. Never authority."""

    selector_target: str | None
    release_entries: tuple[str, ...]
    manifest_bytes: bytes | None
    tree: tuple[ReleaseTreeEntryV1, ...]
    venv_file_set_digest: str | None
    host_files: Mapping[str, str | None]      # installed absolute path -> SHA-256 (None: absent)


RELEASE_REASONS = (
    "RELEASE_INPUT_MALFORMED",
    "RELEASE_SELECTOR_MISMATCH",
    "RELEASE_SET_UNEXPECTED",
    "RELEASE_MANIFEST_MISSING",
    "RELEASE_MANIFEST_HASH_MISMATCH",
    "RELEASE_MANIFEST_MALFORMED",
    "RELEASE_TREE_UNEXPECTED_TYPE",
    "RELEASE_TREE_OWNERSHIP",
    "RELEASE_TREE_FILE_MISSING",
    "RELEASE_TREE_FILE_MISMATCH",
    "RELEASE_TREE_EXTRA_FILE",
    "RELEASE_VENV_UNOBSERVED",
    "HOST_FILE_BYTES_MISMATCH",
    "RELEASE_RUNTIME_MANIFEST_MISMATCH",
)
MANIFEST_NAME = "release-manifest.json"


@dataclass(frozen=True)
class ReleaseResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status == PASS


def runtime_files_digest(files: Mapping[str, str], *, prefixes: tuple[str, ...]) -> str:
    """SHA-256 of JCS `{path: sha256}` over the runtime members with `prefixes`."""
    return _sha256(_jcs({path: sha for path, sha in sorted(files.items()) if path.startswith(prefixes)}))


AUTHORITY_RUNTIME_PREFIXES = ("lilith_authority_dev/", "lilith_memory/", "lilith_owner_memory/",
                              "assets/lilith-authority-dev.")
WITNESS_RUNTIME_PREFIXES = ("lilith_recovery_witness/", "assets/lilith-recovery-witness")
ROOT_TOOLING_PREFIXES = ("lilith_authority_root/", "cli/")


def verify_installed_release(observation: Any, *, release_sha: str, attested_manifest_sha256: str,
                             host_targets: Mapping[str, str],
                             reviewed_runtime_digests: Mapping[str, str] | None = None,
                             owner: tuple[int, int] = (0, 0)) -> ReleaseResultV1:
    """§23: the selected release is exactly the attested manifest.

    - `current -> releases/<release_sha>` and `releases/` holds exactly it;
    - `release-manifest.json` hashes to the attested value and names this SHA;
    - every manifest file is present with its bytes, root-owned, mode 0644 or
      0755; directories root 0755; no symlink; no extra file outside `venv/`;
    - the venv file set was observed (drift detection only; built on-host);
    - each host-installed file (units, CLIs) equals its release member;
    - the authority / witness / root-tooling runtime digests equal the
      reviewed source values when given.
    Git SHA alone is never evidence; the bytes are.
    """
    facts: dict[str, Any] = {"releaseSha": release_sha, "authorityGranted": False}
    try:
        if not isinstance(observation, InstalledReleaseObservationV1) or not isinstance(release_sha, str) \
                or _SHA40.fullmatch(release_sha) is None or not isinstance(host_targets, Mapping):
            raise _Rejected("RELEASE_INPUT_MALFORMED")
        _check(observation.selector_target == f"releases/{release_sha}", "RELEASE_SELECTOR_MISMATCH",
               str(observation.selector_target))
        _check(list(observation.release_entries) == [release_sha], "RELEASE_SET_UNEXPECTED",
               ",".join(observation.release_entries))
        _check(observation.manifest_bytes is not None, "RELEASE_MANIFEST_MISSING")
        _check(_sha256(observation.manifest_bytes) == attested_manifest_sha256, "RELEASE_MANIFEST_HASH_MISMATCH")
        try:
            manifest = json.loads(observation.manifest_bytes)
            files = {item["path"]: item["sha256"] for item in manifest["files"]}
            _check(manifest["candidateSha"] == release_sha and len(files) == len(manifest["files"]),
                   "RELEASE_MANIFEST_MALFORMED")
        except (ValueError, TypeError, KeyError) as exc:
            raise _Rejected("RELEASE_MANIFEST_MALFORMED") from exc
        facts["manifestSha256"] = attested_manifest_sha256
        expected = {**files, MANIFEST_NAME: _sha256(observation.manifest_bytes)}
        seen: set[str] = set()
        for entry in observation.tree:
            _check(entry.kind in (WR.REGULAR, WR.DIRECTORY), "RELEASE_TREE_UNEXPECTED_TYPE", entry.path)
            _check((entry.uid, entry.gid) == tuple(owner), "RELEASE_TREE_OWNERSHIP", entry.path)
            if entry.kind == WR.DIRECTORY:
                _check(entry.mode == 0o755, "RELEASE_TREE_OWNERSHIP", entry.path)
                continue
            _check(entry.mode in (0o644, 0o755), "RELEASE_TREE_OWNERSHIP", entry.path)
            _check(entry.path in expected, "RELEASE_TREE_EXTRA_FILE", entry.path)
            _check(entry.sha256 == expected[entry.path], "RELEASE_TREE_FILE_MISMATCH", entry.path)
            seen.add(entry.path)
        missing = sorted(set(expected) - seen)
        _check(not missing, "RELEASE_TREE_FILE_MISSING", missing[0] if missing else None)
        _check(isinstance(observation.venv_file_set_digest, str)
               and _HEX64.fullmatch(observation.venv_file_set_digest) is not None, "RELEASE_VENV_UNOBSERVED")
        facts["venvFileSetDigest"] = observation.venv_file_set_digest
        for target, member in sorted(host_targets.items()):
            _check(member in files and observation.host_files.get(target) == files[member],
                   "HOST_FILE_BYTES_MISMATCH", target)
        digests = {"authority": runtime_files_digest(files, prefixes=AUTHORITY_RUNTIME_PREFIXES),
                   "witness": runtime_files_digest(files, prefixes=WITNESS_RUNTIME_PREFIXES),
                   "rootTooling": runtime_files_digest(files, prefixes=ROOT_TOOLING_PREFIXES)}
        facts["runtimeDigests"] = digests
        for name, reviewed in sorted((reviewed_runtime_digests or {}).items()):
            _check(digests.get(name) == reviewed, "RELEASE_RUNTIME_MANIFEST_MISMATCH", name)
    except _Rejected as rejected:
        return ReleaseResultV1(FAIL, rejected.reason, rejected.detail, facts)
    return ReleaseResultV1(PASS, facts=facts)


class _Rejected(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _check(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Rejected(reason, detail)


# ------------------------------------------ external inputs (typed, closed) ---

@dataclass(frozen=True)
class UnitStateObservationV1:
    """`systemctl show` facts for one unit. Never a start, never an enable."""

    unit: str
    load_state: str | None
    active_state: str | None
    unit_file_state: str | None
    need_daemon_reload: str | None
    fragment_sha256: str | None = None


@dataclass(frozen=True)
class ExternalProofV1:
    """A root- or CI-produced proof result, bound by its transcript digest."""

    name: str
    result: str                  # PASS | FAIL
    transcript_sha256: str
    detail: str | None = None


@dataclass(frozen=True)
class ActivationObservationV1:
    """The B1c activation verifier's line and the B1c file-set comparison."""

    line: str
    b1c_unchanged: bool


# E-19: the COMPLETE line the B1c activation verifier prints while the grant is absent
# (`scripts/dev_deployer/lilith_activation_verify.py`, NOT_ACCEPTED branch), byte-identical in every
# preserved DEV host POST. Exact equality only: no prefix, trim, case or field-order tolerance.
ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"


def _activation_evidence(value: Any) -> str | None:
    """The observed line as package evidence: a UTF-8-encodable `str`, else None (never a canonicalization crash)."""
    if type(value) is not str:
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return value

# PR-2 (snapshot inventory). Absent until PR-2 exists; never a default pass.
SNAPSHOT_ACCEPTED = "ACCEPTED"
SNAPSHOT_CLASSES_PERMITTED = frozenset({"SAFE_RETAINED_CIPHERTEXT", "KNOWN_CUSTODY_DEBT", "NO_SNAPSHOTS"})


@dataclass(frozen=True)
class SnapshotInventoryResultV1:
    status: str
    record_sha256: str
    artefact_classes: tuple[str, ...]
    named_debts: tuple[str, ...] = ()


# PR-3 (owner off-host register and material). Absent until PR-3 exists.
@dataclass(frozen=True)
class OwnerOffHostMaterialV1:
    status: str                              # PRESENT
    register_sha256: str
    genesis_pin_digest: str
    k_root_public_key_sha256: str
    k_wit_public_key_sha256: str
    k_act_publication_sha256: str
    registry_head: RC.RegistryHeadV1
    release_sha: str
    release_manifest_sha256: str
    authorization_ids: tuple[str, ...] = ()
    burned_ordinals: tuple[int, ...] = ()


REQUIRED_PROOFS = ("SIGNER_DENIAL", "DEPLOYER_DENIAL", "BROKER_DENIAL", "BROKER_PRESERVATION", "OS_DENIAL",
                   "SECRET_HYGIENE", "PRESERVATION_SET")
# The deployer-observed maturity once every PR-1A object exists (DR-5 ladder).
REQUIRED_DEPLOYER_MATURITY = "maturity=P1A-9"

# E-22 owner risk adjudication (OD-M12-10; docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md §17).
# The ONE E-22 outcome other than PASS that the package can carry: a genuine SECRET_HYGIENE FAIL whose `detail`
# names an owner adjudication pinned here by a reviewed, merged owner record, for the DEV_SYNTHETIC K-ACT only.
# The control side admits that detail only for the exact historical failure set (mb12_readiness_inputs). It is
# never PASS and never a clean scan; every other check stays PASS-only.
OWNER_RISK_ADJUDICATED = "OWNER_RISK_ADJUDICATED"
E22_ADJUDICATION_DETAIL_PREFIX = "OWNER_RISK_ADJUDICATION="
E22_ADJUDICATION_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"
E22_ADJUDICATION_ENVIRONMENT = SC.ENVIRONMENT          # "dev": the DEV_SYNTHETIC deployment only
E22_ADJUDICATED_FAILURES = (
    "FAIL: JOURNAL_SCAN_NOT_PASS",
    "FAIL: JOURNAL_MARKER class=PEM_PRIVATE_KEY count=12",
    "FAIL: CEREMONY_TRANSCRIPT_NOT_RETAINED B1B3D-L2b",
    "FAIL: CEREMONY_WINDOW_NOT_RECORDED B1B3D-L2b",
)
# adjudication SHA-256 -> the owner decision record SHA-256 that accepted it.
ACCEPTED_E22_ADJUDICATIONS: Mapping[str, str] = {
    "9528f7338b0a832bb821884654b1b8e2a8c86c1b65f4bf17ea2be2a48cbe9989":
        "56e71df1b7bf5c599c7d3f09edd5b12a37cf642c63d715b2f823f2ff92242c5a",
}
E22_ADJUDICATION_NONCLAIM = (
    "E-22 SECRET_HYGIENE: OWNER_RISK_ADJUDICATED (OD-M12-10), NOT a clean scan: JOURNAL_SECRET_SCAN=FAIL stands "
    "(12 PEM_PRIVATE_KEY markers, purpose UNKNOWN x3); the B1b-3d L2b transcript was not retained and its window "
    "not recorded; exposure of the DEV_SYNTHETIC K-ACT during or around L2b is not excluded; no other key, "
    "ceremony, environment or PROD")

PR1_NONCLAIMS = (
    "authorityGranted: false",
    "activationGranted: false",
    "issuance: UNWIRED; positive evidence issuance: NOT ACCEPTED, NOT PROVEN",
    "legacy B1b-3d §22 DEV_SYNTHETIC CUSTODY PROVEN: NOT CLAIMED",
    "wholeHostRollbackProtected: false",
    "registry-head / RecoveryEpoch transition executed: NONE",
    "media zeroization / remanence elimination: NOT CLAIMED",
    "PROD authority, Privacy custody, Stage III, First Memory: NOT CLAIMED",
)


# ------------------------------------------------ the package (RR-38, §19) ---

PACKAGE_TYPE = "LILITH_PR1_OWNER_ACCEPTANCE_PACKAGE"
PACKAGE_SCHEMA_VERSION = 1
PACKAGE_DOMAIN_SEPARATOR = b"LILITH_PR1_OWNER_ACCEPTANCE_PACKAGE_V1\x00"

PACKAGE_CHECKS = (
    "E01_INSTALLED_RELEASE", "E02_KACT_PUBLICATION", "E03_HEALTH_FINGERPRINT", "E04_CURRENT_PRESERVED",
    "E05_CREDENTIAL_INVENTORY", "E06_UNIT_CREDENTIAL_MAPPING", "E07_SIGNER_CUSTODY_DENIAL",
    "E08_DEPLOYER_DENIAL", "E09_BROKER_DENIAL_PRESERVATION", "E10_KWIT_IDENTITY", "E11_V2_GENESIS",
    "E12_GENESIS_PIN", "E13_KROOT_REGISTRY", "E14_RECOVERY_EPOCH", "E15_AUTHORITY_LEDGER", "E16_HOLD_STORE",
    "E17_READINESS", "E18_OFFHOST_REPRODUCTION_INPUTS", "E19_ACTIVATION_DARK", "E20_SNAPSHOT_INVENTORY",
    "E21_OFFHOST_REGISTER", "E22_SECRET_HYGIENE", "E23_PRESERVATION_SET", "E24_NONCLAIMS",
)
WITNESS_UNITS = ("lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                 "lilith-recovery-witness-signer.socket")
SIGNER_UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket")


@dataclass(frozen=True)
class Pr1AcceptanceInputsV1:
    """Everything the PR-1 package binds. Every field is story-4 input until
    the check that names it verifies it; None means ABSENT (NOT_READY)."""

    environment: str
    readiness: SR.SuccessorReadinessInputsV1 | None
    release_sha: str | None
    installed_release: InstalledReleaseObservationV1 | None
    attested_manifest_sha256: str | None
    host_targets: Mapping[str, str]
    reviewed_runtime_digests: Mapping[str, str] | None
    current_first_preflight: CurrentBlobObservationV1 | None
    current_now: CurrentBlobObservationV1 | None
    pinned_current_sha256: str | None
    unit_states: tuple[UnitStateObservationV1, ...]
    witness_publication: Mapping[str, Any] | None
    witness_anchor: Mapping[str, Any] | None
    proofs: Mapping[str, ExternalProofV1]
    activation: ActivationObservationV1 | None
    snapshot_inventory: SnapshotInventoryResultV1 | None = None       # PR-2
    offhost_material: OwnerOffHostMaterialV1 | None = None            # PR-3
    profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE
    witness_profile: B.WitnessProfileV1 = B.DEV_SYNTHETIC_WITNESS_PROFILE
    owner_ids: tuple[int, int] = (0, 0)   # root; TEST seam only


@dataclass(frozen=True)
class Pr1AcceptanceResultV1:
    status: str
    mode: str
    reasons: tuple[str, ...]
    checks: Mapping[str, WR.CheckOutcomeV1]
    package: Mapping[str, Any]
    package_digest: str
    readiness: SR.SuccessorReadinessResultV1 | None = None

    @property
    def ready(self) -> bool:
        return self.status == READY


def package_digest(package: Mapping[str, Any]) -> str:
    """SHA-256(LILITH_PR1_OWNER_ACCEPTANCE_PACKAGE_V1\\0 ‖ JCS(package)).

    A reproducibility digest for the owner's decision, never a signature."""
    return _sha256(PACKAGE_DOMAIN_SEPARATOR + _jcs(dict(package)))


def _readiness_check(result: SR.SuccessorReadinessResultV1 | None, *names: str) -> tuple[str | None, str | None]:
    if result is None:
        return "READINESS_INPUT_MISSING", None
    for name in names:
        outcome = result.checks.get(name)
        if outcome is None or outcome.status != PASS:
            return f"{name}:{None if outcome is None else outcome.reason}", None if outcome is None else outcome.detail
    return None, None


def _proof_reason(proofs: Mapping[str, ExternalProofV1], *names: str, detail: str | None = None) -> str | None:
    for name in names:
        proof = proofs.get(name) if isinstance(proofs, Mapping) else None
        if proof is None:
            return f"PROOF_MISSING:{name}"
        if not isinstance(proof, ExternalProofV1) or proof.name != name \
                or not isinstance(proof.transcript_sha256, str) or _HEX64.fullmatch(proof.transcript_sha256) is None:
            return f"PROOF_MALFORMED:{name}"
        if proof.result != PASS:
            return f"PROOF_NOT_PASS:{name}"
        if detail is not None and proof.detail != detail:
            return f"PROOF_SCOPE_MISMATCH:{name}"
    return None


def _secret_hygiene_outcome(inputs: Pr1AcceptanceInputsV1) -> WR.CheckOutcomeV1:
    """E-22: PASS; or OWNER_RISK_ADJUDICATED for a genuine FAIL naming a pinned adjudication, DEV_SYNTHETIC only."""
    proofs = inputs.proofs if isinstance(inputs.proofs, Mapping) else {}
    proof = proofs.get("SECRET_HYGIENE")
    detail = proof.detail if isinstance(proof, ExternalProofV1) else None
    if detail is None:
        reason = _proof_reason(proofs, "SECRET_HYGIENE")
        return WR.CheckOutcomeV1(PASS) if reason is None else WR.CheckOutcomeV1(FAIL, reason)
    reason = _proof_reason(proofs, "SECRET_HYGIENE")
    adjudication = detail[len(E22_ADJUDICATION_DETAIL_PREFIX):] if type(detail) is str else ""
    if reason not in (None, "PROOF_NOT_PASS:SECRET_HYGIENE"):
        return WR.CheckOutcomeV1(FAIL, reason)
    if type(detail) is not str or not detail.startswith(E22_ADJUDICATION_DETAIL_PREFIX) \
            or _HEX64.fullmatch(adjudication) is None:
        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_MALFORMED")
    if proof.result != FAIL:
        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_NOT_FOR_FAIL")
    if inputs.environment != E22_ADJUDICATION_ENVIRONMENT or not SC.is_dev_synthetic(inputs.profile) \
            or inputs.profile.environment != E22_ADJUDICATION_ENVIRONMENT \
            or inputs.profile.initial_key_id != E22_ADJUDICATION_KEY_ID:
        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_OUT_OF_SCOPE")
    if adjudication not in ACCEPTED_E22_ADJUDICATIONS:
        return WR.CheckOutcomeV1(FAIL, "E22_ADJUDICATION_NOT_ACCEPTED")
    return WR.CheckOutcomeV1(OWNER_RISK_ADJUDICATED, adjudication)


def _unit_reason(states: tuple[UnitStateObservationV1, ...]) -> str | None:
    by_unit = {state.unit: state for state in states if isinstance(state, UnitStateObservationV1)}
    for unit in SIGNER_UNITS + WITNESS_UNITS:
        state = by_unit.get(unit)
        if state is None:
            return f"UNIT_UNOBSERVED:{unit}"
        if state.load_state != "loaded" or state.need_daemon_reload != "no":
            return f"UNIT_NOT_LOADED_CURRENT:{unit}"
        if state.unit_file_state not in ("static", ""):
            return f"UNIT_ENABLEABLE_OR_ENABLED:{unit}"
    return None


def evaluate_pr1_acceptance(inputs: Pr1AcceptanceInputsV1, *, mode: str) -> Pr1AcceptanceResultV1:
    """E-1 .. E-24 over one set of observations, and the canonical package.

    HOLD_RELEASE_ELIGIBILITY is the package the owner approves before
    `HELD -> RELEASED`; FULL_READINESS is the same package after RELEASED.
    Both describe INITIAL_CUSTODY only (PR-1 scope, RR-39). READY grants
    nothing: `authorityGranted`, `activationGranted`, and `issuanceWired`
    are always false in the package.
    """
    checks: dict[str, WR.CheckOutcomeV1] = {}

    def record(name: str, reason: str | None, detail: str | None = None) -> None:
        checks[name] = WR.CheckOutcomeV1(PASS) if reason is None else WR.CheckOutcomeV1(FAIL, reason, detail)

    evidence: dict[str, Any] = {}
    if mode not in SR.READINESS_MODES or not isinstance(inputs, Pr1AcceptanceInputsV1):
        for name in PACKAGE_CHECKS:
            record(name, "MALFORMED_INPUT")
        return _package(str(mode), getattr(inputs, "environment", None), checks, evidence, None)

    readiness = None
    if isinstance(inputs.readiness, SR.SuccessorReadinessInputsV1):
        readiness = SR.evaluate_successor_readiness(inputs.readiness, mode=mode)
        evidence["readiness"] = {"mode": mode, "status": readiness.status,
                                 "readinessDigest": readiness.facts.get("readinessDigest"),
                                 "reasons": list(readiness.reasons)}
    base = inputs.readiness.base if readiness is not None else None

    # E-1 installed release.
    if inputs.installed_release is None or inputs.release_sha is None or inputs.attested_manifest_sha256 is None:
        record("E01_INSTALLED_RELEASE", "INSTALLED_RELEASE_UNOBSERVED")
    else:
        release = verify_installed_release(inputs.installed_release, release_sha=inputs.release_sha,
                                           attested_manifest_sha256=inputs.attested_manifest_sha256,
                                           host_targets=inputs.host_targets,
                                           reviewed_runtime_digests=inputs.reviewed_runtime_digests,
                                           owner=inputs.owner_ids)
        evidence["installedRelease"] = dict(release.facts)
        record("E01_INSTALLED_RELEASE", release.reason, release.detail)

    # E-2 / E-3 K-ACT publication and HEALTH (B3, B4; RR-14 binding).
    record("E02_KACT_PUBLICATION", *_readiness_check(readiness, "PUBLICATION_BYTES", "CEREMONY_PROVENANCE"))
    record("E03_HEALTH_FINGERPRINT", *_readiness_check(readiness, "LOADED_KEY_BINDING"))
    if base is not None and isinstance(base.publication, Mapping):
        try:
            published = RC.KeyPublicationV1.from_dict(base.publication)
            evidence["kActPublication"] = {
                "keyId": published.key_id, "publicKeySha256": published.public_key_sha256,
                "blobSha256": published.blob_sha256,
                "publicationSha256": _sha256(SC.canonical_publication_bytes(base.publication))}
        except (OwnerProofError, TypeError):
            evidence["kActPublication"] = None
        evidence["health"] = {"publicKeySha256": (base.health or {}).get("publicKeySha256")
                              if isinstance(base.health, Mapping) else None}

    # E-4 CURRENT preservation since the first PR-1 preflight.
    reason = current_preservation_reason(inputs.current_first_preflight, inputs.current_now,
                                         pinned_sha256=inputs.pinned_current_sha256, owner=inputs.owner_ids)
    if inputs.pinned_current_sha256 is None and reason is None:
        reason = "CURRENT_PIN_MISSING"
    record("E04_CURRENT_PRESERVED", reason)
    if isinstance(inputs.current_now, CurrentBlobObservationV1):
        evidence["currentBlob"] = inputs.current_now.to_dict()

    # E-5 inventory STEADY (credstore = CURRENT only; PREPARED/RETIRED empty).
    inventory_reason, inventory_detail = _readiness_check(readiness, "CREDENTIAL_INVENTORY")
    if inventory_reason is None and base.inventory_phase != WR.STEADY:
        inventory_reason = "CREDENTIAL_INVENTORY_NOT_STEADY"
    record("E05_CREDENTIAL_INVENTORY", inventory_reason, inventory_detail)
    if base is not None:
        evidence["credentialInventory"] = {"phase": base.inventory_phase}

    # E-6 unit credential mapping (B5) and current unit definitions.
    unit_reason, unit_detail = _readiness_check(readiness, "LOADED_KEY_BINDING")
    record("E06_UNIT_CREDENTIAL_MAPPING", unit_reason or _unit_reason(tuple(inputs.unit_states)), unit_detail)
    evidence["unitStates"] = [{"unit": s.unit, "loadState": s.load_state, "activeState": s.active_state,
                               "unitFileState": s.unit_file_state, "needDaemonReload": s.need_daemon_reload,
                               "fragmentSha256": s.fragment_sha256}
                              for s in sorted(inputs.unit_states, key=lambda s: s.unit)
                              if isinstance(s, UnitStateObservationV1)]

    # E-7 .. E-9, E-22, E-23 external proofs, non-vacuous.
    record("E07_SIGNER_CUSTODY_DENIAL", _proof_reason(inputs.proofs, "SIGNER_DENIAL", "OS_DENIAL"))
    record("E08_DEPLOYER_DENIAL", _proof_reason(inputs.proofs, "DEPLOYER_DENIAL", detail=REQUIRED_DEPLOYER_MATURITY))
    record("E09_BROKER_DENIAL_PRESERVATION", _proof_reason(inputs.proofs, "BROKER_DENIAL", "BROKER_PRESERVATION"))
    checks["E22_SECRET_HYGIENE"] = e22 = _secret_hygiene_outcome(inputs)
    if e22.status == OWNER_RISK_ADJUDICATED:
        evidence["secretHygieneAdjudication"] = {
            "status": OWNER_RISK_ADJUDICATED, "decision": "OD-M12-10", "adjudicationSha256": e22.reason,
            "ownerRecordSha256": ACCEPTED_E22_ADJUDICATIONS[e22.reason], "keyId": E22_ADJUDICATION_KEY_ID,
            "transcriptSha256": inputs.proofs["SECRET_HYGIENE"].transcript_sha256,
            "failures": list(E22_ADJUDICATED_FAILURES), "nonclaim": E22_ADJUDICATION_NONCLAIM}
    record("E23_PRESERVATION_SET", _proof_reason(inputs.proofs, "PRESERVATION_SET"))
    evidence["proofs"] = {name: {"result": proof.result, "transcriptSha256": proof.transcript_sha256,
                                 "detail": proof.detail}
                          for name, proof in sorted((inputs.proofs or {}).items())
                          if isinstance(proof, ExternalProofV1)}

    # E-10 K-WIT identity, distinctness, anchor equality.
    if base is None or inputs.witness_publication is None or inputs.witness_anchor is None:
        record("E10_KWIT_IDENTITY", "KWIT_EVIDENCE_MISSING")
    else:
        registry = _head_registry(readiness, base)
        distinct = B.witness_distinctness_reason(
            witness_publication=inputs.witness_publication, actor_publication=base.publication, registry=registry,
            registry_root=base.store.registry_root, anchor=inputs.witness_anchor, profile=inputs.witness_profile)
        if distinct is None:
            anchor = R.TrustedWitnessAnchorV1.from_dict(inputs.witness_anchor)
            if (anchor.witness_key_id, anchor.public_key) != (base.store.anchor.witness_key_id,
                                                              base.store.anchor.public_key):
                distinct = "WITNESS_ANCHOR_NOT_INSTALLED_ANCHOR"
        record("E10_KWIT_IDENTITY", distinct)
        try:
            witness = B.WitnessKeyPublicationV1.from_dict(inputs.witness_publication)
            evidence["kWit"] = {"witnessKeyId": witness.witness_key_id,
                                "publicKeySha256": witness.public_key_sha256, "blobSha256": witness.blob_sha256,
                                "anchorSha256": _sha256(_jcs(dict(inputs.witness_anchor)))}
        except (OwnerProofError, TypeError):
            evidence["kWit"] = None

    # E-11 .. E-17 from the verified witness state and readiness.
    record("E11_V2_GENESIS", *_readiness_check(readiness, "WITNESS_CHAIN"))
    record("E12_GENESIS_PIN", *_readiness_check(readiness, "GENESIS_PIN"))
    record("E13_KROOT_REGISTRY", *_readiness_check(readiness, "HEAD_REGISTRY", "REGISTRY_HISTORY",
                                                   "SINGLE_CURRENT_KEY", "AUTHORIZATION_HISTORY"))
    record("E14_RECOVERY_EPOCH", *_readiness_check(readiness, "HEAD_REGISTRY", "COMPROMISE_EPOCH"))
    record("E15_AUTHORITY_LEDGER", *_readiness_check(readiness, "AUTHORITY_LEDGER_POSITION"))
    _witness_evidence(evidence, readiness, base)
    record("E16_HOLD_STORE", *_hold_store_reason(readiness, None if readiness is None else inputs.readiness.hold_store,
                                                 mode, inputs.profile, evidence))
    record("E17_READINESS", None if readiness is not None and readiness.ready else
           ("READINESS_INPUT_MISSING" if readiness is None else "READINESS_NOT_READY"),
           None if readiness is None else ",".join(readiness.reasons) or None)

    # E-18 / E-21 PR-3 off-host material (never manufactured here).
    record("E21_OFFHOST_REGISTER", _offhost_reason(inputs.offhost_material))
    record("E18_OFFHOST_REPRODUCTION_INPUTS", _reproduction_reason(inputs, evidence))
    if isinstance(inputs.offhost_material, OwnerOffHostMaterialV1):
        material = inputs.offhost_material
        evidence["offHostRegister"] = {
            "registerSha256": material.register_sha256, "genesisPinDigest": material.genesis_pin_digest,
            "kRootPublicKeySha256": material.k_root_public_key_sha256,
            "kWitPublicKeySha256": material.k_wit_public_key_sha256,
            "kActPublicationSha256": material.k_act_publication_sha256,
            "registryHead": material.registry_head.to_dict() if isinstance(material.registry_head,
                                                                           RC.RegistryHeadV1) else None,
            "releaseSha": material.release_sha, "releaseManifestSha256": material.release_manifest_sha256,
            "authorizationIds": list(material.authorization_ids), "burnedOrdinals": list(material.burned_ordinals)}
    else:
        evidence["offHostRegister"] = None

    # E-19 activation stays dark.
    activation = inputs.activation
    record("E19_ACTIVATION_DARK", None if isinstance(activation, ActivationObservationV1)
           and type(activation.line) is str and activation.line == ACTIVATION_DARK_LINE
           and activation.b1c_unchanged is True
           else ("ACTIVATION_UNOBSERVED" if activation is None else "ACTIVATION_NOT_DARK"))
    # A malformed value FAILs above and is evidenced as null: it never reaches (or crashes) the package digest.
    evidence["activation"] = None if not isinstance(activation, ActivationObservationV1) else {
        "line": _activation_evidence(activation.line),
        "b1cUnchanged": activation.b1c_unchanged if type(activation.b1c_unchanged) is bool else None}

    # E-20 PR-2 snapshot inventory (never manufactured here).
    record("E20_SNAPSHOT_INVENTORY", _snapshot_reason(inputs.snapshot_inventory))
    snapshot = inputs.snapshot_inventory
    evidence["snapshotInventory"] = None if not isinstance(snapshot, SnapshotInventoryResultV1) else {
        "status": snapshot.status, "recordSha256": snapshot.record_sha256,
        "artefactClasses": sorted(snapshot.artefact_classes), "namedDebts": sorted(snapshot.named_debts)}

    record("E24_NONCLAIMS", None)
    return _package(mode, inputs.environment, checks, evidence, readiness)


def _head_registry(readiness: SR.SuccessorReadinessResultV1 | None, base: WR.WitnessReadinessInputsV1) -> Any:
    head = (readiness.facts.get("headRegistry") or {}) if readiness is not None else {}
    for registry in base.head_registries:
        try:
            if RC.registry_digest(registry) == head.get("registryDigest"):
                return registry
        except (OwnerProofError, TypeError, KeyError):
            continue
    return None


def _witness_evidence(evidence: dict[str, Any], readiness: SR.SuccessorReadinessResultV1 | None,
                      base: WR.WitnessReadinessInputsV1 | None) -> None:
    if readiness is None or base is None:
        return
    scan = WR.classify_witness_store(observation=base.witness_store, context=base.store)
    evidence["witness"] = {"classification": scan.classification,
                           "genesisDigest": None if scan.genesis is None else scan.genesis.digest,
                           "headDigest": None if scan.head is None else scan.head.digest,
                           "headVersion": None if scan.head is None else scan.head.witness_version,
                           "chainLength": scan.facts.get("chainLength")}
    pin = base.store.genesis_pin
    evidence["genesisPin"] = {"onHostDigest": pin.get("genesisWitnessDigest") if isinstance(pin, Mapping) else None}
    registry = _head_registry(readiness, base)
    if registry is not None:
        parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
        head = RC.registry_head(registry)
        evidence["registry"] = {"version": head.version, "digest": head.digest,
                                "rootKeyId": parsed.registry_root_key_id,
                                "policyVersion": parsed.policy_version}
        evidence["recoveryEpoch"] = {**parsed.recovery_epoch.to_dict(),
                                     "digest": R.epoch_digest(parsed.recovery_epoch, parsed.environment)}
    ledger = base.ledger_observation
    if isinstance(ledger, RC.AuthorityLedgerObservationV1):
        evidence["authorityLedger"] = {"sequence": ledger.sequence, "head": ledger.head,
                                       "registryView": ledger.registry_view,
                                       "signingKeyIds": list(ledger.signing_key_ids)}


def _hold_store_reason(readiness: SR.SuccessorReadinessResultV1 | None, observation: Any, mode: str,
                       profile: SC.CustodyProfileV1, evidence: dict[str, Any]) -> tuple[str | None, str | None]:
    """The exact store readiness judged: one INITIAL_CUSTODY record (PR-1 scope)."""
    if readiness is None:
        return "READINESS_INPUT_MISSING", None
    holds, reason, detail = SC.parse_hold_store(observation, profile=profile)
    if holds is None:
        return reason, detail
    evidence["holdStore"] = {"listingDigest": hold_listing_digest(observation),
                             "records": [[h.ceremony_id, h.transition_kind, h.state] for _, h in sorted(holds.items())]}
    outcome = readiness.checks.get("CEREMONY_HOLD")
    if outcome is None or outcome.status != PASS:
        return f"CEREMONY_HOLD:{None if outcome is None else outcome.reason}", None
    expected_state = SC.HELD if mode == SR.HOLD_RELEASE_ELIGIBILITY else SC.RELEASED
    initial = SC.initial_ceremony_id(profile.environment, profile.initial_key_id)
    if list(holds) != [initial] or holds[initial].transition_kind != SC.INITIAL_CUSTODY \
            or holds[initial].state != expected_state:
        return "HOLD_STORE_NOT_SINGLE_INITIAL_CUSTODY", expected_state
    return None, None


def _offhost_reason(material: OwnerOffHostMaterialV1 | None) -> str | None:
    if material is None:
        return "OFFHOST_REGISTER_ABSENT_PR3"
    if not isinstance(material, OwnerOffHostMaterialV1) or material.status != "PRESENT" \
            or not isinstance(material.registry_head, RC.RegistryHeadV1):
        return "OFFHOST_REGISTER_MALFORMED"
    for value in (material.register_sha256, material.genesis_pin_digest, material.k_root_public_key_sha256,
                  material.k_wit_public_key_sha256, material.k_act_publication_sha256,
                  material.release_manifest_sha256):
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            return "OFFHOST_REGISTER_MALFORMED"
    if not isinstance(material.release_sha, str) or _SHA40.fullmatch(material.release_sha) is None:
        return "OFFHOST_REGISTER_MALFORMED"
    if material.authorization_ids or material.burned_ordinals:
        return "OFFHOST_REGISTER_NOT_EMPTY_AT_PR1"
    return None


def _reproduction_reason(inputs: Pr1AcceptanceInputsV1, evidence: Mapping[str, Any]) -> str | None:
    """PR-3 material must bind exactly what the host shows (E-12, E-13, E-10,
    E-2, E-1). The owner's own off-host reproduction (RR-38 B) stays a
    separate act that ends in the approved package digest."""
    material = inputs.offhost_material
    if _offhost_reason(material) is not None:
        return "OFFHOST_MATERIAL_UNAVAILABLE"
    pin = (evidence.get("genesisPin") or {}).get("onHostDigest")
    genesis = (evidence.get("witness") or {}).get("genesisDigest")
    if pin is None or material.genesis_pin_digest != pin or material.genesis_pin_digest != genesis:
        return "OFFHOST_PIN_MISMATCH"
    registry = evidence.get("registry") or {}
    if material.registry_head != RC.RegistryHeadV1(registry.get("version"), registry.get("digest")):
        return "OFFHOST_REGISTRY_HEAD_MISMATCH"
    if material.k_wit_public_key_sha256 != (evidence.get("kWit") or {}).get("publicKeySha256"):
        return "OFFHOST_KWIT_MISMATCH"
    if material.k_act_publication_sha256 != (evidence.get("kActPublication") or {}).get("publicationSha256"):
        return "OFFHOST_KACT_PUBLICATION_MISMATCH"
    root = inputs.readiness.base.store.registry_root if inputs.readiness is not None else None
    if root is None or material.k_root_public_key_sha256 != _sha256(root.public_key):
        return "OFFHOST_KROOT_MISMATCH"
    if (material.release_sha, material.release_manifest_sha256) != (inputs.release_sha,
                                                                    inputs.attested_manifest_sha256):
        return "OFFHOST_RELEASE_PROVENANCE_MISMATCH"
    return None


def _snapshot_reason(snapshot: SnapshotInventoryResultV1 | None) -> str | None:
    if snapshot is None:
        return "SNAPSHOT_INVENTORY_ABSENT_PR2"
    if not isinstance(snapshot, SnapshotInventoryResultV1) or not isinstance(snapshot.record_sha256, str) \
            or _HEX64.fullmatch(snapshot.record_sha256) is None:
        return "SNAPSHOT_INVENTORY_MALFORMED"
    if snapshot.status != SNAPSHOT_ACCEPTED:
        return "SNAPSHOT_INVENTORY_NOT_ACCEPTED"
    if not snapshot.artefact_classes or not set(snapshot.artefact_classes) <= SNAPSHOT_CLASSES_PERMITTED:
        return "SNAPSHOT_INVENTORY_CLASS_NOT_PERMITTED"
    if "KNOWN_CUSTODY_DEBT" in snapshot.artefact_classes and not snapshot.named_debts:
        return "SNAPSHOT_DEBT_NOT_NAMED"
    return None


def _package(mode: str, environment: Any, checks: dict[str, WR.CheckOutcomeV1], evidence: dict[str, Any],
             readiness: SR.SuccessorReadinessResultV1 | None) -> Pr1AcceptanceResultV1:
    for name in PACKAGE_CHECKS:
        checks.setdefault(name, WR.CheckOutcomeV1(WR.NOT_EVALUATED, "PREREQUISITE_NOT_VERIFIED"))
    ordered = {name: checks[name] for name in PACKAGE_CHECKS}
    # OWNER_RISK_ADJUDICATED satisfies E-22 only (OD-M12-10); it is kept distinct in the package, never shown as PASS.
    adjudicated = ordered["E22_SECRET_HYGIENE"].status == OWNER_RISK_ADJUDICATED
    reasons = tuple(f"{name}:{outcome.reason}" for name, outcome in ordered.items()
                    if outcome.status != PASS and not (adjudicated and name == "E22_SECRET_HYGIENE"))
    status = READY if not reasons else NOT_READY
    package = {
        "packageType": PACKAGE_TYPE, "schemaVersion": PACKAGE_SCHEMA_VERSION, "environment": environment,
        "mode": mode, "scope": "PR1_INITIAL_CUSTODY", "status": status,
        "authorityGranted": False, "activationGranted": False, "issuanceWired": False,
        "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED,
        "checks": {name: [outcome.status, outcome.reason] for name, outcome in ordered.items()},
        "evidence": _jsonable(evidence),
        "nonclaims": list(PR1_NONCLAIMS) + ([E22_ADJUDICATION_NONCLAIM] if adjudicated else []),
    }
    return Pr1AcceptanceResultV1(status, mode, reasons, ordered, package, package_digest(package), readiness)


def _jsonable(value: Any) -> Any:
    """Normalize to the JCS-representable subset (dict / list / str / int / bool / None)."""
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"not JCS-representable: {type(value).__name__}")


# --------------------------------------------------- release decision (RR-38) ---

RELEASE_PERMITTED = "RELEASE_PERMITTED"
RELEASE_DENIED = "RELEASE_DENIED"
RELEASE_DECISION_REASONS = (
    "APPROVED_DIGEST_MISSING",
    "APPROVED_DIGEST_MALFORMED",
    "PACKAGE_MODE_NOT_ELIGIBILITY",
    "PACKAGE_NOT_READY",
    "PACKAGE_DIGEST_MISMATCH",
)


@dataclass(frozen=True)
class ReleaseDecisionV1:
    status: str
    reason: str | None = None

    @property
    def permitted(self) -> bool:
        return self.status == RELEASE_PERMITTED


def release_decision(approved_package_digest: Any, current: Pr1AcceptanceResultV1) -> ReleaseDecisionV1:
    """RR-38: `approvedPackageDigest == freshlyComputedPackageDigest` over a
    current HOLD_RELEASE_ELIGIBILITY re-run that is READY. No screenshot, no
    string comparison of any other form, no reuse of an older approval."""
    if approved_package_digest is None:
        return ReleaseDecisionV1(RELEASE_DENIED, "APPROVED_DIGEST_MISSING")
    try:
        _digest(approved_package_digest, "approved_package_digest")
    except OwnerProofError:
        return ReleaseDecisionV1(RELEASE_DENIED, "APPROVED_DIGEST_MALFORMED")
    if not isinstance(current, Pr1AcceptanceResultV1) or current.mode != SR.HOLD_RELEASE_ELIGIBILITY:
        return ReleaseDecisionV1(RELEASE_DENIED, "PACKAGE_MODE_NOT_ELIGIBILITY")
    if not current.ready:
        return ReleaseDecisionV1(RELEASE_DENIED, "PACKAGE_NOT_READY")
    if not hmac.compare_digest(approved_package_digest, current.package_digest):
        return ReleaseDecisionV1(RELEASE_DENIED, "PACKAGE_DIGEST_MISMATCH")
    return ReleaseDecisionV1(RELEASE_PERMITTED)
