# Slice 15B2b-B1b-3e — PR-1A Final Read-Only Gate (before M-A1)

Status:

- **FINAL READ-ONLY GATE**
- **NO LIVE MUTATION**
- **M-A1 NOT AUTHORIZED** (a separate explicit owner instruction is required)
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`PR1A_FINAL_GATE_PASS`** (`ARTIFACT_CHECK_PASS` + fresh DEV baseline PASS)

Branch `claude/15b2b-b1b3e-pr1a-final-readonly-gate`.

## 1. Ceremony identities

| Identity | Value |
| --- | --- |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` (the merge of PR #92) |
| `PAYLOAD_SOURCE_SHA` (NEW `RELEASE_SHA`) | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |

Control source:
- `git rev-parse HEAD` = `CONTROL_SHA`, and the working tree was clean.
- The merge tree of `c1eb568` is identical to the reviewed branch head
  `47328d5` (`^{tree}` equal).
- `aee323e..c1eb568` changes no installable payload source (§8).

## 2. Artifact check — `ARTIFACT_CHECK_PASS`

The stored candidate is in
`C:\Users\edufo\lilith-b1b3e-pr1a-aee323e94412accbe321bc84eae78c5b8cf95afc\candidate\`,
the owner workstation location from the
[build gate](slice-15b2b-b1b3e-pr1a-build-attestation.md) §13. It was checked
with the tooling merged at `CONTROL_SHA`:
`attest_authority_dev_build.py`, SHA-256 `709cd552…d3e3`, unchanged. The
recipe source root is the clean `aee323e` worktree `build-a/src`.

| Check | Result |
| --- | --- |
| files present; `sha256sum -c SHA256SUMS` | archive, stamp, attestation: OK |
| archive SHA-256 / size | `25f1ff03…250a` / 5 354 725 bytes, both as accepted |
| `check --attestation … --sha aee323e…` | `{"attestationDigest": "86ed2659…c683", "failures": [], "result": "PASS"}` |
| what `check` compares | installer `verify_archive`, which covers the stamp, the internal manifest, the exact member set (no extra or missing payload), and the size bounds. It then compares, one by one, `sourceCommit`, `archiveSha256`, `builderStampSha256`, `manifestSha256`, the authority / root-tooling / witness digests, `unitDigests`, `cliDigests`, `hostTargets`, and `dependencyInventorySha256` |
| full re-inspection | `identitySha256` = `60cf0c7e35d782ceea510d949d60b164bfb0210db33332ea778bb2b93d4d6824`, equal to BUILD_A at build time, with **zero** differing identity paths. That covers every tar header, the member order, the gzip header, 65 payload files, and 66 members |
| attestation file | canonical form verified. Digest recomputed as `86ed2659…c683`. `sourceCommit` = `aee323e…` |
| digests | authority `4b32f169…671b`, root tooling `28e9d6cb…b903`, witness `5137ddb0…d3c3`, dependency inventory `a34972dd…2a0a`, manifest `1d578ca7…4e8f` |

No rebuild was made, and no artifact was substituted.

## 3. Fresh DEV preflight

**Live contact.**

| Item | Value |
| --- | --- |
| Window | 2026-09-28 `12:52:41Z` to `13:07:53Z` (UTC). The IAP round-trips were slow |
| Target | `lilith-dev-01` (DEV) only. PROD was not contacted |
| Principal | the same OS Login user `ravindupahasara2_gmail_com` over `gcloud compute ssh lilith-dev-01 --tunnel-through-iap`, with the existing `sudo` to root |
| Transport | each tool streamed as gzip+base64 in `--command` into `sudo /usr/bin/python3 -I -B -`. The local transport wrapper's SHA-256 is `e0a9b5d9…8651` (it only builds the command) |
| Files on DEV | none copied, none written |

**Tools.** Only reviewed tools, all at `CONTROL_SHA`:

- `observe_authority_dev_host.py observe` (`a2f21b45…08bf`), run twice;
- `install_authority_dev.py upgrade-baseline` and
  `status --expect L2b.2 9ac7de2…` (`fe10d9a3…5487`);
- `verify_broker_dev_current_incarnation.py preservation` (`bbca69bc…b85b0b`);
- `probe_needrestart_lilith_override.py probe` (`edd23ac7…b2db`);
- the installed `/usr/local/sbin/lilith-activation-verify`.

The old scratch probe was **not** used. The GCE instance id came from a
workstation-side read-only `gcloud compute instances describe`.

**Transcripts.** They are stored on the owner workstation at
`…\lilith-b1b3e-pr1a-aee323e…\final-readonly-gate\` with `SHA256SUMS`.

| Transcript | SHA-256 (prefix) |
| --- | --- |
| `obs1` | `44fea5eb` |
| `obs2` | `376119a2` |
| `baseline` | `621802a5` |
| `status` | `f0a80384` |
| `broker` | `f57a6bcc` |
| `needrestart` | `8cfbe21b` |
| `activation` | `37b889bd` |

### 3.1 Host identity and boot continuity

| Fact | Observed | Accepted preflight | Match |
| --- | --- | --- | --- |
| hostname | `lilith-dev-01` | same | yes |
| machine-id | `ae929170e6fa4c8ab9cc7b9547238d9d` | same | yes |
| GCE instance id | `7687007163730582258`, RUNNING, `lastStartTimestamp` 2026-09-13T10:58:28-07:00 | same id | yes |
| boot ID | `24d1771d-e1b5-4e5f-816d-da08ad8b367a` | same | **no reboot** |
| OS / kernel | Ubuntu 24.04.4 LTS / `6.17.0-1022-gcp` | same | yes |
| swap | none | none | yes |
| `reboot-required` | present | present (known, D-6) | unchanged |

No reboot occurred, so neither `BASELINE_REESTABLISHED_AFTER_REBOOT` nor
`BASELINE_INVALID_AFTER_REBOOT` applies. The baseline was still verified in
full from scratch.

**Observer stability.** Both observer runs (`13:00:19Z` and `13:07:53Z`)
gave the same `stableSha256`:
`c6663364de56fb9b67a43b7b6466d3a51318e0cb0fb9654c045a9e6fd49d1818`.

### 3.2 Old installed release

- `releases/` holds exactly `9ac7de22bf977385ceb954624677e33f0bae062b`.
- `current -> releases/9ac7de2…`.
- **Tree:**
  - manifest `c9f2f76e…370d`, 23 files, 0 mismatched, 0 not in manifest;
  - no unexpected entry;
  - all `0:0`, modes `0644`/`0755`;
  - tree `ac62b1dd…a991`;
  - venv 1391 entries, `03bf7233…9165`.

  All of these equal the preflight.
- **Installed host files:** unit `249f2ec9…`, socket `bff5e927…`, tmpfiles
  `2a1891ef…`, keygen `f1e7020b…`. They equal the release members and the
  preflight.
- `status --expect L2b.2 9ac7de2…`: `PASS`, `failures=[]`.

### 3.3 CURRENT credential and credential store

- **CURRENT:**
  - `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`;
  - regular file, `nlink 1`, not a symlink, `root:root 0600`;
  - device 2049, inode 1738, size 219;
  - `mtimeNs` = `ctimeNs` = `1790493331258019177`;
  - SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`.

  It was never decrypted.
