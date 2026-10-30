# Goals security and privacy plan v0.2 (PROPOSAL, nothing deployed or activated)

Builds on [`../goals-hardening-v0.1/REVIEW.md`](../goals-hardening-v0.1/REVIEW.md). Nothing here changes a running service,
FORGET, Privacy, authentication or a permission.

## 1. Authenticated goal writes

**PR #289 alone is not protection.** While `LILITH_OS_GOAL_WRITE_TOKEN` is unset, the routes are as open as before. Treat
the endpoints as unauthenticated until step 4 below is done and verified.

**Why ordering matters:** setting the token before callers send it would break PROD's Goals lane, which posts with no
header. DEV's adapter never posts.

| Step | Change | Effect |
|---|---|---|
| 1 | Merge and deploy #289, with the `a9fc562f` pins moved in the same change | Unchanged: token unset |
| 2 | Teach the PROD lane's `_post_goal_json` to send the header from a root-only credential | Harmless while unset |
| 3 | Provision a token of 32+ characters through the service's credential mechanism, never in `Environment=` text in Git | |
| 4 | Set it on Core API and verify: no header 401, wrong header 401, right header 200 | **Now protected** |
| 5 | Add the same check to `POST /os/tasks` and `POST /os/drafts` | The gap in those routes closes |

**Rollback:** unset the variable and restart Core API.

**Better long-term:** step 4's token is one shared secret. Binding Core API to `127.0.0.1` (it listens on `0.0.0.0:8765`,
reachable through IAP) removes the route for anything off-host, but changes how the IAP path reaches it, so it needs its
own review.

**Conversational goal creation stays disabled** regardless: the adapter refuses it, and P-2 and P-3 are both open.

## 2. FORGET and retention coverage for goal rows

**Owner:** Privacy. This changes policy, so it needs your decision (P-2).

| Data | Retention today | FORGET today | Proposed |
|---|---|---|---|
| `goal` rows | none | none | FORGET: delete all. Retention: delete terminal goals after a fixed period |
| `goal_trace` rows | none | none | Same; delete with the goal. Keep none after FORGET |
| `sqlite_sequence` row for `goal_trace` | none | none | Delete, so no count of past activity remains |

**Sensitive fields:** `title`, `description`, `target_json`, `blocked_reason`, `provenance_json` (`sourceChannel` is the
session key), `goal_trace.reason`, and the arbitration columns.

**Design:**
1. **A separate owner for the Core API DB.** `hermes_forget_executor.py` is scoped to `HERMES_HOME` and `state.db`. It should
   not gain a second database implicitly: add an explicit, allowlisted step with the same fail-closed rule (an unknown
   table refuses).
2. **Deletion:** with `secure_delete=ON`, in one transaction, then `VACUUM`, because freed pages can otherwise keep text.
   This file is not in WAL mode, so there is no WAL to truncate.
3. **Lock:** take the executor's own lock, and refuse while a Core API write is in flight.
4. **Backups:** any copy of this DB, including the root-only G-S and G3 backups, is outside FORGET too. Backups must be removed
   or included. The G-S backup holds no goal rows; a future pre-seed backup would hold none either, by construction.
5. **Verification:** after the delete, `goal` and `goal_trace` have 0 rows and the file holds no marker from a canary row.

**Retention:** active goals must not age out by inactivity. Suggested rule: delete `COMPLETED`, `CANCELLED` and `FAILED`
goals and their traces after 30 days, as the same daily job.

**Tests to write when approved:** canary title gone from the file bytes after FORGET; unknown table refuses; hold blocks;
lock held refuses; idempotent re-run. The G3 cleanup is a working model for the delete, sequence reset and refusal rules.

## 3. Database mode 0644

**State:** a read as `nobody` fails, because `/home/lilith` is 750 and `data/` is 700. The file itself is world-readable, and
the unit has `UMask=0022`.

**Plan:**
1. `scripts/bootstrap_core_api_dev.sh`: add `UMask=0077` to the unit. That file is a deployment script, so the change
   is `DEPLOY_REQUIRED`, and it is deliberately not in this PR.
2. In the next gated window: `chmod 0600` the live DB.
3. Add a mode check to the standard preflights.

**Verify afterwards:** Core API reads and writes as `lilith`; `chmod` leaves the logical digest unchanged; root-run checks are
unaffected. **Rollback:** `chmod 0644`.

**Note:** the `-journal` file SQLite creates during a write inherits the DB's mode, so it needs no separate rule.

## Open decisions

| Decision | Needed before |
|---|---|
| P-2: FORGET and retention scope above | any real goal |
| P-3: authentication order above | any conversational goal creation |
| Adopt `dev-goals-hardening` | Goals live beyond synthetic data |
