# F9-C privileged Hermes erasure executor. LOCAL result (2026-10-24)

**Status:** local only, validated in the WSL mirror; for owner review.
- **Not done:** no DEV or PROD contact, no install on DEV, no Groq call or budget reset, no commit or push, no real conversation.
- **The F8r4 installation and rollback baseline are untouched:** the package files here are new, plus one patched copy of `restore_f8r2.sh` for the F9 candidate. DEV's installed F8r4 is unchanged.
- **Synthetic success here is not authorization for personal data.**

## What was built

Core API cumulative patch (Slices 1–3, restore fix, gate, spool client): `f9c-executor-cumulative.patch`, sha256 `973cf9156ab7e24593406c5b5038d7798b4c794fbc509f2a94f64d0b31e9fa60` (14 files, +3389/−24). Evidence logs: `evidence/`.

### Hermes package additions (staging `f9c/executor/pkgfiles/`; destined for the F9 candidate)

| File | sha256 | Role |
|---|---|---|
| `bin/hermes_forget_executor.py` | `3d5b9f91…70e9` | root executor (stdlib only + hash-pinned Core API modules) |
| `bin/hermes_restore_guard.py` | `1c2da721…a959` | epoch-based restore refusal |
| `bin/restore_f8r2.sh` | `be9b13bd…65ee` (base `654525bc…`) | runs the guard before moving anything |
| `systemd/hermes-forget-executor.service` | `1b24ef34…0bb4` | root oneshot, sandboxed, `Conflicts=`/`OnSuccess=` |
| `systemd/hermes-forget.path` | `9c8e3a5f…378a` | `PathExistsGlob=/run/hermes-forget/spool/*.req` |
| `systemd/hermes-forget-restart.service` | `d847db79…1c88` | reset-failed + start the gateway after success |
| `systemd/hermes-gateway-dev.service.d/50-forget.conf` | `eec9b656…8f51` | gateway refuses to start while an erasure is in progress; cannot see spool, state, receipts or config |
| `systemd/hermes-forget.tmpfiles.conf` | `d4ad5823…716b` | spool `root:lilith-forget 0730`, receipts `0750`, state and epochs root `0700` |

### Core API (worktree, uncommitted)

| File | sha256 | Role |
|---|---|---|
| `lilith_memory/hermes_erasure_spool.py` (new, 80 lines) | `64a4d15f…8817` | the Slice 2 `HermesErasureExecutor`: queue only, never overwrite, receipt trust rules |
| `tests/test_hermes_erasure_spool.py` (new) | `64848d77…` | 3 unprivileged tests |

**Slice 1–3, the restore fix and the gate are unchanged.** `hermes_erasure_owner.py` is still `280d9236…` and `privacy_governance.py` is still `e65a6cdf…`.

## How it works (exact behaviour)

### Trigger and request

- **Trigger:** the Core API spool client writes `{v, owner, authorizationRefId, executionNonce}` (the Slice 2 contract) as `<refdigest>-<uuid>.req`. The temp file is renamed into place, so there is never a partial request and never a second hard link.
- **Activation:** the root path unit starts the executor. Starting it stops the gateway (`Conflicts=`).
- **A request is never authorization.** It is rejected before any action unless all of these hold:
  - a regular file owned by the Core API uid;
  - not world-writable, a single link, at most 1 KiB, opened `O_NOFOLLOW`;
  - exactly the four fields, with valid formats.
- A rejected request is renamed `*.failed`, so the path unit has no trigger loop.

### Independent check #2 (interim V1, DEV_SYNTHETIC only)

1. The executor hashes the five Core API modules (`__init__`, `canonical_contracts`, `memory_action_v2`, `canonical_authority`, `privacy_governance`) against pins in its root-owned config **before importing them**, and again after import. Tampered code is never executed (tested).
2. It opens the Privacy DB **read-only**. With no WAL content it uses `immutable`; otherwise `mode=ro`.
3. It runs `resolve_erasure_authorization(owner=HERMES_DEV_CONVERSATION)`: owner listed, exact nonce, HMAC, hold ACTIVE.
4. It requires the First Interaction identity and the provisioned required-owner floor.
5. **No receipt is ever written for an unverified request**, so a forged request cannot poison a real authorization's receipt.

