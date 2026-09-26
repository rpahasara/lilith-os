# Publication Notes

Status: **RECONCILIATION RECORD — NOTHING PUBLISHED.** This note grades which
findings are mature enough for which kind of public writing, and which claims
are off-limits. It follows the public-writing rules in the
[research README](README.md) and the [journal README](../journal/README.md).

## Source-status vocabulary for any draft

Every factual sentence in a draft should be traceable to one of:

| Status | Use in public writing |
| --- | --- |
| CANONICAL | Stated in an accepted ADR or acceptance record |
| IMPLEMENTED | Code exists (cite path) |
| TEST-PROVEN | Synthetic tests pass (cite suite) |
| DEV-PROVEN | Exact-SHA synthetic run on DEV (cite run) |
| OPERATIONALLY OBSERVED | Real-data pre-DEV live or shadow observation (cite record) |
| INFERRED | Author interpretation — say so |
| PROPOSED | Design only — say so |
| RESEARCH / UNKNOWN | Open — say so |

## Maturity by venue

| Venue | Mature topics (with required caveat) |
| --- | --- |
| **Engineering blog** | Execution ≠ verification, including our own `curl -f` and display-string failures ([RQ-034](findings/rq-034-execution-is-not-verification.md)); idempotency at every write boundary ([RQ-008](findings/rq-008-duplicate-action-prevention.md)); conflict as state ([RQ-012](findings/rq-012-contradiction-and-supersession.md)); one cognitive seam for many channels — caveat: route-level parity ([RQ-004](findings/rq-004-shared-state-across-channels.md)); designing a one-shot crash experiment that stopped at INTENT ([RQ-033](findings/rq-033-unknown-state-and-crash-semantics.md)); regression discipline ≠ evaluation ([RQ-044](findings/rq-044-evaluation-and-regression.md)) |
| **Architecture article** | "Planner proposes · policy governs · connectors perform · verifier proves"; proposal-only planning with grounder ≠ validator — caveat: model planning not live ([RQ-021](findings/rq-021-playbooks-and-planning.md)); provenance explains authorization, not truth ([RQ-013](findings/rq-013-provenance-and-explanation.md)); authority context without host binding — design plus TEST ([RQ-001](findings/rq-001-identity-continuity.md)); architecture evolution record |
| **Security case study** | Removing root from routine deployment with per-run denial proofs — caveat: cross-environment PROD debt open ([RQ-047](findings/rq-047-injection-secrets-authority.md)); digest-bound owner authorization — caveat: synthetic only ([RQ-028](findings/rq-028-approval-binding.md)); one authority mechanism per tier ([RQ-026](findings/rq-026-authority-gradient.md)); forgetting as a privacy authority ([RQ-011](findings/rq-011-forgetting-and-deletion.md)); separating who may admit memory from what memory is ([RQ-009](findings/rq-009-memory-admission.md)) |
| **AI cognition research note** | Carrying epistemic basis end to end — caveat: no adversarial inference path yet ([RQ-015](findings/rq-015-inference-is-not-memory.md)); a drive system that was correct and behaviourally inert ([RQ-040](findings/rq-040-attention-motivation-affect.md)); attention must not rewrite commitments ([RQ-019](findings/rq-019-goal-arbitration.md)) |
| **Future academic paper** | Not yet mature. Candidate core: governed memory authority (RQ-009/013/015/028 findings) **after** real-user or at least adversarial evaluation, a literature review, and live (not unit-only) crash evidence. |

Not mature for any venue: identity continuity as solved; multi-runtime
continuity; interruption quality; any affect or relationship capability (none
exists); any claim about real canonical memory (none exists).

## Claims that must not appear

Unless a future literature review and evidence support them:

- "nobody else does this", "first ever", "novel" (no literature review done);
- "solved consciousness", "LILITH feels", "human emotions achieved";
- "LILITH remembers you" in the canonical-memory sense (zero real memories);
- "crash-safe" or "proven under failure" for owner authority (live-unproven);
- "Level 2 isolation" (explicitly not claimed by B1c);
- "production" for Slices 7–15B2a without saying they were hand-deployed
  before a DEV environment existed.

## Lessons from the archived Master (added 2026-09-26)

Master v1.0 (2026-09-14) carried novelty language in its RQ-101–120 texts
(for example "Your unique angle", "Novelty: This is meta-research"), and v1.1
replaced it with testable questions the same day. Treat that as the house
standard: any draft drawing on MASTER:RQ-101–121 should use the v1.1 wording.
The Master's own "novelty discipline" note requires a literature review before
publication.

## Sanitization before any publication

In-repo records contain operational identifiers (cloud project, zone,
instance IDs, service-account names, host paths, run IDs, hashes). The
Infrastructure, CI/CD & Operations originals, which contain operational
topology and inventory, are PRIVATE HISTORICAL SOURCES and are deliberately not
in this repository; drafts must not quote topology details from them. The
research README requires removing personal data, secrets, and operationally
sensitive details from public material. Drafts should cite records by
concept, not reproduce identifiers, and must never include key material,
tokens, or private connector content.
