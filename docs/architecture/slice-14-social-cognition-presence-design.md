# LILITH Slice 14 — Social Cognition Grounding + Presence Contract V1

> **Status:** IMPLEMENTED, TESTED, AND DEPLOYED (PASS) on 2026-09-09.
> **Layer:** a deliberately narrowed implementation of L11 · Social Cognition / Personality. V1 implements structured current-turn observation only; it does not implement a new personality or relationship-model owner.
> **Governing invariant:** **Social Cognition observes. SOUL/personality expresses. Social Guard enforces social reply conformance. Presence Contract describes future embodiment semantics.**
> **Target:** `lilith-01` backend Router only (`~/.hermes/lilith_router/`). No frontend, Hsin, Presence renderer, World, Memory, DB, prompt, response, connector, or execution change.

---

## 1. Corrected ownership map

Mandatory runtime inspection found the existing live owners and V1 preserves them:

| Concern | Authoritative owner | Slice 14 authority |
|---|---|---|
| Base identity/personality | `/home/lilith/.hermes/SOUL.md` | none |
| Contextual social-mode prompt adaptation | Router-local `policy.py` | none |
| Social response conformance/regeneration | `social_guard.py` | none |
| Final social-enforcement seam | `enforce_reply()` in `gateway_integration.py` | none; function remains byte-identical |
| Named personality overlays | Hermes `hermes_cli/personality.py` | none |
| Current-turn social observation | `social_cognition.py` | sole Slice-14 runtime responsibility |
| Renderer-independent semantic hint | `presence_contract.py` | typed, ephemeral description only |
| Visual/voice embodiment | existing Presence renderer | none |

There is no `PersonalityProfile`, personality composer, `InteractionStyle`, second social prompt, text renderer, text rewriter, or reply regenerator in Slice 14.

## 2. Runtime scope and non-authority

V1 is deterministic, bounded, current-turn-only, ephemeral, and shadow-only. It extracts directly grounded role/recipient evidence, derives a minimal social-context snapshot, validates it, derives a minimal Presence semantic hint, validates it, emits a safe trace, and discards the runtime objects after the turn.

It never returns or changes `final_response`; never changes `turn_route` or `combined_ephemeral`; never changes Planning, Ethics, Reasoning, cognitive, goal, explicit-action, or social-lane precedence; never calls SOUL, Policy, Social Guard, Hermes personality, World, Memory, tools, connectors, HTTP, or a database; and never persists anything.

## 3. SocialInput and provenance split

```
SocialInput {
  schemaVersion
  correlationId
  channel
  sessionActor {
    actorRef
    bindingType: CURRENT_TURN_SENDER_BINDING
    participantKind: CURRENT_TURN_SENDER
    identityStatus: SESSION_BOUND
  }
  socialTurnEvidence: SocialTurnEvidence
}

SocialTurnEvidence {
  schemaVersion
  correlationId
  turnRef
  sourceOwner: TURN
  evidenceItems[]
  sourceRefs[]
}
```

`sessionActor` and `channel` are Router/session metadata and are intentionally outside the TURN-owned evidence object. `CURRENT_TURN_SENDER + SESSION_BOUND` means only the actor attached to the current Router/session context. It is not an authenticated-human, account-owner, named-person, or cross-device identity claim. `CURRENT_USER` is rejected.

Each evidence item has `evidenceRef`, `evidenceType`, and a direct `sourceRange { start, endExclusive }`; optional fields are limited to directly grounded `literalRoleLabel`, `assertionStatus`, `constraintDimension`, `constraintValue`, and `relatedSourceRefs`. Evidence is capped at eight items.

## 4. Admitted evidence and exact consumers

| Evidence type | Exact consumer |
|---|---|
| `THIRD_PARTY_ROLE_MENTION` | creates a turn-local ROLE_ONLY third-party participant |
| `INTENDED_RECIPIENT_RELATION` | links a grounded participant to AudienceContext |
| `EXPLICIT_FORMALITY_REQUEST` | FORMALITY=PROFESSIONAL constraint → Presence formality |
| `EXPLICIT_CASUAL_STYLE_REQUEST` | FORMALITY=CASUAL constraint → neutral/default Presence formality |
| `EXPLICIT_HUMOR_REQUEST` | social cue → Presence playfulness PERMITTED |
| `PLAYFUL_CONTEXT_CUE` | social cue → Presence playfulness PERMITTED |
| `EXPLICIT_SUPPORT_REQUEST` | social cue → Presence social tone SUPPORTIVE |
| `EXPLICIT_DIFFICULTY_SELF_REPORT` | social cue → Presence social tone SUPPORTIVE |
| `USER_CORRECTION` | turn-local correction cue/conflict |

