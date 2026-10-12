# Slice 15B2b-B1b-3e — E-19 Maintenance Observer and Two-Release-Aware Verification

Status:

- **REPOSITORY-ONLY ENGINEERING SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`.
- **Base:** main `53dad7b2f7f5f620674b070e4eb9a380e16d44a9`, the merge of PR #188. Post-merge workflow `38278859185`
  succeeded. That workflow result does **not** establish M-B10 DR-5 W10_1 EQUAL or a fresh host POST; that
  preservation check is still outstanding.
- **What this slice adds:** a read-only observer and pure verification functions for the merged
  `UPGRADE_FROM_P1B10_DEV_SYNTHETIC` contract
  ([E-19 release maintenance](slice-15b2b-b1b3e-e19-release-maintenance.md)).
- **What it does not change:** the contract tool `e19_p1b10_upgrade.py` (pinned, `18d07807…`), the merged candidate
  drop-ins, every historical M-B10 operator, and all evidence.
- **What it does not do:** stage, select or retire a release; stop or start a unit; run daemon-reload; install a
  drop-in; load K-WIT or K-ACT; write HELD or the ledger; grant an acceptance.

```text
observed != accepted;  UNKNOWN (null) != drift ("ABSENT" / a different value);  POST9A-R VERIFIED != acceptance
maintenanceReady = an exact phase AND the restart boundary exactly effective;  readiness != a go
```

## 1. The observer (`services/owner-memory-control/tools/e19_maintenance_observer.py`)

`observe(inputs)` runs as root on DEV with the release interpreter, design only. It takes exactly these inputs:

- `newRelease`, which must equal the repository's `NEW_RELEASE`. It is `None` today, so `observe` refuses with
  `NEW_RELEASE_NOT_ESTABLISHED`. No NEW hash is invented.
- `afterCursor`: the accepted U0 journal cursor, or `null` for the self-anchored U0 candidate.
- the W10 arguments.

It returns one bundle `{observation, healthCapture, w10Report, w10ReportSha256, socketContacted}`, where
`observation` is exactly the closed document the merged classifier judges.

| Fact | Read (root, read-only) |
| --- | --- |
| release set, `current`, interrupted operations | `listdir /opt/lilith-authority-dev` and `releases/` (`.<sha>.staging`, `.current.tmp` are visible); `readlink current` (absent → `"ABSENT"`, a directory → `"NOT_A_SYMLINK"`) |
| per-release tree | `release_tree_verified`: the installer's `release_tree_failures`, restated read-only and bounded. The manifest is canonical for the SHA; every file has its bytes; root-owned; modes; no symlink; nothing extra outside `venv/`. A test proves it agrees with the installer. **Never** the single-release installer `status`, **never** E-01. |
| witness service and sockets, signer, broker PID | one `systemctl show -p …` (fixed properties) |
| effective restart boundary | the unit properties (`Restart`, `StopWhenUnneeded`, `RefuseManualStart`, `DropInPaths`, `NeedDaemonReload`) plus the SHA-256 of each installed drop-in, compared with the merged candidate pins; a missing drop-in is `"ABSENT"` |
| witness cwd | `readlink /proc/<MainPID>/cwd`, only while RUNNING (a retired tree shows as `… (deleted)`) |
| journal cursor and loads | `journalctl -n 1 -o json` → `__CURSOR`; `journalctl -u lilith-recovery-witness.service -o json --after-cursor=<U0 cursor>` → distinct invocation ids, one per exec, i.e. per K-WIT load attempt; the signer's invocations ever (must be none) |
| custody, trust, HELD files | SHA-256 via `O_NOFOLLOW`, bounded at 64 MiB: CURRENT (ciphertext, never decrypted), K-ACT publication, K-WIT blob (ciphertext), both anchors, the registry, `chain/1.json`, `witness.json`, the HELD record, owner inputs, ledger files, unit files, CLIs; lstat-only identities (the host key is never opened); listings of the credstore, the custody root (names only), the witness credentials and the hold store |
| ledger head, committed genesis | the **unchanged** W10 verifier (`mb10_held_verifier.evaluate`, which runs the W9 / M-B6 ledger judgement). If W10 and seamed W9 are exact, the head is the accepted one. A `LEDGER_*` failure is drift (`LEDGER_NOT_EXACT`). Otherwise it is UNKNOWN. A missing genesis is `"ABSENT"`. |
| broker | the **unchanged** broker `preservation` read (`evaluate_preservation(collect())`) |
| activation | `lilith-activation-verify`: exactly one line, verbatim |

**UNKNOWN versus drift.** A read that cannot be made (a command fails, the output is unparseable, a file is
unreadable) is `null`, which the classifier reports as `US_UNKNOWN`: re-observe read-only. A path that does not exist
is the observed string `"ABSENT"`, and any different value is observed drift. The classifier reports drift as HALT
(preserved facts), STOP_BOUNDARY or a release-set STOP.

**Socket contact.** The observer calls the owner CLI `health` **only** when all of the following hold:

- the service is `active`/`running` with a MainPID;
- both sockets are `active`;
- the restart boundary is exactly effective.

It then re-reads the InvocationID and MainPID. If they changed, there is no capture and health stays `null`. A
stopped, failed, activating or sockets-left-listening witness is never contacted. `socketContacted` records whether
the call was made. The health reply is judged by the unchanged `mb9_witness_verifier.check_health`, and any failed
reply check becomes an observed `NOT_EXACT:<failures>` classification.

## 2. Two-release-aware verification (pure)

- **`verify(bundle, u0_acceptance, replacement=None)`.** Runs the merged classifier against the owner-accepted U0
  bundle; the replacement acceptance is needed only for U5. It adds:
  - `restartBoundaryReasons`: each property or drop-in that differs;
  - `maintenanceReady`: true only on an exact phase **and** an exactly effective boundary.

  A missing or ineffective boundary always refuses maintenance readiness. Because health is never captured without
  the boundary, the classifier then reports `US_RESTART_BOUNDARY_NOT_EFFECTIVE` or `US_UNKNOWN`.
- **`post9a_r_evidence(bundle, denials, u0_acceptance)`.** Assembles the merged POST9A-R evidence from **one**
  bundle:
  - its observation;
  - its own W10 report, which must still match the bundle's `w10ReportSha256` (otherwise `W10_NOT_BOUND`);
  - its own bound health capture (before and after identities);
  - the three denial-proof transcripts.

  Each transcript is PASS only on exit 0, LF-only output, and the proof's exact final line:
  - `MB9_WITNESS_DENIAL_PROOF=PASS phase=P1B-9b denied=<n≥1> allowed_by_design=<m> allowed=0`;
  - `MB10_HOLD_DENIAL_PROOF=PASS phase=P1B-10 denied=<n≥1> allowed=0`;
  - `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5`.

  The evidence is bound to the accepted U0 baseline digest and to the actual witness incarnation.
- **`post9a_r(...)`.** The merged `post9a_r` over that evidence. It returns `acceptanceGranted: false`. The
  replacement acceptance remains the owner's verbatim statement and local record (merged contract §4.6).

`w10OutputSha256` is the digest of the in-process W10 report (canonical JSON), not of a streamed verifier stdout.

## 3. Restart-boundary verification

It uses only the merged candidate drop-ins (`e19_witness_restart_dropins/`, pins `661a486d…` / `adef5469…`) and the
merged `RESTART_BOUNDARY`. The checks are read-only: installed bytes plus effective `systemctl show` properties. A
missing drop-in, changed bytes, an extra `DropInPaths` entry, `Restart=on-failure`, `StopWhenUnneeded=no` or a
pending reload each refuse maintenance readiness. Nothing is installed or reloaded.

## 3a. Owner-review corrections on `7742b6fc` (CHANGES REQUIRED, F1–F5)

| Finding | Correction | Regression |
| --- | --- | --- |
| **F1** bytecode | `sys.dont_write_bytecode = True` is set before any tool or release import. Importing release modules from `current` as root would otherwise write `__pycache__` into `releases/<sha>`, a mutation that also fails the tree check. **The live operator must still run the interpreter read-only (`-I -B`, as the `mb6_operator` BOOT loader does)**, because a top-level script import compiles before the flag runs. | `test_p4_f1_observer_execution_writes_no_bytecode`: a subprocess with no `-B` and no `PYTHONDONTWRITEBYTECODE` runs the observer and imports a release-shaped module; no `__pycache__` or `.pyc` appears anywhere |
| **F2** W10 binding | The W10 report's `witnessInvocationId`, `witnessMainPid` and `witnessNRestarts` must equal the observation's witness identity. At observe time a non-matching report is discarded, so the ledger head and genesis become UNKNOWN. In `post9a_r_evidence` it is refused (`W10_NOT_THIS_OBSERVATION`), even when its own digest is valid. | `test_p1_f2_a_stale_w10_report_cannot_be_spliced_into_post9a_r` (a U0 report with a U4 observation) |
| **F3** unit identity | `FragmentPath` is read. Each witness unit must be exactly `/etc/systemd/system/<unit>`, and no shadow fragment or `.d` directory may exist in any `SHADOW_BASES` location (the P1B-10R list, reused from `mb11_restart_boundary_install`). Failures appear in `unitFragmentReasons`, and `maintenanceReady` requires that list to be empty. | `test_p2_f3_a_shadow_unit_or_foreign_fragment_refuses_readiness` (`/run/systemd/system` unit, `/run/systemd/system/<socket>.d`, transient fragment) |
| **F4** journal retention | Before witness loads are counted after the baseline cursor, `_cursor_retained` reads the first entry of `journalctl --cursor=<C>` (one bounded line, then journalctl is stopped). The cursor counts as retained only if that entry's `__CURSOR` is exactly `C`; a vacuumed cursor lands on the nearest entry and is `False`. Not retained or unreadable leaves the invocation list `null` (UNKNOWN) and refuses readiness. The same applies to the U0 candidate. The exact live seek behaviour is a DEV proof obligation for the operator slice. | `test_p5_f4_an_unretained_baseline_cursor_makes_loads_unknown`, `test_p5_f4_retention_is_proven_by_the_exact_entry_at_the_cursor` |
| **F5** release `venv` | Before `venv/` is excluded from the walk, `lstat` must show a genuine directory, owned by the canonical owner, mode `0755`. A symlink, a regular file, a wider mode or a missing `venv` fails the tree check. **Installer parity gap (recorded, not changed here):** `install_authority_dev.release_tree_failures` removes `venv` from the walk without this check. Closing it is a separate installer change. | `test_p3_f5_the_release_venv_must_be_a_genuine_root_directory` |

## 4. Tests

The new suite `test_b1b3e_e19_maintenance_observer.py` has 34 tests (28 plus the six F1–F5 regressions in §3a) and runs on a POSIX synthetic host. That host is
a temporary root with real release trees (installer `manifest_for` / `canonical`), custody files and the real
candidate drop-ins. It fakes only systemd, the journal, the owner CLI, activation, W10 and the broker. The custody
digest pins are patched to the synthetic bytes; the drop-in pins are the real ones.

- **The phase path:**
  - every phase U0 → U5 is observed and verified exactly, with `maintenanceReady`;
  - the self-anchored U0 candidate becomes the accepted U0 bundle;
  - POST9A-R VERIFIED at U4 with two releases installed, without any acceptance being granted;
  - U5 is a STOP without the local acceptance and exact with it.
- **UNKNOWN versus drift:**
  - unreadable units, journal, files, activation, broker and W10 are UNKNOWN;
  - an absent or replaced credential, registry, HELD, hold listing, credstore, custody, owner inputs, CLIs,
    activation, broker, ledger or genesis is HALT;
  - signer activity is HALT; a reboot is a STOP.
- **Release sets:** staging and selector residue; a third release; `current` missing or not a symlink; tampered,
  extra, symlinked or wrong-mode files in NEW; a changed OLD manifest; installer-equivalence of the tree check.
- **Restart boundary:** six boundary failures, each in a running and a stopped phase, refuse readiness without socket
  contact; a boundary failure refuses the U0 baseline.
- **Socket contact:** no contact when stopped, failed, activating or sockets-left-listening; an identity change
  around health gives no capture; a drifted health reply is observed drift.
- **Forged inputs:** forged U0 bundles; forged denial transcripts (wrong phase, exit 1, CRLF, `allowed=1`, PASS not
  last, missing proof); a tampered W10 report; a foreign health capture; a non-exact W10.
- **Read-only:** a byte, mode, mtime and inode snapshot of the whole synthetic host is unchanged by observing every
  phase; the default host commands are only `systemctl show`, `journalctl` reads, `lilith-activation-verify` and
  owner `health`; the code contains no mutating operation.
- **Pins:** the contract pin, the drop-in pins, and the host paths, which equal the installer and `mb6_operator`
  constants.

## 5. Remaining requirements (not authorized)

1. **The post-merge M-B10 preservation.** DR-5 W10_1 EQUAL and a fresh `mb10` host POST after PRs #186, #187 and
   #188.
2. **The witness restart-boundary installer and status tool**, following P1B-10R. The boundary must be effective
   before any U0 baseline can be accepted; today the observer would correctly report it as not effective.
3. **An operator form** that streams this observer as a pinned in-memory bundle over the existing transport
   (`mb6_operator` BOOT pattern, interpreter `-I -B`). There is no DEV run yet. Its first live use must also
   prove the `journalctl --cursor` retention behaviour (F4).
4. **The NEW release**, built from protected main, attested and pinned in `NEW_RELEASE` / `NEW_MANIFEST_SHA256` by a
   merged owner record. Until then `observe` refuses.
5. **The re-pinned two-release host-read path** for the remaining `mb9` / `mb10` reads (merged record §8), the
   installer stages, and the reviewed stop and start paths.
6. **Ordering note.** `SIGNER_DARK` requires no signer drop-ins, so installing the P1B-10R signer overlay before
   this transition would HALT the contract. Either the E-19 transition precedes the P1B-10R install, or the owner
   amends that one fact.

## 6. State

```text
E19_MAINTENANCE_OBSERVER = SOURCE ONLY (read-only; refuses until NEW_RELEASE is pinned); NOT RUN ON DEV
TWO_RELEASE_VERIFICATION = verify / post9a_r_evidence / post9a_r (pure; acceptanceGranted = false)
WITNESS RESTART BOUNDARY = CANDIDATE FILES, NOT INSTALLED; read-only verification only
POST-MERGE M-B10 PRESERVATION (after #186 / #187 / #188) = NOT ESTABLISHED
E19-D1 … E19-D5 = PROPOSED;  LIVE_MUTATION = NONE;  DEV_CONTACT = NONE
RELEASE / current / WITNESS / K-WIT / CUSTODY / HELD / LEDGER / SIGNER = UNCHANGED;  authorityGranted = false
```
