# Slice 15B2b-B1b-3e — E-19 Witness Restart Boundary: Installer and Read-Only Verification

Status:

- **REPOSITORY-ONLY ENGINEERING SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`.
- **Base:** main `ee77aa7c113281fb6c32247b11b49b4cd1b0f585`, the PR #189 merge. Its workflow `38295150689` succeeded.
  The post-merge M-B10 preservation (DR-5 W10_1 EQUAL plus a fresh host POST) is still outstanding.
- **What this slice adds:** the tool `services/owner-memory-control/tools/e19_witness_restart_boundary_install.py`
  (SHA-256 `8691cd0558b8deceba3e424c0a63487b5bca928991f37d87b05c5f68fdc0b339`),
  which installs and verifies the witness restart boundary that the merged E-19 contract requires before any U0
  baseline (`e19_p1b10_upgrade.py` §4.4, E19-D3, PROPOSED).
- **What it reuses unchanged:** the three merged candidate drop-ins (`e19_witness_restart_dropins/`, pins
  `661a486d…`, `adef5469…` ×2) and the reviewed P1B-10R pattern (`mb11_restart_boundary_install.py`).
- **What it does not do:** no install, daemon-reload, witness restart, K-WIT load, signer start, P1B-10R action,
  release replacement or authority activation happens. No code here reloads, starts, stops or restarts a unit.

```text
installed != reloaded != effective != U0 accepted;  the witness RUNS throughout: same incarnation, no new K-WIT load
```

## 1. Phases and transitions

Unlike the signer, the witness **runs** during this stage. Every phase therefore also requires:

- the accepted incarnation `8af12bd64d024d0eba56bbcedbc534a6` / `1580`, active and running with NRestarts 0;
- both sockets active;
- **no witness invocation (K-WIT load) after the plan's journal cursor**, with that cursor proven still retained
  (`journalctl --cursor` returns exactly that entry; the E-19 observer's F4 rule).

| Phase | Facts |
| --- | --- |
| `WRB_0_PRE_INSTALL_EXACT` | release fragments byte-exact (`E.OLD_RELEASE` assets: service `9f78130c…`, owner socket `d260917f…`, signer socket `ad345d18…`), `FragmentPath` = `/etc/systemd/system/<unit>`, loaded, static; no overlay and no shadow anywhere in the P1B-10R `SHADOW_BASES`; release defaults in effect (`Restart=on-failure`, sockets `StopWhenUnneeded=no`, `RefuseManualStart=no`); `DropInPaths` empty; `NeedDaemonReload=no`; activation exactly dark; the witness as above |
| `WRB_1_INSTALLED_RELOAD_PENDING` | the three overlay files exact (bytes, `root:root`, 0644, one link; directories 0755); `NeedDaemonReload=yes` on all three units, which still report the release defaults |
| `WRB_2_EFFECTIVE_EXACT` | `NeedDaemonReload=no`, and the effective properties plus drop-in bytes are exactly the merged `RESTART_BOUNDARY` (service `Restart=no`; sockets `StopWhenUnneeded=yes`, `RefuseManualStart=yes`; exact `DropInPaths`) |
| `WRB_PARTIAL_INSTALL` | a strict prefix of the install's own writes (directory, then the file, unit by unit), including an `O_EXCL` file created but not yet written |
| `WRB_FOREIGN_OR_ALTERED` | anything else in an overlay directory (altered bytes, extra files, wrong metadata, a symlink, an out-of-order directory) or any shadow fragment or `.d` |
| `WRB_UNIT_NOT_EXACT` | fragment bytes or path, load or enablement, a pending reload at WRB_0, a mixed reload state, or an effective property that differs after reload |
| `WRB_WITNESS_NOT_THE_ACCEPTED_INCARNATION` | stopped, restarted, another identity (including the historical B3 one), sockets inactive, or **any** invocation after the plan cursor |
| `WRB_AUTHORITY_NOT_DARK` / `UNCLASSIFIED_STOP` | activation not dark / unknown evidence: units unreadable, journal cursor not retained or unknown, no activation output |

The transitions are never merged into one:

1. **`plan`** (read-only) requires exact WRB_0. It returns the plan digest and the plan cursor. The digest binds the
   fragments, every unit property including the witness InvocationID / MainPID / NRestarts, the shadows, the
   activation line and the candidate pins. The cursor binds every later load count.
2. **`install <plan-digest> <plan-cursor>`** (one owner go). A fresh observation, counted after the plan cursor, must
   be exact WRB_0 with an equal digest. The install then:
   - creates each directory with `mkdir` (never existing) and each file with `O_EXCL`;
   - fsyncs them;
   - never overwrites, repairs, removes or rolls back anything;
   - performs no reload, start, stop or restart.

   The read-back must be WRB_1. The candidate bytes are re-hashed against the merged pins before any write. A second
   use is refused (`NOT_WRB_0:WRB_1`).
3. **`systemctl daemon-reload`** is the owner's **separate** command under its own authorization. The tool never
   runs it.
4. **`expect WRB_2_EFFECTIVE_EXACT <plan-cursor>`** (read-only) verifies the effective configuration, an unchanged
   witness incarnation, and zero K-WIT loads since the plan.

## 2. What else sees the overlay

- **DR-5: unchanged.** This is proven statically from the pinned script (`prove_dr5_unaffected`):
  - no DR-5 list names a path at or beneath a witness `.d` directory;
  - `/etc/systemd/system` is a write-denied parent;
  - the only `systemctl` uses are sudo-denial probes of the mutating verbs in `AB_UNIT_VERBS`, none of which reads
    unit configuration.

  The W10_1 DR-5 targets are therefore unaffected.
- **PR-1A host observer: changes by exactly the overlay.** Its `DropInPaths`, drop-in entries and
  `/etc/systemd/system` inventory change by exactly the three candidates (`expected_observer_changes`).
  `observer_delta_reasons` flags any other change, including any change of the witness incarnation. Later host-POST
  byte comparisons must use it.
- **W9 verifier and installer `status`: fail during WRB_1 only.** Both require `NeedDaemonReload=no`, so
  W9/W10-based host reads and `status --expect` fail between install and reload. Install and reload should run
  back-to-back with no routine host read in between. From WRB_2 on they are unaffected, because neither reads
  `DropInPaths` or `Restart`.
- **Compatibility consequence.** With `RefuseManualStart=yes` on both sockets, the reviewed `mb9_operator`
  `restart` form, which starts the two sockets explicitly, will be **refused** once the boundary is effective. Every
  later witness start must use the merged `E.START_COMMAND` (the service only; its `Requires=` pulls the sockets).
- **Ordering.** Only the three witness units change. The merged contract still requires the signer to have no
  drop-ins, so the P1B-10R signer overlay must wait until after the E-19 transition.

## 3. Tests

The new suite `test_b1b3e_e19_witness_restart_boundary.py` has 17 tests and runs on a POSIX synthetic host. The fake
systemd derives the effective properties by parsing the drop-ins it last loaded (with the reviewed `parse_unit`), and
reports `NeedDaemonReload=yes` while the files on disk differ from what it loaded.

- **The full sequence:** WRB_0 → plan → install → WRB_1 → owner reload (fake) → WRB_2. The witness keeps
  `8af12bd6…`/`1580`/0 throughout, with **zero** K-WIT loads. The effective state equals `RESTART_BOUNDARY`, and the
  E-19 observer's own `boundary_reasons` agrees.
- **Witness changes:** a reload that restarts the witness is WRB_WITNESS. A restart, identity change, stop or load
  between plan and install refuses the install, and nothing is written.
- **The plan:** it is state-bound, refuses invalid digests and cursors, refuses a state change, and is single-use.
- **No overwrite:** an existing drop-in is never overwritten, even with the pre-check bypassed (`FileExistsError`,
  bytes unchanged).
- **Partial and foreign installs:** every interrupted install is WRB_PARTIAL. Out-of-order, altered, extra, wrong
  mode, symlinked, a `/run` shadow unit and a `/run` shadow `.d` are each WRB_FOREIGN.
- **Unknown evidence:** unknown units, an unretained or unknown cursor and no activation output are UNCLASSIFIED; a
  non-dark activation is WRB_DARK.
- **Unit state:** fragment bytes or path, a pending reload, every effective property after reload, and a partial
  reload are each WRB_UNIT. The witness must be the accepted running incarnation.
- **DR-5:** unchanged; three mutated scripts are refused.
- **Pins and code:** the release fragments are re-derived from the repository and the release file set; a tampered
  candidate is refused; there are no reload, start or stop calls; writes appear only in `install`, with exactly one
  `O_CREAT` (always `O_EXCL`); bytecode writing is off; the exact host-observer delta is checked.

## 4. Remaining live prerequisites (none authorized)

1. **The post-merge M-B10 preservation.** DR-5 W10_1 EQUAL and a fresh host POST after #186, #187, #188 and #189.
2. **A disposable-runner proof**, like the P1B-10R probe, that on real systemd:
   - the three drop-ins produce exactly `RESTART_BOUNDARY`;
   - `daemon-reload` does not restart an active service;
   - `StopWhenUnneeded=yes` leaves the sockets of an active service running;
   - `journalctl --cursor` returns the exact entry, which the F4 rule relies on.
3. **An operator form** that streams this tool as a pinned bundle (interpreter `-I -B`) over the existing
   transport, then a read-only `observe` + `plan` on DEV.
4. **Owner authorizations:** E19-D3 accepted, an install go naming the plan digest and cursor, and a separate
   daemon-reload authorization. Then `expect WRB_2` and the owner's acceptance of the effective boundary.

## 5. State

```text
WITNESS_RESTART_BOUNDARY = INSTALLER + VERIFIER SOURCE ONLY; NOT RUN; DROP-INS NOT INSTALLED
DR-5 DELTA = EMPTY (proven from the pinned script); HOST OBSERVER DELTA = exactly the three candidates
POST-MERGE M-B10 PRESERVATION = NOT ESTABLISHED;  E19-D1 … E19-D5 = PROPOSED
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  WITNESS / K-WIT / SIGNER / HELD / LEDGER / RELEASE = UNCHANGED
```
