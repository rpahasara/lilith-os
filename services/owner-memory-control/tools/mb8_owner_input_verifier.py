#!/usr/bin/env python3
"""15B2b-B1b-3e Package A (M-B7 / M-B8): READ-ONLY owner-input verifier and W8 partial-state classifier (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md §5, §6.

M-B8 is the installer stage `install-owner-inputs <RELEASE_SHA> <genesis-pin> <register>`
(P1B-8): two write-once (`O_EXCL`) root:root 0644 files, the genesis-pin copy
first, then the authorization-register copy, each fsynced with its directory.
It is two ordered mutations, not one transaction. This tool judges the host
before M-B7, between M-B7 and M-B8, and after (or instead of) that one
invocation. It classifies the host into exactly one W8 host phase, and
produces the host-observable evidence the sequencer names:

    hostCandidateDigestEqualsOwnerDigest   (M-B7, recomputed in memory; nothing written)
    onHostPinCopyEqualsOffHost              pinEqualsCandidateDigest   (M-B8)

`pinStoredOffHostTwoCopies` is owner custody (P-A, P-B) and is never host-observable.

Every judgment is a content judgment against OWNER-computed values passed as
arguments, never against a host value: the expected ledger head, the
candidate digest and the owner-chosen `updatedAt`. The trust anchors and
Registry V1 are judged by the accepted W5 verifier (imported unchanged), and
the ledger by the accepted M-B6 verifier's own byte-level reader (imported
unchanged): the database and its WAL are read as bytes, the committed image
is rebuilt and examined in memory. No temporary copy, no lock, no `-shm`.

It runs on DEV as root with the installed release interpreter, streamed by the
Package A operator as one hash-gated bundle with the W5 and M-B6 verifiers:

    ... observe <ledger-head> <candidate-digest> <updatedAt>
    ... expect <PHASE> <ledger-head> <candidate-digest> <updatedAt>

It takes no path argument. It never opens a credential, the credstore, the
host credential key or the K-WIT blob; never decrypts, signs, starts, stops,
reloads or enables anything; and contacts nothing.

    candidate != pin != committed genesis;  on-host pin copy != owner pin (P-A, P-B)
    OWNER_INPUTS_INSTALLED_EXACT != owner acceptance != M-B9a authorization
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

import mb6_ledger_verifier as V6

VERIFIER_TYPE = "LILITH_MB8_OWNER_INPUT_VERIFICATION"
ENVIRONMENT = "dev"
RELEASE_TREE = V6.RELEASE_TREE
OWNER_INPUT_DIR = "/etc/lilith-authority-dev/owner"
PIN_NAME = "genesis-pin.json"
REGISTER_NAME = "authorization-register.json"
PIN_COPY = OWNER_INPUT_DIR + "/" + PIN_NAME
REGISTER_COPY = OWNER_INPUT_DIR + "/" + REGISTER_NAME
OWNER_NAMES = (PIN_NAME, REGISTER_NAME)           # install order: the pin, then the register
HOLD_STORE = V6.HOLD_STORE
LATER_PATHS = V6.LATER_PATHS                      # M-B9a witness state, running units and sockets
MAX_FILE = 64 * 1024
W5_GAPS = frozenset({"AUTHORIZATION_REGISTER_COPY_MISSING", "GENESIS_PIN_COPY_MISSING"})
PIN_TYPE = "LILITH_RECOVERY_WITNESS_V2_GENESIS_PIN"
REGISTER_TYPE = "LILITH_OWNER_AUTHORIZATION_REGISTER"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")

EVIDENCE = ("hostCandidateDigestEqualsOwnerDigest", "onHostPinCopyEqualsOffHost", "pinEqualsCandidateDigest")

# ------------------------------------------------------------------ phases ---
# Host phases (what the host alone shows).
W8_0 = "W8_0_NO_OWNER_INPUTS"                       # pre-M-B8; also the only valid state during and after M-B7
W8_1 = "W8_1_PIN_PARTIAL"                           # pin created, its bytes/chmod not complete; register absent
W8_2 = "W8_2_PIN_ONLY_EXACT"                        # pin exact; register not created
W8_3 = "W8_3_PIN_EXACT_REGISTER_PARTIAL"            # pin exact; register created, not complete
EXACT = "OWNER_INPUTS_INSTALLED_EXACT"              # both exact, every content check passes
FOREIGN = "W8_FOREIGN_OR_UNSAFE_STOP"               # content or metadata the installer cannot produce
LATER_STATE = "OUT_OF_SCOPE_LATER_STATE"
UNCLASSIFIED = "UNCLASSIFIED_STOP"
HOST_PHASES = (W8_0, W8_1, W8_2, W8_3, EXACT, FOREIGN, LATER_STATE, UNCLASSIFIED)
PARTIAL_PHASES = (W8_1, W8_2, W8_3)

# Sequence phases (host phase + the operator's attempt marker, transcript and POST record).
S8_R = "S8_R_ATTEMPT_CONSUMED_NO_MUTATION"
S8_4 = "S8_4_INSTALLED_TRANSCRIPT_INCOMPLETE"
S8_5 = "S8_5_INSTALLED_POST_PENDING"
S8_6 = "S8_6_POST_VERIFIED_ACCEPTANCE_PENDING"
SEQUENCE_PHASES = (W8_0, S8_R, W8_1, W8_2, W8_3, S8_4, S8_5, S8_6, FOREIGN, LATER_STATE, UNCLASSIFIED)

# Routing of every sequence phase (record §6). No route is automatic; each needs its own owner act.
SAFE_RETRY = "SAFE_RETRY"
SAFE_REMOVE_AND_RETRY = "SAFE_REMOVE_AND_RETRY"
SAFE_ADOPT = "SAFE_ADOPT"
STOP_OWNER_ADJUDICATION = "STOP_OWNER_ADJUDICATION"
NOT_REACHABLE_BY_DESIGN = "NOT_REACHABLE_BY_DESIGN"
ROUTING = {
    W8_0: (SAFE_RETRY, "nothing installed; the go is not consumed"),
    S8_R: (SAFE_RETRY, "the go is consumed; nothing installed; a new attempt needs a new owner go and a fresh re-proof"),
    W8_1: (SAFE_REMOVE_AND_RETRY, "bounded removal (plan digest, separate authorization), then a new go"),
    W8_2: (SAFE_REMOVE_AND_RETRY, "bounded removal (plan digest, separate authorization), then a new go"),
    W8_3: (SAFE_REMOVE_AND_RETRY, "bounded removal (plan digest, separate authorization), then a new go"),
    S8_4: (SAFE_ADOPT, "host exact but the transcript is incomplete: read-only POST, then an owner adoption decision"),
    S8_5: (SAFE_ADOPT, "run the read-only POST"),
    S8_6: (SAFE_ADOPT, "owner acceptance of Package A (separate)"),
    FOREIGN: (STOP_OWNER_ADJUDICATION, "content the installer cannot produce; no tool acts on it"),
    LATER_STATE: (STOP_OWNER_ADJUDICATION, "M-B9a or later state present: outside Package A"),
    UNCLASSIFIED: (STOP_OWNER_ADJUDICATION, "an inconsistent or unreachable combination"),
}

# Transcript classes of the one `install-owner-inputs` invocation (classify_transcript).
NOT_INVOKED = "NOT_INVOKED"
INSTALL_PASS = "INSTALL_PASS"
INSTALL_REFUSED = "INSTALL_REFUSED"                 # an InstallError: always raised before the first write
INSTALL_STATUS_FAIL = "INSTALL_STATUS_FAIL"         # both writes returned; the P1B-8 status did not PASS
FAILED_UNCLASSIFIED = "FAILED_UNCLASSIFIED"
GUARD_STOPPED = "GUARD_STOPPED"
TRANSPORT_FAILED = "TRANSPORT_FAILED"
TRANSCRIPT_CLASSES = (NOT_INVOKED, INSTALL_PASS, INSTALL_REFUSED, INSTALL_STATUS_FAIL, FAILED_UNCLASSIFIED,
                      GUARD_STOPPED, TRANSPORT_FAILED)
FILE_STATES = ("ABSENT", "EXACT", "PARTIAL", "FOREIGN", "UNSAFE")


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    """The installer's one stored form (`_canonical_document`): sorted keys, no whitespace, ASCII, no newline."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def expected_pin_bytes(candidate_digest: str) -> bytes:
    return _canonical_bytes({"pinType": PIN_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT,
                             "genesisWitnessDigest": candidate_digest})


