"""FM-02 First Memory semantic profile: a re-export of the L04-owned normalizer.

The one authoritative copy is `lilith_memory.first_interaction_v1` (Core API), which L04 dispatches for value schema
`FirstInteractionEpisodeV1`. This module keeps the owner-memory-control import path stable and defines nothing of its
own, so there is no second normalizer to drift.
"""

from __future__ import annotations

from lilith_memory.first_interaction_v1 import (  # noqa: F401
    ACCESS,
    BINDING_FIELDS,
    CLOSING,
    LILITH,
    MAX_QUOTATION_CHARS,
    MAX_QUOTATIONS,
    MAX_TURN_CHARS,
    MAX_TURNS,
    MEMORY_CLASS,
    OPENING,
    OWNER,
    OWNER_ONLY,
    RECORDED_INTERACTION,
    RETENTION,
    SPEAKERS,
    SUBJECT_KEY,
    SUBJECT_NAMESPACE,
    TRANSCRIPT_SCHEMA,
    UNTIL_OWNER_FORGET,
    VALUE_SCHEMA,
    VALUE_SCHEMA_VERSION,
    FirstMemoryContractViolation,
    dialogue_text,
    normalize_first_interaction_episode,
    parse_transcript,
    verify_episode_evidence,
)
