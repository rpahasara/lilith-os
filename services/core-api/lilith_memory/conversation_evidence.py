"""F2/F3 First Interaction candidate evidence gate over server-captured conversation evidence.

- **Capture is the relay's, not this module's.** The Core API conversation relay (`app.py`, `POST /os/conversation`)
  records OWNER/LILITH exchanges for authenticated capture sessions and seals them into
  `fi_conversation_evidence` (exact transcript bytes, their SHA-256, a minted evidence reference). The PROD API never
  imports this package; this module only reads that table, read-only.
- **Candidate gate.** `FirstInteractionEvidenceGate` finds the sealed bytes by the value's evidence reference (never
  caller-supplied bytes), re-checks their recorded digest, runs the existing `verify_episode_evidence` (which also
  applies the verbatim-text rules: text that is not exactly acceptable is refused, never repaired), then requires the
  value's identity binding to equal a trusted identity binding whose environment equals the trusted deployment
  environment. Without a trusted identity binding it refuses: no profile or charter is created or approved here.

Nothing here admits, accepts or activates memory, and no result claims truth or First Memory acceptance. The
relay's capture credential is service authentication (Next server proxy to Core API), not owner authentication:
captured evidence proves what the relay carried, never who the owner is.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:
    from . import first_interaction_v1 as FI
except ImportError:  # deploy-exact flat-directory tests
    import first_interaction_v1 as FI

ENVIRONMENTS = frozenset({"test", "dev", "prod"})
EVIDENCE_SEMANTICS = "CAPTURED_CONVERSATION_EVIDENCE_NOT_A_MEMORY_ACCEPTANCE"


class ConversationEvidenceError(ValueError):
    """Closed refusal; `code` names the reason and never carries dialogue text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _refuse(code: str) -> None:
    raise ConversationEvidenceError(code)


class ConversationEvidenceReader:
    """Read-only view of the relay's sealed transcripts (`fi_conversation_evidence`)."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def sealed_transcript(self, evidence_ref: str) -> Optional[bytes]:
        """The exact sealed bytes, re-checked against their recorded digest; None when no such evidence exists."""
        if not self.path.is_file():
            return None
        conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=5.0)
        try:
            row = conn.execute("SELECT transcript, sha256 FROM fi_conversation_evidence WHERE evidence_ref=?",
                               (evidence_ref,)).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()
        if row is None:
            return None
        data = bytes(row[0])
        if hashlib.sha256(data).hexdigest() != row[1]:
            _refuse("EVIDENCE_CORRUPT")
        return data


@dataclass(frozen=True)
class TrustedIdentityBindingV1:
    """The identity binding of an owner-accepted LILITH identity profile and that profile's environment. It comes
    from trusted code or configuration, never from a conversation payload or a memory value."""

    environment: str
    binding: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.environment, str) or self.environment not in ENVIRONMENTS:
            _refuse("IDENTITY_PROFILE_MALFORMED")
        try:
            checked = FI._binding(self.binding)
        except FI.FirstMemoryContractViolation:
            _refuse("IDENTITY_PROFILE_MALFORMED")
        object.__setattr__(self, "binding", dict(checked))


class FirstInteractionEvidenceGate:
    """Verifies a First Interaction candidate value against sealed captured evidence and the trusted identity.

    `evidence_source.sealed_transcript(evidence_ref)` returns the exact sealed bytes or None. Facts only: the result
    never admits, accepts, authorizes or certifies truth."""

    def __init__(self, evidence_source: Any, *, trusted_identity: Optional[TrustedIdentityBindingV1],
                 deployment_environment: str):
        self.evidence_source = evidence_source
        self.trusted_identity = trusted_identity
        self.deployment_environment = deployment_environment

    def __call__(self, normalized_value_json: str, *, expected_conversation_ref: Optional[str] = None
                 ) -> Dict[str, Any]:
        trusted = self.trusted_identity
        if not isinstance(trusted, TrustedIdentityBindingV1):
            _refuse("IDENTITY_PROFILE_UNAVAILABLE")
        if self.deployment_environment not in ENVIRONMENTS or trusted.environment != self.deployment_environment:
            _refuse("IDENTITY_ENVIRONMENT_MISMATCH")
        try:
            value = json.loads(normalized_value_json)
            evidence_ref = value["transcript"]["evidenceRef"]
        except (TypeError, ValueError, KeyError):
            _refuse("VALUE_NOT_CANONICAL")
        if not isinstance(evidence_ref, str):
            _refuse("VALUE_NOT_CANONICAL")
        transcript = self.evidence_source.sealed_transcript(evidence_ref)
        if transcript is None:
            _refuse("EVIDENCE_UNKNOWN")
        try:
            facts = FI.verify_episode_evidence(normalized_value_json, transcript)
            conversation_ref = FI.parse_transcript(transcript)["conversationRef"]
        except FI.FirstMemoryContractViolation as exc:
            _refuse(str(exc))
        if expected_conversation_ref is not None and conversation_ref != expected_conversation_ref:
            _refuse("CONVERSATION_MISMATCH")
        if value["identityBinding"] != trusted.binding:
            _refuse("IDENTITY_BINDING_MISMATCH")
        return {**facts, "semantics": EVIDENCE_SEMANTICS, "evidenceRef": evidence_ref,
                "conversationRef": conversation_ref, "identityEnvironment": trusted.environment,
                "firstMemoryAccepted": False}