def expected_register_bytes(registry_digest: str) -> bytes:
    return _canonical_bytes({"registerType": REGISTER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT,
                             "authorizations": [],
                             "headRegistries": [{"registryVersion": 1, "registryDigest": registry_digest}]})


def classify_file(root: Path, absolute: str, expected: bytes, *, owner_uid: int, owner_gid: int) -> dict[str, Any]:
    """ABSENT | EXACT | PARTIAL (a prefix of the expected bytes as the installer leaves it mid-write) | FOREIGN |
    UNSAFE. Read through `O_NOFOLLOW`, bounded, never opened for writing."""
    path = _host(root, absolute)
    meta = V6._lstat(path)
    if meta is None:
        return {"state": "ABSENT"}
    facts: dict[str, Any] = {"uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
                             "size": meta.st_size, "links": meta.st_nlink, "inode": meta.st_ino}
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != owner_uid or meta.st_size > MAX_FILE or meta.st_nlink != 1:
        return dict(facts, state="UNSAFE")
    data = V6._read(path, MAX_FILE)
    facts["sha256"] = V6._sha(data)
    if data == expected and (meta.st_gid, stat.S_IMODE(meta.st_mode)) == (owner_gid, 0o644):
        return dict(facts, state="EXACT")
    if meta.st_gid == owner_gid and stat.S_IMODE(meta.st_mode) & ~0o644 == 0 and expected.startswith(data):
        return dict(facts, state="PARTIAL")
    return dict(facts, state="FOREIGN")


