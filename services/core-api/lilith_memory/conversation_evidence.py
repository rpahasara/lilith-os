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
import os
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
FIRST_INTERACTION_IDENTITY = (FI.MEMORY_CLASS, FI.SUBJECT_NAMESPACE, FI.SUBJECT_KEY)
# Identical DDL in app.py. One row: the Privacy authority's opaque restore-suppression selector for the First
# Interaction identity, so the relay can check Privacy suppression read-only without the Privacy secret.
CAPTURE_PRIVACY_BINDING_DDL = (
    "CREATE TABLE IF NOT EXISTS fi_capture_privacy_binding ("
    "identity_selector TEXT NOT NULL CHECK(length(identity_selector)=64))",
    "CREATE TRIGGER IF NOT EXISTS fi_capture_privacy_binding_no_update BEFORE UPDATE ON fi_capture_privacy_binding "
    "BEGIN SELECT RAISE(ABORT,'capture privacy binding is permanent'); END",
    "CREATE TRIGGER IF NOT EXISTS fi_capture_privacy_binding_no_delete BEFORE DELETE ON fi_capture_privacy_binding "
    "BEGIN SELECT RAISE(ABORT,'capture privacy binding is permanent'); END",
)


class ConversationEvidenceError(ValueError):
    """Closed refusal; `code` names the reason and never carries dialogue text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _refuse(code: str) -> None:
    raise ConversationEvidenceError(code)


def provision_capture_store(path: Path, privacy_store: Any) -> str:
    """Operator provisioning of the relay's capture database, run with the Privacy Governance store (the only holder
    of the selector secret). Refuses, creating nothing, once the First Interaction identity is held or forgotten
    (Privacy restore suppression is permanent). Otherwise records the identity's selector, which the relay then
    checks against Privacy suppression inside every capture transaction. Idempotent; a different binding refuses."""
    path = Path(path)
    if privacy_store.is_held(*FIRST_INTERACTION_IDENTITY):          # ACTIVE hold, or ACTIVE/COMPLETE suppression
        _refuse("CAPTURE_PRIVACY_FORGOTTEN")
    selector = privacy_store.identity_selector(FIRST_INTERACTION_IDENTITY)
    created = not path.exists()
    conn = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
    try:
        if created and os.name != "nt":
            os.chmod(path, 0o600)
        conn.execute("BEGIN IMMEDIATE")
        for statement in CAPTURE_PRIVACY_BINDING_DDL:
            conn.execute(statement)
        rows = [str(r[0]) for r in conn.execute("SELECT identity_selector FROM fi_capture_privacy_binding")]
        if rows and rows != [selector]:
            _refuse("CAPTURE_BINDING_MISMATCH")
        if not rows:
            conn.execute("INSERT INTO fi_capture_privacy_binding VALUES (?)", (selector,))
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return selector


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
