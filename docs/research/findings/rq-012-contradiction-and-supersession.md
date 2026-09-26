# REPO:RQ-012 — Contradiction, supersession, and history

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-012** (in-repo register). MASTER equivalent: MASTER:RQ-006 (SEMANTIC MATCH); related MASTER:RQ-103 (adversarial memory), MASTER:RQ-085.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - S4 (2026-08-24) truth ladder: STALE / CONFLICTED claims are "visible; never silently merged" — the rule Slice 7 implemented on 2026-09-07.
> - MASTER:RQ-006 proposes temporal validity (valid_from / valid_until).

## Research question

How should contradictory memories coexist and resolve? (In-repo RQ-012;
related RQ-013, RQ-038.)

## Why it matters to LILITH

Preferences change, sources disagree, and corrections arrive late. Silently
overwriting destroys the record of what LILITH believed and why; never
resolving leaves her paralysed.

## Original hypothesis / problem

Preserve temporal validity and provenance; never blindly overwrite history.

## Architecture explored

- **World Model** ([Slice 7 spec](../../architecture/slice-7-world-model-backend-spec.md)):
  deterministic reconciliation rules R0–R8. Newer observation supersedes
  older; VERIFIED outranks INFERRED; equal authority that disagrees and is not
  clearly newer becomes `CONFLICTED` with both chains retained; unavailable
  sources never overwrite; unknown returns 404. No LLM resolves conflicts.
- **Long-Term Memory** (15B1): SUPERSEDE creates a new revision against the
  exact expected active revision; RESTORE creates a new revision linking both
  current and restored history, never repointing to an old revision.
- CA-V1 §12: "conflict = supersede, never delete".

## Experiments / implementation slices

Slice 7 A–R; Slice 7 live controlled conflict; 7.1 event-time supersession;
15B1 C/D/E/G (supersede, stale supersede, restore, cross-item restore).

## Evidence

- OPERATIONAL (pre-DEV live): a controlled conflict became `CONFLICTED` with
  both provenance chains kept and value not overwritten; a newer
  `career_event` superseded an older belief value (Slices 7, 7.1).
- TEST: stale SUPERSEDE → `PRECONDITION_FAILED / ACTIVE_REVISION_MISMATCH`,
  no partial write; cross-item RESTORE rejected (15B1).

## Negative findings / failures

- Conflict resolution is purely rule-based; there is no user-facing
  disambiguation flow in production (CA-V1 flow E is design only).
- Semantic contradictions (two differently worded facts) are not detected;
  only same-key disagreements are.

## Current answer

- **PROVEN (pre-DEV live, TEST):** for keyed beliefs and canonical revisions,
  deterministic rules can retain contradictions, supersede by time or
  epistemic authority, and preserve full history.
- **DESIGNED:** Meta-cognition contradiction signals and user disambiguation.
- **INFERRED:** current evidence supports "represent conflict as state" as
  workable at small scale with a closed predicate vocabulary.
- **UNKNOWN:** behaviour with fuzzy semantic claims, fraud, or many
  unequal-authority sources.

## Confidence / maturity

Medium for keyed beliefs; low beyond that.

## What remains unanswered

The register's contradiction corpus (preference change, correction, fraud,
uncertain evidence); how conflicts surface to the user; LTM-level
contradiction across classes.

## Related RQs

RQ-013, RQ-038, RQ-010, RQ-015.

## Related slices

7, 7.1, 15B1.

## Publication notes

Mature for an **engineering blog** on "conflict is a state, not an error" with
live evidence from a small real dataset (8 applications, 31 beliefs).
