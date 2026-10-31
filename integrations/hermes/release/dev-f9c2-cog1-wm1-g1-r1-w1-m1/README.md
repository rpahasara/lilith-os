# m1: Motivation shadow (CANDIDATE, NOT INSTALLED)

`f293e72-f9c2-cog1-wm1-g1-r1-w1-m1`: the w1 release with Slice 11 Motivation also in shadow on `lilith_os`. **No sealed host package exists yet, and nothing here has run on DEV.**

## What changes

| Member | Change |
|---|---|
| `RELEASE_ID` | new |
| `home/router.yaml` | `motivation_enabled: true`, `motivation_mode: shadow` |
| `bin/verify_release.py` | Motivation added to the shadow lanes; `motivation.py` pinned |
| `lilith_router/motivation.py` | counts-only trace, from `overlays/dev-motivation-private-trace` |

The only code change is two trace lines. The base module is `docs/architecture/slice-11/motivation.py`, byte-identical to DEV's `f95d4f56...`, checked 2026-10-30.

## Behaviour in shadow, measured on the real gateway, adapter and Core API

| Property | Result |
|---|---|
| When it runs | only inside a Workspace turn, so only after a Reasoning match |
| Core API | 3 more GETs: 8 per matching turn, against 5 on w1 |
| Writes | none on an empty store |
| Provider | none. `motivation.py` imports only stdlib; no model call |
| Reply | unchanged. Candidates do not enter the Workspace pool in shadow |
| Record | one `motivation` record before `workspace`: drive classes, fixed cause codes and counts. No goal id, task id or condition text, even for a blocked goal |
| Outage | fails open |

**Dependencies:** Workspace, for the candidates and the turn; Goals and Tasks through read routes; World Model only through Workspace candidates. It does not use Planning.

**Startup verifier:** refuses Motivation off, live or absent, a changed `motivation.py`, any later lane on, a missing schema, or any goal row.

**Privacy and FORGET:** records go to the decision log, under 7-day retention and the full FORGET purge of `logs/`. No new store and no change to FORGET. The snapshot is ephemeral.

**Rollback:** `install_m1.sh revert` to w1: router, verifier and `motivation.py`.

## Limits and blockers

- **Populated stores fail closed at start only.** The install refuses a goal row and the verifier refuses to start. A goal added later would still write a focus trace, though the record stays counts-only.
- **A focus read writes a trace when a goal exists.** Motivation adds a second focus read per turn, but a test shows one trace. Same empty-store rule.
- **Empty stores give empty results.** Both drives read `SATISFIED`, so a DEV window proves plumbing, not drive quality.
- **Depends on w1 acceptance.** Build the host package only after the owner accepts w1.

## Evidence

| Check | Result |
|---|---|
| `test_m1_motivation.py`, `test_m1_release.py`, `test_m1_installer.py` | 25 run: 23 pass, 2 Linux-only skipped |
| `sim_install_m1.sh`, real installers and verifiers, chained f9c2 to w1 to m1 | 36/36, including a refused goal row, FORGET races, revert failures, and return to r1 |
| `dev-motivation-private-trace` tests | 3/3 |

## Planned DEV test, not built

The w1 method: stop the gate for four `TEST_ONLY` turns. Expected: T1 and T2 add a `motivation` record ahead of `workspace` and read 8 routes each, 16 in total; T3 and T4 unchanged. No provider request and no budget change.
