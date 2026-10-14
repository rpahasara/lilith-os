# Slice 15B2b-B1b-3e — M-B11 P1B-10R: Install, Unexpected `P10R_2` Read-Back and Owner Acceptance (2026-10-14)

Status:

- **OWNER ACCEPTANCE RECEIPT (APPEND-ONLY).** This file records the single live P1B-10R install on DEV, its unexpected
  read-back, the independent adjudication, the owner's Option A decision and the post-install preservation. It
  changes no tool, test, pin, workflow or record.
- **Owner decision (Option A, 2026-10-14): the independently verified `P10R_2_EFFECTIVE_EXACT` configuration is
  ACCEPTED as the effective signer restart boundary, and the separately planned `systemctl daemon-reload` for this
  installation is WAIVED.**
- **The install's own result is not rewritten.** It returned `P1B10R_INSTALLED_READBACK_NOT_P10R_1` and the local
  driver stopped with rc 1. That stays the recorded outcome: it was never a normal `P10R_1` success.
- **Reload provenance is UNKNOWN.** Why systemd already loaded the drop-ins is not established (§4). The idle-unit
  explanation is a hypothesis, not proven provenance.
- **The [P1B-10R design record](slice-15b2b-b1b3e-mb11-restart-boundary-p1b10r.md) is not rewritten.** Its §9
  state block (`NOT RUN`, `OVERLAY = NOT INSTALLED ON DEV`) was correct when written and is asserted by
  `test_b1b3e_mb11_restart_boundary_install.RecordTests`. This receipt supersedes it on the installed-overlay
  outcome only, from 2026-10-14. Its §10a assumption (an installed but not reloaded overlay is not loaded) did not
  hold on DEV (§4, §6).
- **Writing this record contacted no live system.** The evidence stays in the owner's local evidence directories (§7).

```text
install rc 0 + both drop-ins written  !=  P10R_1 (read-back was P10R_2)  !=  daemon-reload performed (none by any tool)
P10R_2 observed and owner-accepted  !=  reload provenance known (UNKNOWN)
boundary effective  !=  M-B11 / signer start  !=  K-ACT load  !=  Registry effective  !=  authority  !=  FIRST_MEMORY_READY
```

## 1. Identities

