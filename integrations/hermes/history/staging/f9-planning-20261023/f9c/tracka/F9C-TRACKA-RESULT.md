# F9-C Track A: hold-first FORGET + executor integration + F8r4→F9 upgrade. LOCAL result (2026-10-24)

**Status:** local only.
- **Validated:** the offline matrix and the WSL real-systemd mirror.
- **Not done:** no DEV or PROD contact, Groq call, commit, push or deployment.
- **Not changed:** no governed component (witness, signer, broker, authority, DR-5 pins) was modified.
- **Not built:** Track B (witness anchor) and Track C (external recovery service).

## 1. What was built

### Core API (worktree `lilith-os-f9c1`, uncommitted; cumulative patch `f9c-tracka-coreapi-cumulative.patch`)

| File | Change |
|---|---|
| `lilith_memory/privacy_forget_intent.py` (new) | Durable intent + hold-first runner (summary below the table) |
| `lilith_memory/privacy_governance.py` (+41) | read-only `identity_forget_completed(identity, required_owner)`: no ACTIVE hold, a suppression selector, and an HMAC-verified completion receipt for it that lists the required owner as COMPLETE |
| `app.py` (+33) | `_refuse_while_forget_pending()` at the top of `/os/conversation` **and** in `_relay_conversation`. It is a pure filesystem check with no `lilith_memory` import (the existing test still holds) |
| `tests/test_privacy_forget_intent.py` (new) | 14 tests |

**`ForgetIntentStore`:**
- **What it writes:** one fixed-name intent `{v, identity, intentRefId, actorRefId, recordedAt}`. It carries no content and no evidence.
- **Where:** the sticky directory `/var/lib/hermes-forget/intent` (`1730 root:lilith-forget`).
- **How:** temp file + fsync + hard link + directory fsync, so it is complete before it is visible. It never overwrites.

**`HoldFirstForgetRunner`:** calls `begin_forget` (through the unchanged Slice 3 runner) only when the intent is root-owned AND the gateway is observed stopped (unit inactive, port closed).
- `ACTOR_*` refusals, including consumed evidence (H6), leave the intent durable and blocking.

**Relay refusal outcomes:**

| Situation | Result |
|---|---|
| intent present | **503 `FORGET_HOLD_ACTIVE`** before the console is reached |
| F9-C host with unreadable intent state | 503 `FORGET_STATE_UNAVAILABLE` |
| host without F9-C | relays as before |

### Hermes package `f293e72-f9c1` = the accepted F9-B tree + the F9-C overlay only (reproducible)

| Path | |
|---|---|
| `bin/hermes_forget_executor.py` | accepted executor + finalization fix + `--hold`, intent release in reconcile, `--cancel-intent --confirm-owner-approved`, and `delivery_obligations` added to the state.db purge (found by the drill, §2.3) |
| `systemd/hermes-forget-hold.{path,service}` (new) | `PathExistsGlob=…/intent/*.intent`; hold unit `Conflicts=` the gateway, `RemainAfterExit=`, takes ownership, verifies the stop |
| `systemd/hermes-gateway-dev.service.d/50-forget.conf` | adds `ConditionPathExistsGlob=!…/intent/*.intent` |
| `systemd/hermes-forget-reconcile.service` | runs while the marker exists **or** an intent is pending; releases the intent only on Privacy proof |
| `systemd/hermes-forget-restart.service` | refuses while an intent exists; stops the hold unit before starting the gateway |
| `systemd/hermes-forget.tmpfiles.conf` | + `d /var/lib/hermes-forget/intent 1770 root lilith-forget` (sticky; the group may create and fsync, never remove a root-owned intent) |
| `bin/install_f9c.sh` (new) | Detail below |
| `bin/rollback.sh` | + F9-C units/config; **R-2 refuses, before changing anything, while a FORGET is pending**; never moves `/var/lib/hermes-forget` (the epochs feed the restore guard); C-3 decided on what was pending before it started |
| `bin/preserve_f8r4.sh` (new) | U-1: proves the accepted F8r4 is running, inventories it (incl. provider gate + key), runs F8r4's own R-1/R-2 |
| `bin/restore_f8r4.sh` (new) | Detail below |
| executor + reconcile units, `hermes-forget.path`, `hermes_restore_guard.py`, `restore_f8r2.sh` | the accepted F9-C executor slice, unchanged |