def _release_modules():
    import mb4_mb5_trust_install_verifier as V5
    from lilith_authority_dev import ledger as L
    from lilith_authority_host import inputs as HI
    from lilith_owner_memory import authority_contracts as A
    from lilith_owner_memory import authority_ledger_journal as J
    from lilith_owner_memory import pr1_bootstrap as B
    from lilith_owner_memory import recovery_contracts as R
    from lilith_owner_memory import rotation_contracts as RC
    from lilith_owner_memory import witness_readiness as WR
    from lilith_owner_memory.contracts import _canonical
    return V5, L, HI, A, J, B, R, RC, WR, _canonical


def _ledger(root: Path, expected_head: str, pins: V6.LedgerPinsV1, signer: tuple[int, int],
            L, J, R, A, canonical) -> tuple[bool, dict[str, Any] | None, list[str]]:
    """The accepted M-B6 ledger, exactly (W6-6 content), read with the M-B6 verifier's own byte reader."""
    state = _host(root, V6.STATE_DIR)
    meta = V6._lstat(state)
    if meta is None or not stat.S_ISDIR(meta.st_mode):
        return False, None, ["LEDGER_STATE_DIRECTORY_ABSENT"]
    if (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) != (*signer, 0o700):
        return False, None, ["LEDGER_STATE_DIRECTORY_INEXACT"]
    entries = sorted(os.listdir(state))
    if V6.LEDGER_NAME not in entries or not set(entries) <= V6.STATE_NAMES:
        return False, None, ["LEDGER_STATE_ENTRIES_INEXACT"]
    for name in entries:
        item = V6._lstat(state / name)
        if item is None or not stat.S_ISREG(item.st_mode) or item.st_uid != signer[0] \
                or stat.S_IMODE(item.st_mode) & 0o077:
            return False, None, ["LEDGER_ARTIFACT_UNSAFE"]
    ledger = V6._lstat(state / V6.LEDGER_NAME)
    if (ledger.st_uid, ledger.st_gid, stat.S_IMODE(ledger.st_mode)) != (*signer, 0o600):
        return False, None, ["LEDGER_FILE_INEXACT"]
    try:
        db = V6._read(state / V6.LEDGER_NAME)
        wal = V6._read(state / V6.WAL_NAME) if V6.WAL_NAME in entries else None
        image, _wal = V6.committed_image(db, wal)
        facts = V6.examine_image(image)
    except (V6.Refused, V6.WalError, OSError) as exc:
        return False, None, ["LEDGER_UNREADABLE:" + (getattr(exc, "reason", None) or type(exc).__name__)]
    if facts.get("state") != "COMMITTED":
        return False, None, ["LEDGER_IMAGE_" + str(facts.get("state"))]
    op = V6.pinned_genesis_op(pins)
    content = V6._content_checks(facts, op, expected_head, pins, L, J, R, A, canonical)
    failed = sorted(name for name, ok in content.items() if not ok)
    if failed or V6.ledger_head(op) != expected_head:
        return False, None, ["LEDGER_CONTENT:" + name for name in failed] or ["OWNER_HEAD_NOT_THE_HEAD_OF_REGISTRY_V1"]
    row = facts["journal"][0]
    return True, {"sequence": row[0], "head": row[4], "op": json.loads(row[2])}, []