- **Baseline match.** `upgrade-baseline`: `PASS`, `acceptedCurrentSha256`
  and `acceptedOldRelease` both true. Its `currentBlob`, `hostKey`, and
  `signerAccount` are **field-for-field equal** to the accepted preflight §15
  baseline.
- **Credstore.** `/etc/credstore.encrypted` is `root:root 0700` with
  exactly one entry, CURRENT. `/etc/credstore` is empty.

### 3.4 Host credential secret (stat only)

`/var/lib/systemd/credential.secret` was not opened: the observer refuses
it in code.

| Fact | Value |
| --- | --- |
| type | regular file |
| owner / mode | `root:root 0400` |
| identity | device 2049, inode 5768, size 4112 |
| times | mtime / ctime ns `1790490701237702273` / `1790490701241702264` |
| status prerequisite | PRESENT_SECURE |

All values are unchanged from the preflight.

### 3.5 Services

- **`lilith-authority-dev.service`:**
  - loaded, inactive/dead, `static`, `NeedDaemonReload=no`, `NRestarts=0`,
    `MainPID=0`;
  - `InvocationID`, `ExecMainStartTimestamp`, and `InactiveExitTimestamp`
    all empty: never started.
- **Socket:** loaded, inactive, `static`.
- **Enablement:** no enablement links and no drop-ins.
- **Recovery witness:** all three units `not-found`, and no witness
  account.
