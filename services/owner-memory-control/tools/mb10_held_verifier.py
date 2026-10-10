#!/usr/bin/env python3
"""15B2b-B1b-3e M-B10 (WRITE_HELD): READ-ONLY post-HELD host verifier and W10 classifier (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-mb10-held-package.md §3 – §6.
DESIGN / SOURCE ONLY: running it live needs a separate owner authorization (record §9).

M-B10 is one root invocation of the reviewed release CLI `lilith-authority-hold-dev create-initial-held`. It writes
ONE INITIAL_CUSTODY HELD record into the empty hold store `/var/lib/lilith-authority-custody/holds`: a scratch
file in the parent, fsync, rename into the store, fsync of both directories (`hold_store.HoldStoreV1._publish`).
HELD is forward only (RR-40): never deleted, recreated or re-bound.

The accepted W9 verifier (`mb9_witness_verifier.py`, pinned, UNCHANGED) classifies any non-empty hold store as
`W9_LATER_STATE`. This verifier does not reinterpret that: it reports the unchanged W9 judgement as `w9PhaseDirect`
and, separately, judges

1. the witness side with the SAME W9 code, with only the hold-store listing judged here instead
   (`w9PhaseHoldJudgedSeparately`; the substitution is consulted exactly once, or the result is UNCLASSIFIED);
2. the hold store itself, read-only (`lstat`, `O_NOFOLLOW` reads, no lock), against the ONE expected HELD record,
   which is fully determined by fixed context: environment `dev`, the derived initial ceremony id, the initial
   key id and the committed witness genesis digest. Bytes, name, owner, mode and link count must be exact;
3. the release's own complete root observer (`HoldStoreV1.observe`, shared lock, writes nothing) as a cross-check.

A non-empty hold store is never success by itself: only exactly one byte-exact HELD bound to the committed genesis
is `W10_1_HELD_EXACT`. Malformed, duplicate, re-bound, released or foreign content is a HALT for owner
adjudication. UNKNOWN is never absence and never success.

    ... observe <ledger-head> <candidate-digest> <updatedAt>
    ... expect <PHASE> <ledger-head> <candidate-digest> <updatedAt>

It runs on DEV as root under the release interpreter, streamed by the M-B10 operator as one hash-gated bundle
with the W5, M-B6, W8 and W9 verifiers. It never opens a socket, a credential or a key, never writes, and never
invokes the hold CLI.

    HELD = restrictive custody state only;  HELD != issuance authority;  HELD != signer start != activation
    W10_1_HELD_EXACT != owner acceptance;  non-empty hold store != HELD exact;  UNKNOWN != success
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import mb9_witness_verifier as V9

V6 = V9.V6
VERIFIER_TYPE = "LILITH_MB10_HELD_VERIFICATION"
ENVIRONMENT = "dev"
HOLD_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE_NAME = "holds"
HOLD_STORE = HOLD_PARENT + "/" + HOLD_STORE_NAME
DIRECTORY_MODE = 0o700
RECORD_MODE = 0o600
MAX_RECORD = 4096                                   # pr1_acceptance.MAX_HOLD_RECORD_BYTES
HOLD_CLI = "/usr/local/sbin/lilith-authority-hold-dev"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_NAME = re.compile(r"[0-9a-f]{64}\.json\Z")

# The accepted DEV world (Package B / Package C records). The expected HELD is derived from fixed context by the
# release contract (`successor_custody`); these pins are the derivation for the committed genesis, re-derived by
# the tests and by `expected_held` at run time.
ACCEPTED_GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
INITIAL_KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"
INITIAL_CEREMONY_ID = "dev.initial-custody." + INITIAL_KEY_ID
EXPECTED_HELD_NAME = "1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json"
EXPECTED_HELD_SHA256 = "c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d"
EXPECTED_HELD_LENGTH = 421

# ------------------------------------------------------------------ phases ---
W10_0 = "W10_0_PRE_HELD_EXACT"                       # W9_5 exact; hold store exactly empty; signer inactive
W10_1 = "W10_1_HELD_EXACT"                           # W9_5 (hold judged here); exactly the one expected HELD
W10_1S = "W10_1S_HELD_EXACT_WITNESS_STOPPED"         # as W10_1 with the witness stopped (W9_5S), e.g. a reboot
W10_SCRATCH = "W10_P_SCRATCH_RESIDUE_NOT_HELD"       # the writer's scratch in the parent; the store still empty
W10_MALFORMED = "W10_HOLD_RECORD_MALFORMED"          # entries that are not one canonical, exact HELD record
W10_MISBOUND = "W10_HELD_MISBOUND"                   # a valid INITIAL_CUSTODY HELD bound to another witness digest
W10_UNEXPECTED = "W10_HOLD_SET_UNEXPECTED"           # duplicate, extra, RELEASED or another ceremony
W10_FOREIGN = "W10_FOREIGN_OR_UNSAFE"                # hold directories or parent content the writer cannot produce
W10_WITNESS = "W10_WITNESS_NOT_EXACT"                # the witness side is not W9_5 / W9_5S
W10_LATER = "W10_SIGNER_OR_LATER_STATE"              # the signer or a later witness state (W9 LATER_STATE)
UNCLASSIFIED = "UNCLASSIFIED_STOP"
HOST_PHASES = (W10_0, W10_1, W10_1S, W10_SCRATCH, W10_MALFORMED, W10_MISBOUND, W10_UNEXPECTED, W10_FOREIGN,
               W10_WITNESS, W10_LATER, UNCLASSIFIED)
HALT_PHASES = (W10_MALFORMED, W10_MISBOUND, W10_UNEXPECTED, W10_FOREIGN)

# Hold-store classes (independent of the witness side; the sequence classifier needs both).
HS_EMPTY = "EMPTY"
HS_HELD_EXACT = "HELD_EXACT"
HS_SCRATCH = "SCRATCH_ONLY"
HS_MALFORMED = "MALFORMED"
HS_MISBOUND = "MISBOUND"
HS_UNEXPECTED = "UNEXPECTED_SET"
HS_UNSAFE = "UNSAFE"
HS_UNREADABLE = "UNREADABLE"
HOLD_CLASSES = (HS_EMPTY, HS_HELD_EXACT, HS_SCRATCH, HS_MALFORMED, HS_MISBOUND, HS_UNEXPECTED, HS_UNSAFE,
                HS_UNREADABLE)

# Routes. No route is automatic; each needs its own owner act.
PROCEED_BY_GATE_AND_GO = "PROCEED_BY_GATE_AND_GO"
SAFE_ADOPT = "SAFE_ADOPT"
SAFE_RESTART = "SAFE_RESTART"
STOP_REVALIDATE = "STOP_REVALIDATE"
STOP_OWNER_ADJUDICATION = "STOP_OWNER_ADJUDICATION"
HALT = "HALT_PENDING_OWNER_ADJUDICATION"
PHASE_TABLE = {
    W10_0: (PROCEED_BY_GATE_AND_GO, "the M-B10 write may run only under an exact gate and a separate one-attempt go"),
    W10_1: (SAFE_ADOPT, "forward only: read-only POST10, then the owner acceptance; never a second write"),
    W10_1S: (SAFE_RESTART, "forward only: a separately authorized witness restart, then a fresh POST10"),
    W10_SCRATCH: (STOP_OWNER_ADJUDICATION, "HELD was not written (the store is empty) but the scratch blocks every "
                                           "writer: a separately reviewed bounded scratch removal is required first"),
    W10_MALFORMED: (HALT, "RR-40: no deletion, repair, rewrite or retry by any tool"),
    W10_MISBOUND: (HALT, "RR-40: never re-bound; no tool acts on it"),
    W10_UNEXPECTED: (HALT, "duplicate, released or foreign ceremony: outside M-B10; no tool acts on it"),
    W10_FOREIGN: (HALT, "content the writer cannot produce: no tool acts on it"),
    W10_WITNESS: (STOP_REVALIDATE, "the witness side is not exact: no M-B10 evidence is valid until revalidated"),
    W10_LATER: (STOP_OWNER_ADJUDICATION, "signer or later state: outside M-B10"),
    UNCLASSIFIED: (STOP_OWNER_ADJUDICATION, "UNKNOWN is never absence and never success"),
}


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _host(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


# ------------------------------------------------------------ expected HELD ---

def pinned_expected_held(genesis_digest: str, *, initial_key_id: str = INITIAL_KEY_ID) -> dict[str, Any]:
    """The same record, stdlib only (the owner laptop has no release contract): the fixed field set, sorted
    compact JSON. For these ASCII values that is exactly the RFC 8785 form; `expected_held` and the tests prove
    the equality with the release contract."""
    if not isinstance(genesis_digest, str) or _HEX64.fullmatch(genesis_digest) is None:
        raise Refused("GENESIS_DIGEST_INVALID")
    ceremony = f"{ENVIRONMENT}.initial-custody.{initial_key_id}"
    record = {"protocol": "LILITH_CEREMONY_HOLD", "schemaVersion": 1, "environment": ENVIRONMENT,
              "ceremonyId": ceremony, "transitionKind": "INITIAL_CUSTODY", "state": "HELD",
              "reason": "INITIAL_CUSTODY_BOOTSTRAP", "expectedPredecessorKeyId": None,
              "expectedSuccessorKeyId": initial_key_id, "observedWitnessDigest": genesis_digest}
    data = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return {"record": record, "bytes": data, "name": hashlib.sha256(ceremony.encode("utf-8")).hexdigest() + ".json",
            "sha256": hashlib.sha256(data).hexdigest(), "length": len(data), "ceremonyId": ceremony}


def expected_held(genesis_digest: str) -> dict[str, Any]:
    """The ONE INITIAL_CUSTODY HELD record bound to `genesis_digest`, by the release contract: name, bytes, digest.
    Nothing in it is operator text, a timestamp or a random value. It must equal the stdlib form, and for the
    accepted genesis the pins."""
    if not isinstance(genesis_digest, str) or _HEX64.fullmatch(genesis_digest) is None:
        raise Refused("GENESIS_DIGEST_INVALID")
    from lilith_owner_memory import successor_custody as SC

    profile = SC.custody_profile(ENVIRONMENT)
    ceremony = SC.initial_ceremony_id(ENVIRONMENT, profile.initial_key_id)
    record = SC.CeremonyHoldV1(ENVIRONMENT, ceremony, SC.INITIAL_CUSTODY, SC.HELD, SC.INITIAL_CUSTODY_BOOTSTRAP, None,
                               profile.initial_key_id, genesis_digest).to_dict()
    data = SC.hold_record_bytes(record)
    expected = {"record": record, "bytes": data, "name": SC.hold_record_name(ceremony),
                "sha256": hashlib.sha256(data).hexdigest(), "length": len(data), "ceremonyId": ceremony}
    if expected != pinned_expected_held(genesis_digest, initial_key_id=profile.initial_key_id):
        raise Refused("EXPECTED_HELD_FORMS_DIFFER")
    if genesis_digest == ACCEPTED_GENESIS and (expected["name"], expected["sha256"], expected["length"],
                                               expected["ceremonyId"]) != (EXPECTED_HELD_NAME, EXPECTED_HELD_SHA256,
                                                                           EXPECTED_HELD_LENGTH, INITIAL_CEREMONY_ID):
        raise Refused("EXPECTED_HELD_PIN_MISMATCH")
    return expected


def expected_cli_stdout(expected: Mapping[str, Any]) -> bytes:
    """The exact stdout of one successful `create-initial-held` (cli.main: compact, sorted JSON, one LF)."""
    return json.dumps({"record": expected["record"]}, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def scratch_name(expected: Mapping[str, Any]) -> str:
    """The writer's only scratch name in the parent (`hold_store._publish`)."""
    return f".{expected['name']}.tmp"