| Item | Value |
| --- | --- |
| main / control | `d9e1aaec37fe1d2fa2534d47f5a6200e2ec62055` (PR #197 merge), clean control clone |
| last DEV deploy | run `38572866000`, success, completed 2026-10-14T13:37:44Z (before the install; no deploy since) |
| install tool | `mb11_restart_boundary_install.py` `428d93b4b36bdb8d7783e2c1f22d3961fd5cf3623ce0ee0d419ab3b81c53c8af` (the E-19 re-pin; equals `e19_operator.TOOL_PINS` and `e19_completion.MB11_REPINNED_SHA256`) |
| boundary module | `mb11_restart_boundary.py` `10147341819c27bb3720a87264ffea78f1bf1c3c2a23d7804ac900370cfe7419` |
| route | the reviewed mb6 BOOT stdin bundle `[mb6_ledger_verifier, mb11_restart_boundary, mb11_restart_boundary_install]` (`e19_operator.Operator.bundled`, release python) over the pinned direct-plink transport with the `lilith-dev-01` hostname guard |
| release binding | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` (E-19 NEW, sole installed) |
| release fragments | service `11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254`, socket `bff5e9275ad1478dd068855465d65542ceb338e5e9236e43d1bd43d7c50c194f` (unchanged) |
| plan digest | `2a004a4195116462d60fdff978229f9a2364427704e4d16d5dec729801106592` |
| witness (unchanged) | `90b28f9d06fd48a1a1bdc3ae39474fb1` / PID `69238` / NRestarts 0 |

## 2. Sequence (2026-10-14, UTC)

1. **Fresh preflight + plan (14:04Z).** `observe` once → `P10R_0_PRE_INSTALL_EXACT`, rc 0. `plan` once → rc 0, the
   plan digest above. Recomputing the digest locally from the observation gave the same value. An earlier attempt
   that day stopped in local preflight because the supplied install-tool pin (`44ab3f04…`) was obsolete; that
   attempt made no DEV contact.
2. **Owner-authorized install (16:12:53–16:13:10Z), invoked exactly once.** `install 2a004a41…6592`: rc 0, stdout
   808 B, stderr empty, `planDigest` echoed. Result **`P1B10R_INSTALLED_READBACK_NOT_P10R_1`**. Read-back
   **`P10R_2_EFFECTIVE_EXACT`**, overlay `EXACT`, reasons `[]`, `reloadPerformedByTool=false`. The driver required
   `P10R_1` and **stopped with rc 1**. There was no follow-up DEV call, retry, reload, repair or rollback.
3. **Independent adjudication (16:18:34Z).** One read-only `observe`, rc 0 → `P10R_2_EFFECTIVE_EXACT`, reasons `[]`,
   `boundary_reasons` `[]`. The local `classify` of the same observation equals the remote one.
4. **Owner decision: Option A** (this record's Status).
5. **Post-install preservation (17:52:19Z acquisition).** One `e19_operator host U5_OLD_RETIRED_REPLACEMENT_ACCEPTED`
   → `host/05`, PASS (§5). Observer delta against `host/04` = exactly the two drop-ins (§5). DR-5: the pinned-script
   proof is EMPTY, and one comparison against the historical deploy log is EQUAL (§5, with its limitation).

## 3. What the installer code proves

`install(digest)` (tool `428d93b4…`), in order:

1. It refuses unless the digest is 64 lowercase hex characters.
2. It verifies both embedded payloads against their pins **before** observing or writing anything.
3. It requires a fresh observation that is exactly `P10R_0` and whose `plan_digest` equals the digest. Otherwise it
   raises `Refused`, exits rc 2 and writes nothing.
4. For each unit in order (service, then socket):
   - `mkdir` the `.d` directory (0755, root:root);
   - create the file with `O_EXCL | O_NOFOLLOW` (0644, root:root);
   - write the payload, `fchmod`, `fchown` and `fsync` it;
   - `fsync` the directory.
5. It then `fsync`s `/etc/systemd/system`.
6. Only then does it re-observe, classify and return. It returns `P1B10R_INSTALLED` only for a `P10R_1` read-back,
   and `P1B10R_INSTALLED_READBACK_NOT_P10R_1` for anything else.

The tool contains no reload, start or stop call. An rc 0 result object therefore proves both drop-ins were fully
written before the read-back. **`reloadPerformedByTool=false` proves only that this tool did not reload. It does
not prove that no other component reloaded systemd.**

## 4. Discrepancy: why the read-back was `P10R_2`

- **Classifier.** In the EXACT overlay branch, `classify` returns `P10R_1` only while no unit reports a drop-in in
  `DropInPaths` and every unit still shows the release defaults (§10a correction). It returns `P10R_2` when both
  units are loaded with exactly the candidate drop-ins and effective values and `NeedDaemonReload=no`. A read-back
  of `P10R_2` therefore means systemd **already had** the drop-ins loaded about 1 s after the writes.
- **Expected basis.** §10a relied on the E-19 PR #190 disposable systemd 255 probe. In that probe, units stayed
  loaded through the install, and adding drop-ins left `DropInPaths` empty until a reload. The WRB install on the
  running witness matched that probe.
- **Hypothesis (NOT PROVEN).** Both signer units are static, inactive and unreferenced. systemd may garbage-collect
  such units from memory. A later query (`systemctl show`) then loads them fresh from disk, new drop-ins included,
  with `NeedDaemonReload=no`.
- **Not excluded.** A `daemon-reload` by another component in the same window would produce the same state, for
  example a package hook, needrestart or another session. The observe form reads no journal and no systemd reload
  timestamps. **Provenance: UNKNOWN.**

## 5. Evidence of the accepted state

**Installed overlay** (independent observation; unchanged at the 17:52Z host read):

| Path | SHA-256 | Size | Metadata |
| --- | --- | --- | --- |
| `/etc/systemd/system/lilith-authority-dev.service.d/` | | | dir, root:root, 0755 |
| `/etc/systemd/system/lilith-authority-dev.service.d/10-no-implicit-restart.conf` | `e3faf9efa91f0238ee6110a33cf6c9f024aca1029fe05bd26fba4c21679c6b92` | 210 B | file, root:root, 0644, 1 link |
| `/etc/systemd/system/lilith-authority-dev.socket.d/` | | | dir, root:root, 0755 |
| `/etc/systemd/system/lilith-authority-dev.socket.d/10-no-reactivation.conf` | `85589f80764311f7e1152cf0e9ea51208662bce25806ceb524777961f579b9b9` | 256 B | file, root:root, 0644, 1 link |

The bytes on disk equal `mb11_restart_boundary.DROPIN_BYTES`. Each `.d` directory holds only its candidate. There
are no shadow units.

**Effective systemd properties:**

| Unit | DropInPaths | Effective values | Common |
| --- | --- | --- | --- |
| `lilith-authority-dev.service` | the service drop-in | `Restart=no`, MainPID 0 | inactive/dead, loaded, static, `NeedDaemonReload=no`, InvocationID empty, `FragmentPath` in `/etc/systemd/system` |
| `lilith-authority-dev.socket` | the socket drop-in | `StopWhenUnneeded=yes`, `RefuseManualStart=yes` | as above |

**Activation:** exactly `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false`.

**Post-install host U5** (`host/05-U5_OLD_RETIRED_REPLACEMENT_ACCEPTED`, acquired 17:52:19Z):

- `E19_HOST_U5_OLD_RETIRED_REPLACEMENT_ACCEPTED_PASS`, all 11 reads rc 0, `readinessExact`, `E19_OLD_RETIRED`,
  NEW sole and selected, installer P1B-10 on NEW PASS.
- Witness `90b28f9d…`/69238/0, active/running. Both witness sockets are active, so there was no additional K-WIT
  load.
- `W9_LATER_STATE`, `W10_1_HELD_EXACT` with no failures. HELD `c713ea1d…` listed, chain exact, broker preserved,
  signer units inactive, activation dark.
- W10 reports registry not effective, authority not active and issuance `NONE`.
- `HOST_RESULT` `aac2b926…` and the W10 output `314ca426…` are byte-identical to `host/04`. Every host file is
  byte-identical to `host/04` except `identity.out` (clock) and `observer.out`.

**Observer delta.** `mb11_restart_boundary_install.observer_delta_reasons(host/04 facts, host/05 facts)` is `[]`.
The only non-clock changes are exactly `expected_observer_changes()`:

- both `DropInPaths`;
- the two drop-in entries;
- the two `.d` names in the `/etc/systemd/system` inventory.

The observer completed (`PR1A_HOST_OBSERVATION=COMPLETE`, stable `9e32d96a…`).

**DR-5:**

- **Pinned-script proof.** `prove_dr5_unaffected` on the pinned `scripts/deployer_authority_boundary_proof.sh`
  (`9b569f9b…`) returns `EMPTY_PROVEN_FROM_PINNED_SCRIPT`, `unitDirWriteDeniedParent=true`. No DR-5 list names a
  path at or under either overlay directory.
- **One `e19_dr5_target.py compare`** of `host/05` against the **preserved historical** deploy `38572866000` log
  (`a2e0f999…`) → `EQUAL`, `WITNESS_RUNNING_HELD_E19`, allowed 0, old lines 0. The compare output (`c008cd9c…`) is
  identical to the PR #197 comparison.
- **Limitation:** that log predates the install. The compare binds the fresh host evidence to historical DR-5
  output; it is **not** a fresh post-install DR-5 execution. The post-install DR-5 claim rests on the pinned-script
  proof. No deploy was triggered to obtain fresh DR-5 output; the next routine deploy provides one.

## 6. Source correction (proposal only; not implemented here)

The install's fail-closed behaviour was correct: it stopped on a read-back the record did not predict. A future
P1B-10R-style install on idle units should be able to report `P10R_2` right after writing without implying a
reload. **No such install is pending**, since the DEV overlay is installed and accepted. The tool is also pinned
by identity in:

- `e19_operator.TOOL_PINS`, whose hash `b9832816…` the E-19 drivers and `test_b1b3e_e19_completion` pin;
- `e19_completion.MB11_REPINNED_SHA256`;
- the E-19 observer BOOT bundle.

**An in-place edit would invalidate the E-19 trust chain, so none is made.** If it is ever needed, the narrow
correction is a separately versioned tool. It would keep `classify`, `plan_digest`, `boundary_reasons` and the
write path byte-equivalent and change only the result label:

- `P10R_1` read-back → `P1B10R_INSTALLED` (pending reload);
- `P10R_2` read-back → `P1B10R_INSTALLED_ALREADY_EFFECTIVE`, with `reloadPerformedByTool=false` and a
  `reloadProvenance: "UNKNOWN"` field (never "reloaded");
- every other read-back (`PARTIAL`, `FOREIGN`, `UNIT_NOT_EXACT`, `ACTIVE`, `AUTHORITY_NOT_DARK`, `UNCLASSIFIED`)
  stays `..._READBACK_NOT_P10R_1` / STOP.

It would add no replay, repair or rollback. §10a would be amended to state that `P10R_1` holds only while the
units stay loaded. Tests would cover each of these cases, plus the unchanged E-19 pins.

## 7. Evidence (owner-local)

| Evidence | Directory | `SHA256SUMS` SHA-256 |
| --- | --- | --- |
| preflight + plan | `lilith-mb11-p1b10r-corrected-d9e1aae` | `43fa28487152fde30b16d7f51b300b73ceb8adba0bbde15ac48741e5dacf2d38` |
| install (driver STOP rc 1) | `lilith-mb11-p1b10r-install-d9e1aae` | `93868df0c2830bed46433a2c782e23c14c94f37606b0fc2f154f6bd0085ae700` |
| independent adjudication | `lilith-mb11-p1b10r-adjudicate-d9e1aae` | `c68e0a74602f43b62945d7883a03c4d20a2cf07332a33d47c9285a784d948974` |
| post-install host U5 + observer delta | `lilith-p1b10r-accept-host-u5-d9e1aae` | `1303224cca5df27be3c57413e5624386554d27807528901b07db426adbb490e9` |
| DR-5 proof + historical-log compare | `lilith-p1b10r-accept-dr5-d9e1aae` | `918c281753de329c403cf99bc51d6b07352ce24e779e2926d378a1467339d728` |

Raw outputs (all in the directories above):

| Output | SHA-256 |
| --- | --- |
| install stdout | `2157ae4d5039fd21cee5f4db5c1871fcc5b0343cab98a83adfee5a728d99d3c8` |
| adjudication observe stdout | `71016257588d1a78a4f2d8960a9eaf8350098a2325e41ed3d394d6379ba93acb` |
| preflight observe stdout | `07d56a9975346b145234536fb5e314b2d83e80377364a9c0b532c04d285777dd` |
| plan stdout | `32e1b4489fe6adc26433af4463f545a0421e304551d206d8e48f82f78bae3274` |

The earlier E-19 and P1B-10R evidence manifests were re-verified before and after each step and are unchanged.

## 8. State (from 2026-10-14)

```text
P1B_10R = INSTALLED ONCE; read-back P10R_2 (result P1B10R_INSTALLED_READBACK_NOT_P10R_1; driver STOP rc 1)
OVERLAY = INSTALLED ON DEV, EFFECTIVE (P10R_2_EFFECTIVE_EXACT, independently observed); OWNER-ACCEPTED (Option A)
DAEMON_RELOAD (planned standalone step) = WAIVED by owner; none performed by any tool; reload provenance UNKNOWN
SIGNER = INACTIVE (static, loaded, no InvocationID); RefuseManualStart=yes on the signer socket
K_ACT_LOADS = 0
WITNESS = 90b28f9d…/69238/0 (unchanged); HELD = EXACT; W10_1_HELD_EXACT
DR-5 = pinned-script delta EMPTY; historical-log compare EQUAL (not a fresh post-install DR-5 execution)
M-B11 = NOT AUTHORIZED
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
ISSUANCE_AUTHORITY = NONE
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
```

`RefuseManualStart=yes` means the signer socket can no longer be started by hand. Any later M-B11 start must use the
service start path designed for it, as for the witness after WRB_2.