- **Runtime paths:** `/run/credentials` is empty.
- **Broker:** `lilith-memory-broker.service` is active with
  `InvocationID 42af2691…`, PID 132976, `NRestarts=0`.

No unexpected authority-sensitive service is running.

### 3.6 PR1_ABSENT

Every PR-1 object in the observer's fixed set is **absent**:

- the custody root and `prepared/` / `retired/` (PREPARED, RETIRED);
- `/var/lib/lilith-authority-custody` and `holds/` (hold store);
- `/etc/lilith-recovery-witness` and `credentials/` with the K-WIT blob,
  plus the superseded credstore K-WIT name;
- `/var/lib/lilith-recovery-witness` (witness chain, pointer, genesis);
- `/etc/lilith-authority-dev` with `trust/`, `registry/`, `owner/` (owner
  register and pin copies), `hold`, and `INSTALLED`;
- `/var/lib/lilith-authority-dev` with `authority_ledger.db`;
- the `/run` state and credential directories of both services.

The five new CLIs and the witness unit and tmpfiles files are absent. The
LILITH namespace inventory equals the preflight's.

### 3.7 Activation

`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false`
(exit 1). `/etc/lilith-os-dev/activation/` is empty. The verifier's bytes
(`44046cae…a32`) equal the reviewed source.

### 3.8 DR-5

The current routine run for `CONTROL_SHA` itself is `36422246261`: event
`workflow_run`, `MODE=DEPLOY_REQUIRED`, base `aee323e`, candidate
`c1eb568`. Its DR-5 step ran at `12:31:04Z`–`12:33:15Z`, and the job
finished at `12:35:53Z`, before this gate's first contact.

| Output | Value |
| --- | --- |
| effective-sudo proof | `SUDO_EFFECTIVE_PROOF=PASS user=sa_112096412008414111981 mode=self` |
| PR-1 ladder line | `PR1_AUTHORITY_BOUNDARY maturity=PR1_ABSENT` |
| base ladder line | `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` |

- `sudo -u` to `lilith-memory-broker` and `lilith-authority-dev` is denied.
- Both host prerequisites are `PRESENT_SECURE`.
- CURRENT is `UNOBSERVABLE_BY_DESIGN`.
- Absent PR-1 objects stay `DEFERRED_UNTIL_OBJECT_EXISTS`, never
  "denied".

### 3.9 Broker

`BROKER_PRESERVATION=PASS`, `failures=[]`.

