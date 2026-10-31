# DEV auth window, 2026-10-31: stopped at B1, recovered

**Result: not complete.** #306, with #289 inside it, merged as `75ca0db`, and its one DEV deployment passed. Enforcement never started.

| Step | Result |
|---|---|
| A0 real preflight, A1 drop-in | PASS |
| Merge, DEV deployment | PASS, `DEPLOY_REQUIRED`, health passed |
| B0 merged code running | PASS |
| B1 tokens | **FAIL:** tokens correct, but its line-count check used a redirect the unprivileged shell can't open |
| RB | **PASS, 12 seconds:** the previous release restored, with database, budget, ledger and e1 unchanged |

**First real recovery on any host.** It reached the previous release, not a failure-free path. It doesn't prove enforcement, the router under enforcement, or the forward step.

**State left:** Core API on `d82f7dac`, open as before; `75ca0db` installed beside it; main holds #306. **DEV runs older code than main until the resume runs.** The simulation runs as root, so it couldn't see this defect; static checks now cover that class.