# --------------------------------------------------------- the hold store ---

def _lstat(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _facts(meta: os.stat_result | None) -> dict[str, Any] | None:
    if meta is None:
        return None
    kind = ("symlink" if stat.S_ISLNK(meta.st_mode) else "dir" if stat.S_ISDIR(meta.st_mode)
            else "file" if stat.S_ISREG(meta.st_mode) else "other")
    return {"kind": kind, "uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o"),
            "size": meta.st_size, "links": meta.st_nlink}


def _read(path: Path, meta: os.stat_result) -> bytes | None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        if os.fstat(fd).st_ino != meta.st_ino:
            return None
        data = os.read(fd, MAX_RECORD + 1)
    finally:
        os.close(fd)
    return data if len(data) <= MAX_RECORD else None


def observe_hold_store(root: Path, expected: Mapping[str, Any], *, owner: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """The read-only judgement of the hold store against the ONE expected HELD (no lock, no write)."""
    parent_path, store_path = _host(root, HOLD_PARENT), _host(root, HOLD_STORE)
    facts: dict[str, Any] = {"parent": None, "store": None, "parentListing": None, "listing": None, "entries": {},
                             "failures": []}
    failures = facts["failures"]

    def exact_dir(meta: os.stat_result | None) -> bool:
        return (meta is not None and stat.S_ISDIR(meta.st_mode) and (meta.st_uid, meta.st_gid) == owner
                and stat.S_IMODE(meta.st_mode) == DIRECTORY_MODE)

    try:
        parent = _lstat(parent_path)
        facts["parent"] = _facts(parent)
        if parent is None or not exact_dir(parent):
            failures.append("HOLD_PARENT_ABSENT_OR_UNSAFE")
            return dict(facts, holdClass=HS_UNSAFE)
        parent_names = sorted(os.listdir(parent_path))
        facts["parentListing"] = parent_names
        store = _lstat(store_path)
        facts["store"] = _facts(store)
        if store is None or not exact_dir(store):
            failures.append("HOLD_STORE_ABSENT_OR_UNSAFE")
            return dict(facts, holdClass=HS_UNSAFE)
        before = (store.st_ino, store.st_mtime_ns, store.st_ctime_ns)
        names = sorted(os.listdir(store_path))
        facts["listing"] = names
        observed: dict[str, bytes] = {}
        for name in names:
            meta = _lstat(store_path / name)
            info = _facts(meta)
            facts["entries"][name] = info
            if meta is None or not stat.S_ISREG(meta.st_mode) or (meta.st_uid, meta.st_gid) != owner \
                    or stat.S_IMODE(meta.st_mode) != RECORD_MODE or meta.st_nlink != 1 or meta.st_size > MAX_RECORD:
                failures.append("HOLD_ENTRY_METADATA:" + name)
                continue
            data = _read(store_path / name, meta)
            if data is None:
                failures.append("HOLD_ENTRY_UNREADABLE:" + name)
                continue
            observed[name] = data
            info["sha256"] = hashlib.sha256(data).hexdigest()
        after = _lstat(store_path)
        if after is None or (after.st_ino, after.st_mtime_ns, after.st_ctime_ns) != before:
            failures.append("HOLD_STORE_CHANGED_DURING_OBSERVATION")
            return dict(facts, holdClass=HS_UNREADABLE)
    except OSError as exc:
        failures.append("HOLD_STORE_UNREADABLE:" + type(exc).__name__)
        return dict(facts, holdClass=HS_UNREADABLE)

    scratch = scratch_name(expected)
    extra = [name for name in parent_names if name != HOLD_STORE_NAME]
    if HOLD_STORE_NAME not in parent_names or any(name != scratch for name in extra):
        failures.append("HOLD_PARENT_UNEXPECTED_ENTRY")
        return dict(facts, holdClass=HS_UNSAFE)
    if extra:                                       # exactly the writer's scratch
        if names:
            failures.append("SCRATCH_WITH_RECORDS_UNREACHABLE")
            return dict(facts, holdClass=HS_UNSAFE)
        return dict(facts, holdClass=HS_SCRATCH)
    if not names:
        return dict(facts, holdClass=HS_EMPTY)
    if len(names) > 1:
        failures.append("HOLD_SET_MORE_THAN_ONE")
        return dict(facts, holdClass=HS_UNEXPECTED)
    name = names[0]
    data = observed.get(name)
    if data is None:
        return dict(facts, holdClass=HS_MALFORMED)
    if name == expected["name"] and data == expected["bytes"]:
        return dict(facts, holdClass=HS_HELD_EXACT)
    return dict(facts, holdClass=_diagnose(name, data, expected, failures))


def _diagnose(name: str, data: bytes, expected: Mapping[str, Any], failures: list[str]) -> str:
    """Why one entry is not the expected HELD (diagnosis only; every outcome here is a HALT)."""
    from lilith_owner_memory import successor_custody as SC
    from lilith_owner_memory import witness_readiness as WR

    if _RECORD_NAME.fullmatch(name) is None:
        failures.append("HOLD_NAME_INVALID")
        return HS_MALFORMED
    holds, reason, _ = SC.parse_hold_store(SC.HoldStoreObservationV1((WR.StoreEntryV1(name, WR.REGULAR, data),)),
                                           profile=SC.custody_profile(ENVIRONMENT))
    if holds is None:
        failures.append("HOLD_RECORD_INVALID:" + str(reason))
        return HS_MALFORMED
    (hold,) = holds.values()
    if hold.transition_kind != SC.INITIAL_CUSTODY or hold.state != SC.HELD:
        failures.append(f"HOLD_NOT_INITIAL_HELD:{hold.transition_kind}:{hold.state}")
        return HS_UNEXPECTED
    if hold.observed_witness_digest != expected["record"]["observedWitnessDigest"]:
        failures.append("HELD_BOUND_TO_ANOTHER_WITNESS_DIGEST")
        return HS_MISBOUND
    failures.append("HELD_BYTES_NOT_CANONICAL")
    return HS_MALFORMED


def canonical_observation(root: Path, owner: tuple[int, int]) -> dict[str, Any]:
    """The release's complete root observer (`HoldStoreV1.observe`: shared lock, writes nothing) as a cross-check."""
    try:
        from lilith_authority_root.hold_store import HoldStoreError, HoldStoreV1
    except ImportError:
        return {"observed": False, "reason": "RELEASE_OBSERVER_UNAVAILABLE"}
    try:
        observed = HoldStoreV1(environment=ENVIRONMENT, root=root, owner_uid=owner[0], owner_gid=owner[1]).observe()
    except HoldStoreError as exc:
        return {"observed": False, "reason": exc.reason}
    except OSError as exc:
        return {"observed": False, "reason": "OS_ERROR:" + type(exc).__name__}
    return {"observed": True, "listingDigest": observed.listing_digest,
            "entries": [entry.name for entry in observed.observation.entries]}


# ------------------------------------------------------- witness side (W9) ---

@contextlib.contextmanager
def hold_store_judged_separately() -> Iterator[list[str]]:
    """Run the UNCHANGED W9 judgement with only its hold-store listing handed to this verifier: every other path
    is the original reader. The caller requires the substitution to be consulted exactly once."""
    original = V6._listing
    consulted: list[str] = []

    def listing(root, path):
        if path == V9.HOLD_STORE:
            consulted.append(path)
            return []
        return original(root, path)

    V6._listing = listing
    try:
        yield consulted
    finally:
        V6._listing = original


def _signer_or_later(report: Mapping[str, Any]) -> bool:
    units = report.get("units") or {}
    signer_units = [units.get(name, {}).get("ActiveState") for name in V9.SIGNER_UNITS]
    return any(report.get("signerLaterState", {}).values()) or any(state != "inactive" for state in signer_units)


# ---------------------------------------------------------------- evaluate ---

def evaluate(expected_head: str, candidate_digest: str, updated_at: str, *, root: Path | str = Path("/"),
             owner_uid: int = 0, owner_gid: int = 0, w9: Callable[..., dict] | None = None,
             canonical: Callable[[Path, tuple[int, int]], dict] | None = None, **w9_seams: Any) -> dict[str, Any]:
    """One read-only observation and judgement. `w9`, `canonical` and `w9_seams` (passed to the W9 verifier:
    signer, witness, units, pins, trust_pins) are TEST seams."""
    root = Path(root)
    expected = expected_held(candidate_digest)
    w9 = w9 or V9.evaluate
    canonical = canonical or canonical_observation
    owner = (owner_uid, owner_gid)
    args = (expected_head, candidate_digest, updated_at)
    seams = dict(root=root, owner_uid=owner_uid, owner_gid=owner_gid, **w9_seams)
    failures: list[str] = []
    direct = w9(*args, **seams)
    with hold_store_judged_separately() as consulted:
        separate = w9(*args, **seams)
    seam_exact = consulted == [V9.HOLD_STORE]
    if not seam_exact:
        failures.append("W9_HOLD_SEAM_NOT_CONSULTED_EXACTLY_ONCE")
    hold = observe_hold_store(root, expected, owner=owner)
    cross = canonical(root, owner)
    failures.extend(hold["failures"])
    w9_phase, w9_direct = separate.get("phase"), direct.get("phase")
    committed = (separate.get("committedGenesis") or {}).get("digest")
    hold_class = hold["holdClass"]

    phase: str
    if not seam_exact or w9_phase not in V9.HOST_PHASES or w9_direct not in V9.HOST_PHASES:
        phase = UNCLASSIFIED
    elif hold_class == HS_UNREADABLE:
        phase = UNCLASSIFIED
    elif hold_class in (HS_MALFORMED, HS_MISBOUND, HS_UNEXPECTED, HS_UNSAFE):
        phase = {HS_MALFORMED: W10_MALFORMED, HS_MISBOUND: W10_MISBOUND, HS_UNEXPECTED: W10_UNEXPECTED,
                 HS_UNSAFE: W10_FOREIGN}[hold_class]
    elif w9_phase == V9.UNCLASSIFIED:
        phase = UNCLASSIFIED
    elif w9_phase == V9.LATER_STATE or _signer_or_later(separate):
        phase = W10_LATER
    elif w9_phase not in (V9.W9_5, V9.W9_5S) or committed != candidate_digest:
        phase = W10_WITNESS
    elif hold_class == HS_SCRATCH:
        phase = W10_SCRATCH
    elif hold_class == HS_EMPTY:
        # with an empty store the unchanged W9 judgement and this one must agree, and the release observer too
        consistent = w9_direct == w9_phase and cross.get("observed") is True and cross.get("entries") == []
        if not consistent:
            failures.append("EMPTY_STORE_JUDGEMENTS_DISAGREE")
        phase = (W10_0 if w9_phase == V9.W9_5 else W10_WITNESS) if consistent else UNCLASSIFIED
    elif hold_class == HS_HELD_EXACT:
        # the unchanged W9 judgement must report the HELD as later state, and the release observer must see it
        consistent = (w9_direct == V9.LATER_STATE and cross.get("observed") is True
                      and cross.get("entries") == [expected["name"]])
        if not consistent:
            failures.append("HELD_JUDGEMENTS_DISAGREE")
        phase = (W10_1 if w9_phase == V9.W9_5 else W10_1S) if consistent else UNCLASSIFIED
    else:
        phase = UNCLASSIFIED

    route, note = PHASE_TABLE[phase]
    entry = hold["entries"].get(expected["name"]) or {}
    return {
        "verifierType": VERIFIER_TYPE, "schemaVersion": 1, "environment": ENVIRONMENT, "phase": phase,
        "routing": route, "routeNote": note, "holdClass": hold_class,
        "w9PhaseHoldJudgedSeparately": w9_phase, "w9PhaseDirect": w9_direct, "w9HoldSeamExact": seam_exact,
        "committedGenesisDigest": committed, "candidateDigest": candidate_digest,
        "expectedHeld": {"name": expected["name"], "sha256": expected["sha256"], "length": expected["length"],
                         "ceremonyId": expected["ceremonyId"],
                         "observedWitnessDigest": expected["record"]["observedWitnessDigest"]},
        "observedHeldSha256": entry.get("sha256"), "holdStore": {k: v for k, v in hold.items() if k != "failures"},
        "releaseObserver": cross,
        "witnessInvocationId": separate.get("witnessInvocationId"), "witnessMainPid": separate.get("witnessMainPid"),
        "witnessNRestarts": separate.get("witnessNRestarts"), "runtime": separate.get("runtime"),
        "signerLaterState": separate.get("signerLaterState"), "w9Failures": separate.get("failures"),
        "failures": failures, "heldGrantsAuthority": False, "issuanceAuthority": "NONE",
        "registryEffective": False, "authorityActive": False, "authorityGranted": False,
    }


# ------------------------------------------------------------- transcripts ---

NOT_INVOKED = "NOT_INVOKED"
GUARD_STOPPED = "GUARD_STOPPED"
TRANSPORT_FAILED = "TRANSPORT_FAILED"
FAILED_UNCLASSIFIED = "FAILED_UNCLASSIFIED"
HELD_RETURNED_EXACT = "HELD_RETURNED_EXACT"
HELD_RETURNED_NOT_EXACT = "HELD_RETURNED_NOT_EXACT"
REFUSED_BEFORE_WRITE = "REFUSED_BEFORE_WRITE"
REFUSED_AMBIGUOUS = "REFUSED_AMBIGUOUS"
TRANSCRIPT_CLASSES = (NOT_INVOKED, HELD_RETURNED_EXACT, HELD_RETURNED_NOT_EXACT, REFUSED_BEFORE_WRITE,
                      REFUSED_AMBIGUOUS, GUARD_STOPPED, TRANSPORT_FAILED, FAILED_UNCLASSIFIED)
# Refusals `cli._hold` / `HoldStoreV1.create_initial_held` raise strictly before the scratch file is created.
# Even these never prove absence on their own: the host classification decides.
BEFORE_WRITE_REASONS = frozenset({
    "USAGE", "NOT_ROOT", "HOLD_PARENT_MISSING", "HOLD_PARENT_UNSAFE", "HOLD_PARENT_UNEXPECTED_ENTRY",
    "HOLD_DIRECTORY_MISSING", "HOLD_DIRECTORY_UNSAFE", "HOLD_STORE_BUSY", "HOLD_STORE_ENTRY_INVALID",
    "HOLD_STORE_CHANGED_DURING_OBSERVATION", "HOLD_STORE_RECORDS_INVALID", "HOLD_STORE_NOT_EMPTY",
    "HOLD_WITNESS_NOT_CONSISTENT", "HOLD_GENESIS_NOT_PINNED", "HOLD_TRANSITION_REFUSED"})
REFUSAL_PREFIX = "lilith-authority-hold-dev: REFUSED "


def classify_hold_transcript(returncode: int | None, stdout: bytes, stderr: bytes, *,
                             expected: Mapping[str, Any]) -> tuple[str, str | None]:
    """The one `lilith-authority-hold-dev create-initial-held`. Never a proof of presence or absence."""
    if returncode is None:
        return TRANSPORT_FAILED, "NO_RETURN_CODE"
    if returncode in (96, 97):
        return GUARD_STOPPED, str(returncode)
    if returncode == 255:
        return TRANSPORT_FAILED, "SSH_255"
    if returncode == 0:
        if stdout == expected_cli_stdout(expected) and stderr == b"":
            return HELD_RETURNED_EXACT, None
        return HELD_RETURNED_NOT_EXACT, "STDOUT_OR_STDERR_NOT_EXACT"
    text = stderr.decode("utf-8", "replace").strip()
    if returncode == 2 and not stdout.strip() and text.startswith(REFUSAL_PREFIX) and "\n" not in text:
        reason = text[len(REFUSAL_PREFIX):]
        if reason in BEFORE_WRITE_REASONS or reason.startswith("HOST_INPUTS_INCOMPLETE:"):
            return REFUSED_BEFORE_WRITE, reason
        return REFUSED_AMBIGUOUS, reason            # e.g. OSError: it may be raised after the rename
    return FAILED_UNCLASSIFIED, f"EXIT_{returncode}"


# ---------------------------------------------------------------- sequence ---
# Record §6: the post-marker classification. Dispositions say what the sequence may do next.
ENDS_LINKED_SUCCESSOR = "ENDS_LINKED_SUCCESSOR_PERMITTED"      # nothing written; a new gate and a new go may follow
ENDS_REVALIDATE = "ENDS_REVALIDATE_THEN_LINKED_SUCCESSOR"     # nothing written; revalidation first
CONTINUE = "CONTINUE"                                          # read-only next step under the same sequence
READ_BACK = "READ_BACK_REQUIRED"                               # a fresh read-only classification decides
STOP_ADJUDICATION = "STOP_OWNER_ADJUDICATION"
HALT_PERMANENT = "HALT_PERMANENT_PENDING_ADJUDICATION"

S10_0 = "S10_0_NOT_ATTEMPTED"
S10_R = "S10_R_CONSUMED_NOT_WRITTEN"
S10_R_DRIFT = "S10_R_HOST_DRIFT_NOT_WRITTEN"
S10_POST_PENDING = "S10_HELD_POST_PENDING"
S10_UNACKNOWLEDGED = "S10_HELD_UNACKNOWLEDGED"
S10_POST_NOT_VERIFIED = "S10_HELD_POST_NOT_VERIFIED"
S10_POST_VERIFIED = "S10_POST_VERIFIED_ACCEPTANCE_PENDING"
S10_ADOPTION = "S10_POST_VERIFIED_ADOPTION_PENDING"
S10_ACCEPTED = "S10_ACCEPTED"
S10_DR5_DRIFT = "S10_ACCEPTED_DR5_DRIFT"
S10_WITNESS_STOPPED = "S10_HELD_WITNESS_STOPPED"
S10_HELD_DRIFT = "S10_HELD_WITH_HOST_DRIFT"
S10_SCRATCH = "S10_SCRATCH_RESIDUE_NOT_WRITTEN"
S10_HALT = "S10_HALT_HOLD_STORE_INVALID"
S10_UNEXPLAINED = "S10_UNEXPLAINED_HOLD_STATE"
S10_UNCLASSIFIED = "S10_UNCLASSIFIED_STOP"
SEQUENCE_TABLE = {
    S10_0: (CONTINUE, "no marker; W10_0: the gate and the separate go may proceed"),
    S10_R: (ENDS_LINKED_SUCCESSOR, "go consumed; the host proves the store empty and the witness exact: the "
                                   "sequence ends; only a linked successor (new opening, gate and go) may write"),
    S10_R_DRIFT: (ENDS_REVALIDATE, "go consumed; the store is empty but the host drifted: the sequence ends; a "
                                   "reviewed revalidation must reach W10_0 before any linked successor"),
    S10_POST_PENDING: (CONTINUE, "HELD exact and acknowledged: run the read-only POST10"),
    S10_UNACKNOWLEDGED: (CONTINUE, "HELD exact by read-back but the response was not exact or was lost: POST10, "
                                   "then the owner acceptance with the explicit adoption sentence; never a retry"),
    S10_POST_NOT_VERIFIED: (STOP_ADJUDICATION, "HELD exact but POST10 failed: diagnose; a fresh read-only POST10 may "
                                               "be re-run; HELD stays forward only"),
    S10_POST_VERIFIED: (CONTINUE, "POST10 verified: the owner acceptance D3"),
    S10_ADOPTION: (CONTINUE, "POST10 verified: the owner acceptance D3 with the adoption sentence"),
    S10_ACCEPTED: (CONTINUE, "accepted; the first deploy after the freeze must compare EQUAL under W10_1"),
    S10_DR5_DRIFT: (STOP_ADJUDICATION, "the post-HELD DR-5 comparison is not EQUAL: revalidation; HELD stays"),
    S10_WITNESS_STOPPED: (STOP_ADJUDICATION, "HELD exact, witness stopped: a separately authorized restart, then a "
                                             "fresh POST10"),
    S10_HELD_DRIFT: (STOP_ADJUDICATION, "HELD bytes exact but the host drifted: no POST until W10_1 is re-established"),
    S10_SCRATCH: (STOP_ADJUDICATION, "HELD not written; the writer's scratch blocks every writer: a separately reviewed "
                                     "bounded scratch removal, then a linked successor"),
    S10_HALT: (HALT_PERMANENT, "malformed, misbound, unexpected or foreign hold content: RR-40, no tool acts"),
    S10_UNEXPLAINED: (HALT_PERMANENT, "hold content that this sequence did not attempt: no tool acts"),
    S10_UNCLASSIFIED: (READ_BACK, "an inconsistent or unknown combination: a fresh read-only classification; "
                                  "UNKNOWN is never success"),
}


def classify_sequence(*, host_phase: str, hold_class: str, marker: bool, transcript: str = NOT_INVOKED,
                      post_verified: bool = False, post_failed: bool = False, adoption_required: bool = False,
                      accepted: bool = False, dr5: str | None = None) -> str:
    """The M-B10 sequence phase from the host classification and the operator's own records (pure). The
    transcript never proves success or absence: the host decides; contradictions are UNCLASSIFIED."""
    if host_phase not in HOST_PHASES or hold_class not in HOLD_CLASSES or transcript not in TRANSCRIPT_CLASSES:
        return S10_UNCLASSIFIED
    if host_phase in HALT_PHASES:
        return S10_HALT
    if not marker:
        if transcript != NOT_INVOKED or post_verified or accepted:
            return S10_UNCLASSIFIED
        if hold_class in (HS_HELD_EXACT, HS_SCRATCH):
            return S10_UNEXPLAINED
        return S10_0 if host_phase == W10_0 else S10_UNCLASSIFIED
    if host_phase == UNCLASSIFIED or hold_class == HS_UNREADABLE:
        return S10_UNCLASSIFIED
    if host_phase == W10_SCRATCH:
        return S10_SCRATCH
    if host_phase == W10_0:
        if transcript == HELD_RETURNED_EXACT or post_verified or accepted:
            return S10_UNCLASSIFIED                 # a claimed success the host does not show
        return S10_R
    if host_phase in (W10_WITNESS, W10_LATER):
        if hold_class == HS_EMPTY:
            return S10_R_DRIFT if not (post_verified or accepted) else S10_UNCLASSIFIED
        if hold_class == HS_HELD_EXACT:
            return S10_HELD_DRIFT
        return S10_UNCLASSIFIED
    if host_phase == W10_1S:
        return S10_WITNESS_STOPPED
    if host_phase == W10_1:
        if transcript == NOT_INVOKED:
            return S10_UNEXPLAINED                  # a marker is always followed by exactly one recorded invocation
        if accepted:
            return S10_DR5_DRIFT if dr5 not in (None, "EQUAL") else S10_ACCEPTED
        if post_verified:
            return S10_ADOPTION if adoption_required else S10_POST_VERIFIED
        if post_failed:
            return S10_POST_NOT_VERIFIED
        return S10_POST_PENDING if transcript == HELD_RETURNED_EXACT else S10_UNACKNOWLEDGED
    return S10_UNCLASSIFIED


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
        if V9.RELEASE_TREE not in sys.path:
            sys.path.insert(0, V9.RELEASE_TREE)
        report = evaluate(*args)
    except (Refused, V9.Refused, V6.Refused, V9.V8.Refused) as exc:
        print(f"mb10_held_verifier: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    if argv[0] == "expect":
        return 0 if report["phase"] == argv[1] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