`CURRENT_TURN_SENDER_BINDING` is session metadata, not TURN text evidence. No thanks/apology/casual-address/warmth/brevity/detail/generic third-party/affect category is admitted.

Playful context requires both a narrow lexical form (trolling/roasting me) and a laughter marker (😂, 🤣, lol, or lmao). Profanity alone, including “wtf,” yields no affect, difficulty, or playfulness cue. Correction handling is limited to a current-turn asserted/negated role contrast; it performs no World reconciliation.

## 5. Participant and audience semantics

```
SocialParticipantRef {
  participantRef
  participantKind: CURRENT_TURN_SENDER | THIRD_PARTY
  identityStatus: SESSION_BOUND | ROLE_ONLY
  literalRoleLabel?
  sourceRefs[]
}

AudienceContext {
  audienceRef
  audienceContextClass: PROFESSIONAL | UNSPECIFIED
  sourceRefs[]
}
```

The shipped extractor recognizes the bounded literal role vocabulary `manager`, `recruiter`, `sister`, `partner`, and `coworker`. These are literal current-turn labels, not relationship classes. No name, email, address, identity, trust, closeness, familiarity, friendship, or durable association is inferred. `ASSISTANT_SELF` is not emitted because V1 has no consumer.

The professional whitelist is exactly `manager` and `recruiter`. PROFESSIONAL requires both a whitelisted literal role and a deterministic intended-recipient relation. Incidental mentions and incoming-message descriptions do not qualify. Ambiguous/multiple recipient relations remain unresolved/unspecified.

## 6. SocialContextSnapshot

```
SocialContextSnapshot {
  schemaVersion
  socialSemanticFingerprint
  turnRef
  channel
  participants[]                 # <= 8
  audienceContext?               # one deterministic recipient only
  explicitInteractionConstraints[] # FORMALITY only; <= 8
  socialCues[]                   # <= 8
  conflicts[]                    # <= 8
  informationNeeded[]            # <= 8
  sourceRefs[]
  sourceAvailability: TURN_ONLY_BY_DESIGN
}
```

The only constraint dimension is FORMALITY with PROFESSIONAL or CASUAL. The cue set is exactly humor, playful-context, support, difficulty-self-report, and correction. Runtime conflicts are only `CONTRADICTORY_FORMALITY_REQUESTS`, `CURRENT_TURN_ROLE_CORRECTION`, and `AMBIGUOUS_RECIPIENT_RELATION`, all observable from current-turn input. There are no World states, World lifecycle/epistemic fields, relationship state, user affect, or psychological scores.

## 7. Semantic fingerprint

`socialSemanticFingerprint` is `scf.` plus the first 16 hexadecimal characters of SHA-256 over canonical compact JSON. The canonical payload contains only:

- sorted participant tuples `(participantKind, identityStatus, literalRoleLabel-or-empty)`;
- audience class plus its participant's literal role;
- sorted FORMALITY constraint pairs;
- sorted cue, conflict, and information-needed codes;
- `sourceAvailability`.

It excludes channel, time, correlation ID, participant/evidence/source reference strings, TURN refs, and source-range offsets. It supports semantic parity comparison only; it is not snapshot object identity, persistence, continuity, or a relationship identifier.

## 8. PresenceSemanticHint

```
PresenceSemanticHint {
  schemaVersion
  correlationId
  socialSemanticFingerprint
  socialTone: NEUTRAL | SUPPORTIVE
  formalityHint: NEUTRAL | PROFESSIONAL
  playfulness: RESTRAINED | PERMITTED
  sourceRefs[]
}
```

Derivation is deterministic and orthogonal:

- support or difficulty cue → SUPPORTIVE; otherwise NEUTRAL;
- explicit formal request → PROFESSIONAL;
- explicit casual request, or contradictory formal/casual requests → NEUTRAL;
- otherwise professional AudienceContext → PROFESSIONAL; otherwise NEUTRAL;
- explicit humor or narrow playful-context cue → PERMITTED; otherwise RESTRAINED.

