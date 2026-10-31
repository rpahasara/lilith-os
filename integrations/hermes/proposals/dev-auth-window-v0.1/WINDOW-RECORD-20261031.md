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

## First resume, 2026-10-31 16:17Z

**Result: not complete, with enforcement proven on the host.**

| Step | Result |
|---|---|
| C0, B1B | PASS |
| B2 writes enforced | PASS: stranger 401 on goals, tasks, drafts; owner and router reach validation |
| B3 reads enforced | PASS: 11 routes 401 to a stranger, wrong token 401, conversation 401 even from loopback, owner 200, router 200 |
| B4 router turns | **FAIL on the check only:** `${DLOG}` was never assigned. The 5 reads were all 200, 0 forwarded, and an independent read found the 6 expected records, with no text or identifiers |
| RB | **PASS:** second real recovery, in 12 seconds |

**State left:** Core API on `d82f7dac`, open; main holds #306. Budget 3/5, ledger 29 lines, DB `88b76a79`, 30 dumps, gate PID 413767.
