# p1: Planning shadow (CANDIDATE, NOT INSTALLED)

`f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1`: the m1 release with Slice 12 Planning also in shadow on `lilith_os`. **Nothing here has run on DEV.**

## What changes

| Member | Change |
|---|---|
| `RELEASE_ID` | new |
| `home/router.yaml` | `planning_enabled: true`, `planning_mode: shadow` |
| `bin/verify_release.py` | Planning added to the shadow lanes; `planning.py` and the new adapter pinned |
| `lilith_router/planning.py` | counts-only trace, from `overlays/dev-planning-hardening` |
| `lilith_router/world_context.py` | from `overlays/dev-cognition-private-intent` |

## Behaviour in shadow, measured on the real gateway, adapter and Core API

| Property | Result |
|---|---|
| When it runs | a plan verb on a named piece of work, not negated or quoted. Casual plans make no read and no record |
| Core API | 6 GETs on a work plan, each route once. The m1 analytic turn falls from 8 reads to 5, because every lane shares the read memo |
| Writes | none on an empty store. The verifier still refuses any goal row |
| Provider | none. No model call |
| Reply | unchanged |
| Record | one `planning` record: counts and types. No message text, goal id, application number or stable plan id |
| Other lanes | same records as m1 on the four m1 turns. **New:** no record carries the application number |
| Outage | fails open; a failed read isn't kept |

**Startup verifier:** refuses Planning off, live or absent, a changed `planning.py` or adapter, any later lane on, a missing schema, or any goal row.

**Privacy and FORGET:** no new store, and no change to FORGET. Records go to the decision log, under 7-day retention and the full FORGET purge of `logs/`. The plan is ephemeral. The read memo holds Core API text in gateway memory for at most 1.5 seconds, and FORGET stops the gateway.

**Rollback:** `install_p1.sh revert` to m1: router, verifier, adapter and `planning.py`.

## Limits

- **Empty stores give thin plans.** A DEV window proves plumbing, not plan quality.
- **A goal added while running** would write a focus trace on a planning turn. The record stays private, and the verifier only checks at start.
- **The Core API access log still names the application** in the read path.
- **Detector scores come from one author's corpus.** See the `dev-planning-hardening` README, with its two known misses.
- **Planning Live, and the model candidate path,** are out of scope.

## Evidence

| Check | Result |
|---|---|
| `test_p1_planning.py`, `test_p1_release.py`, `test_p1_installer.py` | 26 run: 24 pass, 2 Linux-only skipped |
| `sim_install_p1.sh`, real installers and verifiers, chained f9c2 to m1 to p1 | 36/36, including a refused goal row, FORGET races, revert failures, and return to w1 |