**`install_f9c.sh` steps:**
1. Creates the `lilith-forget` group; lilith joins it.
2. Creates the tmpfiles paths.
3. Makes a **root-owned copy** of the five pinned Privacy modules of the deployed Core API (DEV's release is lilith-owned, so root never imports lilith-writable code). `--repin` repeats this after a Core API redeploy.
4. Writes the executor config.
5. Installs the units.
6. Runs a C-3-guarded reload with protected-service parity (strict pending check before any change).
7. Enables the two path units and the timer, then reloads once more so it leaves nothing pending.

**`restore_f8r4.sh`:**
- **Refuses** while a FORGET is pending.
- **Guard:** runs the restore guard.
- **Restores:** moves F8r4 back.
- **Proof:** the inventory must be identical. After a later erasure epoch, *only* conversation-bearing paths may be absent, because the executor already purged them from the quarantine. The F8r4 store then comes back empty.

### Package fingerprints

| Item | Value |
|---|---|
| Package | `hermes-gateway-dev-f293e72-f9c1.tar.gz` sha256 **`4f899311cbd587feb5b5bd39a91361f75c69c5b58b3973b2bb5c6d596b9c41c9`** (WSL `/root/f9ca/out`; two builds byte-identical) |
| MANIFEST | `0caa044e2f10de3a2ba2e8ac17614fd969da823b14b90f5f1dbb1350d6c0a93e` (14,323 = F9-B 14,309 + 14 new) |
| Change set vs F9-B | **new:** the 5 bin + 9 systemd files above. **Changed:** `RELEASE_ID`, `bin/restore_f8r2.sh`, `bin/rollback.sh`. Nothing else. |

**Build note:** the F9-B base tree had accumulated unlisted stdlib `.pyc` byproducts from later test runs. The build now prunes the base to its accepted MANIFEST before overlaying.

## 2. Evidence

### 2.1 Offline (WSL, real Privacy/runner/L04/L18_V2/adapter/spool, real executor subprocess; systemd faked)

**Core API focused suites: 186 OK.**
- `test_privacy_forget_intent`: 15.
- The existing F9-C/runner/restore/capture modules are unchanged.
- One test records as a **non-root uid**: a `1730` directory refuses the directory fsync, `1770` works, and the uid cannot remove a root-held intent.
- One tamper test: an ACTIVE hold beside a verified receipt is never "completed".

**Core API full discover:**
- Python 3.11 env: **271 OK** (256 before + 15).
- The one import error is the known `test_owner_proof` (cp312 `cryptography`); it runs **22/22 OK** under Python 3.12.

**Executor matrix: 46/46 OK.** That is the 38 accepted tests (T1–T25 and the 6 finalization-window tests) plus 8 new hold-first tests. The fixture now also creates Hermes' `delivery_obligations` table with a canary.

| New | Proves |
|---|---|
| end to end | Privacy is untouched until the hold (`privacy_seen_before_hold == [None]`); the intent is taken root-owned; the gateway is stopped; erasure completes; root releases the intent |
| H1 | an unlinked temp file is never an intent |
| H3/H4 | the hold killed before or after taking the intent converges on rerun; the hold never authorizes anything |
| invalid intent | stays blocking; reconcile never releases it; only an owner-approved cancel removes it |
| H5/H7 | reconcile never releases while an authorization is in flight; cancel is refused while one is in flight; resume completes, then the intent is released |
| H6 | evidence consumed without a Privacy transaction: the intent stays durable and blocking, an unconfirmed cancel is refused, nothing is touched; fresh evidence completes |
| H8 | a kill inside the intent release leaves the intent in place; the next reconcile releases it |
| wrong secret | reconcile never releases |

**Mutations: 10/10 detected.**
- reconcile releases without proof;
- the hold never takes ownership;
- cancel ignores in-flight;
- the runner skips the hold;
- the runner releases on a stall;
- completion ignores the required owner;
- completion ignores an ACTIVE hold (detected by the tamper test, added after the first run);
- the relay without the intent check;
- the relay ignoring unreadable state;
- `delivery_obligations` not purged.

Sources were restored (hash-verified).

### 2.2 Real systemd: executor regression (`f9c4-mirror.sh` on the Track A units): 18 PASS / 0 FAIL

- **Sandbox probes:** P-1 (executor sandbox) and P-2 (the gateway cannot see the spool, state, receipts, epochs or config).
- **Scenarios:**
  - M1 end to end, with the restart, receipt, journal, scan, protected-file, marker and epoch checks;
  - M5 start limit;
  - M3 SIGKILL mid-erasure;
  - M6 locked store (fail closed, then the same authorization completes);
  - **M7 finalization window:** a kill after the receipt means the gateway is refused while Privacy is incomplete; the reconcile timer then releases and restarts.
- **Coverage note:** this ran on the Track A unit files (new reconcile/restart/drop-in conditions). It ran before the `delivery_obligations` purge entry, which the integrated run below then exercised end to end.

### 2.3 Integrated upgrade + drill rehearsal (`f9ca-rehearse.sh`, final package `4f899311…`): 51/51 rows OK

The run uses the WSL mirror with DEV's unit text and stand-ins, the real F8r4 and f9c1 packages, the real Hermes gateway, and the real Core API under DEV's unit. The provider is synthetic, and none is reachable after the upgrade.

| Step | Result |
|---|---|
| M0 | DR-5 `F8_DR5_EQUAL 7fe21378…` |
| F8r4 installed + key + canary turn through the Core API relay | 200 |
| U-1 `preserve_f8r4.sh` | 18,425 files inventoried; HERMES_HOME = memories; gate config + key quarantined |
| U-2 f9c1 `install.sh` | staged |
| U-3 | stand-in deploy of the F9-C Core API (lilith-owned, like DEV), then `install_f9c.sh`: PASS. The executor imports a **root-owned copy equal to the deployed bytes**. Before the Core API restart, the relay refused (it can't read the intent state yet, so it fails closed). After the restart, the Core API carries `lilith-forget`. DR-5 EQUAL |
| U-4 | verify `--full` PASS; `.env` keys = `LILITH_OS_PORT,LILITH_OS_TOKEN`; two canary turns 200; **0 provider requests** (no key) |
| D-1 while held (before Privacy acts) | intent `root:lilith-forget 640`; 0 Privacy holds; **relay 503 `FORGET_HOLD_ACTIVE`**; gateway start refused (`cond=no`); port closed; lilith cannot remove the intent |
| D-1 | `status=COMPLETE … L04,L18_V2,HERMES_DEV_CONVERSATION`; root released the intent + marker after Privacy completion; the gateway restarted; **canaries 0** in HERMES_HOME, backups (including the F8r4 quarantine copies) and executor state; namespace journal 0; relay 200 after release; 1 receipt, epoch 1 |
| H2 | intent recorded, hold not yet run, gateway **still up**: relay refuses at once (503). A gateway restart cannot resume (`cond=no`) |
| H9 | after the root hold, the Core API uid cannot remove the intent |
| H6 stall | no authorization, FORGET not complete: reconcile keeps the intent |
| R-0 | `rollback.sh remove` refused while the intent is pending, **before changing anything** (units still active, nothing pending) |
| cancel | unconfirmed cancel refused; the owner-approved cancel removed the never-authorized intent; the gateway resumes only afterwards |
| R-2 | f9c rollback removed it; epochs kept; F9-C config quarantined |
| R-3 `restore_f8r4.sh` | guard `F9_RESTORE_ALLOWED epoch=1`; **21,158 non-conversation entries identical**; 31 conversation entries exempt (purged by the FORGET); F8r4 key restored byte-identical; restored store carries no pre-FORGET conversation; turn on the restored F8r4 200 |
| final | DR-5 EQUAL |

**Observation, F8r4 vs restored:** the remaining diffs are all expected.
- Core API restarted (new PID);
- the mirror's test Privacy key and the `/etc/tmpfiles.d` mtime;
- the stand-in Core API release switch and the Privacy DB rewritten by the drill fixture;
- `/etc/group` (`lilith-forget` stays: rollback never deletes).

Nothing changed in authority, witness or broker paths.

**Defects found and fixed during this campaign:**

| # | Defect | Effect | Fix |
|---|---|---|---|
| 1 | `install_f9c.sh` assumed a root-owned Core API release; DEV's is lilith-owned | refusal; also, root importing lilith-writable code would be a TOCTOU | root-owned pinned copy |
| 2 | the intent directory was `1730`, so the Core API's directory fsync got EACCES | the intent was linked, and so blocking, but the drill aborted | `1770` + a non-root regression test |
| 3 | the post-change C-3 check refused our own drop-in | install aborted before reload | strict check before changes; jobs-only after |
| 4 | systemd 255 marks **every** unit `NeedDaemonReload` after any enable/disable; rollback and restore then withheld their reloads | restore refused | C-3 decided on the state before the change; rollback reloads after its own disables; R-2 refuses before touching anything |
| 5 | `nullglob` does not drop a literal path, so the pending-FORGET guards were always true | rollback and restore always refused | explicit existence check |
| 6 | **real Hermes table `delivery_obligations`** (outbound reply text, created lazily by `gateway/delivery_ledger.py`) was not in the purge list | the executor refused `UNKNOWN_HERMES_SCHEMA` (fail closed; nothing touched, hold ACTIVE) | purged + matrix fixture + mutation |

**Not separately proven:** the restore path with **no** erasure (identical inventory including conversation state). The first attempt that would have covered it stopped at U-3 under the old installer, and its cleanup exposed defect 5. It was not re-run; only the erased path is proven.

## 3. DR-5 and protected services

- **DR-5:** `F8_DR5_EQUAL 7fe21378…` at M0, after `install_f9c` and at the end.
- **Never touched:** sudoers, polkit, the deployer, signer, broker, witness and authority.
- **Protected-service parity** (Core API, broker, authority, witness, stage3) was checked across every daemon-reload by `install_f9c.sh`, `rollback.sh` and `restore_f8r4.sh`.
- **Expected host deltas for the DEV record:**
  - group `lilith-forget` + the `lilith` membership (they persist after rollback);
  - `/etc/hermes-forget`;
  - `/var/lib/hermes-forget` (epochs persist after rollback);
  - 7 units + the gateway drop-in;
  - 3 enabled units (2 path units + the timer).

## 4. Readiness for controlled DEV deployment

**The Track A local integration is complete. A DEV deployment is NOT ready to execute yet.** Blockers B-1 to B-4 each need a decision or a small, separate piece of work, and none is a redesign.

| # | Blocker | Why | Smallest next step |
|---|---|---|---|
| B-1 | The F9-C Core API code (Slices 1–3, restore fix, gate, spool, Track A) is **uncommitted** in `lilith-os-f9c1` | The DEV deployer only accepts an attested bundle keyed to a commit SHA; `install_f9c.sh` refuses without the F9-C Core API deployed | Owner authorizes commit + PR. Then the governed DEV deploy, which also restarts the Core API so it gains `lilith-forget` |
| B-2 | DEV Privacy DB v1→v2 migration + Hermes owner-floor provisioning | `privacy_schema_v2` exists only as library functions; no DEV operator step exists | An offline operator script (Core API stopped), with the backup taken first |
| B-3 | DEV drill tooling | The mirror drill uses the runner **test fixture** (a temp Privacy DB copied **over** the DEV path, a test actor authority). That must never run on DEV. DEV has no First Interaction memory and no operator path to issue FORGET actor evidence | A small DEV drill CLI (as lilith: runner from DEV config + DEV-synthetic evidence issuance) plus a synthetic FI seeding step. This needs an owner decision on DEV evidence issuance (interim V1 HMAC, DEV_SYNTHETIC only, per A-4) |
| B-4 | DEV facts to confirm read-only | the DEV Privacy secret path/owner (`install_f9c.sh` needs it root-owned); the deployed Core API path; free disk; no pending reloads/jobs | A read-only DEV preflight |

**Recorded, not blocking:**
- **Groq key:** it stays in the F8r4 quarantine, so f9c runs with `NOT-PROVISIONED` (structurally zero provider calls). Re-provisioning is a separate owner step.
- **Reboot:** not exercised in WSL. The intent, marker, journals and epochs are persistent files, and the gateway conditions are evaluated at every start.
- **Shared uid:** A-3b is unchanged (the Core API and gateway share uid `lilith`; the sandbox is the separation).
- **Not live-eligible:** Track A is not live-eligible. Track B (anchor), A-3 and A-4 are still required for live First Memory.

**DEV order once B-1..B-4 are resolved:**
1. G-0 owner authorization;
2. preflight;
3. U-1 `preserve_f8r4.sh`;
4. `backup_pre_install.sh`;
5. `install.sh`;
6. governed Core API deploy;
7. `install_f9c.sh`;
8. Core API restart;
9. Privacy v2 + floor;
10. console token;
11. verify;
12. gateway start;
13. synthetic turns;
14. drill;
15. canary scan.

Rollback: R-2 `rollback.sh remove` (refused while a FORGET is pending), then R-3 `restore_f8r4.sh`.

**STOP. Nothing has been committed, pushed or deployed.**
