# Slice 15B2b-B1b-3e — Broker Preservation Re-pin (post-restart baseline)

Status:

- **SOURCE / DOCUMENTATION CHANGE ONLY.** `LIVE_MUTATION = NONE`, and no DEV
  contact.
- **Step 2 of 2.** Merge this only after the owner has accepted the
  candidate in the
  [broker restart recovery record](slice-15b2b-b1b3e-broker-restart-recovery.md)
  §6 (step 1), and that record has merged. Without that acceptance, this
  change must not land.
- On merge, `preservation` pins the post-restart broker baseline. The
  2026-09-29 post-reboot baseline is **retired** (broker continuity only).
- **B-5 GRANT REMAINS VOID. M-B1 NOT AUTHORIZED. FIRST MEMORY NOT
  AUTHORIZED.**

```text
re-pinned != fresh PR-2 PASS != eligible != M-B1 authorized
```

## 1. Pins

In `scripts/verify_broker_dev_current_incarnation.py`:

| Constant | Old (retired) | New (accepted in step 1) |
| --- | --- | --- |
| `ACCEPTED_CURRENT_INCARNATION` | `84798e5b74494e1ea362ce90f1cf04ad` | `c4b9cb38d7a041dc91db0d8ada7e8d04` |
| `ACCEPTED_CURRENT_BASELINE_SHA256` | `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2` | `a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d` |
| `ACCEPTED_CURRENT_BOOT_ID` | `eea461c3-60f0-4b10-8ee9-556dcef19711` | **unchanged**: the restart kept the boot |
| `ACCEPTED_CURRENT_IDENTITY` | PID `2586`, start ticks `69918`, libraries `40e68a1c…87bd` | PID `35622`, start ticks `26369693`, libraries `818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60`. Boot, `nRestarts` `"0"`, release `817a83e4…`, manifest `7a46ac83…` unchanged |
| `ACCEPTED_CURRENT_CONTROLLER_EXPECTED` | `CONTROLLER_POST_REBOOT_EXPECTED` | unchanged: the Stage III controller has still never run in this boot |
| `RETIRED_BROKER_BASELINES` | `42af2691…` (pre-reboot) | `42af2691…`, plus **`84798e5b…`** (post-reboot, ended by the 2026-10-02 restart; record: the reboot rebaseline acceptance) |

**Nothing else changes.** That includes every check, every operation, the
`rebaseline` supersession semantics, and the controller contracts.

## 2. Proof against the real host data

The step-1 record captured the verifier's own read-only `collect()`
observation at each gate (evidence `C:\Users\edufo\lilith-b1b3e-broker-recovery\`,
`SHA256SUMS` `4df22e74…`). **This change's verifier** (SHA-256
`2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba`), with its
real constants and no overrides, was evaluated in WSL on those observations:

| Observation | `preservation` |
| --- | --- |
| pre-restart (`10:10Z`, broker 2586 mapping the deleted `libcrypto.so.3`) | **FAIL**: `RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE`, plus the identity and incarnation of the retired baseline |
| post-restart (`10:16Z`) | **PASS**, `failures=[]`; identity and candidate match |
| post-restart, after five minutes or more (`10:23Z`) | **PASS**, `failures=[]`; identity and candidate match |

The same replay with the current `main` verifier reproduces the host's own
outputs exactly. The replay is faithful.

## 3. After merge (not authorized by this record)

1. The merge's routine deployment runs DR-5. Its result set must equal the
   accepted run `36552218231`, and this is the first DR-5 after the restart.
2. A **new fresh PR-2 revalidation** (Condition 3) uses the re-pinned
   `preservation` live.
3. The owner re-decides B-5.
4. Only then is Condition 4 (eligibility) evaluated.

## 4. Validation

- `scripts/test_verify_broker_dev_current_incarnation.py` passes. `RepinTests`
  pins the new values and both retired baselines. The record test checks that
  every pinned value appears in the step-1 acceptance record, and that each
  retired baseline appears in its own record.
- The other suites that import the verifier pass:
  - `scripts/test_needrestart_lilith_override.py`
  - `scripts/test_compare_reboot_host_observations.py`
- `scripts/validate_repository.py` passes, and `git diff --check` is clean.

## Explicitly not done

```text
NO LIVE MUTATION BY THIS CHANGE
B-5 GRANT REMAINS VOID
CONDITION 3 NOT YET RE-RUN
CONDITION 4 NOT EVALUATED
CONDITION 5 OPEN
M-B1 NOT AUTHORIZED
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