### Single-principal precondition (before any change)

| Condition | Refusal code |
|---|---|
| `.env` keys ⊆ {LILITH_OS_PORT, LILITH_OS_TOKEN} | MULTI_PRINCIPAL_STORE |
| `plugins.enabled` exactly [lilith_os], no `platforms:` | MULTI_PRINCIPAL_STORE |
| every session's `source` is lilith_os | UNRECOGNIZED_SESSION |
| at most one distinct `user_id` | AMBIGUOUS_OWNERSHIP |
| every state.db table known | UNKNOWN_HERMES_SCHEMA |

A refusal before anything changes writes a **REJECTED** receipt bound to the verified authorization. The adapter raises `EXECUTOR_REJECTED`; the Privacy hold stays ACTIVE and nothing is touched.

### Phases

Each phase is idempotent and journalled per authorization in `/var/lib/hermes-forget/state/<sha256(ref)>.json`, fsync'd.

| Phase | Action | Verification |
|---|---|---|
| VALIDATE | precondition, protected-file snapshot, durable `in-progress` marker | the gateway drop-in refuses to start while the marker exists |
| STOP | `Conflicts=` stopped the gateway | unit inactive, no `hermes_cli.main gateway` process, 9901 closed |
| SQLITE | allowlisted whole-store purge by direct SQL (no Hermes code runs as root), every FTS table `rebuild`, `secure_delete`, `wal_checkpoint(TRUNCATE)`, VACUUM | sessions/messages/linkage 0, FTS docsize 0, integrity ok, freelist 0, WAL empty; a lock gives `STATE_DB_LOCKED` with nothing deleted |
| FILES | empties `logs sessions pending_messages runtime state gateway cache audio_cache image_cache` and removes runtime files, never following a symlink | dirs empty; protected files (SOUL.md, config, .env, router, plugins, memories, skills, cron/jobs.json) byte-identical to the snapshot |
| JOURNAL | rotate + vacuum the `hermes-gateway-dev` namespace only | no namespace entry older than the phase start remains |
| BACKUPS | **tombstone first** (content-free: path digest, kind, size, sha256 before), then removes `state.db*`, HERMES_HOME conversation paths inside HERMES_HOME copies, namespace journal copies and tar members (archive rewritten, other members kept) | rescan finds none; code and config in backups are kept |
| EPOCH | append `{epoch, at, sha256(ref)}` to root-only `epochs.log`, monotonic, idempotent per authorization | contiguous |
| FINISH | journal FINISHED, marker removed, then the Slice 2 receipt (`root:lilith-forget 0640`, digest-bound) | — |

**Receipt ordering (a defect the matrix found and fixed).** A crash between the receipt and the marker removal left the marker forever, because the adapter's retry only re-reads the receipt. The executor now records FINISHED, removes the marker, and only then writes the receipt. A crash before the receipt leaves verified-erased data and the gateway allowed; the adapter's retry gets the receipt rewritten.

### Failure and rollback behaviour

- Any failure means **no receipt, hold ACTIVE, marker kept, gateway stopped**:
  - the drop-in `ConditionPathExists=!marker` refuses every start;
  - no `OnFailure` restart exists;
  - the request is parked.
- The adapter's next retry submits a new request and the executor resumes from the journal.
- A SIGKILL leaves the request in the spool; the path unit re-runs the executor, which resumes (mirror M3).
- A reboot loses `/run`. The marker and journal in `/var/lib` survive, and the retry resumes.
- Success runs `OnSuccess=` reset-failed + start, so the start limit can't strand the gateway (M5).

### Restore suppression

- `hermes_restore_guard.py check <artefact>…` refuses (`F8_RESTORE_CONVERSATION_SUPPRESSED`, exit 3) any conversation-bearing item captured at or before the latest epoch.
- Capture time is the earliest of the artefact's name stamp and its mtime, so a renamed old copy can't pass.
- `restore_f8r2.sh` runs it before moving anything.
- Code/config-only artefacts, and history captured after the epoch, are allowed.

## Security-boundary review

