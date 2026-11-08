# 07. Autonomous goals, initiative, planning and verified outcome learning

Topic 7.

**Design anchors.**
- **Goal Commitment & Intention Continuity contract (GC):**
  - goal ≠ commitment ≠ intention (GC-03..08);
  - a commitment is not permission (GC-15);
  - completion needs proof (GC-21), and there is no revival or retroactive undo (GC-24);
  - self-directed goals are research (GC-25) under a bounded policy (GC-26);
  - initiative is separately gated (GC-45).
- **Initiative, Interruption & Autonomous Action contract (IA):**
  - triggers are evidence (IA-06);
  - interruptions need eligibility (IA-13) and respect quiet hours and focus (IA-14);
  - relationships cannot confer contact rights (IA-20), and affect and personality are non-authoritative (IA-21);
  - budgets constrain and never authorize (IA-23);
  - cooldowns (IA-24) and disengagement fencing (IA-25);
  - no hidden schedulers (IA-37).
- **Learning, Skill Acquisition & Competence contract (LS):**
  - no silent promotion (LS-16) and clean evaluation (LS-17);
  - learning does not rewrite personality (LS-21);
  - affect cannot grade (LS-23), and tool knowledge is not permission (LS-25).

## 1. Commitments: the missing middle between conversation and goals

LILITH makes promises in conversation ("I'll remind you to send it tomorrow") that live only in transcript text.

| Component | Responsibility | Reuses | Persistence |
| --- | --- | --- | --- |
| Commitment proposer | Detect an explicit promise or request ("remind me", "check on", "follow up") and propose a `CommitmentRecord` (who, what, when, completion condition) | cognitive lane draft path (Slice 7.2 durable drafts), Goals lane create flow | proposal → owner-visible list |
| Commitment store | Due dates, status, completion proof | goal store / FSM (Slice 8) as a typed child | Core API |
| Due-check | Deterministic scan at turn start (and later on a timer) | goal grounding | none |

**Cost.** Detection is deterministic for explicit forms; ambiguous forms are left to the existing agent call. Zero
extra calls.

**Experiment.** E-7 (commitment recall: was a promised follow-up honoured or acknowledged within its window?).

## 2. Initiative: proposal-first, owner-gated

The first initiative is the smallest that proves value: **one bounded check-in channel**, the owner's Telegram DM.

1. Triggers are evidence:
   - a commitment due;
   - a goal deadline approaching or passed;
   - a calendar event (after OAuth recovery) or meeting prep (existing job).
2. An eligibility gate covers quiet hours, a daily cap of 1–2, a cooldown, and an immediate stop on "not now"
   (IA-13/14/24/25).
3. The message is composed by the normal reply path with `TurnContext`. There is no separate persona.
4. Every initiative is logged with its trigger evidence, which feeds E-9.

**Excluded.**
- Initiative driven by affect, drives or "missing" the owner (AP-25, IA-21).
- Self-created goals (GC-25).
- Any external action beyond sending the message.

**Dependencies.**
- Commitments (§1).
- OAuth for calendar triggers (migration).
- The existing morning brief and meeting-prep jobs are the natural first hosts. They already run on timers, so this is
  an evolution, not new infrastructure.

**Cost.** One agent or lean call per initiative, at most 2 a day.

## 3. Planning with verified outcomes

**Today.** Planning proposes; nothing records whether a plan worked.

**Loop.**
1. A plan step is accepted (existing approval path).
2. Execution happens through existing tools or Core API commands.
3. **L15 read-back** confirms or fails it.
4. An `OutcomeEvent` is written to L18.
5. Replanning is proposed on failure (V1 L10).
6. Consolidation (C-3) adjusts the priority of procedures and approaches that worked.

**Scope limit.** Only for Core API actions that already have read-back (drafts, tasks, goals). Conversational advice
outcomes are recorded only when the owner states them ("that worked", "they rejected me"). The appraisal congruence
signal in [05 §3](05-social-affect.md) reuses those statements.

## 4. Self-directed goals: research only

Kept as the GC-25 research topic. Entry conditions for any future study:
- commitments and initiative have run for weeks with a low owner-veto rate (E-9);
- a bounded autonomous-goal policy has been accepted (GC-26);
- a manipulation and sycophancy review has been done (GC-42).

## 5. Skill and competence learning

**Near term:** procedural "recipes" from repeated successful tool sequences, as *proposals* in the nightly review (LS-15
proposal through read-back).
- Context-specific competence claims only (LS-12).
- Regressions remain visible (LS-34).

**No autonomous self-modification of prompts or tools** (LS-29, PE-11).
