# Slice 15B2b-B1b-3e PR-3 P3-3A: Android-Safe Create-Only Replica Publication

**Status: P3-3A DESIGN + OFFLINE SOURCE + SYNTHETIC TESTS.** P3-3 remains
**`P3_3_STORAGE_INCOMPLETE`**.

- Real Replica A is untouched. Real Replica B is absent. There is no real
  record 1, and real freshness remains `FRESHNESS_UNKNOWN`.
- The S25 is **not** admitted storage.
- There was no phone, DEV, or cloud contact in this task.

| Field | Value |
| --- | --- |
| Amends | [PR-3 foundation](slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md) §24.3 step 4 and §25.1 ("hard links REQUIRED") |
| Source | `services/owner-memory-control/lilith_owner_memory/create_only_publish.py` (backends); `owner_freshness_tool.py` (probe, admission, record and envelope writers, strict read) |
| Phone probe | `services/owner-memory-control/tools/android_p3_probe.py` (standalone, Termux) |
| Tests | `…/tests/test_b1b3e_pr3_p33a_create_only_publication.py`; updated `…_p33_storage_gate.py` |

## 1. Observation that triggered P3-3A

This is the owner's report. The phone was physically disconnected from the
laptop at the time.

```text
Samsung S25 Ultra, Termux app-private storage:
DIRECTORY_FSYNC = PASS
HARD_LINK = FAIL   (Permission denied)
```

This is consistent with Android's SELinux policy, which denies untrusted
apps (Termux included) the `link` permission on their own app-data files.
The P3-2 hard-link publisher therefore cannot run there. P3-3A asks whether
another primitive gives the same security meaning, **without weakening the
property**.

## 2. The abstract create-only property

```text
AN ACCEPTED RECORD FILE MAY BE CREATED EXACTLY ONCE AT ITS CANONICAL FINAL NAME,
AND AN EXISTING ACCEPTED FILE IS NEVER SILENTLY REPLACED.
```

Every admitted backend must provide all of the following:

