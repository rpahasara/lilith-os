"""TEST-ONLY FM-02 First Memory semantic profile (draft, NOT ACCEPTED).

One closed autobiographical memory class: `OWNER_DIRECTED_FIRST_INTERACTION` in `lilith.core.autobiographical`, value
schema `FirstInteractionEpisodeV1`. The admitted value records ONE new authenticated owner-LILITH conversation as it
happened. It is not genesis evidence and not the owner-origin statement; neither belongs in this value.

- **Existing L04 encoding.** `normalize_first_interaction_episode` returns `(canonical, payloadDigest)` with the same
  rule as `learning_v2.normalize_project_codename`: `canonical_contracts.canonical_json` (sorted keys, compact,
  `ensure_ascii`) and `sha256(canonical.encode("ascii"))`. Non-ASCII dialogue is carried as JSON escapes, so the
  unchanged Identity V1 check (`sha256(value.encode("ascii")) == payloadDigest`) applies as is. No new payload digest,
  signature or authority mechanism exists here.
- **Verbatim, not sanitized.** Dialogue text is never trimmed, case-folded or Unicode-normalized. Text that is not
  already NFC, or that carries controls, bidi overrides, surrogates, private-use or unassigned code points, is
  refused, never repaired. `verify_episode_evidence` checks every quotation against the exact transcript bytes whose
  SHA-256 the value records; an awkward or wrong reply stays exactly as it was said.
- **No status claims.** The value has a closed key set: no accepted status, truth certification, authority, firstness
  or admission time. Admission time is L04's own `memory_admission.created_at`. Firstness is derived from accepted
  admission order in the autobiographical namespace, never asserted by the value.
- **Not admissible today.** L04 V2 dispatches only `OWNER_DIRECTED_PROJECT_CODENAME_V1` / `HomelabCodenameV1`, so the
  genuine chain refuses this class (tested). Admission needs the accepted-contract change listed in the FM-02 report.

Pure: no I/O, no store, no signer, nothing admitted or authorized.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping

from lilith_memory import canonical_contracts as C

from . import identity_profile as IP

MEMORY_CLASS = "OWNER_DIRECTED_FIRST_INTERACTION"
SUBJECT_NAMESPACE = "lilith.core.autobiographical"
SUBJECT_KEY = "episode.first-interaction"
VALUE_SCHEMA = "FirstInteractionEpisodeV1"
VALUE_SCHEMA_VERSION = 1
TRANSCRIPT_SCHEMA = "lilith.fm02.transcript.v1"

RECORDED_INTERACTION = "RECORDED_INTERACTION"
OWNER, LILITH = "OWNER", "LILITH"
SPEAKERS = frozenset({OWNER, LILITH})
OPENING, CLOSING = "OPENING", "CLOSING"
OWNER_ONLY = "OWNER_ONLY"
UNTIL_OWNER_FORGET = "UNTIL_OWNER_FORGET"

VALUE_FIELDS = frozenset({"schemaVersion", "valueSchema", "identityBinding", "truthBasis", "eventTime", "transcript",
                          "quotations", "access", "retention"})
EVENT_TIME_FIELDS = frozenset({"startedAt", "endedAt"})
TRANSCRIPT_REF_FIELDS = frozenset({"schema", "evidenceRef", "sha256", "turnCount"})
QUOTATION_FIELDS = frozenset({"position", "turnIndex", "speaker", "start", "end", "text"})
ACCESS = {"consumerScope": OWNER_ONLY}
# Existing controls only: erasure is the Privacy-owned FORGET path (PRIVACY_GOVERNANCE_AUTHORITY_V1).
RETENTION = {"mode": UNTIL_OWNER_FORGET, "erasureAuthority": C.PRIVACY_GOVERNANCE_AUTHORITY_V1}

TRANSCRIPT_FIELDS = frozenset({"schema", "conversationRef", "turns"})
TURN_FIELDS = frozenset({"index", "speaker", "at", "text"})

MAX_QUOTATIONS = 8
MAX_QUOTATION_CHARS = 4000
MAX_TURNS = 2000
MAX_TURN_CHARS = 20000

_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY_ID = re.compile(r"lid1\.[0-9a-f]{32}\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?\Z")
# Format characters that ordinary Unicode text needs: ZERO WIDTH JOINER (emoji sequences) and ZERO WIDTH NON-JOINER.
# Language-neutral: transcripts are preserved exactly whatever their language. Every other Cf (bidi overrides and
# isolates, tags, invisible operators) is refused.
_ALLOWED_FORMAT = frozenset({"\u200d", "\u200c"})


class FirstMemoryContractViolation(ValueError):
    pass


def _fail(reason: str) -> None:
    raise FirstMemoryContractViolation(reason)


def _closed(value: Any, fields: frozenset[str], reason: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(reason)
    return value


def _int(value: Any, reason: str, *, low: int = 0, high: int | None = None) -> int:
    if type(value) is not int or value < low or (high is not None and value > high):
        _fail(reason)
    return value


def _timestamp(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        _fail(reason)
    return value


def dialogue_text(value: Any, *, limit: int, reason: str) -> str:
    """Exact dialogue text, or refusal. Never trimmed or normalized: refusing is the only repair."""
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        _fail(reason)
    if unicodedata.normalize("NFC", value) != value:
        _fail("TEXT_NOT_NFC")
    for ch in value:
        category = unicodedata.category(ch)
        if ch in "\n\t":
            continue
        if category in {"Cc", "Cs", "Co", "Cn", "Zl", "Zp"} or (category == "Cf" and ch not in _ALLOWED_FORMAT):
            _fail("TEXT_PROHIBITED_CHARACTER")
    return value


def _binding(value: Any) -> dict[str, str]:
    binding = _closed(value, IP.BINDING_FIELDS, "IDENTITY_BINDING_MALFORMED")
    if not (isinstance(binding["lilithIdentityId"], str) and _IDENTITY_ID.fullmatch(binding["lilithIdentityId"])
            and isinstance(binding["charterVersion"], str) and _VERSION.fullmatch(binding["charterVersion"])
            and all(isinstance(binding[k], str) and _HEX64.fullmatch(binding[k])
                    for k in ("charterDigest", "identityProfileDigest"))):
        _fail("IDENTITY_BINDING_MALFORMED")
    return {k: binding[k] for k in IP.BINDING_FIELDS}


def _quotations(value: Any, turn_count: int) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= MAX_QUOTATIONS:
        _fail("QUOTATIONS_MALFORMED")
    out = []
    for raw in value:
        quote = _closed(raw, QUOTATION_FIELDS, "QUOTATION_MALFORMED")
        if quote["position"] not in {OPENING, CLOSING} or quote["speaker"] not in SPEAKERS:
            _fail("QUOTATION_MALFORMED")
        text = dialogue_text(quote["text"], limit=MAX_QUOTATION_CHARS, reason="QUOTATION_MALFORMED")
        start = _int(quote["start"], "QUOTATION_MALFORMED")
        if _int(quote["end"], "QUOTATION_MALFORMED") - start != len(text):
            _fail("QUOTATION_OFFSETS_INVALID")
        out.append({"position": quote["position"], "turnIndex": _int(quote["turnIndex"], "QUOTATION_MALFORMED",
                                                                     high=turn_count - 1),
                    "speaker": quote["speaker"], "start": start, "end": quote["end"], "text": text})
    out.sort(key=lambda q: (q["turnIndex"], q["start"], q["end"]))
    spans = [(q["turnIndex"], q["start"], q["end"]) for q in out]
    if len(set(spans)) != len(spans):
        _fail("QUOTATION_DUPLICATE")
    openings = [i for i, q in enumerate(out) if q["position"] == OPENING]
    closings = [i for i, q in enumerate(out) if q["position"] == CLOSING]
    if not openings or not closings or openings[-1] > closings[0]:
        _fail("QUOTATION_ORDER_INVALID")    # at least one of each, every OPENING before every CLOSING
    return out


def normalize_first_interaction_episode(value: Mapping[str, Any]) -> tuple[str, str]:
    """`(canonical, payloadDigest)` under the existing L04 value encoding. Structural only: the evidence check is
    `verify_episode_evidence`. The output is a candidate value; it is never an admission or an acceptance."""
    v = _closed(value, VALUE_FIELDS, "VALUE_FIELDS_INVALID")
    if type(v["schemaVersion"]) is not int or v["schemaVersion"] != VALUE_SCHEMA_VERSION \
            or v["valueSchema"] != VALUE_SCHEMA:
        _fail("VALUE_SCHEMA_UNSUPPORTED")
    if v["truthBasis"] != RECORDED_INTERACTION:
        _fail("TRUTH_BASIS_UNSUPPORTED")
    if dict(_closed(v["access"], frozenset(ACCESS), "ACCESS_UNSUPPORTED")) != ACCESS:
        _fail("ACCESS_UNSUPPORTED")
    if dict(_closed(v["retention"], frozenset(RETENTION), "RETENTION_UNSUPPORTED")) != RETENTION:
        _fail("RETENTION_UNSUPPORTED")
    times = _closed(v["eventTime"], EVENT_TIME_FIELDS, "EVENT_TIME_MALFORMED")
    started, ended = (_timestamp(times[k], "EVENT_TIME_MALFORMED") for k in ("startedAt", "endedAt"))
    if _instant(ended) < _instant(started):
        _fail("EVENT_TIME_ORDER_INVALID")
    transcript = _closed(v["transcript"], TRANSCRIPT_REF_FIELDS, "TRANSCRIPT_REF_MALFORMED")
    if transcript["schema"] != TRANSCRIPT_SCHEMA or not isinstance(transcript["sha256"], str) \
            or not _HEX64.fullmatch(transcript["sha256"]):
        _fail("TRANSCRIPT_REF_MALFORMED")
    try:
        C.require_id(transcript["evidenceRef"], "evidenceRef")
    except C.ContractError:
        _fail("TRANSCRIPT_REF_MALFORMED")
    turn_count = _int(transcript["turnCount"], "TRANSCRIPT_REF_MALFORMED", low=2, high=MAX_TURNS)
    normalized = {
        "schemaVersion": VALUE_SCHEMA_VERSION,
        "valueSchema": VALUE_SCHEMA,
        "identityBinding": _binding(v["identityBinding"]),
        "truthBasis": RECORDED_INTERACTION,
        "eventTime": {"startedAt": started, "endedAt": ended},
        "transcript": {"schema": TRANSCRIPT_SCHEMA, "evidenceRef": transcript["evidenceRef"],
                       "sha256": transcript["sha256"], "turnCount": turn_count},
        "quotations": _quotations(v["quotations"], turn_count),
        "access": dict(ACCESS),
        "retention": dict(RETENTION),
    }
    try:
        encoded = C.canonical_json(normalized)
    except C.ContractError:
        _fail("VALUE_NOT_CANONICAL")
    return encoded, hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _instant(stamp: str) -> tuple[str, int]:
    whole, _, fraction = stamp[:-1].partition(".")
    return whole, int((fraction or "0").ljust(6, "0"))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        _fail("TRANSCRIPT_MALFORMED")
    return dict(pairs)


def parse_transcript(transcript_bytes: bytes) -> dict[str, Any]:
    """The TEST transcript evidence format: UTF-8 JSON, closed keys, turns in order, verbatim text."""
    if not isinstance(transcript_bytes, (bytes, bytearray)) or not transcript_bytes:
        _fail("TRANSCRIPT_MISSING")
    try:
        transcript = json.loads(bytes(transcript_bytes).decode("utf-8"), object_pairs_hook=_reject_duplicate_keys,
                                parse_constant=lambda _c: _fail("TRANSCRIPT_MALFORMED"))
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, FirstMemoryContractViolation):
            raise
        _fail("TRANSCRIPT_MALFORMED")
    transcript = _closed(transcript, TRANSCRIPT_FIELDS, "TRANSCRIPT_MALFORMED")
    turns = transcript["turns"]
    if transcript["schema"] != TRANSCRIPT_SCHEMA or not isinstance(turns, list) or not 2 <= len(turns) <= MAX_TURNS:
        _fail("TRANSCRIPT_MALFORMED")
    previous = None
    for index, raw in enumerate(turns):
        turn = _closed(raw, TURN_FIELDS, "TRANSCRIPT_MALFORMED")
        if type(turn["index"]) is not int or turn["index"] != index or turn["speaker"] not in SPEAKERS:
            _fail("TRANSCRIPT_MALFORMED")
        at = _instant(_timestamp(turn["at"], "TRANSCRIPT_MALFORMED"))
        if previous is not None and at < previous:
            _fail("TRANSCRIPT_MALFORMED")
        previous = at
        dialogue_text(turn["text"], limit=MAX_TURN_CHARS, reason="TRANSCRIPT_MALFORMED")
    if {t["speaker"] for t in turns} != SPEAKERS:
        _fail("TRANSCRIPT_NOT_OWNER_LILITH_DIALOGUE")
    return transcript


def verify_episode_evidence(normalized_value_json: str, transcript_bytes: bytes) -> dict[str, Any]:
    """Facts when the canonical value is exactly what the transcript evidence supports, else
    FirstMemoryContractViolation. Evidence consistency only: not admission, acceptance or truth certification."""
    if not isinstance(normalized_value_json, str):
        _fail("VALUE_NOT_CANONICAL")
    try:
        value = json.loads(normalized_value_json)
    except ValueError:
        _fail("VALUE_NOT_CANONICAL")
    canonical, payload_digest = normalize_first_interaction_episode(value)
    if canonical != normalized_value_json:
        _fail("VALUE_NOT_CANONICAL")
    ref = value["transcript"]
    if hashlib.sha256(bytes(transcript_bytes or b"")).hexdigest() != ref["sha256"]:
        _fail("TRANSCRIPT_DIGEST_MISMATCH")
    turns = parse_transcript(transcript_bytes)["turns"]
    if len(turns) != ref["turnCount"]:
        _fail("TURN_COUNT_MISMATCH")
    if (value["eventTime"]["startedAt"], value["eventTime"]["endedAt"]) != (turns[0]["at"], turns[-1]["at"]):
        _fail("EVENT_TIME_MISMATCH")
    for quote in value["quotations"]:
        turn = turns[quote["turnIndex"]]
        if turn["speaker"] != quote["speaker"]:
            _fail("QUOTATION_SPEAKER_MISMATCH")
        if turn["text"][quote["start"]:quote["end"]] != quote["text"]:
            _fail("QUOTATION_NOT_VERBATIM")
    return {"payloadDigest": payload_digest, "transcriptSha256": ref["sha256"], "turnCount": len(turns),
            "truthClaim": False, "authorizesAdmission": False}