def _signer_ids() -> tuple[int, int]:
    import pwd

    entry = pwd.getpwnam(V6.SIGNER_USER)
    return entry.pw_uid, entry.pw_gid


def evaluate(expected_head: str, candidate_digest: str, updated_at: str, *, root: Path | str = Path("/"),
             owner_uid: int = 0, owner_gid: int = 0, signer: tuple[int, int] | None = None,
             pins: V6.LedgerPinsV1 = V6.ACCEPTED_PINS, trust_pins: Any = None) -> dict[str, Any]:
    """One read-only observation and judgment. `root`, `owner_*`, `signer`, `pins`, `trust_pins` are TEST seams."""
    for value, reason in ((expected_head, "EXPECTED_HEAD_INVALID"), (candidate_digest, "CANDIDATE_DIGEST_INVALID")):
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            raise Refused(reason)
    if not isinstance(updated_at, str) or _INSTANT.fullmatch(updated_at) is None:
        raise Refused("UPDATED_AT_INVALID")
    V5, L, HI, A, J, B, R, RC, WR, canonical = _release_modules()
    root = Path(root)
    signer = signer if signer is not None else _signer_ids()
    trust_pins = trust_pins if trust_pins is not None else V5.ACCEPTED_PINS
    failures: list[str] = []

    host = HI.read_host_inputs(environment=ENVIRONMENT, root=root, owner_uid=owner_uid)
    reasons = set(host.reasons)

    # The accepted W5 judgment, unchanged. Its `registryVerifiesOnHost` also requires the host-input reasons to
    # be at most the two W5 gaps, so a present-but-partial owner copy fails it without any trust or registry
    # change. Only then, and only with the exact pinned registry bytes, the registry content is instead proven
    # by the in-memory candidate below (`build_genesis_candidate` re-verifies Registry V1 under the installed root).
    trust = V5.evaluate(root=root, owner_uid=owner_uid, owner_gid=owner_gid, pins=trust_pins)
    evidence5 = trust["evidence"]
    registry_file = trust["files"].get(V5.REGISTRY, {})
    registry_bytes_exact = (registry_file.get("state") == "PRESENT" and registry_file.get("metadataExact") is True
                            and registry_file.get("sha256") == trust_pins.registry_sha256)
    owner_copy_reasons_only = reasons <= W5_GAPS | {"GENESIS_PIN_COPY_INVALID", "AUTHORIZATION_REGISTER_COPY_INVALID"}
    trust_exact = (evidence5.get("anchorsEqualOwnerCopies") is True and evidence5.get("witnessAnchorNamesKWit") is True
                   and (evidence5.get("registryVerifiesOnHost") is True
                        or (registry_bytes_exact and owner_copy_reasons_only and bool(reasons - W5_GAPS))))
    if not trust_exact:
        failures.append("TRUST_REGISTRY_NOT_EXACT")
    ledger_exact, ledger, ledger_failures = _ledger(root, expected_head, pins, signer, L, J, R, A, canonical)
    failures.extend(ledger_failures)

    later = {path: V6._lstat(_host(root, path)) is not None for path in LATER_PATHS}
    holds = V6._listing(root, HOLD_STORE)
    later_absent = not any(later.values()) and holds == []
    if not later_absent:
        failures.append("LATER_STATE_PRESENT")

    owner_dir = V6._facts(V6._lstat(_host(root, OWNER_INPUT_DIR)))
    owner_dir_exact = (owner_dir.get("kind") == "dir"
                       and (owner_dir["uid"], owner_dir["gid"], owner_dir["mode"]) == (owner_uid, owner_gid, "0755"))
    listing = V6._listing(root, OWNER_INPUT_DIR)
    if not owner_dir_exact:
        failures.append("OWNER_INPUT_DIRECTORY_INEXACT")
    elif not set(listing or []) <= set(OWNER_NAMES):
        failures.append("OWNER_INPUT_DIRECTORY_UNEXPECTED_ENTRY")
    pin_bytes = expected_pin_bytes(candidate_digest)
    register_bytes = expected_register_bytes(trust_pins.registry_digest)
    files = {PIN_COPY: classify_file(root, PIN_COPY, pin_bytes, owner_uid=owner_uid, owner_gid=owner_gid),
             REGISTER_COPY: classify_file(root, REGISTER_COPY, register_bytes, owner_uid=owner_uid,
                                          owner_gid=owner_gid)}
    pin_state, register_state = files[PIN_COPY]["state"], files[REGISTER_COPY]["state"]

    # M-B7, in memory: the candidate the INSTALLED registry, root anchor and ledger imply at `updatedAt`.
    built = None
    if trust_exact and ledger_exact:
        registry = next((r for r in host.registries if r.get("registryVersion") == 1), None)
        try:
            op = ledger["op"]
            observation = RC.AuthorityLedgerObservationV1(
                environment=ENVIRONMENT, recovery_epoch=A.RecoveryEpochV1.from_dict(op["recoveryEpoch"]),
                sequence=ledger["sequence"], head=ledger["head"], registry_view=op["registryVersion"],
                signing_key_ids=tuple(op["signingKeyIds"]))
            built = B.build_genesis_candidate(registry=registry, registry_root=host.registry_root,
                                              ledger_observation=observation, updated_at=updated_at,
                                              profile=B.witness_profile(ENVIRONMENT))
        except Exception:  # noqa: BLE001 - any refusal fails closed
            built = None
    host_candidate_equal = built is not None and built.built and built.digest == candidate_digest
    if trust_exact and ledger_exact and not host_candidate_equal:
        failures.append("HOST_CANDIDATE_NOT_OWNER_CANDIDATE")

    pin_reason = B.candidate_pin_reason(host.genesis_pin, built, environment=ENVIRONMENT) if built else "NO_CANDIDATE"
    try:
        register = WR.OwnerAuthorizationRegisterV1.from_dict(host.owner_register) if host.owner_register else None
    except Exception:  # noqa: BLE001
        register = None
    register_exact = (register is not None and not register.authorizations
                      and register.head_registries == frozenset({RC.RegistryHeadV1(1, trust_pins.registry_digest)}))

    states = (pin_state, register_state)
    phase: str
    if not later_absent:
        phase = LATER_STATE
    elif not (trust_exact and ledger_exact and host_candidate_equal and owner_dir_exact) \
            or not set(listing or []) <= set(OWNER_NAMES):
        phase = UNCLASSIFIED
    elif "UNSAFE" in states or "FOREIGN" in states:
        phase = FOREIGN
    elif states == ("ABSENT", "ABSENT"):
        phase = W8_0 if reasons == W5_GAPS else UNCLASSIFIED
    elif states == ("PARTIAL", "ABSENT"):
        phase = W8_1
    elif states == ("EXACT", "ABSENT"):
        phase = W8_2
    elif states == ("EXACT", "PARTIAL"):
        phase = W8_3
    elif states == ("EXACT", "EXACT"):
        phase = EXACT if (not reasons and pin_reason is None and register_exact) else UNCLASSIFIED
    else:
        phase = UNCLASSIFIED              # register without an exact pin: the installer writes the pin first
        failures.append("OWNER_INPUT_ORDER_NOT_REACHABLE")
    if phase == W8_0 and reasons != W5_GAPS:
        failures.append("HOST_INPUT_REASONS_NOT_EXACTLY_W5_GAPS")

    evidence = {
        "hostCandidateDigestEqualsOwnerDigest": phase in (W8_0, EXACT) and host_candidate_equal,
        "onHostPinCopyEqualsOffHost": phase == EXACT and pin_state == "EXACT",
        "pinEqualsCandidateDigest": phase == EXACT and pin_reason is None and host_candidate_equal,
    }
    return {
        "verifierType": VERIFIER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "phase": phase,
        "routing": ROUTING.get(phase, ROUTING[UNCLASSIFIED])[0], "evidence": evidence,
        "expectedLedgerHead": expected_head, "candidateDigest": candidate_digest, "updatedAt": updated_at,
        "hostCandidateDigest": built.digest if built is not None and built.built else None,
        "expectedGenesisPinSha256": V6._sha(pin_bytes), "expectedAuthorizationRegisterSha256": V6._sha(register_bytes),
        "files": files, "ownerInputDirectory": owner_dir, "ownerInputListing": listing,
        "hostInputReasons": sorted(reasons), "laterState": later, "holdStoreListing": holds,
        "checks": {"trustRegistryExact": trust_exact, "ledgerExact": ledger_exact, "laterStateAbsent": later_absent,
                   "ownerInputDirectoryExact": owner_dir_exact, "hostCandidateEqualsOwner": host_candidate_equal,
                   "hostPinReason": pin_reason, "registerExact": register_exact},
        "pinStoredOffHostTwoCopies": "NOT_HOST_OBSERVABLE",
        "trust": {"phase": trust["phase"], "evidence": trust["evidence"], "registryDigest": trust["registryDigest"]},
        "failures": failures, "witnessGenesisPresent": later.get("/var/lib/lilith-recovery-witness", False),
        "registryEffective": False, "authorityActive": False, "authorityGranted": False,
    }