Only evidence refs that caused selected non-default values are included. Default NEUTRAL/RESTRAINED values use no refs. Refs must be unique, resolve in the snapshot, and equal the exact causal set.

`WARM` is absent and rejected. The schema has no affect/emotion, mood, sentiment, intensity, energy, timing, response phase, gaze, expression, pose, bone, blendshape, animation, camera, text, style, or renderer command.

## 9. Validation and fail-open behavior

Both modules use closed schemas and reject rather than synthesize or repair unsupported meaning. Validators reject CURRENT_USER/authenticated-human claims, WORLD_REFERENCED and World fields, relationship classes/state, trust/familiarity/closeness/friendship, affect/emotion/sentiment, verbosity/detail/warmth, personality, prompt/final-response/Policy/goal/task/draft/execution fields, renderer controls, unsupported recipient/professional-audience semantics, unresolved/duplicate provenance, unbounded arrays, and fingerprint mismatches.

The Router observer catches extraction, snapshot-validation, Presence-derivation/validation, and trace failures. It returns `None` on every path; failure produces at most a safe INVALID trace and the existing conversation proceeds unchanged. Trace-write failure is separately swallowed. There are no retries that can alter conversation semantics.

## 10. Router integration and rollout

`gateway_integration.py` invokes `_observe_social_cognition` after source, platform, chat ID, session key, and message have been resolved, and before classifier/planning/ethics/reasoning/cognitive/goal/social decisions. The call has no result consumer.

`config.py` adds only:

```yaml
social_cognition_enabled: true
social_cognition_mode: shadow
```

Channel scope reuses `cognitive_channels: [lilith_os, telegram]`; Discord is excluded. The observer is active only when enabled, mode equals exactly `shadow`, and the channel matches. `live` and all unknown modes disable the observer for that turn. V1 has no live consumer.

## 11. Safe trace

The trace schema is: `lane`, `correlation_id`, `social_semantic_fingerprint`, `participant_count`, `participant_kinds`, `audience_context_class`, `constraint_types`, `cue_types`, `conflict_types`, `information_need_codes`, `source_availability`, the three Presence values, `validation_status`, `fallback_reason`, `duration_ms`, `schema_version`, and `timestamp`.

It contains no raw turn text, source ranges, literal role labels, names, emails, relationship data, prompt/SOUL content, affect/sentiment, or hidden reasoning.

## 12. Tests and acceptance

The deploy-exact isolated tree passed 49 Slice-14 tests and 226 total discovered Slice 8–14 tests. Standalone regressions passed: classifier 18/18, Social Guard 34/34, integration fail-open 14/14, and all world-context checks. The production staging copy and installed tree each passed Slice 14 49/49. The A–L acceptance matrix passed after the single gateway restart, including a VALID Home shadow trace and equal Home/Telegram participant/cue/audience/Presence semantics and semantic fingerprint with no Telegram send.

The suite explicitly covers the requested A–CO boundaries: ownership separation; TURN/session provenance; role/audience grounding; no LLM/World/Memory/affect/relationship/personality/text mutation/tools/connectors/POST/DB/write behavior; shadow-only gating; route non-interference; safe trace; parity; protected owners; Slice 8–13 regressions; and unchanged frontend tree.

## 13. Limitations and recorded debt

- V1 uses direct deterministic regex evidence only; ambiguous recipient meaning remains unspecified.
- Literal role recognition is intentionally bounded and the professional whitelist is fixed to manager/recruiter.
- No World/Memory context, durable social model, relationship continuity, LLM recipient inference, or Presence renderer consumer exists.
- Presence hints are computed and discarded in shadow; they do not change text or embodiment.
- `STREAMED_RESPONSE_VS_POST_ENFORCEMENT_FINAL_RESPONSE_RECONCILIATION` remains recorded architectural debt. Current transport may stream/finalize initial text before `enforce_reply()` replaces/regenerates it. Slice 14 makes no `run.py`, transport, streaming, or finalization change.

Deployment evidence, hashes, restart details, and rollback are recorded in `docs/architecture/slice-14/DEPLOYMENT-RECORD.md`.
