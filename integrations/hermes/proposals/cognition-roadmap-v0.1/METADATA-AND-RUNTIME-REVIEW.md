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

| Store | Retention | FORGET | Gap |
|---|---|---|---|
| Decision log | 7 days | purged | none |
| Sessions, request dumps | 7 days after the session ends; dumps go with their session | covered | a dump's age alone does not remove it |
| `goal`, `goal_trace` | **none** | **none** | candidate in `goal-forget-v0.1` |
| `tasks`, `drafts` | **none** | **none** | candidate added; tasks need an owner decision on age |
| `world_belief*` | **none** | **none** | not yet analysed; holds owner facts on PROD |
| Backups | manual | **none** | restore gate candidate; both DEV backups hold 0 rows |

## Runtime hardening

| Item | State | Proposal |
|---|---|---|
| DB mode 0644 | any local user can read it | 0600 and `UMask=0077` |
| Core API on `0.0.0.0:8765` | reachable through IAP | bind to `127.0.0.1` at stage 6 |
| GETs that create schema or write traces | `_drafts_db()` runs DDL; a focus read writes | read-only paths for reads; the verifier's empty-store rule is a stopgap |
| Adapter read budget | per entry, not per turn | one budget per turn |
| Write auth | open on DEV and PROD | #289 and the staged plan |

**Not reviewed:** PROD runtime state, which needs its own read-only approval, and live systemd sandboxing.