# ------------------------------------------------------------- sequence ---

def classify_transcript(returncode: int | None, stdout: bytes, stderr: bytes) -> tuple[str, str | None]:
    """(class, detail) of the one `install-owner-inputs`. Success: exit 0, empty stderr, a P1B-8 PASS report."""
    if returncode is None:
        return TRANSPORT_FAILED, "NO_RETURN_CODE"
    if returncode in (96, 97):
        return GUARD_STOPPED, str(returncode)
    if returncode == 255:
        return TRANSPORT_FAILED, "SSH_255"
    try:
        report = json.loads(stdout.decode("utf-8")) if stdout.strip() else None
    except (UnicodeDecodeError, ValueError):
        report = None
    if isinstance(report, dict) and report.get("stage") == "P1B-8":
        if returncode == 0 and report.get("result") == "PASS" and report.get("failures") == [] and stderr == b"":
            return INSTALL_PASS, None
        if returncode == 1 and report.get("result") == "FAIL":
            return INSTALL_STATUS_FAIL, ",".join(str(x) for x in report.get("failures", []))[:512]
        return FAILED_UNCLASSIFIED, "REPORT_NOT_EXACT"
    text = stderr.decode("utf-8", "replace").strip()
    prefix = "install_authority_dev: REFUSED "
    if returncode == 2 and not stdout.strip() and text.startswith(prefix) and "\n" not in text:
        return INSTALL_REFUSED, text[len(prefix):]
    return FAILED_UNCLASSIFIED, f"EXIT_{returncode}"


