# REPO:RQ-004 — One canonical state across channels (and, eventually, runtimes)

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-004** (in-repo register). MASTER equivalent: MASTER:RQ-002 (SEMANTIC MATCH); related MASTER:RQ-051, 053, 054, 055.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - J1 Entry 11 (PRIMARY) confirms Slice 3: backend-authoritative task history restored after reload and after clearing localStorage, and surviving backend restart.
> - MASTER:RQ-002 records the same task-store revisioning as its "existing foundation"; Master §07 designs cross-device continuity (TARGET).

## Research question

How can one identity operate across Hermes, local, and cloud runtimes?
(In-repo RQ-004; related RQ-005, RQ-007, RQ-024.)

## Why it matters to LILITH

The user reaches LILITH through several surfaces (Home/Command Center,
Telegram). If each surface held its own state, LILITH would answer
differently, or act twice, depending on where it was asked.

## Original hypothesis / problem

Register hypothesis: runtimes are clients of a canonical state plane using
revisions, operation IDs, and explicit conflicts. [ADR-0002](../../adr/0002-canonical-durable-state.md)
accepted a canonical authority for durable task and identity state.

## Architecture explored

- Backend-authoritative stores on the VM: tasks (Slice 3), drafts (Slice 4),
  World Model (Slice 7), goals (Slice 8).
- A single conversation seam: Home and Telegram converge at the Hermes
  `run_sync` → Router V2 seam, where the cognitive lanes (7.2–13) run.
  Router V2 source itself is **not** in this repository (REPORTED).

## Experiments / implementation slices

- Slice 3: backend task store authoritative over browser cache (PRIMARY,
  J1 Entry 11; frontend client OBSERVED).
- Slice 7.2 (REPORTED): World-Model-first lane shared by Home and Telegram.
- Slices 8–13: each deployment record includes a Home/Telegram parity check.

## Evidence

- OPERATIONAL (pre-DEV live, route-level): identical goal grounding (Slice 8),
  identical reasoning input core (Slice 9), identical workspace selection with
  `PARITY_OK: True` (Slice 10), identical motivation snapshot (Slice 11),
  identical `PlanSnapshot` (Slice 12), identical content-seeded
  `ethicalSnapshotId` (Slice 13). See the
  [slice records](../slice-history.md#per-slice-records).
- Telegram live end-to-end acceptance for 7.2 is REPORTED (user-confirmed).

## Negative findings / failures

- N-12: parity was computed **in-process** at route or lane level; "no real
  Telegram message sent" in Slices 10–13. It is not end-to-end transport
  parity.
- Only one runtime (Hermes) exists. Channel parity is not runtime independence.
- Discord is explicitly excluded from the cognitive channels.

## Current answer

- **PROVEN (pre-DEV live, route level):** two channels that converge at one
  Router seam produce identical grounding from one backend state for the
  tested scenarios.
- **DESIGNED:** runtimes as clients of canonical state (ADR-0002).
- **INFERRED:** current evidence supports "one seam, many channels" as a
  practical way to avoid split state; it says nothing about coordinating two
  independent runtimes.
- **UNKNOWN:** leader/lease needs (RQ-005), offline behaviour (RQ-006),
  cross-model normalization (RQ-007).

## Confidence / maturity

Medium for channels; none for multiple runtimes.

## What remains unanswered

A second conforming runtime; partition and overlapping-claim simulations;
whether routing between conversational and specialist models preserves one
governed identity (see the *cognitive substrate continuity* candidate in the
RQ candidates record).

## Related RQs

RQ-005, RQ-006, RQ-007, RQ-024, RQ-001.

## Related slices

Slices 3, 7.2, 8–13; ADR-0002.

## Publication notes

Suitable for an **engineering blog** on "put every channel behind one
cognitive seam" with the explicit caveat that parity was route-level and the
seam's source is outside the public repository.
