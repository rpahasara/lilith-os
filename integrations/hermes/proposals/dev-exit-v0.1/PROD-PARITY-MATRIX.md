# PROD parity matrix (PROPOSAL, offline)

Serves A4 and A7. For every capability PROD has, it says what the first migration would do with it: **PRESERVE**, **DISABLE** on purpose, or **VALIDATE** because the evidence doesn't yet decide it. **Nothing is waived:** each DISABLE needs the owner's signature, and any row still on VALIDATE blocks cutover.

**Proposals only:** the actions below are proposed. Merging this document signs none of them.

**Evidence:** the read-only PROD audit of 2026-10-27 (`PROD-FEATURE-MATRIX.md`, `PROD-COGNITION-MAP.md`, `PROD-DATA-INVENTORY.md`, `PROD-PRESERVATION-RISKS.md`), recovered PROD source in `integrations/hermes/history/prod/`, and DEV as of the e1 run on 2026-10-31. PROD wasn't accessed for this. **Its facts are four days old and must be re-read in the rehearsal.**

**Counts:** 42 rows: 18 PRESERVE, 8 DISABLE and 17 VALIDATE. L18 counts twice, because its rows are preserved while its lane is undecided.

## Conversation and identity

| Capability | PROD | DEV today | Action | What decides it |
|---|---|---|---|---|
| Persona, `SOUL.md` | live, `d082db5a...` | DEV's own, not compared | **VALIDATE** | A8: byte-identical file on the copy, then the fixed prompt set |
| User profile, `USER.md` | live, `6d7804ef...`, Hermes-owned | absent, Hermes memory denied | **VALIDATE** | Is it migrated as is, or does it stay runtime-only? Competes with L04 |
| Conversation history, `state.db` | 35 MB, never read | DEV's own | **PRESERVE** | Row-exact copy. Reading it needs its own Privacy decision |
| Session index | 32 sessions | DEV's own | **PRESERVE** | |
| Router V2 social/technical split | live | present | **VALIDATE** | Never exercised on DEV with a model: A3 |
| Social response guard | live | present, unproven with a reply | **VALIDATE** | A3 |
| Groq and `gpt-5.6-sol` routing, with fallback | live | single provider gate, budget 5 | **VALIDATE** | Which providers PROD keeps, under what budget |
| `lilith_os` channel | live | live | **PRESERVE** | |
| Telegram | live, with cognition | absent | **VALIDATE** | All DEV lanes are `lilith_os` only, so any move here is new behaviour |
| Discord | one channel, social only | absent | **VALIDATE** | Same, and it stays outside cognition |
| WhatsApp | broken since 09-12 | absent | **DISABLE** | Named loss, no working behaviour to lose. Repair stays a separate owner task |

## Cognition (the A4 table)

| Lane | PROD | DEV | Action | Loss if accepted |
|---|---|---|---|---|
| World Model | live on `lilith_os`, Telegram | shadow | **PRESERVE** live, after A3 | |
| Working Memory | per turn | per turn | **PRESERVE** | |
| Goals, reads | live | shadow | **PRESERVE** live, after A3 | |
| Goals, creation by conversation | live | Goals Live proven once, on one synthetic goal | **DISABLE** until A14 to A16 | Conversation can't create a goal |
| Reasoning | live | shadow | **PRESERVE** live, after A3 | |
| Workspace | live | shadow | **PRESERVE** live, with Reasoning | |
| Motivation | live | shadow | **DISABLE** live, keep shadow | A weak input to Workspace, never shown useful |
| Planning | live, can replace the reply | shadow | **DISABLE** live, keep shadow | Planning stops answering directly |
| Ethics | live, advisory | shadow, e1 | **DISABLE** live, keep shadow | Ethics stops answering directly. Its third-party and privacy concerns were being dropped anyway |
| Social Cognition | shadow | off | **VALIDATE** | No DEV release carries it |
| Memory Consolidation (L18) | shadow, 3 candidates | off | **PRESERVE** the rows, lane **VALIDATE** | |
| Canonical memory (L04) | installed, 0 rows, off | live with owner authority | **VALIDATE** | The audit's rule: don't enable on PROD without DEV's authority chain. A12 |
| Legacy containment wrapper | live | present | **PRESERVE** | |

