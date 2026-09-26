# RQ → Evidence Map

Status: **RECONCILIATION RECORD**. Maps every in-repo research question
(RQ-001–RQ-050) to project evidence. The register's **historical status is not
changed**; this map adds a separate, *proposed* evidence assessment. Per the
[register's review cadence](research-question-register.md#review-cadence),
status promotion happens only in a pull request that links evidence and is
accepted; this record proposes, it does not promote.

Numbering is the in-repo register. For Master v1.1 numbers see the
[numbering reconciliation](rq-numbering-reconciliation.md).

## Primary-source pass corrections (2026-09-26)

- **Namespace.** Every RQ in this map is `REPO:RQ-NNN`. MASTER equivalents
  for each row are in the [crosswalk](rq-register-crosswalk.md#repo--master-all-50).
- **Evidence labels upgraded** (no proposed-maturity change results; the
  evidence got stronger, not broader):
  - REPO:RQ-004, 008, 018 — Slice 3 backend task store, revisions,
    idempotency and restart survival: REPORTED → PRIMARY (J1 Entry 11).
  - REPO:RQ-021, 034 — Slice 1–2 self-tests (7/7, 16/16) and the live
    overview-vs-detail discrepancy: REPORTED → PRIMARY (J1 Entries 9–10).
  - REPO:RQ-013, 038 — honest degraded-source handling during the Google OAuth
    failure: PRIMARY (J1 Entry 12).
  - REPO:RQ-024 — Router V2 as the shipped domain-reasoning substrate:
    REPORTED → PRIMARY (S1 pp. 29–30; J1 Entry 9). Its source is still not in
    the repository.
  - REPO:RQ-033 — Stage III-A dispatches: RUN evidence (two failed dispatch
    runs; no experiment ran).
  - REPO:RQ-035, 037, 048 — B1c failures and acceptance: RUN evidence
    (run 36172947091 attempts 1–3; run 36179649106).
- **Older design origins found.** Several REPO hypotheses already appear in
  S4 (2026-08-24) or the Master (2026-09-14): the truth ladder (RQ-012,
  RQ-015), approval classes (RQ-026), secrets vault (RQ-048), memory lifecycle
  (RQ-009, RQ-011). This dates the *designs* earlier; it adds no
  implementation evidence.

## Vocabulary

**Historical status** — copied unchanged from the register (`UNKNOWN`,
`RESEARCH`, `DESIGNED`, `PARTIAL`, …; defined in [method.md](method.md)).

**Evidence type** — the strongest kind of project evidence found:

| Evidence type | Meaning | method.md level |
| --- | --- | --- |
| NONE | No project artifact bears on the question | — |
| DESIGN | Design record, ADR, or invariant only | E0 |
| TEST | Unit, fixture, CI, or sandbox tests with synthetic data | E1–E2 |
| DEV | Exact-SHA synthetic run on `lilith-dev-01` | E2 |
| OPERATIONAL | Real data on `lilith-01` before DEV existed (pre-DEV live or shadow) | E3–E4 |
| DEFERRED | Experiment designed; attempted or blocked; no result | — |

**Proposed maturity** — what the evidence would support under method.md, with
its scope. "=" means no change proposed.

A security or authority verifier does **not** by itself answer a cognitive
question. Where evidence is authority mechanics, the scope column says so.

## Detailed findings

Questions with meaningful evidence have a detailed finding record in
[findings/](findings/README.md): RQ-001, RQ-004, RQ-008, RQ-009, RQ-011,
RQ-012, RQ-013, RQ-015, RQ-019, RQ-021, RQ-026, RQ-028, RQ-033, RQ-034,
RQ-040, RQ-044, RQ-047 (each also covers the related questions it names).

## Map

| RQ | Topic | Historical status | Evidence type | Proposed maturity (scope) | Key evidence | Still unknown |
| --- | --- | --- | --- | --- | --- | --- |
| RQ-001 | Identity invariant across replacement | RESEARCH | DESIGN (+TEST for owner context) | = | ADR-0001; CA-V1; 15B2b-B logical-only owner context; B2a V2 challenge has no host field | No identity charter (N-34); no restoration test |
| RQ-002 | Evolution vs replacement | UNKNOWN | NONE | = | Charter binding deferred (15B2b-B) | Everything |
| RQ-003 | Restore without competing identity | RESEARCH | TEST | PARTIAL (memory-item scope only) | L04 RESTORE creates a new revision linking current and restored history (15B1, 15B2b-A); suppression replay before restore; ledger-epoch voiding PROPOSED, field TEST-implemented (B2a) | Identity-level restore/fork/merge |
| RQ-004 | One identity across runtimes | DESIGNED | OPERATIONAL (channels) | = | Home + Telegram route parity at one Router seam (7.2–13); backend task store authoritative (Slice 3) | A second runtime; channel parity ≠ runtime independence |
| RQ-005 | Leader / leases / ownership | RESEARCH | NONE | = | Only optimistic revisions (Slices 3, 8) | Partition behaviour |
| RQ-006 | Offline runtime envelope | UNKNOWN | NONE | = | — | Everything |
| RQ-007 | Normalizing model/runtime differences | RESEARCH | DESIGN | = | Tool-less reasoning component contract (Slice 9) | Cross-runtime suite |
| RQ-008 | Preventing duplicated actions | DESIGNED | TEST + OPERATIONAL (internal writes) | PARTIAL (internal writes only) | Idempotency keys (Slice 4); `operationId` (Slice 3); cursor + evidence dedup (7.1); deterministic draft dedup (7.3, REPORTED); L04 `ALREADY_APPLIED`; unique claim/nonce (B1b-1) | Any external connector; cross-runtime |
| RQ-009 | What becomes durable memory | DESIGNED | TEST + DEV + OPERATIONAL (shadow) | PARTIAL (authority/gating mechanics only) | 15A shadow candidates; 15B2a actor/consent/policy gates; 15B2b-A DEV durability; B2a verifier | Selection criteria (importance, novelty, sensitivity) untested; zero real admissions |
| RQ-010 | Episodic → semantic consolidation | RESEARCH | OPERATIONAL (shadow) | = | 15A source-event candidates only | Any semantic consolidation |
| RQ-011 | Decay, archive, forgetting | RESEARCH | TEST | = | FORGET hold → erasure (15B2a); STALE sweep (7.1) | Decay policy; retrieval/trust effects |
| RQ-012 | Contradictory memories | DESIGNED | OPERATIONAL | PARTIAL (World Model beliefs, deterministic rules) | `CONFLICTED` retention, supersession (Slice 7, live); L04 supersede lineage (15B1) | Semantic/LTM contradictions; user-facing resolution |
| RQ-013 | Why LILITH believes a claim | PARTIAL | OPERATIONAL + TEST | = (evidence strengthened) | Belief evidence/trace tables live (Slice 7); L04 provenance explanation (15B1); B2a chain | Three multi-source conclusions traced end to end |
| RQ-014 | Which memories enter cognition | RESEARCH | OPERATIONAL | = | Workspace salience bounds reasoning input (Slice 10); bounded working set (Slice 7) | LTM retrieval ranking; privacy leakage |
| RQ-015 | Inference not becoming false memory | DESIGNED | TEST + DEV + OPERATIONAL | PARTIAL (structural separation) | Epistemic states; VERIFIED only via verification path (Slice 7); `SHADOW_ELIGIBLE` ≠ true (15A); `USER_ASSERTED` not promoted (15B2b-A DEV); `truthClaim=false` (B2a) | No LLM-inference write path exists to attack yet |
| RQ-016 | Complete deletion | UNKNOWN | TEST | RESEARCH (exact-lineage erasure only) | Privileged exact-lineage erasure L04/L18 (15B2a); crypto-erasure PROPOSED (15B2b-B) | Embeddings, caches, backups |
| RQ-017 | Sensitive memory routing | RESEARCH | DESIGN | = | Payload excluded from candidates (15A); legacy `USER.md` not accessed | Classification tiers |
| RQ-018 | Conversation / task / goal distinctions | DESIGNED | OPERATIONAL | PARTIAL | Tasks (Slice 3), goals (Slice 8), ephemeral plans (Slice 12), drafts (Slice 4) | Workflows, routines, automations |
| RQ-019 | Conflicting goals | RESEARCH | OPERATIONAL | = (evidence noted) | Deterministic arbitration (Slice 8) | Preference elicitation; inferred trade-offs |
| RQ-020 | Stale or abandoned goals | DESIGNED | OPERATIONAL (trace) | = | GOAL_COMPLETION drive flags blocked, unattended goals (Slice 11) | Reminder precision; annoyance |
| RQ-021 | Playbooks vs model planning | PARTIAL | OPERATIONAL | = (evidence strengthened) | Playbook engine (Slices 1–2); deterministic plan template live, LLM path not wired (Slice 12) | Reliability/cost comparison |
| RQ-022 | Continue / replan / pause / stop | DESIGNED | TEST (fixture) | = | Replanning fixture-only (Slice 12) | Post-execution replanning |
| RQ-023 | Recognizing unreliable reasoning | RESEARCH | OPERATIONAL | = | Uncertainty-analysis framing (Slice 9) | Calibration |
| RQ-024 | Which runtime/model handles a task | DESIGNED | OPERATIONAL (PRIMARY, corrected) | = | Router V2 lanes and precedence (S1, J1 Entry 9; source not in repo) | Routing benchmark |
| RQ-025 | Bounded worker delegation | RESEARCH | NONE | = | — | Everything |
| RQ-026 | Contextual action risk | RESEARCH | OPERATIONAL | = | Static intrinsic classes (Slice 5); advisory consequence reasoning (Slice 13) | Contextual factors |
| RQ-027 | Reducing friction safely | DESIGNED | DESIGN | = | No learning → policy path exists (15A, Slice 13) | Any proposal mechanism |
| RQ-028 | Binding approval to what executes | DESIGNED | OPERATIONAL + TEST | IMPLEMENTED (internal-write approvals; synthetic owner proofs) | Fingerprint freeze, stale-fingerprint reapproval (Slice 4); payload-bound consent (15B2a); digest-bound challenge (B1a); request digest (B1b-1); 89-case tamper matrix (B2a) | External actions; real owner credential |
| RQ-029 | Approval validity over time | RESEARCH | TEST | PARTIAL | Per-class TTL (Slice 5); ≤60 s challenge, expiry re-checked under lock (B1a); expected-revision preconditions (15B1) | Changing external reality |
| RQ-030 | Urgency without authority | RESEARCH | DESIGN | = | Invariant only (roadmap Phase 7; CA-V1) | 3 a.m. matrix |
| RQ-031 | Safe predelegation | RESEARCH | NONE | = | Autonomy never above A3 | Everything |
| RQ-032 | Nondelegable actions | UNKNOWN | DESIGN + TEST | RESEARCH | `mail.send_email` PROHIBITED (Slice 5); owner-only activation (B1c); per-action owner proof for memory (15B2b-B, B1a) | Values review |
| RQ-033 | Timeout after possible success | DESIGNED | TEST + OPERATIONAL + DEFERRED | PARTIAL (internal writes; unit crash hooks) | Verify-before-retry (Slice 4); crash table A1–A5 (B1b-1); A2 live experiment did not run (N-25) | Live crash semantics |
| RQ-034 | Goal vs execution success | PARTIAL | OPERATIONAL + TEST + DEV | = (evidence strengthened) | Content verifier (Slice 1); read-back (Slice 4); deployment ≠ activation (B1c); apply ≠ accepted (B2a) | Contracts per task class |
| RQ-035 | Independent verification | RESEARCH | DEV | = (evidence noted) | Trusted protected-main pre/post snapshots separate from candidate; owner-run gates; federation denial proofs (B1c) | Correlated-failure comparison |
| RQ-036 | Sufficient evidence | DESIGNED | DESIGN + TEST | = | Three-state acceptance records; A–DL matrix (15B2a); nine-step chain (B2a) | Graded profiles R0–R4 |
| RQ-037 | Measuring false PASS/FAIL/unknown | RESEARCH | OPERATIONAL (incidents) | = | False FAIL incidents N-19, N-30; DEFERRED state (N-26) | Benchmark |
| RQ-038 | Tracing conclusions to observations | DESIGNED | OPERATIONAL | PARTIAL | Belief origins `career_events/N` → `job_applications/N` (7.1); L04 provenance | Multi-source brief trace |
| RQ-039 | Non-idempotent external systems | RESEARCH | NONE | = | Google connector modelled unavailable (Slice 6) | Everything |
| RQ-040 | Interrupt vs wait | RESEARCH | OPERATIONAL | = | Salience classes (Slice 10); drives (Slice 11) | Any interruption delivered |
| RQ-041 | Proactivity without surveillance | RESEARCH | DESIGN | = | Motivation scoped, no global scan (Slice 11); no relationship inference (Slice 14) | Abuse review |
| RQ-042 | Correction without overgeneralizing | UNKNOWN | NONE | = | — | Everything |
| RQ-043 | Trustworthy continuity | RESEARCH | NONE | = | — | Human evaluation |
| RQ-044 | Measuring continuity/identity/verification | RESEARCH | TEST | = | Regression suites (335 router, 67 frontend); acceptance matrices | Continuity/identity metrics |
| RQ-045 | Model upgrades changing judgment | DESIGNED | NONE | = | — | Shadow evaluation |
| RQ-046 | Observability without leaking | RESEARCH | OPERATIONAL | = (evidence noted) | Safe traces without raw input (Slices 14, 15A); tokens never printed (B1c) | Debugging utility after redaction |
| RQ-047 | Prompt-injection resilience | RESEARCH | OPERATIONAL (structural) | = (evidence noted) | Policy outside model (Slice 5); tool-less reasoning/planning/ethics (Slices 9, 12, 13); ungrounded leak fixed (7.2, REPORTED) | Adversarial corpus |
| RQ-048 | Secret isolation | DESIGNED | DEV | = | Tokens never printed; private credential off-host (B1a); deployer denials (B1c) | App-held issuance keys (N-35); B1b-3 |
| RQ-049 | Backup/restore vs continuity | UNKNOWN | TEST + DESIGN | RESEARCH | Suppression replay precedes restore (15B2a, 15B2b-A); verified backups; ledger epoch field (B2a) | Tabletop with concurrent writes |
| RQ-050 | When to advance autonomy | RESEARCH | OPERATIONAL | = | A3 reached for internal writes (Slices 4–5); roadmap not updated (N-16) | Quantitative gates |

## Summary

| Strongest evidence type | Count | RQs |
| --- | --- | --- |
| NONE | 9 | 002, 005, 006, 025, 031, 039, 042, 043, 045 |
| DESIGN only (for the question as posed) | 6 | 001, 007, 017, 027, 030, 041 |
| TEST or DEV, no operational evidence | 11 | 003, 011, 016, 022, 029, 032, 035, 036, 044, 048, 049 |
| OPERATIONAL (real data, pre-DEV live or shadow) | 24 | 004, 008, 009, 010, 012, 013, 014, 015, 018, 019, 020, 021, 023, 024, 026, 028, 033, 034, 037, 038, 040, 046, 047, 050 |

"Operational" evidence for RQ-024 rests on primary documents (S1, J1), not
on repository source (Router V2 source is not in the repository). Operational evidence never means real canonical memory or
owner authority; neither exists.

**Proposed maturity changes (not applied):** RQ-003 → PARTIAL (item scope);
RQ-008 → PARTIAL; RQ-009 → PARTIAL (mechanics); RQ-012 → PARTIAL;
RQ-015 → PARTIAL; RQ-016 → RESEARCH; RQ-018 → PARTIAL; RQ-028 → IMPLEMENTED
(scoped); RQ-029 → PARTIAL; RQ-032 → RESEARCH; RQ-033 → PARTIAL;
RQ-038 → PARTIAL; RQ-049 → RESEARCH. **No question is proposed as VALIDATED.**

**Questions with no project evidence:** RQ-002, RQ-005, RQ-006, RQ-025,
RQ-031, RQ-039, RQ-042, RQ-043, RQ-045.