- **Least privilege by sandbox (verified by the mirror's executor-sandbox probe, P-1, run with the exact `[Service]` block):**
  - **can:** write the Hermes conversation store, its own state and spool, Hermes backups and the Hermes namespace journal;
  - **can read only:** the Privacy DB (`privacy_write=EROFS`);
  - **cannot see:** cognitive DB, Core API DB, provider key, broker/authority data, sudoers content (`ABSENT`/`HIDDEN`);
  - **read-only:** `/etc` and code (`EROFS`);
  - **network:** only 127.0.0.1; the VPC/PROD address and the metadata server are `BLOCKED`.
- **Capabilities and syscalls:**
  - capabilities limited to `CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_CHOWN`;
  - `NoNewPrivileges`, `MemoryDenyWriteExecute`, `@system-service` minus `@privileged` etc., plus `@chown` re-allowed.
  - **Defect found by the mirror:** `@privileged` contains `@chown`, so every chown hit EPERM inside the sandbox. Fixed with that single line.
- **Gateway isolation (P-2, from inside the real gateway sandbox):** spool list/write, state, receipts, epochs and executor config are all `DENIED`; the Privacy DB is `ABSENT` (T6).
- **No sudo, no polkit, no deployer, signer, broker, witness or DR-5 change.** Activation is a root path unit on a group-writable spool, which is the reviewed A-3 architecture.
- **Known weakness (A-3b, unchanged):** the Core API and the gateway share uid `lilith`; separation is the gateway sandbox.
- **Content-free:**
  - receipts, journal, tombstones, epochs and executor logs carry no canary (T24);
  - receipts claim `LOGICAL_ERASURE_VERIFIED` and `ATTESTED_ZDR_NOT_VERIFIED` only (T25).

## Test evidence

### Offline matrix

`tests/test_f9c_executor_matrix.py`, run as root in WSL. It drives the real executor in a fresh interpreter, and the real Privacy, runner, L04, L18_V2, adapter and spool client. It uses Hermes' own schema and FTS triggers, real tar archives and a real full tmpfs; only systemd and journald are faked. **32/32 OK** (final run; matrix file `9e137aac…`).

| T | Test(s) | Result |
|---|---|---|
| T1, T19, T23–T25 | full FORGET through the real executor: erased, protected kept, backup code kept, canary 0 everywhere, receipt claims | PASS |
| T3 | wrong nonce / forged ref / other-secret HMAC (executor alone); authorization without Hermes; unpinned modules; **tampered module never imported** | PASS |
| T4 | replay after completion touches nothing | PASS |
| T5 | extra `sessionIds`, wrong owner, oversize, not JSON, symlink, hard link, wrong uid | PASS |
| T7 | SIGKILL at each of 15 points: blocked (hold ACTIVE, marker or verified state), retry converges, epoch stays 1; **no backup deleted before its tombstone** | PASS |
| T8 | reboot: spool lost, adapter retry resumes | PASS |
| T9 | locked state.db; gateway refusing to stop; port still listening | PASS |
| T10 | rows only in the WAL (SIGTERM-like writer) erased | PASS |
| T11 / T11b | real ENOSPC on tmpfs: COMMIT rolls back, fail closed, converges after space is freed / VACUUM failure after commit keeps rows deleted | PASS |
| T12 / T12b | journal vacuum failure / vacuum leaving old entries | PASS |
| T13 | tombstone failure deletes no backup; retry | PASS |
| T15, T16 | another owner fails first; adapter timeout then a late receipt is reused (no resubmit) | PASS |
| T17 | other platform token, extra plugin, foreign session source, two users, unknown table → REJECTED, nothing touched | PASS |
| T18 | pre-epoch copy refused; renamed old copy refused; code-only and post-epoch allowed; restore_f8r2 runs the guard first; epoch log root-only and contiguous | PASS |
| T20 | executor never writes the Privacy or cognitive DB (byte-identical) | PASS |
| other | symlinks never followed (inside and as a purge dir); stale FTS index rebuilt | PASS |

### Real systemd mirror

`mirror/f9c4-mirror.sh`, WSL systemd 255. It installs the real units, tmpfiles, drop-in and journald namespace; the gateway stand-in runs inside the **real package gateway unit's sandbox**. **All PASS** (third run):

| | Result |
|---|---|
| P-1 | executor sandbox as above |
| P-2 | gateway sandbox (T6) |
| M1 (T1) | Core API runner as uid lilith → spool → path unit → root executor → receipt `root:lilith-forget 640` COMPLETE, epoch 1 → adapter verified → Privacy COMPLETE (L04, L18_V2, Hermes) → gateway restarted by OnSuccess; no namespace entry older than the executor start; canary 0 in HERMES_HOME, backups, executor state/spool; SOUL.md unchanged; backup code kept; marker cleared |
| M5 (T14) | gateway at `start-limit-hit` → FORGET COMPLETE → reset-failed + start brought it back |
| M3 (T7 real) | SIGKILL after FILES: marker present, gateway inactive; the path unit re-ran the executor; FORGET COMPLETE; canary 0 |
| M6 (T9 real) | locked store: STATE_DB_LOCKED, no receipt; `systemctl start hermes-gateway-dev` → inactive, `ConditionResult=no`; the same authorization completed on retry; gateway back |
| teardown | mirror restored exactly (HERMES_HOME `memories`, the two original backups, `lilith-dev.db`; no units, group or paths left) |

Earlier mirror runs, kept as evidence:
- **run 1:** a harness error (the Core API test ran from an unreadable cwd);
- **run 2:** found the `@chown` sandbox defect. Fail-closed behaviour held throughout: the marker kept the gateway refused and there was no receipt.

### Mutations

`tests/mutate_executor.py`, on a separate copy:
- **21 mutations: 19 detected.** The 4 first-run survivors each gained a test: pre-import pin check, tombstone ordering, a purge directory that is itself a symlink, stale FTS.
- **2 equivalent:** removing either explicit WAL checkpoint is masked by SQLite's own checkpoint on the last close. The WAL check runs after close, so it observes the real end state.

### Regressions

| Suite | Result |
|---|---|
| Windows Core API | **275 OK** (run before the 3 POSIX-only spool tests were added; they skip on Windows) |
| Linux Core API (py3.11 FastAPI env) | **257 run: 256 OK + the usual `test_owner_proof` placeholder**; `test_owner_proof` 22 OK (py3.12) → 278 |
| Linux focused modules (spool, gate, restore, Slices 1–3, F4, F1) | **158/158** (py3.11); py3.12 136 + 2 FastAPI import placeholders |
| Linux owner-memory-control ×2 | **2114 OK (16 skipped) ×2, failure set identical to b9eb32c**; gated accepted read 3 OK |
| Linux executor matrix (root) | **32/32 OK** |

## Not covered (stated plainly)

- **T21:** the F8r4→F9 upgrade and rollback scripts (A-7, separate slice). This includes code/config-only backups (D-5 going forward) and a conversation-suppressed restore mode. Today the guard makes `restore_f8r2.sh` refuse instead.
- **T20 full:** DR-5 EQUAL and protected-service PIDs on a real DEV-like host. The mirror proves sandbox reachability, not DR-5 against the DEV baseline.
- **T22:** Privacy schema migration (Slice 1 tests, unchanged).
- **T8 real reboot:** the distro reboot was not exercised under systemd. Offline T8 covers the spool loss; the mirror proves path-unit re-runs and marker persistence.
- **The real Hermes gateway:** the mirror uses a stand-in in the real gateway sandbox, and Hermes' own schema comes from its source. The F9-A "no onboarding note on an emptied store" property is covered by the F9-A tests, not re-run here.

## Remaining blockers (each needs approval)

1. **A trusted Privacy rollback anchor is REQUIRED before real First Memory.** Neither the gate nor the executor detects a rolled-back Privacy DB.
2. **Gate wiring into every real serving path;** callers using bare Privacy stores stay ungated. The DR-5 durability probe and the capture relay have their own boundary concerns.
3. **Signed `PrivacyAuthorizationV2`** (no secret in the executor), real owner authentication, a dedicated Hermes service account (A-3b) and M2 identity mapping, all before live use.
4. **F9 package integration:** build the F9 candidate with these files, the config renderer and the pins; upgrade and rollback scripts (A-7); then DEV install and the drill (A-8).
5. **Provisioning items:**
   - the `lilith-forget` group (observation-baseline change, A-3);
   - the Privacy secret's real location (the mirror used `/etc/lilith-os-dev/privacy-authority.key`);
   - the executor config pins rendered at build time.