| Fact | Value |
| --- | --- |
| incarnation | `42af2691b8d24ee5a92a286197c5444c` |
| process | PID 132976, start ticks 108213277, `2026-09-26T06:34:08Z`, `NRestarts=0` |
| boot | `24d1771d…` |
| release | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`; manifest `7a46ac83…` |
| shared libraries | `40e68a1c…` |
| candidate | `3549585487ad…a7eee5` = accepted |

- Equivalent: release, config, state, identity boundary, socket boundary,
  and deployer policy text. Stage III is untouched.
- `processContinuity=false` is the expected Stage II historical reference
  (DR-1).
- `authorityCustodyJudgment=NOT_PERFORMED`.
- Reported custody paths: only the accepted B1b-3d objects are present.
- The broker was not restarted.

### 3.10 needrestart

`NEEDRESTART_LILITH_OVERRIDE=PASS`. The snippet `503279…68d2` is
`root:root 0644`. `EXCLUDED`: the broker, `lilith-authority-dev.service`,
and `lilith-recovery-witness.service`. Every control unit is `DEFAULT`.
Nothing was edited.

### 3.11 Filesystem

Everything resolves to `st_dev 2049` (ext4 `/dev/root`, `8:1`, mounted at
`/`):

- CURRENT and `/etc/credstore.encrypted`;
- the host key;
- `/etc`, which is the nearest existing parent of
  `/etc/lilith-authority-custody` and `/etc/lilith-recovery-witness/credentials`;
- `/var/lib`, which is the nearest existing parent of
  `/var/lib/lilith-authority-custody/holds`, `/var/lib/lilith-authority-dev`,
  and `/var/lib/lilith-recovery-witness`;
- `/opt/lilith-authority-dev`, `/usr/local/sbin`, and `/etc/systemd/system`.

The future CURRENT / PREPARED / RETIRED layout stays on one filesystem.
Nothing was created to establish this.

## 4. PR-2 / PR-3

```text
SNAPSHOT_INVENTORY=NOT_COMPLETED_PR2
OWNER_OFFHOST_REGISTER=NOT_COMPLETED_PR3
```

These do not block the PR-1A inert installation, which asserts nothing
about custody (preflight §21). They do block PR-1B bootstrap per the accepted
order. No PASS input was fabricated.

## 5. origin/main drift

`origin/main` = `c1eb56842d464f6690b7d55a1f6915d54618e006`, equal to
`CONTROL_SHA` at the start and at the end of this gate. **No drift.**
`CONTROL_SHA` was not switched.

## 6. Discrepancies

| # | Observation | Classification |
| --- | --- | --- |
| G-1 | IAP round-trips were slow (≈ 7 min for the first observer call) | transport latency only. Each tool ran exactly once as intended (the observer twice by design), and all return codes were as expected |
| G-2 | Routine run `36422246261` deployed core-api (`DEPLOY_REQUIRED`) at 12:30–12:36Z, before this gate | the routine path DR-5 exists to prove harmless. Broker preservation, CURRENT, and the release tree are all unchanged afterwards |
| G-3 | `reboot-required` is still pending | unchanged known risk (preflight D-6). A reboot before M-A1 invalidates this gate |
| G-4 | Installer `status` reads without `O_NOATIME` (preflight D-1) | atime only. mtime, ctime, and inode are unchanged, as the second observer run proves (identical `stableSha256`) |

No material drift from the accepted baseline.

## 7. Result

```text
ARTIFACT_CHECK_PASS
fresh DEV baseline: PASS (no reboot; baseline identical)
PR1A_FINAL_GATE_PASS
```

**M-A1 is not performed and not authorized by this record.** It needs a
separate explicit owner instruction. That instruction must pin exactly the
four identities in §1. If DEV reboots, the broker restarts, main changes
ceremony or payload source, or time passes long enough that the owner wants
new evidence, this gate must be repeated first.

## Explicitly not done

```text
ARTIFACT VERIFIED READ-ONLY
READ-ONLY DEV CONTACT ONLY
NO PROD CONTACT
NO LIVE FILE MUTATION
NO INSTALL
NO ARTIFACT TRANSFER TO DEV
NO PERMISSION CHANGE
NO SERVICE START/STOP/RESTART
NO DAEMON-RELOAD
NO K-WIT GENERATION
NO LEDGER
NO WITNESS
NO HOLD
NO REGISTRY CHANGE
NO KEY ROTATION
M-A1 NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
