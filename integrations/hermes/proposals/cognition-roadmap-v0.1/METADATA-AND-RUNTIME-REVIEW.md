# Metadata and runtime review (PROPOSAL, nothing changed)

Findings from reading the merged source and measuring lanes offline, 2026-10-30. Nothing here is deployed.

## What the decision log can hold

Under 7-day retention and the full FORGET purge of `logs/`. No record holds message text.

| Lane | Identifying fields | State |
|---|---|---|
| All | `chat_id`, timing, message length | Accepted metadata |
| Workspace | none: counts only since w1 | Fixed |
| Reasoning, cognitive | `intent.app_id` | Links a record to an application number |
| Goal | `intent.app_id` | Same |
| Motivation (off on DEV) | `per_drive[].relatedGoalIds`, `resolutionConditions` once a goal is blocked | **Must fix before goal rows are allowed** |
| Planning (off on DEV) | `trace.goal_ref`, `subject_target`, `intent.app_id`, stable `plan_snapshot_id` | **Must fix before Planning shadow** |

**Decision needed:** whether `app_id` stays. It helps debugging, and it ties a record to one application for 7 days.

## Retention and FORGET coverage

**The deployed FORGET executor covers `state.db` and listed Hermes directories. It does not open the Core API database at all.** Read from `release/dev-f9c2/bin/hermes_forget_executor.py`.

| Store | Holds | Retention | FORGET | Candidate |
|---|---|---|---|---|
| Decision log | metadata | 7 days | purged | none needed |
| Sessions, request dumps | conversation; content-free dumps | 7 days after the session ends | purged | none needed |
| `goal`, `goal_trace` | titles, reasons, provenance | **none** | **none** | erase, prune terminal |
| `tasks` | titles, records | **none** | **none** | erase; age needs a decision |
| `drafts` | subjects, bodies | **none** | **none** | erase, prune discarded |
| `world_belief`, evidence, conflict, trace | facts about the owner, with sources | **none** | **none** | erase, prune superseded evidence |
| `world_working_seed` | session focus | **none** | **none** | erase |
| `world_ingest_cursor` | a position only | not needed | **must stay** | kept |
| `career_events` (PROD) | the source of beliefs | unknown | **none** | not reviewed |
| Backups | whole DB copies | manual | **none** | restore gate; both DEV backups hold 0 rows |

**Rebuild risk:** beliefs are derived from `career_events` through a cursor. Resetting the cursor would rebuild every belief, and leaving `career_events` in place means the source facts survive. **World Model FORGET is not complete until `career_events` has an owner decision.**

**PROD:** the candidate refuses a DB with tables it doesn't know, and `career_events` is one, so it cannot run on PROD as written. That is deliberate.

**Open owner decisions:**
1. Does principal FORGET erase `career_events`, or only what is derived from it?
2. How long do completed tasks stay?
3. Does `app_id` stay in records?

## Runtime hardening

| Item | State | Proposal |
|---|---|---|
| DB mode 0644 | any local user can read it | 0600 and `UMask=0077` |
| Core API on `0.0.0.0:8765` | reachable through IAP | bind to `127.0.0.1` at stage 6 |
| GETs that create schema or write traces | `_drafts_db()` runs DDL; a focus read writes | read-only paths for reads; the verifier's empty-store rule is a stopgap |
| Adapter read budget | per entry, not per turn | one budget per turn |
| Write auth | open on DEV and PROD | #289 and the staged plan |
| Read auth | `GET /os/goals`, `/os/tasks`, `/os/drafts` and `/os/world` need no credential | #289 covers writes only. Extend it after stage 5, since the same routes return owner content |

**Not reviewed:** PROD runtime state, which needs its own read-only approval, and live systemd sandboxing.
