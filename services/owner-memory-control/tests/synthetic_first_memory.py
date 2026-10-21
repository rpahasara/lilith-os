"""TEST-ONLY synthetic FM-02 fixtures. Never a real conversation, identity or memory.

The dialogue below is invented for tests and labelled as such. It is NOT LILITH's reply and must never be presented
as one: a real First Memory value is built only from the recorded transcript of the real conversation. The dialogue
is English. It exercises Unicode handling: precomposed accents, curly quotes and an em dash, a ZWJ emoji sequence,
an emoji with a variation selector, non-BMP emoji, and a deliberately awkward LILITH reply (typo and a wrong guess)
that the record must keep exactly. These are test inputs only; no language rule exists in the profile.
"""

from __future__ import annotations

import copy
import hashlib
import json

import synthetic_identity as SI
from lilith_owner_memory import first_memory_profile as FM

OPENING_OWNER = "TEST_ONLY hi LILITH \u2014 I made you a caf\u00e9 latte \U0001f60a"
# U+1F469 U+200D U+1F4BB is one ZWJ emoji sequence (woman technologist); U+2764 U+FE0F uses a variation selector.
OPENING_LILITH = "TEST_ONLY oh! hello, is it moring already? \u201cna\u00efve\u201d me \U0001f469\u200d\U0001f4bb \u2764\ufe0f"
MIDDLE_OWNER = "TEST_ONLY it's evening actually.\nwe were just talking about tea"
CLOSING_LILITH = "TEST_ONLY sorry, I guessed wrong. good night \U0001f319"
CLOSING_OWNER = "TEST_ONLY good night"

TURNS = [
    (FM.OWNER, "2026-11-01T18:00:00Z", OPENING_OWNER),
    (FM.LILITH, "2026-11-01T18:00:04.250Z", OPENING_LILITH),
    (FM.OWNER, "2026-11-01T18:01:10Z", MIDDLE_OWNER),
    (FM.LILITH, "2026-11-01T18:01:15Z", CLOSING_LILITH),
    (FM.OWNER, "2026-11-01T18:02:00.5Z", CLOSING_OWNER),
]


def transcript_bytes(turns=None, **overrides) -> bytes:
    """Transcript evidence as UTF-8 JSON (deliberately not ASCII-escaped: the digest is over these exact bytes)."""
    doc = {"schema": FM.TRANSCRIPT_SCHEMA, "conversationRef": "conv.test-only.fm02.1",
           "turns": [{"index": i, "speaker": s, "at": at, "text": text}
                     for i, (s, at, text) in enumerate(TURNS if turns is None else turns)]}
    doc.update(overrides)
    return json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")


def quotation(position, turn_index, *, start=0, end=None, text=None, speaker=None) -> dict:
    speaker_, _at, full = TURNS[turn_index]
    end = len(full) if end is None else end
    return {"position": position, "turnIndex": turn_index, "speaker": speaker or speaker_, "start": start,
            "end": end, "text": full[start:end] if text is None else text}


def value(evidence: bytes | None = None, **overrides) -> dict:
    evidence = transcript_bytes() if evidence is None else evidence
    out = {
        "schemaVersion": 1,
        "valueSchema": FM.VALUE_SCHEMA,
        "identityBinding": SI.profile().binding(),
        "truthBasis": FM.RECORDED_INTERACTION,
        "eventTime": {"startedAt": TURNS[0][1], "endedAt": TURNS[-1][1]},
        "transcript": {"schema": FM.TRANSCRIPT_SCHEMA, "evidenceRef": "evidence.test-only.fm02.transcript.1",
                       "sha256": hashlib.sha256(evidence).hexdigest(), "turnCount": len(TURNS)},
        "quotations": [quotation(FM.OPENING, 0), quotation(FM.OPENING, 1),
                       quotation(FM.CLOSING, 3), quotation(FM.CLOSING, 4)],
        "access": {"consumerScope": FM.OWNER_ONLY},
        "retention": dict(FM.RETENTION),
    }
    out.update(copy.deepcopy(overrides))
    return out


def canonical(**overrides) -> str:
    return FM.normalize_first_interaction_episode(value(**overrides))[0]
