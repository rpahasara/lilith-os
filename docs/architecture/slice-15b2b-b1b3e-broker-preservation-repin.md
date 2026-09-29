# Slice 15B2b-B1b-3e — Broker Preservation Re-pin (post-reboot baseline)

Status:

- **SOURCE / DOCUMENTATION CHANGE ONLY**; `LIVE_MUTATION = NONE`; no DEV contact
- **OLD BROKER BASELINE RETIRED** (broker continuity only)
- **NEW BROKER BASELINE PINNED** in `preservation`
- **PR-1B NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**
- Classification: **`BROKER_PRESERVATION_REPIN_READY`**

```text
broker preservation PASS != authority readiness != PR-1B authorization
```

## 1. Order of events

1. **Owner acceptance first.** The owner explicitly accepted candidate
   `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2` on boot
   `eea461c3-60f0-4b10-8ee9-556dcef19711` as the new broker continuity
   baseline, broker runtime scope only. See the
   [acceptance record](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline-acceptance.md)
   §5, merged to `main` as `54d7504` (PR #106).
2. **Post-acceptance §10 validation passed**
   (`POST_ACCEPTANCE_DR5_D1_D4_PASS`, 2026-09-29):
   - **DR-5:** routine run `36550054125` (main `54d7504`, `DEPLOY_REQUIRED`)
     showed `PR1_AUTHORITY_BOUNDARY maturity=P1A-9` and
     `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`. There was no real
     `FAIL` and no `ALLOWED(unexpected)`. The only change from the
     pre-reboot DR-5 is the six new OR-6 `/run` denials.
   - **D-1:** `rebaseline` gave exactly `50003745…` with incarnation
     `84798e5b…`, PID 2586, start ticks 69918, `NRestarts=0`.
   - **D-2:** `status --expect P1A-9` PASS.
   - **D-3:** `GRANT_ABSENT`.
   - **D-4:** the `routine-deploy` structural comparison PASSed. The only
     delta was `DEPLOY_LOCK_CREATED`, with the exact stat contract.

   Evidence: owner workstation
   `C:\Users\edufo\lilith-b1b3e-pre-pr1b-reboot\dr5\`, `SHA256SUMS`
   `9f2bb51e…`.
3. **Then this re-pin.** It is a reviewed source change that makes
   `preservation` validate the accepted baseline.

## 2. Pins

In `scripts/verify_broker_dev_current_incarnation.py`:

| Constant | Old (retired) | New (accepted) |
| --- | --- | --- |
| `ACCEPTED_CURRENT_INCARNATION` | `42af2691b8d24ee5a92a286197c5444c` | `84798e5b74494e1ea362ce90f1cf04ad` |
| `ACCEPTED_CURRENT_BASELINE_SHA256` | `3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5` | `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2` |
| `ACCEPTED_CURRENT_BOOT_ID` | `24d1771d-e1b5-4e5f-816d-da08ad8b367a` | `eea461c3-60f0-4b10-8ee9-556dcef19711` |
| `ACCEPTED_CURRENT_IDENTITY` (new) | — (old values: PID 132976, start ticks 108213277) | boot `eea461c3…`, PID `2586`, start ticks `69918`, `nRestarts` `"0"`, release `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, manifest `7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614`, shared libraries `40e68a1c27328c27b811da19bb17a1262cbacff18dcd7ab397e06bebb17a87bd` |
| `ACCEPTED_CURRENT_CONTROLLER_EXPECTED` (new) | the pre-reboot `CONTROLLER_EXPECTED` (`failed/exit-code`), implicit | `CONTROLLER_POST_REBOOT_EXPECTED` (loaded, `inactive/dead`, `Result=success`, `ExecMainStatus=0`, `Restart=no`, `NRestarts=0`, no InvocationID) |
| `RETIRED_BROKER_BASELINES` (new) | — | the old incarnation, boot, and candidate, with a pointer to their record. Reference only; never accepted by any operation |

The new values are the full values from the acceptance record and the D-1
evidence, not abbreviations.

## 3. Semantics

**`preservation`.** Only its reference changes, plus two narrow additions:

- The accepted process identity is checked explicitly
  (`ACCEPTED_IDENTITY_CHANGED:<field>`), in addition to the candidate digest.
  The digest already covered every one of those fields. The explicit check
  only makes a mismatch name its field, so it is not weaker.
- The Stage III controller is checked against the accepted boot's state.

**Why the controller contract had to move.** The accepted baseline lives on
a post-reboot boot. On that boot systemd no longer holds the controller's
pre-reboot `failed/exit-code` result. Re-pinning the constants alone would
have left `preservation` failing on DEV with `STAGE3_CONTROLLER_CHANGED`. The
new contract is the one `rebaseline` already used and the live host showed
(ceremony Q7). It is stricter: the unit must be loaded and have no
InvocationID, meaning it never ran in the accepted boot.

Both are keyword parameters with reviewed defaults. There is no new
operation, flag, or environment switch.

**`rebaseline`.** The code is unchanged. Its supersession reference is
`ACCEPTED_CURRENT_*`, so it now supersedes the newly accepted baseline. A
future candidate must come from a further boot and a new incarnation. Run
against the live host today, it correctly refuses the accepted baseline as a
"new" candidate (`REBOOT_NOT_OBSERVED`, `RUNTIME_INCARNATION_NOT_REPLACED`).

**`baseline`.** Unchanged: the historical pre-custody semantics.

**Not changed:**

- authority, custody, or activation semantics;
- installer `status` or PR-1A logic;
- PR-1B sequencing;
- freshness or owner-acceptance logic;
- any unit, tmpfiles, or release file.

## 4. Source and tests

| File | Change |
| --- | --- |
| `scripts/verify_broker_dev_current_incarnation.py` | §2 pins; `evaluate_preservation(accepted_identity=…, controller_expected=…)`; `acceptedIdentity` and `acceptedIdentityMatches` output fields; docstrings |
| `scripts/test_verify_broker_dev_current_incarnation.py` | the existing pre-reboot preservation fixture now passes its own pins explicitly, including its failed-controller contract. The real-pin tests now read the acceptance record, and retired values are checked against the old record. There are 12 new `RepinTests` |

**`RepinTests`.** They prove:

- the real pins equal the accepted baseline exactly, and release and
  manifest agree with the verifier's release pins;
- `preservation` accepts the exact accepted post-reboot shape;
- it rejects:
  - the whole retired baseline;
  - the old incarnation alone;
  - the old PID and the old start ticks;
  - a candidate mismatch (library digest, start time, pinned digest);
  - `NRestarts != 0`;
  - a boot mismatch (the old boot or another boot);
  - the pre-reboot controller state and a controller that ran;
- every broker drift class still fails;
- `rebaseline` fixture results are unchanged, and it refuses the accepted
  baseline as new against the real pins; `baseline` is unchanged;
- a PASS carries `authorityCustodyJudgment=NOT_PERFORMED` and
  `authorityMaturity=NOT_ESTABLISHED_BY_PRESERVATION`, and no PR-1B, K-WIT,
  INITIAL_CUSTODY, freshness, or DR-5 token.

The verifier's SHA-256 changes to
`bd7aa35a2e7834a6cc35ba7d1a069a0847a69a03fa7d0d9fe30a5f227703292d` (was `72d0a99d…8a43`). Every
later ceremony must hash the tool from its own `CONTROL_SHA`.

## 5. After merge (not authorized by this record)

- The merge is `DEPLOY_REQUIRED` (the verifier is not a control-only path).
  The routine run re-proves DR-5.
- The first read-only `preservation` run on DEV from the merged `main` is
  expected to return `BROKER_PRESERVATION=PASS`, with incarnation
  `84798e5b…` and candidate `50003745…`. That run is the live confirmation
  of this re-pin. Any FAIL is a STOP.
- Next in the accepted order: **PR-2 read-only revalidation**.

## 6. Nonclaims

This re-pin creates **no** authority, custody, or freshness transition. It
does not claim:

- behavioural equivalence of the broker runtime;
- whole-host rollback resistance (OR-1 open);
- that DR-3 is closed;
- any K-ROOT, K-WIT, registry, ledger, witness state, hold, RecoveryEpoch,
  INITIAL_CUSTODY, or real owner record 1. Real owner freshness remains
  `FRESHNESS_UNKNOWN`.

## Explicitly not done

```text
NO DEV CONTACT
NO DEV MUTATION
NO BROKER RESTART
NO AUTHORITY START
NO WITNESS START
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
