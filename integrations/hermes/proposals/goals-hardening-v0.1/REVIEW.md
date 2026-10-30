# Goals security and detector review (PROPOSAL, nothing wired or deployed)

Reviewed at `main` `96e29fe`, plus one read-only metadata check on DEV (2026-10-30). Nothing in this folder changes a
release, a service, FORGET or a permission. Every fix below needs its own owner approval.

| # | Issue | Severity today | Smallest correction | State |
|---|---|---|---|---|
| 1 | Over-eager Goals detection | Medium for live, low in shadow | Tighten two regular expressions | Candidate here, not wired |
| 2 | Needless career-data read | Low | One line in the governed adapter | Patch here, not applied |
| 3 | Unauthenticated goal writes | Medium; contained on DEV | Opt-in caller token | PR #289, needs a deploy decision |
| 4 | Goal rows outside retention and FORGET | None while the store is empty; **blocks real goals** | Add the goal store to Privacy's scope | Design only; owner decision P-2 |
| 5 | DB file mode 0644 | Low: not reachable by other users | `UMask=0077` plus a gated `chmod` | Plan only |

## 1. Over-eager Goals intent detection

**Cause:** `_GOAL_QUERY_RE` matches the bare word `goal`, and `_GOAL_CREATE_RE` matches a verb such as `make` or `start`
within 40 characters of `goal`, anywhere in the text.

**Effect in live mode:** "that was a great goal by the striker" sends the goal policy, and every goal title in the store,
to the provider. "he could make a great goal from there" is treated as a create request.

**Measured** by [`test_goals_hardening.py`](test_goals_hardening.py):

| Detector | Queries | Creates | False matches (12 unrelated messages) | False creates |
|---|---|---|---|---|
| Deployed PROD | 15/15 | 7/7 | **9** | 2 |
| [Candidate](goal_detector_candidate.py) | 15/15 | 7/7 | 0 | 0 |

**Limit:** this corpus is small, and the candidate was written against it, so 0 is not an expected real-world rate. Shadow
records from real use are the better measure.

**Deployment path:** the PROD module is byte-pinned, so the candidate would live in the governed adapter as an override,
which needs a new adapter hash and a new release. Do this **before** any real goal exists under Goals live.

## 2. Unnecessary career-data read

**Cause:** on a create turn, `create_tracking_goal` calls `_goal_title_for`, which reads all of `/career/applications`,
then posts. The DEV adapter refuses the post, so the read has no use.

**Effect:** one wasted read per create turn. The data does not reach the prompt. On DEV the route currently fails because
the career tables are absent.

**Fix:** [`adapter_career_read.patch`](adapter_career_read.patch) replaces `_goal_title_for` in the adapter's I/O seam. The
test shows reads fall from three to the two goal routes, with the same prompt text. It changes the adapter hash, so it
should ship in the same release as item 1.

## 3. Unauthenticated goal creation endpoints

**Facts:**
- `POST /os/goals`, `/transition` and `/link_task` have no caller check.
- Core API listens on `0.0.0.0:8765`. The earlier exposure check found it reachable only through IAP, by accounts that
  are already administrators.
- The DEV adapter never posts, so conversation cannot create a goal. Any local process could.

**Fix:** PR #289 adds an opt-in token. Unset, behaviour is identical. It is `DEPLOY_REQUIRED`, because it changes `app.py`.

**Not covered:** `POST /os/tasks` and `POST /os/drafts` have the same gap. PROD's Goals lane must learn to send the token
before the token is set there.

## 4. Goal-data retention and FORGET coverage

**Facts:** the FORGET executor has no reference to the goal store, and the 7-day retention covers Hermes sessions and logs
only. Goal titles, descriptions, targets and `provenance_json` (which holds the session key as `sourceChannel`), plus
`goal_trace`, are outside both.

**Containment today:** 0 rows, and no conversation path can create one.

**Smallest design, for the Privacy owner:**
1. Treat `goal` and `goal_trace` as FORGET targets: on a whole-store FORGET, delete both, with `secure_delete` on.
2. Decide what retention means for goals. Active goals should not age out by inactivity, so the likely rule is to purge
   terminal goals and traces after a fixed period.
3. Add both tables to the FORGET verification, so an unknown table fails closed.

**Not implemented:** this changes Privacy policy. Until decided, keep goal creation disabled and use only synthetic rows
that have an approved cleanup.

## 5. Database permission mode 0644

**Read-only result on DEV:**

| Path | Owner | Mode |
|---|---|---|
| `/home/lilith` | `lilith:lilith` | 750 |
| `/home/lilith/.hermes` | `root:root` | 755 |
| `/home/lilith/.hermes/lilith-os-dev` | `lilith:lilith` | 700 |
| `.../data` | `lilith:lilith` | 700 |
| `.../data/lilith-dev.db` | `lilith:lilith` | 644 |

The Core API unit has `UMask=0022`, no `ProtectHome` and no `ProtectSystem`. A read test as `nobody` failed: the parent
directories block traversal. So **the mode is not reachable by other local users today**; the protection comes from the
directories, not the file.

**Fix, as defence in depth:**
1. Add `UMask=0077` to the unit in `scripts/bootstrap_core_api_dev.sh`, so a recreated file is private.
2. A gated `chmod 0600` on the live DB, with the Core API checked afterwards.

**Note:** `chmod` changes file metadata only, so the logical digest stays the same. Both steps change DEV runtime security
settings, so they wait for approval.

## Recommended order

1. Decide P-2 and P-3 before any real goal.
2. Ship items 1 and 2 together in one adapter release, in shadow first.
3. Plan the `app.py` deploy for item 3, with the `a9fc562f` pins moved in the same step.
4. Item 5 whenever a gated window is next open.
