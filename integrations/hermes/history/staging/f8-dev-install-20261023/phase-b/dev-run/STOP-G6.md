# STOP at G-6 (F8r4 Phase B, lilith-dev-01, 2026-10-23)

**Status:**
- F8r4 is installed (G-0 … G-5c PASS).
- It STOPPED at G-6, and R-1 was applied per the runbook.
- **0 provider requests** (budget_used 0; 0 FORWARDED lines; ledger holds only the initial RESET line).
- G-6b, G-7, G-7d, G-8, G-9 and G-10 were NOT run.

## What failed

The `G-5c-6b.txt` checks ran at about 12:42:51, 9 s after `systemctl start`:
- The gateway was active/running, 0 restarts, static, on `127.0.0.1:9901` (after ~6 s).
- The gate was active/running, 0 restarts, static, **but 9911 was not listening yet**.
- `gate_budget.sh show` returned empty (connection refused).
- `ps -o user=` reported `root` for the gate MainPID.
- No pending reload; protected services unchanged.
- The script printed `G6_FAIL`.

## Diagnosis (read-only, `diag-g6.out`, 12:43–12:44)

- systemd forked the gate at 12:42:41–42 ("Started" at 12:42:42).
- The gate's own `F8_GATE START` line, its ledger creation and the 9911 bind happened at **12:43:12, about 30 s later**.
- After that the gate ran as **uid 64597 (dynamic `hermes-provider-gate-dev`), CapEff 0, NoNewPrivs 1, Seccomp 2**. Budget: key_loaded true, 0/5 used, available, state OK.
- The `root` reading at 12:42:51 is consistent with systemd's forked child still in its pre-exec sandbox setup (root until the exec). The gate's start line came 21 s later, so no gate code had run at that point.
- **The cause of the ~30 s startup delay is not established.**
- Harness defect: the G-6 wrapper waited only for 9901, not for 9911 (the runbook allows ≤ 90 s). It also exited inside its logging block, so the first output was empty (rc 1) and had to be re-read from DEV.

## R-1 (`R-1-after-G6.txt`, sha `780e54dc…d117`)

- `F8_ROLLBACK_STOPPED`; 9901 and 9911 closed. The gate and timer are inactive.
- The gateway is `failed` because Hermes exits 1 on SIGTERM (same as N-1). NRestarts 0.
- Protected services unchanged: api 176771, broker 3411, authority 128648, witness 127192, 0 restarts, same InvocationIDs.
- Observation vs G-1: EQUAL in all 6 sections. DR-5: `F8_DR5_EQUAL 7fe21378…`. Core API health ok.
- The key stays root-only on DEV (`ac61a7947e36…`). It was never printed, and no request used it.

## Owner decision

- **A.** Re-run G-6 with a corrected wrapper that waits ≤ 90 s for both listeners and the gate START line, records the gate uid from `/proc/<pid>/status`, and saves its output before exiting; then G-6b. The package and runbook criteria are unchanged.
- **B.** Roll back further: R-2 (move f8r4 and the key to quarantine; revoke the key at Groq), then R-3/R-3v (restore F8r2).