**The detector change is itself a behaviour change.** Hardened detectors fire far less than PROD's, so even a "preserved" live lane runs less often. Only a model window measures what that does.

## Data

| Store | PROD, 2026-10-27 | Action | Check |
|---|---|---|---|
| World Model | 31 beliefs, 93 evidence, 93 trace, cursor 17 | **PRESERVE** | Row digests, cursor unchanged |
| Goals | 3 goals, 11 traces | **PRESERVE** | Focus stays the ACTIVE goal; trace count unchanged with `LILITH_OS_FOCUS_READ_ONLY=1` |
| Tasks, drafts | 7 and 10 | **PRESERVE** | Row digests |
| Career CRM | 8 applications, 7 companies, 9 people, 11 activities, 11 events | **PRESERVE** | FORGET's scope for these is an open owner decision |
| `cognitive_memory.db` | L04 0, L18 3 | **PRESERVE** | |
| `privacy_governance.db` | V1 config, 0 requests | **VALIDATE** | V1 doesn't cover `state.db` or `USER.md`, and DEV's F9-C is a different authority. Which owns PROD? |
| Decision log | 213 lines | **PRESERVE** | The only trace of live lanes. It has no retention purge on PROD |
| Authority keys | 3 × 32 B | **PRESERVE** | Never regenerate |
| Credentials | `.env`, `auth.json`, provider and channel tokens | **PRESERVE** | Never copied into a rehearsal unmasked |

## Automation and connectors

| Capability | PROD | DEV | Action | What decides it |
|---|---|---|---|---|
| Career and Gmail watchers | timers fire, data dead: OAuth `invalid_grant` since 08-31 | absent | **VALIDATE** | Owner repairs OAuth, or accepts the loss (A15). Repair needs tombstones first: a watcher can re-deliver erased items |
| Agenda, morning brief | degraded: sent with an error | absent | **VALIDATE** | Same |
| Meeting prep | stale since 08-31 | absent | **DISABLE** | Named loss until OAuth returns |
| Hermes tool authority | full toolsets on Telegram, Discord, WhatsApp, CLI: terminal, file, delegation, code execution, memory | `lilith_os: []`, all denied | **VALIDATE** | **The largest silent change available.** Applying DEV's denial removes tools from those channels. Keeping them keeps a posture the audit flagged. Owner decision |
| Hermes cron, kanban | dormant, 0 tasks | denied | **DISABLE** | Unused |
| Voice | configured, no evidence of use | denied | **DISABLE** | Unused |

## Platform

| Capability | PROD | Target | Action | What decides it |
|---|---|---|---|---|
| Core API | `519b309`, unit binds `0.0.0.0:8765` per recovered source | main plus #289 and #306 | **VALIDATE** | **#306 found `POST /os/conversation` had no owner check.** Recorded firewall allows the IAP range only; re-read it. Don't bind loopback while the tunnel is the route in |
| Command Center relay | path not established by the audit | header required after #306 | **VALIDATE** | Trace it, and send the header before enforcing |
| Backups | one disk, one crash-consistent snapshot, no schedule | scheduled, restorable | **VALIDATE** | First PROD change, before any code |

## Decisions this needs from the owner

1. Sign the DISABLE rows, each a named loss.
2. Hermes tools on Telegram and Discord: keep or remove.
3. Telegram and Discord cognition: carried over, or `lilith_os` only at first.
4. OAuth and WhatsApp: repair or accept the loss.
5. `USER.md`, and which authority owns FORGET on PROD.
