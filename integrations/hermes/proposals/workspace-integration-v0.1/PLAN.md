# Global Workspace (Slice 10) integration plan (PROPOSAL, nothing enabled)

Reviewed at `main` `96e29fe`. The measurements come from [`test_workspace_effects.py`](test_workspace_effects.py), which
runs the real gateway, governed adapter and Core API with test-only router copies.

## Answer: Reasoning must be validated first

This is a code dependency, not a preference:

- **Workspace has no entry of its own.** The gateway only builds a snapshot inside the Reasoning, Planning or Ethics
  lanes, after that lane's detector matches. With `workspace_enabled: true` alone it never runs (measured).
- **Workspace live has no effect without Reasoning live.** Its only use is to bound the input to `run_reasoning`, which
  runs only when `reasoning_is_live`.

So the order is Reasoning shadow (PR #288), then Workspace shadow as a separate release. Nothing requires combining them,
and **they should not be combined**: Reasoning shadow is write-free, and Workspace shadow is not.

## Measured effects

| Router flags (test-only) | Turn | Core API reads | Schema change | Records |
|---|---|---|---|---|
| Workspace shadow only | analytic | 0 | none | no workspace record |
| Reasoning shadow only | analytic | 0 | none | reasoning |
| Reasoning + Workspace shadow | analytic, naming an application | **5**: `/os/goals?limit=200`, `/os/goals/focus`, `/os/drafts?limit=200`, `/os/tasks?limit=200`, `/os/world?…entity_id=14` | **creates `drafts` and its indexes** | reasoning, workspace |
| Reasoning + Workspace shadow | social | 0 | none | no workspace record |
| Reasoning + Workspace shadow | goal question | 0 | none | no workspace record |

The World Model shadow record also fires when the message names an application. That is unchanged behaviour.

**So "shadow" is not side-effect-free for Workspace.** The model is not called and the reply is unchanged, but it makes
real reads, and those reads can write:

## Blockers

| # | Blocker | Why | Smallest resolution |
|---|---|---|---|
| 1 | **`GET /os/drafts` runs DDL** | `_drafts_db()` runs `CREATE TABLE IF NOT EXISTS`; the table is absent on DEV, so the first analytic turn changes the schema | A `drafts` schema bootstrap gate, as G-S did for goals, plus a verifier rule refusing start without the table |
| 2 | **`GET /os/goals/focus` can write** | A trace row whenever the winner changes. None on an empty store (proven); one with goals | Accept and document it, as for Goals live. Goal rows stay out of FORGET until P-2 |
| 3 | **Reasoning shadow not yet validated on DEV** | PR #288 is not merged or installed | Merge, install and run a shadow window first |
| 4 | **Detector precision** | Workspace runs on every Reasoning match, and casual text matches ("what next on the playlist"). Each match costs up to 5 reads | Use the Reasoning shadow records to size this; tighten the detector first if it is high |
| 5 | **Trace metadata** | The workspace trace holds candidate ids, which can include goal ids and application numbers. No message text (tested) | Same treatment as other decision records: 7-day retention, FORGET, counts-only observation. Needs owner acceptance |
| 6 | **Verifier** | `SHADOW_LANES` would need Workspace; `workspace_capacity` is already an allowed key | A new release, as for r1 |

**Not blockers:**
- `workspace.py` is already in the assembled DEV tree, and has no I/O of its own.
- All five reads are already on the adapter's GET allowlist.
- No new provider exposure in shadow: no model call. Live would change the Reasoning prompt, not add a call.
- Motivation stays off; Workspace does not need it.

## Proposed sequence

1. Merge and install r1; run one Reasoning shadow window; review detector records. The test turns can use the 3 open
   budget requests or the known refusal path, which needs a decision.
2. `drafts` schema bootstrap gate, as G-S, with a new DB reference.
3. Release `…-r1-w1`: Workspace shadow beside Reasoning shadow, with a verifier schema rule for `drafts`.
4. Workspace shadow window with an empty store.
5. Populated synthetic check, reusing the G3 goals, to see a real snapshot.
6. Workspace live only together with a Reasoning live decision.

## Offline validation criteria for the Workspace release

- **Release definition:** exactly three member changes against r1; the verifier changes only the lane policy; the router
  sets only `workspace_enabled` and `workspace_mode: shadow`.
- **Verifier:** refuses live, a missing mode, a wrong channel, an unknown key, and a missing or mismatched `drafts` schema.
- **Behaviour, on the real gateway, adapter and Core API:**
  - an analytic turn reads only the five allowlisted routes, stays within the per-turn read bound, writes 0, and leaves
    the reply path `None`;
  - on the bootstrapped schema: no schema change, no row change, byte-identical DB on an empty store;
  - social, goal, pending and draft turns: 0 reads and no workspace record;
  - a Core API outage or malformed response fails open, with the turn identical to r1;
  - a hung Core API costs one read until the breaker cools down.
- **Privacy:** no message text in any record; candidate ids only; other platforms not observed.
- **Installer:** the same simulation set as r1, including FORGET races, automatic revert and revert to r1.

## Not done here

No release, no flag, no `drafts` bootstrap script. This is a plan and a measurement only.