def classify_sequence(*, host_phase: str, attempt_consumed: bool, transcript: str, post_verified: bool) -> str:
    """The W8 sequence phase from the host phase and the operator's own records (pure)."""
    if host_phase not in HOST_PHASES or transcript not in TRANSCRIPT_CLASSES:
        return UNCLASSIFIED
    if host_phase in (FOREIGN, LATER_STATE, UNCLASSIFIED):
        return host_phase
    if not attempt_consumed:
        return W8_0 if host_phase == W8_0 and transcript == NOT_INVOKED and not post_verified else UNCLASSIFIED
    if transcript == NOT_INVOKED:
        return UNCLASSIFIED               # a marker is always followed by exactly one recorded invocation
    if host_phase == W8_0:
        return S8_R if transcript != INSTALL_PASS and not post_verified else UNCLASSIFIED
    if host_phase in PARTIAL_PHASES:
        return host_phase if transcript != INSTALL_PASS and not post_verified else UNCLASSIFIED
    if transcript in (INSTALL_REFUSED, GUARD_STOPPED):
        return UNCLASSIFIED               # a refusal precedes the first write: it never leaves both copies
    if transcript == INSTALL_PASS:
        return S8_6 if post_verified else S8_5
    return S8_4 if not post_verified else UNCLASSIFIED


# ------------------------------------------------------------------ entry ---

def main(argv: list[str]) -> int:
    try:
        if len(argv) == 4 and argv[0] == "observe":
            args = argv[1:]
        elif len(argv) == 5 and argv[0] == "expect" and argv[1] in HOST_PHASES:
            args = argv[2:]
        else:
            raise Refused("USAGE")
        V6.require_dev_root()
        if RELEASE_TREE not in sys.path:
            sys.path.insert(0, RELEASE_TREE)
        report = evaluate(*args)
    except (Refused, V6.Refused) as exc:
        print(f"mb8_owner_input_verifier: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    if argv[0] == "expect":
        return 0 if report["phase"] == argv[1] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