- no overwrite of an existing final path;
- no last-write-wins;
- no silent replacement;
- crash-safe detection of incomplete publication;
- file contents fsynced before publication;
- a directory fsync after it;
- a canonical re-read after publication (the tool's post-write check);
- malformed or interrupted state fails closed;
- no automatic repair;
- no ambiguity between accepted and pending state.

The probe proves these per backend. It publishes once, re-reads, and then
checks two refusals: a second publish is refused, and a **racing primitive
call that skips the pre-check** is refused by the primitive itself. The
original bytes must stay untouched.

## 3. Candidates evaluated

| # | Candidate | Verdict |
| --- | --- | --- |
| A | `renameat2(…, RENAME_NOREPLACE)` | viable. Atomic; fails `EEXIST` if the target exists; ext4 and f2fs support the flag; exported by bionic from API 30 and by glibc 2.28+; called through libc, or the raw syscall if libc does not export it |
| B | `O_CREAT\|O_EXCL` directly on the canonical final path | never overwrites, but its crash states are weaker (§5): **evaluated, not admitted** |
| C | temporary file + `renameat2(RENAME_NOREPLACE)` | this is A as implemented: **`RENAME_NOREPLACE_V1`** |
| D | `link` / `linkat` | the existing **`HARDLINK_PUBLISH_V1`**. Denied on the S25 |
| E | exclusive `mkdir` of a per-record directory + file inside | rejected. It changes the record layout (a directory instead of a file), so it would need a new strict-read format for no security gain over A |
| F | other no-clobber primitives: `RENAME_EXCHANGE`, `O_TMPFILE` + `linkat` | `RENAME_EXCHANGE` swaps rather than refuses, so it is refused. `O_TMPFILE` + `linkat` still needs link permission, so it is as unavailable as D on Android |

**Plain `rename()` / `os.replace()` / `shutil.move` are refused.** On POSIX
they atomically *replace* an existing destination, which is exactly the
silent-replacement failure the property forbids. The publisher contains
none of them (AST-tested), and there is **no fallback** from an unavailable
`renameat2` to an overwriting rename (tested).

## 4. `RENAME_NOREPLACE_V1` analysis

```text
open(pending, O_CREAT|O_EXCL|O_NOFOLLOW) -> write canonical bytes -> fsync(pending)
  -> renameat2(pending, final, RENAME_NOREPLACE) -> fsync(directory) -> strict re-read
```

- If the final exists, `renameat2` fails with `EEXIST`. The pending file is
  removed, the existing final is untouched, and the result is
  `RECORD_EXISTS` / `ENVELOPE_EXISTS`.
- If `renameat2` is unavailable (`ENOSYS`, `EINVAL`, `EPERM`, `EACCES`,
  `EOPNOTSUPP`), publication fails and the backend is reported
  `UNAVAILABLE`. It never degrades.
- The rename is atomic within the directory. After any crash **exactly one
  name** exists, either the pending file or the final.

## 5. `DIRECT_O_EXCL_V1` analysis

```text
open(final, O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW, 0600) -> write -> fsync(file) -> close -> fsync(parent) -> strict re-read
```

| Crash window | What exists | Strict read |
| --- | --- | --- |
| created, zero bytes | an empty file at the canonical final name | `RECORD_ZERO_BYTES`: refused, never deleted |
| partial bytes written | a truncated file at the final name | `RECORD_MALFORMED` (non-canonical, or it does not parse) |
| full bytes, file fsync missing | a complete file before a power loss; possibly zero or partial after one | complete: the name matches the digest (it was the owner-confirmed record); damaged: refused as above |
| file fsynced, directory fsync missing | the entry may or may not survive a power loss | absent (safe retry) or complete |
| process dies before the canonical re-read | a complete, fsynced file | verifies. The owner re-runs `verify-replica`; the tool had not yet reported success |

Strict loading can classify every one of these safely. The filename binds
the record digest, so a damaged file can never be accepted. A separate
pending state is therefore **not needed for safety**.

It is still **not admitted in V1**, because recovering from its crash
states means the owner must remove a file that carries an
**accepted-record name**. That breaks "no ambiguity between accepted and
pending state" at the name level, and it trains exactly the wrong recovery
habit: deleting files named like accepted records.

A and D confine crash residue to a `.pending-*` name. Admitting B later
would need a separate owner decision (P33A-D1).

## 6. Crash matrix

The classes are SAFE_RETRY, INCOMPLETE_FAIL_CLOSED, MANUAL_RECOVERY_REQUIRED,
and IMPOSSIBLE_BY_PRIMITIVE.

| Interruption | `HARDLINK_PUBLISH_V1` | `RENAME_NOREPLACE_V1` | `DIRECT_O_EXCL_V1` (not admitted) |
| --- | --- | --- | --- |
| before the pending create | SAFE_RETRY | SAFE_RETRY | — |
| pending zero/partial, not fsynced | INCOMPLETE_FAIL_CLOSED (`REPLICA_PENDING_WRITE`) → MANUAL | the same | — |
| pending complete, not yet published | INCOMPLETE_FAIL_CLOSED → MANUAL | the same | — |
| final created, zero bytes | IMPOSSIBLE_BY_PRIMITIVE (the final only ever appears as a link to a fully fsynced file) | IMPOSSIBLE_BY_PRIMITIVE | INCOMPLETE_FAIL_CLOSED (`RECORD_ZERO_BYTES`) → MANUAL, on an accepted name |
| final partial | IMPOSSIBLE_BY_PRIMITIVE | IMPOSSIBLE_BY_PRIMITIVE | INCOMPLETE_FAIL_CLOSED (`RECORD_MALFORMED`) → MANUAL, on an accepted name |
| both pending and final present | INCOMPLETE_FAIL_CLOSED (crash after link, before unlink) → MANUAL | IMPOSSIBLE_BY_PRIMITIVE (the rename moves the name) | — |
| published, directory fsync missing | SAFE (either name set survives: pending → fail closed; final → complete) | SAFE (one name survives) | SAFE_RETRY, or complete |
| published, before re-read | complete; owner re-verifies | complete | complete |
| final already exists | refused (`EEXIST`) | refused (`EEXIST`) | refused (`EEXIST`) |

`RENAME_NOREPLACE_V1` is **at least as safe** as the hard-link V1
backend: it has one crash state fewer (no two-name state), and none of
them is worse. It is therefore admitted and **preferred**.

## 7. Backend abstraction and admission

`create_only_publish.publish(directory, final_name, data, backend=…)` is the
single create-only publisher. Both record and envelope writers use it.

| Backend | Status | Preference |
| --- | --- | --- |
| `RENAME_NOREPLACE_V1` | admitted | 1 |
| `HARDLINK_PUBLISH_V1` | admitted | 2 |
| `DIRECT_O_EXCL_V1` | evaluated, **not admitted** | — |

`select_backend` picks the first **admitted** backend whose probe passed,
else `NONE`. The choice is deterministic and depends only on probe results.

- **When the probe runs.** Each `append` / `append-envelope` probes the
  replica's parent directory (temporary files only) and publishes with the
  admitted backend.
- **Admission rule (amends P3-3 §25.1).** A real replica's filesystem is
  `P3_STORAGE_CAPABLE` only if every common check passes (exclusive create,
  file fsync, strict directory fsync, symlink detection, canonical re-read,
  cleanup) **and** `admittedBackend ≠ NONE`. Directory fsync stays
  REQUIRED. Hard links alone are no longer required.

```text
storage backend != record authority
```

## 8. Mixed-backend replicas

**Allowed.** Replica A and Replica B may use different admitted backends.
Both satisfy the same abstract contract and publish byte-identical
canonical records under identical names. Tested: A via hard link, B via
rename-noreplace, `compare-replicas` verified, classification `CURRENT`.

The backend identity **never** enters any of these (tested):

- the `OwnerFreshnessRecordV1` digest;
- the envelope or package digests;
- `REPLICA.json`: the real Replica A manifest is unchanged, and no schema
  change is needed;
- the acceptance-store manifest.

It is recorded for auditability **as evidence only**, in the
`publicationBackend` field of every `append` / `append-envelope` result and
in the probe output. The owner keeps it in the ceremony notes.

## 9. Strict read (refined)

`load_replica` / `load_acceptance_store` refuse all of the following:

- a zero-byte final (`RECORD_ZERO_BYTES` / `ENVELOPE_ZERO_BYTES`, new);
- truncated or malformed canonical bytes (`RECORD_MALFORMED`);
- a filename/digest mismatch (`RECORD_NAME_MISMATCH`);
- a version gap or a duplicated version;
- any `.pending-*` artifact (`REPLICA_PENDING_WRITE`);
- any other temporary or unexpected entry (`REPLICA_UNEXPECTED_ENTRY`,
  including `*.json.tmp` and `.DS_Store`);
- a symlink in place of a regular file.

A symlink at a final name also blocks publication, because `lexists` sees
it, and it is never followed.

**No damaged final is ever deleted or rewritten by the tool.**

## 10. Storage capability output

The probe reports the common checks and each backend separately:

```json
{
  "result": "P3_STORAGE_CAPABLE",
  "checks": {"exclusiveCreate": true, "fileFsync": true, "directoryFsync": true,
             "symlinkDetection": true, "canonicalReread": true, "cleanup": true},
  "backends": {"renameNoReplace": "PASS", "hardlinkPublish": "FAIL", "directExclusiveFinal": "PASS"},
  "admittedBackend": "RENAME_NOREPLACE_V1",
  "evaluatedNotAdmitted": ["DIRECT_O_EXCL_V1"],
  "failure": null
}
```

Admission is never a single generic boolean, and `admittedBackend = NONE`
means `P3_STORAGE_INCAPABLE`.

## 11. Termux probe (prepared; not run by this task)

`services/owner-memory-control/tools/android_p3_probe.py` is a standalone
script: standard library plus `ctypes`, no repository imports, no network.
To run it on the phone, copy the file into Termux's home directory by the
owner's own means, then:

```text
python android_p3_probe.py
```

It uses a fresh `mkdtemp` under `$TMPDIR` (Termux private app storage). It
refuses to run:

- on `/sdcard`, `/storage`, `/mnt`, or `/data/media`;
- anywhere outside `/data/data/com.termux/` or `/data/user/0/com.termux/`;
- anywhere inside an owner replica or acceptance store.

It cleans up after itself and prints only:

```text
ANDROID_P3_PROBE
directory_fsync=PASS|FAIL
hardlink=PASS|FAIL
rename_noreplace=PASS|FAIL|UNAVAILABLE
direct_o_excl=PASS|FAIL
symlink_detection=PASS|FAIL
canonical_reread=PASS|FAIL
cleanup=PASS|FAIL
admitted_backend=RENAME_NOREPLACE_V1|HARDLINK_PUBLISH_V1|NONE
```

Expected on the S25 from the observation: `hardlink=FAIL`,
`directory_fsync=PASS`. `rename_noreplace` is **not yet known**. Android's
app seccomp filter and SELinux policy decide it, and only the probe settles
it. If it reports `UNAVAILABLE` or `FAIL`, the S25 remains
`admitted_backend=NONE` for V1.

### 11.1 Probe portability fix (fail-contained)

**Observed on the real S25 Ultra**, in Termux private storage with Python
3.14:

- a shell `ln a b` gave `Permission denied`;
- `android_p3_probe.py` then crashed with
  `AttributeError: module 'os' has no attribute 'link'`, before printing any
  result.

That was a **probe bug**, not storage evidence. The fix:

- **Hard-link backend.** `os.link` is never assumed:
  - if the attribute is absent, the result is `hardlink=UNAVAILABLE`;
  - if the call fails (for example `EACCES`), the result is `hardlink=FAIL`.

  Both are backend results, never an abort. The same applies to the
  in-repo publisher (`HardLinkUnavailable`, a subclass of
  `BackendUnavailable`) and to the tool's `probe_storage`.
- **Every backend and every common check is fail-contained.** Any error
  becomes that item's `FAIL`/`UNAVAILABLE`. `rename_noreplace`,
  `direct_o_excl`, `directory_fsync`, `symlink_detection`, and
  `canonical_reread` are always evaluated. `os.symlink` is not assumed
  either.
- **The complete result block is always printed.** The only exceptions are
  the fundamental safety preconditions: shared storage, not Termux
  private storage, inside a replica, or failure to create the temporary
  directory.
- **Regression tests.** They cover:
  - `os.link` absent;
  - `os.link` permission denied;
  - rename-noreplace still evaluated after a hard-link failure;
  - `admitted_backend=RENAME_NOREPLACE_V1` when it passes;
  - `NONE` when no admitted backend passes;
  - unexpected errors contained;
  - a common-check failure contained;
  - `main()` always printing the block;
  - the tool probe and publisher without `os.link`.

The S25's `rename_noreplace` result is **still unknown** until the fixed
probe is re-run on the phone. The S25 remains not admitted.

## 12. S25 independence nonclaims

Even with `admitted_backend=RENAME_NOREPLACE_V1`, **phone capability is
not P3-3 completion**. Still required, separately:

- a physical rollback path distinct from Replica A;
- no automatic synchronization with Replica A;
- an understood backup and restore relationship (§13);
- an understood agent write boundary: an agent that can reach the phone
  (ADB, a Termux SSH server, shared automation) would erase the benefit;
- a real Replica B, initialized empty via `init-real-replica
  --other-replica <A>`;
- accepted independence evidence (`check-independence` plus owner
  evidence).

## 13. Android backup / restore evidence required before admission

Evidence requirements only; no live account was examined:

| Question | Evidence required |
| --- | --- |
| Is Termux app-private data included in Android app backup (Google One / Android backup)? | the Termux manifest `allowBackup` setting and backup rules, plus the owner's device backup settings |
| Does Samsung Smart Switch copy app data, including Termux? | the Smart Switch configuration and whether a Smart Switch backup exists, on PC, external media, or cloud |
| Does Samsung Cloud back up app data? | the device settings |
| Could a phone restore (Smart Switch, Google restore, factory-reset restore) roll Replica B back to an older state? | the answer to the rows above. Yes or unknown means a rollback path to record |
| Could Replica A and Replica B share one backup path? (for example, a laptop backup of a Smart Switch archive that also holds the WSL disk) | the owner's backup topology |
| Is the phone storage encrypted and locked when idle? | device settings (custody, not rollback) |

An answer of YES or UNKNOWN for a shared or restorable path means
independence is **not established**.

## 14. Hidden assumptions

> What assumption could make Android support appear safe while it is wrong?

1. **"If O_EXCL prevents overwrite, then every crash state is safe."**
   Rejected. O_EXCL guarantees no *overwrite*, not a *complete* file. A
   direct-O_EXCL crash leaves a zero-length or partial file at the accepted
   name. Content-addressed names make that fail closed, but the only
   recovery is removing a file named like an accepted record. That is why
   `DIRECT_O_EXCL_V1` is not admitted. Durability also still depends on the
   file fsync *and* the directory fsync.
2. **"If the phone is a separate device, it is automatically an independent
   freshness domain."** Rejected. Smart Switch, Google backup, Samsung Cloud,
   a PC backup of a phone archive, or an agent with ADB or SSH reach can put
   both replicas on one rollback or write path. A separate device is
   necessary, not sufficient (§12, §13).
3. **"A passing probe proves the primitive on every future write."** No.
   Android updates can change seccomp or SELinux policy. That is why every
   `append` re-probes and publishes only with a backend that just passed.
4. **"renameat2 exists in libc, so it works."** No. The seccomp policy,
   SELinux, or filesystem support can refuse it. The probe's racing check
   exercises the real primitive, and `UNAVAILABLE` never falls back.

## 15. Decisions

| ID | Question | Decision in this record |
| --- | --- | --- |
| P33A-D1 | admit `DIRECT_O_EXCL_V1`? | **no** in V1 (§5); it needs a separate owner decision |
| P33A-D2 | backend preference | `RENAME_NOREPLACE_V1` > `HARDLINK_PUBLISH_V1`, by crash semantics (§6) |
| P33A-D3 | mixed backends across replicas | **allowed** (§8) |
| P33A-D4 | where backend identity is recorded | evidence only (append output, probe output), never in a digest or manifest |
| P33A-D5 | hard-link requirement from P3-3 §25.1 | **replaced** by "at least one admitted create-only backend"; directory fsync stays required |

These are proposals for owner acceptance.

## 16. Nonclaims

P3-3A does **not** establish any of the following:

- S25 admission;
- P3-3 completion (**`P3_3_STORAGE_INCOMPLETE`** remains);
- Replica B;
- independence;
- any backup analysis;
- real freshness;
- any owner record or envelope;
- any K-ROOT, K-WIT, registry, ledger, witness, hold, RecoveryEpoch,
  INITIAL_CUSTODY, PR-1B, A1–A7, or First Memory progress.

```text
P3-3A ANDROID STORAGE COMPATIBILITY ONLY   P3-3 REMAINS STORAGE_INCOMPLETE
REAL REPLICA A UNTOUCHED   REAL REPLICA B ABSENT   NO REAL RECORD 1   REAL FRESHNESS REMAINS UNKNOWN
NO DEV CONTACT   NO CLOUD CONTACT   NO OWNER KEY   NO K-ROOT ACTIVITY   NO K-WIT   NO REGISTRY
NO LEDGER   NO WITNESS STATE   NO HOLD   NO RECOVERY EPOCH   NO INITIAL_CUSTODY
PR-1B NOT AUTHORIZED   A1-A7 NOT AUTHORIZED   FIRST MEMORY NOT AUTHORIZED
```
