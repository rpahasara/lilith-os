# Cutover 2: the seven-lane architecture on PROD (PROPOSAL, nothing approved)

**Cutover 1 isn't the end of the migration.** Its purpose is a protected, recoverable PROD. **Cutover 2 is the objective:** the modern seven-lane work from DEV on the existing LILITH, with her identity and capabilities intact. It starts straight after Cutover 1 validates.

## Owner conditions, 2026-10-31

The preserve-first plan and R-13 are accepted as a bounded, temporary deferral:

| Condition | Effect |
|---|---|
| Cutover 1 preserves all cognition, identity, memories, goals, tasks, drafts, integrations and functioning capabilities | No PROD data is overwritten |
| R-13 holds only while no new real owner-data capture and no OAuth reactivation occurs | **Either one ends the deferral:** FORGET must come first |
| FORGET's limits stay explicit | Any required erasure is handled correctly, and never claimed complete |
| Cutover 1 isn't completion | This document |

**Today's limit, stated:** PROD can't honour an erasure across Core API, `state.db` or `USER.md`. If one is needed before FORGET is wired, it goes to the owner as a manual, recorded procedure on that request's scope, and snapshots still hold the data.

## Correction to `MIGRATION-PLAN.md`

That plan says lanes are promoted "one at a time". **That isn't possible as built:** the hardened detectors for every lane live in one adapter file. Per-lane flags can only turn a lane off, which is the downgrade the owner ruled out. So Cutover 2 is **one package in one window,** with every lane staying live.

## What changes on PROD

Seven files in `lilith_router`, and nothing else. The rollback is these same files.

| File | PROD | Target | Change |
|---|---|---|---|
| `world_context.py` | `46b8187e` | `f1ee561d` | hardened detection, bounded reads |
| `_prod_world_context.py` | absent | `46b8187e` | **PROD's own file, byte for byte,** which the adapter wraps |
| `gateway_integration.py` | `aef31314` | `5ce4bbd4` | decision records stop holding a 60-character message preview |
| `ethics.py` | `b6e3ce49` | `d6a1c20b` | suppression fixes. **Changes advice:** concerns that never appeared will |
| `planning.py` | `e74f7f7e` | `4c74337d` | counts-only trace |
| `motivation.py`, `workspace.py` | `f95d4f56`, `e209440f` | `fd6c1189`, `d79f67e1` | counts-only traces |

**Stays exactly as it is:** `router.yaml` with every lane `live`, its channels and providers; Social Cognition and L18 in shadow; `SOUL.md`, `USER.md`, `state.db`, every database; Hermes; plugins; `canonical_ltm_enabled: false`. **No DEV router, no DEV database and no DEV release directory go to PROD.**

`reasoning.py` and `ethics_principles.py` do not change.

## What isn't proven yet

| Gap | Why it matters | Closes with |
|---|---|---|
| **Hardened adapter in live mode.** e1 proved shadow | Live lanes change the reply | Test 2 |
| PROD's `router.yaml` with these files | Social Cognition, L18 and Telegram have never run beside the adapter: DEV carries none of them | Test 1 |
| Lower match rate | Lanes fire far less than on PROD today, so some replies lose analysis. **It's the intended fix, and still a behaviour change** | Test 2, Test 3 |
| Two intents in one message | The first wins, and the second goes unanswered | Decision below |

## Tests, reusing what exists

| # | Test | Size | Needs |
|---|---|---|---|
| 1 | Seven-lane suite on an assembled home with PROD's router: lanes live, Social and L18 shadow, Telegram in channels | offline, a variant of `test_seven_lanes.py` | nothing |
| 2 | DEV Live window, synthetic store: lanes live on `lilith_os` | about 10 model requests, one turn per class | **a budget reset, owner-approved,** and a live router release on DEV |
| 3 | On the rehearsal copy: the identity prompts with these files, against the Cutover 1 baseline | the fixed 12 prompts | Privacy decision, separate budget |
| 4 | Rollback: restore the seven files, restart, compare | on the copy, timed | none extra |

## Sequence

1. Cutover 1 validated, and its 48-hour return window closed.
2. Test 1, offline. Can start before that.
3. Test 2 on DEV.
4. Package: the files above, sealed, pinned to PROD's hashes, refusing to run if any differ.
5. Tests 3 and 4 on a fresh copy.
6. Owner authorizes, with signed acceptance.
7. Window: snapshot, stop gateway, swap files, verifier, start, acceptance.
8. Then advanced development, DEV-first.

**Pass:** the identity prompts judged the same by the owner, no row changed by the swap, every lane still live, each capability row passing, and a measured drop in casual messages reaching a lane.

**Not required for Cutover 2:** owner-memory authority, L04, broker, signer, a Hermes upgrade, FORGET beyond R-13's terms, or any new lane.

## Owner decisions, when it's reached

| Decision | Recommendation |
|---|---|
| Budget for Test 2 | about 10 requests |
| Accept that Ethics starts raising concerns it never could | Yes: that's the fix |
| Two intents: accept first-wins for now | Yes, with a post-cutover task |
