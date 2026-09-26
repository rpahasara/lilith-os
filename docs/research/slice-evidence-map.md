# Slice ↔ Research Evidence Map

Status: **RECONCILIATION RECORD**. Maps each slice to the research questions
it tested, the evidence it produced, and the next boundary it created.
*(Primary-source pass, 2026-09-26: all RQ numbers in this file are
`REPO:RQ-NNN`; see the [crosswalk](rq-register-crosswalk.md) for MASTER
equivalents. Slice 1–3 evidence upgraded from REPORTED to PRIMARY, J1.)* RQ
numbers are the **in-repo register** numbering
([research-question-register.md](research-question-register.md)); the
out-of-repo Master numbering is not used here.

Per-slice detail, sources, and failures are in the
[slice history](slice-history.md) and the
[negative results register](negative-results-register.md).

## Evidence levels

The map uses the experiment levels from [method.md](method.md#experiment-levels)
plus an environment tag:

| Level | Meaning (method.md) | Environment tags used here |
| --- | --- | --- |
| E0 | Thought model / design | `design` |
| E1 | Offline simulation | `unit`, `fixture` |
| E2 | Sandbox integration with synthetic data | `CI`, `sandbox`, `DEV-synthetic` |
| E3 | Shadow operation | `pre-DEV shadow` |
| E4 | Approval-gated pilot with bounded real outcomes | `pre-DEV live` |
| E5 | Limited delegation | — (never reached) |

Cognitive lanes that answer the user from real state but cause no action
(Slices 7–13) are tagged **E4-advisory**: real data, real users, no side
effect. This is a reconciliation convention, not a method.md level; it is
flagged so it can be accepted or replaced.

## Map

| Slice | Architecture change | Hypothesis / questions tested | Evidence (level) | Findings | RQs advanced | New questions created | Next boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Slice 1 (code) | First real read capability + typed verifier | Can a verifier refuse transport-only success? | E2 self-test 7/7; live acceptance PRIMARY (J1) | Verifier flagged a live overview-vs-detail inconsistency (PRIMARY, J1) | RQ-034, RQ-021 | How to verify reads with no ground truth? | Slice 2 playbook engine |
| Slice 2 (code) | Shared playbook engine; explicit entity linking | Can one engine serve many read tasks without fuzzy linking? | E2 16/16; live PRIMARY (J1) | Unlinkable → unresolved, never guessed | RQ-021, RQ-013 | — | Durable history (Slice 3) |
| Slice 3 | Backend task store, revisions, operation IDs | Is backend state authoritative over client cache? | E2 32/32; live, restart and 409 PRIMARY (J1) | Revision conflict 409; replay no-op | RQ-004, RQ-008, RQ-018 | Multi-runtime claims? | First write (Slice 4) |
| Slice 4 | Approval-gated unsent draft; fingerprint; read-back | Does approval bind to exactly what executes? Can timeouts avoid duplicate writes? | E2 48/48; **E4** pre-DEV live (real application, unsent draft) | Changed proposal invalidates approval; verify-before-retry | RQ-028, RQ-029, RQ-033, RQ-034, RQ-050 | How long should approvals live? | Generalize to policy (Slice 5) |
| Slice 5 | Policy classes; PROHIBITED; expiry sweep | Can policy be class-based and planner-independent? | E2 60/60; E4 (second write) | Prohibition precedes execution | RQ-026, RQ-027, RQ-031, RQ-032 | Contextual (not static) risk? | Connectors (Slice 6) |
| Slice 6 | Typed connectors; health gate | Does unavailable/unsupported fail closed with zero mutation? | E2 67/67; E4 | Healthy connector never bypasses policy | RQ-034, RQ-039 | Connector reliability priors? | CA-V1; Slice 7 |
| CA-V1 | 19-layer design; §7a; §10 | What layers own which invariants? | E0 | Planner proposes · policy governs · connectors perform · verifier proves | RQ-001, RQ-013, RQ-040 | Whole portfolio | "Spine before mind" |
| Slice 7 / 7.1 | Durable belief store; reconstructible working set; auto-ingest | Can beliefs keep provenance, retain conflict, and survive restart without fabrication? | E1 18/18 + 9/9; **E4-advisory** pre-DEV live (31 real beliefs) | Conflict retained; unavailable never overwrites; WM reconstructed | RQ-012, RQ-013, RQ-015, RQ-008 | TTL policy for beliefs? VERIFIED path unused | Shared lane (7.2) |
| Slice 7.2 / 7.3 | World-Model-first lane at shared Router seam; deterministic dedup | Can two channels share one grounded state? Can duplicates be refused deterministically? | REPORTED E4-advisory (Home + Telegram) | Shadow reproduced ungrounded leak; live fixed it (REPORTED) | RQ-004, RQ-008, RQ-015, RQ-047 | Past duplicates need manual repair | Goals (Slice 8) |
| Slice 8 | Goals, FSM, deterministic arbitration | Can "what to pursue" be deterministic and restart-safe? | E1 22/22 + 9/9; E4-advisory | Focus derived, reconstructed; parity | RQ-018, RQ-019, RQ-020 | Cascades? Inferred priorities? | Reasoning seam (Slice 9) |
| Slice 9 | Tool-less reasoning component | Can the LLM be a bounded, tool-less component that yields to action lanes? | E1 18/18; E4-advisory | Zero tool schemas; fail-open | RQ-023, RQ-047 | Persistence gap (N-06) | Attention (Slice 10) |
| Slice 10 | Deterministic salience arbitration | Can attention bound reasoning input without touching executive focus? | E1 24/24; E4-advisory | Workspace ≠ executive focus | RQ-014, RQ-040 | Interruption delivery; background producers | Motivation (Slice 11) |
| Slice 11 | Ordinal drives, no affect | Can drives bias salience without affect or executive influence? | E1 32/32; E4-advisory | Correct but zero slots in practice (N-07) | RQ-040, RQ-041 | How to measure drive effect? | Planning (Slice 12) |
| Slice 12 | Proposal-only planner; grounder ≠ validator | Can plans be proposed without authority or invented capabilities? | E1 40/40; E4-advisory (template only) | LLM path not live; replanning fixture only | RQ-021, RQ-022 | Post-execution replanning | Ethics (Slice 13) |
| Slice 13 | Advisory ethics, four principles | Can ethics deliberate without ALLOW/DENY? | E1 54/54; E4-advisory | Ethics subtract-gate deferred | RQ-026, RQ-030, RQ-032 | Value priors from memory? | Social (Slice 14) |
| Slice 14 | TURN-only social grounding; Presence contract | Can social cues be grounded without affect or relationship inference? | E1 49/49 (226 suite); **E3** shadow | No live consumer | RQ-043, RQ-046 | Relationship continuity (open) | Learning (15A) |
| 15A | L18 ledger; shadow candidates | Can learning propose without writing memory? | E1 56/56; E3 shadow (3 candidates) | `SHADOW_ELIGIBLE` ≠ true | RQ-009, RQ-010 | Admission criteria | L04 (15B1) |
| 15B1 | L04 CREATE/SUPERSEDE/RESTORE | Can canonical revisions be atomic, replay-safe, and history-preserving? | E1/E2 53 (335 suite); deployed disabled, zero rows | Restore = new revision | RQ-011, RQ-012, RQ-013 | Real consent/verifier/rollback | Authority (15B2a) |
| 15B2a | Actor, Consent, Policy, Rollback, Privacy, containment | Can authority be separated from storage and bound to payload? | E1/E2 55 + A–DL matrix; deployed disabled | FORGET = hold → erasure | RQ-009, RQ-011, RQ-016, RQ-028 | Key custody (N-35) | Runtime foundation (15B2b-A) |
| 15B2b-A | Family-neutral apply; governed package; DEV durability | Can canonical state persist across restart under governed deploy, while PROD stays dark? | E2 DEV-synthetic; PROD DARK audit | `USER_ASSERTED` not promoted | RQ-009, RQ-015, RQ-049 | Owner control | 15B2b-B |
| B1a | Digest-bound WebAuthn owner proof | Can model/HTTP inputs forge owner proof? | E1/E2 CI (golden vectors) | Proof ≠ authority | RQ-028, RQ-029 | Real RP/enrollment | Broker (B1b) |
| B1b-1 / 2a | Broker request construction; crash table | Can proof→authority survive crashes without reissue? | E1 fault hooks | Conservative recovery never reissues | RQ-008, RQ-033 | Live crash evidence | DEV install (B1b-2b) |
| B1b-2b Stage I/II | OS accounts, socket, peer creds (synthetic) | Does OS isolation hold for relay vs ordinary users? | E2 DEV-synthetic; attempt #1 FAILED-INERT, retry #2 ACCEPTED | Isolation positive/negative probes; history-aware retry | RQ-035, RQ-044 | Governance bootstrap cost (N-31) | Stage III |
| Stage III-A A2 | Fault seam, reversible transition, guard, final controller | Does real process death at A2 burn proof without duplicate authority? | E0/E1 only; DEV dispatch **did not run the experiment** | Controller failed at INTENT (N-25) | RQ-033 (no live advance) | A1–A5 live semantics | Deferred |
| B1c | Constrained DEV deployer; activation verifier | Can routine deploy lose root and activation authority? | E2/DEV run 36179649106 | 28 denials; deployment ≠ activation | RQ-035, RQ-048, RQ-037 | Cross-env PROD debt; B1d | 15B2b-B |
| 15B2b-B design | Owner Memory Control | How is owner-chosen memory accepted without model/runtime/DB authority? | E0 | Acceptance = verifier output | RQ-001, RQ-009, RQ-013, RQ-015, RQ-028, RQ-048 | Ten owner decisions | B2a |
| B2a | Acceptance verifier (TEST) | Is every reachable forgery `NOT_ACCEPTED`? | E1/E2 CI (89 cases) | `truthClaim` always false | RQ-013, RQ-015, RQ-028 | Live chain (B2b) | B1b-3 / B2b (unauthorized) |

## Dependency trace: which lower-layer assumptions upper layers rely on

If an upper layer later fails, check these assumptions first.

| Upper layer / claim | Depends on (lower-layer assumption) | Where it was established | Current risk |
| --- | --- | --- | --- |
| Every Home + Telegram parity claim (7.2–14) | Both channels converge at the Hermes `run_sync` → Router V2 seam | Slice 2 / 7.2 (REPORTED; Router V2 source not in repo) | Seam is out-of-repo; parity was route-level (N-12) |
| Beliefs used by reasoning, goals, planning (8–13) | World Model is fed by live `career_events` ingestion | Slice 7.1 | Watcher failing on OAuth (N-15); no TTL, so stale beliefs look ACTIVE |
| 15A learning candidates | `career_events` source schema is stable | 15A preflight fingerprint | Same source degradation (N-15) |
| Slice 8 app-14 BLOCKED state | Two unsent drafts exist and dedup refuses a third | Slice 4 store + 7.3 | Historical duplicates unresolved (N-05) |
| Slice 12 capability view | Static mirror matches the frontend `RealCommandCore` registry | Slice 5 registry | Mirror is non-authoritative and can drift |
| Slice 13 `SKIPPED_KNOWN_PROHIBITION` | Static prohibition mirror matches Slice 5 PROHIBITED list | Slice 5 | Same drift risk; labelled non-authoritative |
| Slice 9/12/13 short-circuit answers | `enforce_reply` runs downstream of the `run.py` hook | Slice 9 | Streaming may precede enforcement (N-11) |
| Slice 10 bounded reasoning input | Slice 8 executive focus is derived, not mutated by attention | Slices 8, 10 | Proven invariant; low risk |
| Canonical apply (15B2b-A) | Authority records are unforgeable by the app | 15B2a | **False today**: app holds issuance keys (N-35) |
| Accepted-memory verdict (B2a) | B1a contract and 15B2a contracts unchanged | B1a, 15B2a | Pinned by golden vectors |
| Owner authority on DEV | No routine identity can root the memory host | B1c | Legacy PROD identity can (N-33) |
| Crash-safe real memory | A1–A5 recovery semantics hold under real process death | B1b-1 fault hooks | Live-unproven (N-25) |
| Identity continuity (ADR-0001, P-01) | A versioned identity charter exists | none | Artifact absent (N-34) |
