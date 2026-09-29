# Slice 15B2b-B1b-3e — Pre-PR-1B Reboot and Rebaseline Ceremony (prepared, not executed)

Status:

- **CEREMONY PREPARED; NOT EXECUTED**
- **REBOOT NOT AUTHORIZED** (M-R1 needs a separate explicit owner instruction after review)
- **BROKER START NOT AUTHORIZED** (M-R2 is a second, separately authorized mutation; §6)
- **NO DEV CONTACT BY THIS PREPARATION**; **NO DEV MUTATION**
- **PR-1B NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**
- Classification: **`PRE_PR1B_REBOOT_CEREMONY_READY`**

```text
reboot                          != rebaseline
runtime directory existence     != witness state != authority readiness
healthy broker service          != accepted broker baseline
successful reboot / rebaseline  != PR-1B eligibility
```

## 1. Purpose

DEV has had one boot since it was created (`24d1771d…`, 2026-09-13).
`/var/run/reboot-required` has been pending since 2026-09-14 (OR-5). The
[P3-5 sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §12
requires the reboot **before PR-1B**, never inside it, followed by a fresh
read-only rebaseline.

This record prepares that ceremony:

1. prove the current pre-reboot state (§3);
2. perform one authorized DEV reboot (M-R1, §4);
3. observe the new host state and answer OR-6 (§5, §7);
4. establish a fresh broker baseline. This needs M-R2, a separately
   authorized broker start (§6, §8);
5. re-prove PR-1A `P1A-9` semantics (§9);
6. re-prove the routine-deployer DR-5 boundary (§10);
7. verify activation stays dark and custody objects are unchanged (§9);
8. verify the P3 owner replicas are unaffected (§12);
9. decide whether DEV is eligible for PR-2 read-only revalidation (§14).

It adds two reviewed read-only helpers and offline tests (§15). It executes
nothing.

## 2. Accepted pre-state

| Item | Accepted value | Source |
| --- | --- | --- |
| `origin/main` at preparation | `c04289810ded60c0a21bd55f1850f32daa283a7e` | merge of PR #103 |
| PR-1A | ACCEPTED; `FINAL_MATURITY=P1A-9`; `AUTHORITY_BOUNDARY=PASS L1c.3` | [PR-1A acceptance](slice-15b2b-b1b3e-pr1a-acceptance.md) |
| PR-2 | ACCEPTED; whole-host rollback resistance **NOT ESTABLISHED**; OR-1..OR-9 carried | [PR-2 acceptance](slice-15b2b-b1b3e-pr2-acceptance.md) |
| PR-3 / P3-3 | COMPLETE; two independent real owner replica domains | [P3-3 acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md) |
| real owner freshness | `FRESHNESS_UNKNOWN`; real record 1 ABSENT; 0 accepted records | same |
| PR-1B | NOT AUTHORIZED | — |
| host | `lilith-dev-01`, instance `7687007163730582258`, machine-id `ae929170e6fa4c8ab9cc7b9547238d9d`, project `lilith-agent-260823-27389`, zone `asia-southeast1-b` | baseline record §2 |
| boot ID | `24d1771d-e1b5-4e5f-816d-da08ad8b367a` | baseline record §3 |
| running kernel | `6.17.0-1022-gcp`; `reboot-required` lists `libc6`, `linux-image-7.0.0-1011-gcp`, `linux-base` (as of 2026-09-26) | baseline record §10 |
| broker incarnation | `42af2691b8d24ee5a92a286197c5444c`, PID `132976`, start ticks `108213277`, `NRestarts=0` | baseline record §3 |
| broker release | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, manifest `7a46ac83…4614`; shared libraries `40e68a1c…87bd` | same |
| accepted broker `baselineCandidate` | `3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5` | same |
| observer `stableSha256` | `5eaec23cef9c8f53db8e6f27e84b270ad6b8567d4f21287a1ffd543550fe2778` (M-A10 POST = PR-2) | PR-2 acceptance |
| sole authority release | `aee323e94412accbe321bc84eae78c5b8cf95afc`, manifest `1d578ca7…4e8f`, tree `675c9482…` | PR-1A acceptance §4 |
| CURRENT | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`, `root:root 0600`, dev 2049, inode 1738, size 219, `mtimeNs`=`ctimeNs`=`1790493331258019177`, SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3` | same §2 |
| host key | `/var/lib/systemd/credential.secret` `root:root 0400`, dev 2049, inode 5768, size 4112; stat only, never opened | final gate §3.4 |
| authority unit assets | service `11b6d00f…`, socket `bff5e927…`, tmpfiles `2a1891ef…` | PR-1A acceptance §4 |
| witness unit assets | service `9f78130c…`, owner socket `d260917f…`, signer socket `ad345d18…`, tmpfiles `c3491d51…` | same |
| accounts | signer `lilith-authority-dev` 995/985; witness `lilith-recovery-witness` 994/984 (locked, nologin, `/nonexistent`) | same |
| custody root | `/etc/lilith-authority-custody` `root:root 0700` = {`prepared`, `retired`}, both empty | same |
| skeleton | `/etc/lilith-authority-dev` = {`owner`,`registry`,`trust`} (each empty); `/etc/lilith-recovery-witness/credentials` empty; `/var/lib/lilith-authority-custody/holds` empty | same |
| absent | K-WIT, registry content, ledger, witness state, hold records, RecoveryEpoch, `/var/lib/lilith-authority-dev`, `/var/lib/lilith-recovery-witness` | same |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`; verifier bytes `44046cae…a32` | same |
| needrestart | `3.6-7ubuntu4.5`; main conf `baacdd68…f7ee`; snippet `503279315ccc884d8a68505c86b51dfd09387b393c9becba684b1fa1c28068d2`; `NEEDRESTART_LILITH_OVERRIDE=PASS` (3 units `EXCLUDED`) | final gate §3.10 |
| last accepted DR-5 | run `36457144642` (main `8a14ea5`): `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` | PR-1A acceptance §3 |
| known debt | kernel reboot pending (OR-5); DR-3 (`ubuntu` root-equivalent) | PR-2 acceptance |

A reboot ends the process/incarnation baseline, which cannot be reused
afterwards. Persistent authority state (CURRENT, release, custody,
skeleton) is unaffected by a reboot and must be byte-identical afterwards.

## 3. Pre-reboot gate (read-only, immediately before M-R1)

### 3.1 Operator, transport, and tools

- **Operator.** The owner's local gcloud/IAP session, as for PR-1A:
  OS Login user `ravindupahasara2_gmail_com`, with the existing `sudo` to root.
  No GitHub Actions runner or deployer identity takes part in §3–§9.
- **Transport.** Every tool is embedded gzip+base64 in `--command`. Never pipe
  a script over stdin on Windows (baseline record §2: plink injects a stray
  `y`). Set `MSYS_NO_PATHCONV=1` in Git Bash.
- **Tools.** Only reviewed tools from protected main at `CONTROL_SHA`. That
  is the merge commit of the PR that carries this record. Hash each tool
  locally and record the digests in the evidence directory before first
  contact.

  | Tool | Operation |
  | --- | --- |
  | `services/authority-dev/ceremony/observe_authority_dev_host.py` | `observe` |
  | `services/authority-dev/ceremony/install_authority_dev.py` | `status --expect P1A-9 aee323e…` |
  | `scripts/verify_broker_dev_current_incarnation.py` | `preservation` (pre), `rebaseline` (post, §8) |
  | `scripts/probe_needrestart_lilith_override.py` | `probe` |
  | installed `/usr/local/sbin/lilith-activation-verify` | (no arguments) |
  | `scripts/compare_reboot_host_observations.py` | offline, on the workstation only (§7) |

- **Evidence.** Everything goes to
  `C:\Users\edufo\lilith-b1b3e-pre-pr1b-reboot\{pre,reboot,post,mr2,dr5}\`,
  with a `SHA256SUMS`. Nothing is copied to DEV, and nothing is written there.

```bash
export MSYS_NO_PATHCONV=1
DEV=lilith-dev-01; ZONE=asia-southeast1-b; PROJECT=lilith-agent-260823-27389
RELEASE_SHA=aee323e94412accbe321bc84eae78c5b8cf95afc
OLD_BOOT=24d1771d-e1b5-4e5f-816d-da08ad8b367a
CONTROL_SHA=$(git rev-parse origin/main)       # must equal the merge of this record's PR
b64() { git show "$CONTROL_SHA:$1" | gzip -9n | base64 -w0; }
dev() { gcloud compute ssh "$DEV" --zone="$ZONE" --project="$PROJECT" --tunnel-through-iap \
          --command="test \"\$(hostname)\" = lilith-dev-01 || exit 97; $1" </dev/null; }
OBS=$(b64 services/authority-dev/ceremony/observe_authority_dev_host.py)
INS=$(b64 services/authority-dev/ceremony/install_authority_dev.py)
BRK=$(b64 scripts/verify_broker_dev_current_incarnation.py)
NRP=$(b64 scripts/probe_needrestart_lilith_override.py)
run_py() { dev "printf %s $1 | base64 -d | gunzip | sudo -n /usr/bin/python3 -I -B - $2"; }
```

### 3.2 Gate steps

Each step's exit code and full transcript are saved. The owner may run the
gate once and then decide on M-R1 in the same window. If more than about one
hour passes, or any merge lands on main, the gate is repeated.

| # | Check (read-only) | Command | Required |
| --- | --- | --- | --- |
| G0 | Control source | `git rev-parse origin/main`; `git status --porcelain` in a clean `CONTROL_SHA` checkout | `origin/main` = `CONTROL_SHA`; clean tree |
| G1 | No routine run in flight; merge freeze | `gh run list --workflow deploy-dev.yml --limit 5` | nothing `in_progress`/`queued`. The owner freezes merges to main from G1 until the end of §9 |
| G2 | Fresh pre-reboot DR-5 | the routine run for `CONTROL_SHA` (the merge of this record's PR is `DEPLOY_REQUIRED`) | `PR1_AUTHORITY_BOUNDARY maturity=P1A-9` and `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`; the job finished before G3 |
| G3 | GCE identity | `gcloud compute instances describe $DEV --zone $ZONE --project $PROJECT --format='value(id,status,lastStartTimestamp,scheduling.automaticRestart,scheduling.onHostMaintenance)'` | id `7687007163730582258`, `RUNNING`; record the rest |
| G4 | Host identity and boot | `dev 'cat /etc/machine-id /proc/sys/kernel/random/boot_id /proc/sys/kernel/osrelease; cut -d" " -f1 /proc/uptime'` | machine-id as §2; boot ID = `$OLD_BOOT`; kernel `6.17.0-1022-gcp` |
| G5 | Observer | `run_py $OBS observe > pre/obs1.txt`, then again `> pre/obs2.txt` | both `PR1A_HOST_OBSERVATION=COMPLETE`, same `stableSha256` = `5eaec23c…2778`. If it differs, compare `sectionSha256` against the PR-2 evidence. Any delta not explained by a reviewed record → **STOP** |
| G6 | Installer status | `run_py $INS "status --expect P1A-9 $RELEASE_SHA"` | `PASS`, `failures=[]` |
| G7 | Broker continuity | `run_py $BRK preservation` | `BROKER_PRESERVATION=PASS`; incarnation `42af2691…`, PID 132976, start ticks 108213277, `NRestarts=0`, release `817a83e…`, candidate `35495854…`, boot `$OLD_BOOT` |
| G8 | Activation | `dev 'sudo -n /usr/local/sbin/lilith-activation-verify; echo rc=$?'` | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`, rc 1 |
| G9 | needrestart | `run_py $NRP probe`; `dev 'dpkg-query -W needrestart; sudo -n sha256sum /etc/needrestart/needrestart.conf /etc/needrestart/conf.d/*; ls -A /etc/needrestart/conf.d'` | `NEEDRESTART_LILITH_OVERRIDE=PASS`; version, main conf, snippet as §2; conf.d = `README.needrestart` + `lilith-authority-sensitive.conf` |
| G10 | Reboot-required and kernels | `dev 'ls -l /var/run/reboot-required*; cat /var/run/reboot-required.pkgs; dpkg-query -W -f="\${Package} \${Version} \${db:Status-Abbrev}\n" "linux-image-*" libc6; ls -l /boot/vmlinuz*; grep -E "^GRUB_DEFAULT" /etc/default/grub /etc/default/grub.d/*.cfg 2>/dev/null; sudo -n grub-editenv list'` | `reboot-required` present; record the package list. **`EXPECTED_KERNEL`** = the newest installed `linux-image-*-gcp` by `sort -V`, and GRUB must boot it by default (`GRUB_DEFAULT=0`, no `saved_entry` pinning an older kernel). An ambiguous default → **STOP** |
| G11 | Package manager idle | `dev 'pgrep -a "apt|dpkg|unattended" || echo idle; sudo -n dpkg --audit; systemctl list-timers --all --no-pager apt-daily.timer apt-daily-upgrade.timer'` | `idle`; `dpkg --audit` empty; neither apt timer is due inside the next 60 minutes. Otherwise wait, then re-run G10–G11. A half-configured package → **STOP** |
| G12 | Unit enablement | `dev 'systemctl list-unit-files "lilith-*" --no-legend --no-pager; find /etc/systemd/system -path "*.wants/*" -name "lilith-*" -printf "%p -> %l\n"; systemctl list-timers --all --no-legend --no-pager | grep -i lilith || echo no-lilith-timers'` | none of the broker, authority, recovery-witness, or Stage III units (`lilith-memory-broker.*`, `lilith-authority-dev.*`, `lilith-recovery-witness*`, `lilith-stage3-*`) is `enabled` or linked in any `.wants/`; no LILITH timer. Record which other units are enabled (for example the Core API unit). An enabled authority, broker, witness, or Stage III unit → **STOP** (it would start at boot) |
| G13 | Boot-time runtime creation | `dev 'ls -l /etc/tmpfiles.d/; sudo -n sha256sum /etc/tmpfiles.d/lilith-*.conf; cat /etc/tmpfiles.d/lilith-*.conf; grep -rl lilith /usr/lib/tmpfiles.d /run/tmpfiles.d 2>/dev/null || echo none'` | lilith tmpfiles = broker `e6139f16…` (`d /run/lilith-memory 0710 root lilith-memory-ipc -`), authority `2a1891ef…`, witness `c3491d51…`. Any other LILITH tmpfiles line → record it, and add it to the §5 expectation before M-R1 |
| G14 | Runtime state before | `dev 'ls -ld /run/lilith-* 2>&1; sudo -n ls -A /run/credentials'` | record. `/run/lilith-authority-dev` and `/run/lilith-recovery-witness` are expected ABSENT. `/run/credentials` is expected empty |
| G15 | Running services | `dev 'systemctl list-units --type=service --state=running --no-legend --plain --no-pager; systemctl --failed --no-legend --no-pager'` | saved as `pre/services.txt`. The Stage III controller is `failed` (expected; it has been since 2026-09-25) |
| G16 | Owner storage | no command: the S25 and WSL Replica A are **not** contacted | §12 expectation recorded |

**STOP BEFORE REBOOT** if any of G0–G15 differs materially from §2, or from
its row above. After a STOP nothing is repaired: report, and wait for the
owner. The pre-state rules:

- a different broker incarnation, PID, start ticks, or candidate;
- `status --expect P1A-9` failing;
- CURRENT, host key, release, custody, skeleton, or account drift;
- activation other than `GRANT_ABSENT`;
- needrestart drift;
- any authority-sensitive unit enabled or running;
- a package operation in flight;
- an ambiguous boot kernel.

## 4. The one mutation: M-R1 (DEV operating-system reboot)

**M-R1 is the only mutation of the reboot ceremony.** It needs a separate
explicit owner instruction, given after this record is reviewed and after a
passing §3 gate. That instruction must pin `CONTROL_SHA`, `$OLD_BOOT`, and
`EXPECTED_KERNEL`.

```bash
dev "test \"\$(cat /proc/sys/kernel/random/boot_id)\" = $OLD_BOOT || exit 96; sudo -n /usr/bin/systemctl reboot"
```

- **Guards:** the hostname guard (`exit 97`) and the boot-ID guard
  (`exit 96`). The command can only reboot `lilith-dev-01`, and only from
  the accepted boot. A replay after the reboot is refused.
- **`systemctl reboot`** is an orderly shutdown. It stops units, unmounts
  cleanly, and reboots with the kernel GRUB selects.
- **Rejected:**
  - `gcloud compute instances reset`: a hard reset, with no orderly
    shutdown;
  - `stop` + `start`: a new host and changed GCE scheduling state;
  - `shutdown -r +N`: a pending timer;
  - `--force`: skips unit stop.
- **Expected client result:** the SSH session drops (exit 255, or the
  command's own exit). That is not a failure.

**Explicitly outside M-R1:**

- no package upgrade, install, or removal; no `apt`, `unattended-upgrade`,
  or `needrestart` run;
- no configuration edit (GRUB, needrestart, systemd, sudoers, tmpfiles);
- no service-specific start, stop, or restart; no `daemon-reload`; no
  enable;
- no credential, key, or custody change;
- no snapshot, image, machine image, or backup creation (OR-8: it would
  make the PR-2 inventory stale);
- no authority, owner-record, freshness, or PR-1B operation.

### 4.1 Waiting for the host (read-only)

From the workstation, poll at most every 30 s, for at most 15 minutes:

```bash
gcloud compute instances describe $DEV --zone $ZONE --project $PROJECT --format='value(status)'
dev 'cat /proc/sys/kernel/random/boot_id'
```

Continue when the boot ID is readable and differs from `$OLD_BOOT`. Record
it as `NEW_BOOT`.

If the host is not back after 15 minutes, read the serial console
**read-only** and STOP:

```bash
gcloud compute instances get-serial-port-output $DEV --zone $ZONE --project $PROJECT
```

Examples are a kernel panic loop (`kernel.panic=10`) or a boot hang. Do not
reboot or reset again. Recovery is a separate owner decision: interactive
serial console, previous-kernel GRUB entry.

**Rollback posture.** There is no disk snapshot (PR-2), and none may be
created for this ceremony. The fallback for a bad kernel is the previous
installed kernel through GRUB. The owner accepts M-R1 with that posture.

## 5. Expected reboot effects

| Change | Classification | Checked by |
| --- | --- | --- |
| boot ID changes | **expected, required** | observer `host.bootId`, comparator `BOOT_ID_CHANGED` |
| kernel becomes `EXPECTED_KERNEL` | **expected, required** (the point of OR-5) | comparator `KERNEL_CHANGED_TO_EXPECTED`; §11 |
| `/var/run/reboot-required` gone | **expected**, but not proof by itself: `/run` is tmpfs, so the file disappears on *any* boot | comparator `REBOOT_REQUIRED_CLEARED` **and** §11 kernel/libc checks |
| uptime resets; `utcNow` later | expected, volatile | observer `VOLATILE` |
| `/run` rebuilt from tmpfiles: `/run/lilith-memory` (`root:lilith-memory-ipc 0710`), `/run/lilith-authority-dev` (`root:root 0700`), `/run/lilith-recovery-witness` (`root:lilith-authority-dev 0710`) | **expected** (OR-6, §7) | comparator `OR6_…`, `RUN_ENTRY_…`; installer status; §7 emptiness check |
| other `/run` entries not recreated (for example a runtime directory of a unit that has not started) | expected, reported | comparator `RUN_ENTRY_NOT_RECREATED:<name>` (not `lilith-memory`, not the two OR-6 dirs) |
| **broker is DOWN** after boot: service `inactive/dead`, socket `inactive`, no `/run/lilith-memory/owner.sock` | **expected**: the socket is `disabled` (no `sockets.target.wants` link), and the service is `static` (no `[Install]`). The broker verifier pins both | observer unit deltas; §6 |
| broker PID, start ticks, InvocationID, and mapped libraries all new (after M-R2) | expected; the old baseline cannot be reused | `rebaseline` (§8) |
| Stage III controller `failed/exit-code` result gone: `inactive/dead`, `Result=success`, no InvocationID | **expected** (systemd does not persist unit results across boots) | `rebaseline` `CONTROLLER_POST_REBOOT_EXPECTED` |
| enabled non-LILITH-authority units restart at boot (for example the Core API) | expected | §3 G15 vs §9 Q9 diff |

**Not automatically acceptable** (the comparator reports each of these as
`unexpected`, and the ceremony stops):

- CURRENT bytes, inode, or times changed (`SECTION_CHANGED:currentBlob`);
- host-key stat changed;
- authority release set, selector, or tree changed;
- any content in `prepared/` or `retired/`;
- K-WIT, registry, ledger, witness state, hold record, or RecoveryEpoch
  appears (`PR1_OBJECT_CHANGED:…`, `SECTION_CHANGED:listings`);
- `/run/credentials/lilith-*` appears;
- any authority or witness unit changes state or enablement, or gets an
  InvocationID;
- the broker's InvocationID survives the reboot;
- activation becomes anything but `GRANT_ABSENT`;
- a new LILITH name appears outside `/run`, or a `/run` LILITH name appears
  that is not one of the two OR-6 directories;
- account, filesystem, or mount identity changes;
- owner storage changes (§12).

## 6. Broker restart boundary and M-R2 (finding RB-1)

**Finding RB-1.** P3-5 §12 says a reboot "restarts the memory broker". That
is wrong. The broker socket is `UnitFileState=disabled` and the service is
`static`, and the accepted verifier pins both
(`SOCKET_EXPECTED`, `SERVICE_EXPECTED`). The broker therefore stays **down**
after boot. This fails closed and needs no action to stay safe.

A fresh broker baseline needs a running broker. That requires a second
mutation, **outside M-R1**:

> **M-R2 — start the memory broker once.** Separately authorized, and only
> after the §9 post-reboot checks pass.

```bash
NEW_BOOT=<boot ID recorded in §4.1>
dev "test \"\$(cat /proc/sys/kernel/random/boot_id)\" = $NEW_BOOT || exit 96; sudo -n /usr/bin/systemctl start lilith-memory-broker.service"
```

- This is the same command the owner used on 2026-09-25 (DR-1). The socket
  is pulled in by `Requires=`.
- There is no `enable`, no `daemon-reload`, and no other unit.
- M-R2 is never retried automatically. If the start fails, record
  `systemctl status` and `journalctl -u lilith-memory-broker -b 0` read-only,
  and STOP.
- **If the owner declines M-R2**, the broker stays down. The result is then
  `BROKER_BASELINE_NOT_ESTABLISHED` (fail-closed), and DEV is **not**
  eligible for PR-2 revalidation until M-R2 and §8 are done.

## 7. OR-6 verification

**Question (PR-2 OR-6).** After the reboot, do the tmpfiles-created
`/run/lilith-*` directories make `status --expect P1A-9` fail, or change
its semantics?

**Source-level answer (this preparation, offline).** No, but only at the
exact tmpfiles spec.

- `install_authority_dev.py` models both directories as `RuntimeDirectory`
  from their phases (`PR1_RUNTIME_DIRECTORIES`):
  - `/run/lilith-authority-dev` from `P1A-8a` as `("dir", 0, 0, "0700")`;
  - `/run/lilith-recovery-witness` from `P1A-8b` as `("dir", 0, "svc", "0710")`.

  Each is ABSENT or exactly that spec, and never required.
- The two runtime *credential* directories stay forbidden at `P1A-9`:
  `/run/credentials/lilith-recovery-witness.service` (from `P1B-9a`) and
  `/run/credentials/lilith-authority-dev.service` (from `P1B-11`).
- New test
  `test_p1a9_status_after_boot_creates_the_tmpfiles_runtime_directories`
  checks these cases:
  - `P1A-9` PASSes with both absent;
  - it PASSes with the authority directory at `0700`;
  - `CONTRACT:` fails at `0755`;
  - `CONTRACT:` fails for the witness directory with the wrong group;
  - it PASSes with the signer's group (runs as root);
  - `UNEXPECTED_PRESENT:` fails for `/run/credentials/lilith-authority-dev.service`.
- DR-5: `AB_LATER` already lists both paths. Once they exist, the deployer
  is probed with `test -w/-r/-x`. New test
  `test_tmpfiles_runtime_directories_after_reboot_are_denied_not_matured`:
  PASS stays `P1A-9`/`L1c.3`, six real `DENIED:` lines appear, and an
  allowed `-x` FAILs.
- `installer status` does **not** list the runtime directories' contents. So
  emptiness is checked explicitly (Q4). The comparator treats any LILITH
  `/run` name other than the two as unexpected.

**Live verification (post-reboot, read-only).**

| # | Command | Required |
| --- | --- | --- |
| O-1 | `dev 'sudo -n stat -c "%n %F %U:%G %a %i %d" /run/lilith-authority-dev /run/lilith-recovery-witness /run/lilith-memory'` | `/run/lilith-authority-dev directory root:root 700`; `/run/lilith-recovery-witness directory root:lilith-authority-dev 710`; `/run/lilith-memory directory root:lilith-memory-ipc 710`. Record inode and device (tmpfs) |
| O-2 | `dev 'sudo -n find /run/lilith-authority-dev /run/lilith-recovery-witness -mindepth 1 -printf "%p\n" | wc -l; sudo -n ls -A /run/credentials'` | `0`; `/run/credentials` holds no `lilith-*` entry |
| O-3 | tmpfiles origin: the G13 lines are unchanged (`sudo -n sha256sum /etc/tmpfiles.d/lilith-*.conf`), and `journalctl -b 0 -u systemd-tmpfiles-setup.service --no-pager` shows no error | expected creation came from the installed definitions |
| O-4 | `run_py $INS "status --expect P1A-9 $RELEASE_SHA"` | **PASS**. The OR-6 answer: `P1A-9` semantics are unchanged by tmpfiles runtime directories |
| O-5 | comparator `or6` block (§9 Q3) | both `post=PRESENT_EXACT_TMPFILES_SPEC` |

**Authority claim.** The directories change nothing:

- No unit is active, so nothing listens in them.
- `lilith-authority-dev.socket` is `static` and inactive; its
  `AssertPathIsDirectory=` is only a start precondition.
- No credential is loaded (`/run/credentials` is empty).
- The witness directory's group is the signer's, which grants nothing
  while no witness process exists.

Directory existence ≠ witness state ≠ authority readiness. OR-6 closes as
**`OR6_EXPECTED_TMPFILES_EFFECT`** only when O-1..O-5 all hold. Any other
result → **STOP** (`OR6_UNEXPECTED`).

## 8. Fresh broker baseline procedure (after M-R2)

The historical incarnation `42af2691` cannot be reused. After the reboot,
`preservation` fails by design (`RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE`,
`BASELINE_CANDIDATE_CHANGED`, and `STAGE3_CONTROLLER_CHANGED`). `baseline`
fails too, because custody exists (`CUSTODY_PATH_PRESENT_BEFORE_B1B3D`).
Neither can produce the new candidate.

This preparation adds the reviewed read-only operation **`rebaseline`** to
`scripts/verify_broker_dev_current_incarnation.py` (§15):

- It runs every broker check of `baseline`: release, config, state,
  identity boundary, full sandbox, socket and runtime directory, owner
  socket listening, Stage III journal and artifacts, deployer policy text,
  mapped shared libraries not deleted and inode-equal to disk, one broker
  process, `NRestarts=0`, `ppid 1`.
- The one reviewed reboot effect it accepts is the Stage III controller.
  It must be `loaded`, `inactive/dead`, `Result=success`,
  `ExecMainStatus=0`, `Restart=no`, `NRestarts=0`, and have **no
  InvocationID**, meaning it never ran in this boot. A controller that is
  still failed, ran, is active, restarts, or whose unit file is gone fails
  with `STAGE3_CONTROLLER_CHANGED`.
- It requires a replacement: boot ID ≠ `24d1771d…`
  (`REBOOT_NOT_OBSERVED`), incarnation ≠ `42af2691…`
  (`RUNTIME_INCARNATION_NOT_REPLACED`), candidate ≠ `35495854…`
  (`BASELINE_CANDIDATE_NOT_REPLACED`).
- It reports custody paths and never judges them
  (`authorityCustodyJudgment=NOT_PERFORMED`).
- A failing run emits no `baselineCandidateSha256`. A passing run's output
  is `ownerAcceptance=PENDING_SEPARATE_EXPLICIT_OWNER_DECISION`,
  `continuityWithAcceptedBaseline=false`.
- It never re-pins the accepted constants: `preservation` keeps pinning
  `42af2691` until a separate reviewed change.

**Procedure.**

| # | Step (read-only after M-R2) | Required |
| --- | --- | --- |
| B-1 | `dev 'systemctl show lilith-memory-broker.service lilith-memory-broker.socket -p Id,ActiveState,SubState,MainPID,InvocationID,NRestarts,ExecMainStartTimestamp,UnitFileState'` | service `active/running`, `static`, `NRestarts=0`; socket `active`, `disabled` |
| B-2 | `run_py $BRK rebaseline > mr2/rebaseline1.json` | `BROKER_REBASELINE=PASS`, `failures=[]` |
| B-3 | record from B-2: `bootId` (= `NEW_BOOT`), `runtimeIncarnation`, `baselineCandidate.pid`, `.startTicks`, `.startTime`, `.nRestarts`, `.releaseSha` (= `817a83e…`), `.manifestSha256` (= `7a46ac83…`), `.sharedLibrariesSha256`, `baselineCandidateSha256`; the facts `releaseEquivalent`…`incarnationHealthy` all `true`; process uid/gid 999/987 (in the candidate checks), `ppid 1` | recompute `baselineCandidateSha256` locally from `baselineCandidate` (canonical JSON, as the verifier does) |
| B-4 | wait ≥ 5 minutes; `run_py $BRK rebaseline > mr2/rebaseline2.json` | identical `baselineCandidateSha256` and incarnation: no restart, no library replacement |
| B-5 | `sharedLibraries` contains the post-reboot `libc.so.6` (not `(deleted)`) | new libc mapped (§11) |

`libc6`/`libexpat` bytes may differ from the 2026-09-26 set if they were
upgraded since. That is expected. `sharedLibrariesSha256` is recorded as
new, never compared with `40e68a1c…`.

The candidate from B-2..B-4 is a **candidate only**. A healthy service is
not an accepted baseline. The owner accepts it (or not) in a new record,
and never edits earlier records. After acceptance, a separate reviewed
source change re-pins `ACCEPTED_CURRENT_INCARNATION`,
`ACCEPTED_CURRENT_BASELINE_SHA256`, and `ACCEPTED_CURRENT_BOOT_ID`, as the
N-45 change did. Until then `preservation` fails by design, and every later
gate uses `rebaseline` with the recorded candidate digest.

## 9. PR-1A P1A-9 rebaseline (post-reboot, read-only)

Run in this order after §4.1 (Q1–Q9), then again after M-R2 (Q3, Q5, Q6 only).

| # | Check | Required |
| --- | --- | --- |
| Q1 | identity: G3 and G4 again | same instance and machine-id; boot = `NEW_BOOT` ≠ `$OLD_BOOT`; kernel = `EXPECTED_KERNEL` |
| Q2 | (the `-b -1` part only if the journal is persistent) `dev 'journalctl --list-boots --no-pager | tail -3; journalctl -b -1 -n 30 --no-pager; journalctl -b 0 -p err --no-pager | head -100; systemctl --failed --no-legend --no-pager'` | previous boot ended with an orderly shutdown; errors recorded and classified. A LILITH authority, witness, or broker error → **STOP** |
| Q3 | `run_py $OBS observe > post/obs1.txt`, then locally: `python scripts/compare_reboot_host_observations.py pre/obs1.txt post/obs1.txt "$EXPECTED_KERNEL" 5eaec23cef9c8f53db8e6f27e84b270ad6b8567d4f21287a1ffd543550fe2778` | `REBOOT_OBSERVATION_COMPARISON=PASS unexpected=0`. `unchangedSections` = releases, hostFiles, accounts, currentBlob, hostKey, listings, filesystems. The new post-reboot `stableSha256` is recorded as the candidate observer baseline |
| Q4 | O-1, O-2, O-3 (§7) | as §7 |
| Q5 | `run_py $INS "status --expect P1A-9 $RELEASE_SHA"` | **PASS**. This covers: sole release `aee323e`; CURRENT; custody root exact; `prepared/`/`retired/` empty; witness account and unit assets exact; skeleton exact; K-WIT, registry, ledger, witness state, holds absent; units not active, not enabled |
| Q6 | `dev 'sudo -n /usr/local/sbin/lilith-activation-verify; echo rc=$?'` | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`, rc 1 |
| Q7 | `dev 'systemctl show lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service -p Id,LoadState,ActiveState,SubState,UnitFileState,InvocationID,NRestarts,NeedDaemonReload'` | authority and witness units: `inactive`, `static`, no InvocationID, `NRestarts=0`, `NeedDaemonReload=no`. Stage III controller: `CONTROLLER_POST_REBOOT_EXPECTED` |
| Q8 | RecoveryEpoch / hold / registry: covered by Q3 (`listings`, `pr1Objects`) and Q5 (`PR1_LISTINGS`) | absent / empty |
| Q9 | `dev 'systemctl list-units --type=service --state=running --no-legend --plain --no-pager'` diffed against `pre/services.txt` | the only LILITH difference is the broker (down until M-R2). Other differences are recorded and classified |

Authority and witness services stay inert. Reviewed boot semantics do not
require them to run: they are `static`, not enabled, and have no
`[Install]`.

**Any unexpected authority material → STOP.**

## 10. DR-5 post-reboot re-proof

- The pre-reboot DR-5 (G2) is **not** reused.
- Owner or root observation never substitutes for the routine deployer
  identity `sa_112096412008414111981`.

**How the routine run is obtained without unrelated source changes.** The
owner merges the PR that carries the post-reboot evidence record, after §8
B-4. The record is under `docs/architecture/`, which is not a
`CONTROL_ONLY_PATHS` entry. `classify_dev_deployment.py` therefore
fail-closes it to `DEPLOY_REQUIRED`: the normal routine DEV run, in which
the DR-5 step runs **before** Package/Deploy. This is the same way every
PR-1A DR-5 was obtained. No workflow dispatch, rerun, or synthetic change is
used.

**Required from that run** (observed read-only from GitHub):

- `event=workflow_run` from a `push` to `main`; head = the evidence-record
  merge; the run **started after `NEW_BOOT`'s boot time**. It is not a rerun
  of an older run.
- `SUDO_EFFECTIVE_PROOF=PASS user=sa_112096412008414111981 mode=self`.
- `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`.
- Last line: `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`.
- Real denials for the current objects:
  - `test -w` on `/etc/lilith-authority-dev`, `trust/`, `registry/`, and
    `owner/`;
  - `test -r/-w/-x` on `/etc/lilith-authority-custody`,
    `/etc/lilith-recovery-witness`, and `/var/lib/lilith-authority-custody`;
  - `test -w` on all witness unit files and all six fixed CLIs;
  - `sudo -u lilith-recovery-witness`, `sudo -u lilith-authority-dev`,
    `sudo -u lilith-memory-broker`, every witness and authority unit verb,
    and every fixed CLI.
- **New after the reboot (OR-6):**
  - `DENIED: test -w`, `DENIED: test -r` and `DENIED: test -x` on
    `/run/lilith-authority-dev` and on `/run/lilith-recovery-witness`,
    replacing their earlier `DEFERRED_UNTIL_OBJECT_EXISTS`;
  - still `DEFERRED_UNTIL_OBJECT_EXISTS` for `/var/lib/lilith-authority-dev`,
    `/var/lib/lilith-recovery-witness`, and both `/run/credentials/…`
    directories;
  - `UNOBSERVABLE_BY_DESIGN` for `prepared`, `retired`, the K-WIT blob path,
    and `holds`.

**After that run** (owner session, read-only): `rebaseline` again, which
must give the **same** candidate digest as B-4. `status --expect P1A-9`
PASS, activation `GRANT_ABSENT`, and observer `stableSha256` equal to the
post-M-R2 value. Together these prove the routine deploy did not touch the
broker or authority state.

A DR-5 FAIL, or a missing or changed PR-1 line, is a **STOP**. Do not rerun.

## 11. needrestart and maintenance

| Item | Before (G9–G11) | After | Required |
| --- | --- | --- | --- |
| running kernel | `6.17.0-1022-gcp` | `/proc/sys/kernel/osrelease` | = `EXPECTED_KERNEL` |
| `reboot-required` / `.pkgs` | present; list recorded | `ls -l /var/run/reboot-required*` | absent |
| libc | `dpkg-query -W libc6` | same package version; `dev 'sudo -n grep -l "libc.so.6 (deleted)" /proc/[0-9]*/maps 2>/dev/null | wc -l'` | same version; `0` processes map a deleted libc |
| needrestart package / main conf / conf.d | `3.6-7ubuntu4.5` / `baacdd68…` / README + snippet | same commands | unchanged |
| protected-service exclusions | probe PASS | `run_py $NRP probe` | `NEEDRESTART_LILITH_OVERRIDE=PASS`: broker, `lilith-authority-dev`, `lilith-recovery-witness` `EXCLUDED`; control units `DEFAULT`; `installedFile.matchesArtifact=true` |
| package activity during the window | G11 idle | `dev 'grep -h " install \| upgrade " /var/log/dpkg.log | tail -20; sudo -n tail -30 /var/log/unattended-upgrades/unattended-upgrades.log'` | no package operation between G11 and the end of §9. If one happened, record it. If it touched a library the broker maps after M-R2, STOP (`RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE` path, baseline record §7) |

`needrestart` itself is **never executed** (baseline record §6). In its
APT-hook default mode it could restart other services. No package upgrade
is authorized by this ceremony.

If `EXPECTED_KERNEL` equals the running kernel at G10 (only libraries
pending), the reboot still clears the library debt. The comparator then
reports `KERNEL_UNCHANGED_AS_EXPECTED`, and §11 records that OR-5 closes
for libraries only.

## 12. Owner storage (nonmutation)

The reboot has no relationship to the owner replicas. **Neither is
contacted during the ceremony**: no S25 contact, no WSL freshness tool, no
envelope or record command.

| Replica | Expectation |
| --- | --- |
| A `owner-primary-dev-synthetic-01` (laptop WSL) | unchanged; empty; `REPLICA.json` `fbdd045c…978b` |
| B `owner-offline-dev-synthetic-01` (S25 Termux) | unchanged; empty; `REPLICA.json` `c068e533…07c4` |
| accepted freshness records | `0` |
| real freshness | **`FRESHNESS_UNKNOWN`** (unchanged) |

A reboot of DEV cannot move owner freshness in either direction. Freshness
is judged owner-side only.

## 13. Failure / stop matrix

After any STOP, PR-1B progression is blocked. Nothing is repaired
automatically, and the host is **not rebooted a second time** "to see if it
fixes it".

| # | Condition | Phase | Classification / action |
| --- | --- | --- | --- |
| F-1 | any G0–G15 mismatch (§3) | pre | `PRE_REBOOT_STATE_DRIFT`: STOP before M-R1 |
| F-2 | an authority, broker, witness, or Stage III unit enabled (G12) | pre | STOP before M-R1; it would start at boot |
| F-3 | package operation in flight, half-configured package, or ambiguous boot kernel | pre | wait, or STOP before M-R1 |
| F-4 | host not back within 15 min; panic or boot loop | reboot | `REBOOT_NOT_COMPLETED`: serial output read-only; STOP; owner recovery decision |
| F-5 | boot ID unchanged | reboot | `REBOOT_NOT_OBSERVED`: STOP (M-R1 did not take effect; do not reissue without owner) |
| F-6 | kernel ≠ `EXPECTED_KERNEL` | post | `KERNEL_NOT_EXPECTED`: STOP; OR-5 stays open |
| F-7 | comparator `unexpected` non-empty | post | `REBOOT_OBSERVATION_UNEXPECTED`: STOP |
| F-8 | `status --expect P1A-9` FAIL | post | `P1A9_REBASELINE_FAILED`: STOP |
| F-9 | CURRENT changed | post | STOP; custody incident |
| F-10 | K-WIT, registry, ledger, witness state, hold, RecoveryEpoch, or `prepared/`/`retired/` content | post | STOP; custody incident |
| F-11 | activation ≠ `GRANT_ABSENT` | post | STOP |
| F-12 | authority or witness unit active, enabled, or with an InvocationID | post | STOP |
| F-13 | OR-6 directory wrong spec, non-empty, or not created; `/run/credentials/lilith-*` present | post | `OR6_UNEXPECTED`: STOP |
| F-14 | broker running before M-R2 | post | STOP: an unexplained start path |
| F-15 | M-R2 start fails, or `rebaseline` FAIL, or B-4 digest differs | M-R2 | `BROKER_BASELINE_NOT_ESTABLISHED`: STOP; no retry |
| F-16 | owner declines M-R2 | M-R2 | `BROKER_BASELINE_NOT_ESTABLISHED` (fail-closed); not PR-2 eligible |
| F-17 | DR-5 FAIL or PR1 line ≠ `P1A-9` | DR-5 | STOP; no rerun |
| F-18 | post-DR-5 `rebaseline` digest ≠ B-4 | DR-5 | STOP: the routine deploy touched the broker |
| F-19 | needrestart, sudoers, or security configuration drift | any | STOP |
| F-20 | unexplained filesystem or runtime state | any | STOP |
| F-21 | any merge to main during the freeze (G1 → end of §9), other than the §10 evidence merge | any | repeat the affected gate steps; if they changed, STOP |

## 14. PR-2 relationship and eligibility decision

A successful reboot and rebaseline is:

- M-R1 done;
- §9 PASS, and OR-6 closed as expected;
- M-R2 done, with B-1..B-5 PASS;
- the owner accepts the new broker candidate;
- §10 DR-5 PASS, with the post-DR-5 digest equal.

When all hold, DEV is **eligible for PR-2 READ-ONLY REVALIDATION**. It is
**not** eligible for PR-1B.

The next required phase remains **PR-2 read-only revalidation**, run after
the fresh baseline (P3-5 §13). It checks:

- no snapshot, instant snapshot, image, machine image, or resource policy was
  created. The reboot itself creates none, and OR-8 must still show none;
- the Admin Activity method set since the PR-2 window. The in-guest reboot
  is not a GCE `reset`, so it should add no compute mutation method;
- the owner storage topology.

No snapshot, backup, or cloud revalidation is executed by this preparation.

## 15. Source and test changes (this preparation)

| File | Change |
| --- | --- |
| `scripts/verify_broker_dev_current_incarnation.py` | third fixed operation `rebaseline` (§8); `ACCEPTED_CURRENT_BOOT_ID`; `CONTROLLER_POST_REBOOT_EXPECTED`; `_broker_checks(controller_expected=…)`; controller collection reads both contracts. `baseline` and `preservation` behaviour and pins unchanged |
| `scripts/test_verify_broker_dev_current_incarnation.py` | `RebaselineTests` (9 tests): pass shape; the same host fails `preservation`/`baseline`; pre-reboot and restart-without-reboot refused; controller states; every drift class after reboot; broker-down fails closed; real supersession pins; the only-fixed-operations test now covers three operations |
| `scripts/compare_reboot_host_observations.py` | new, offline-only PRE/POST observer comparator (§5, §7). It recomputes the observer's stable and section digests and never trusts them. There is no subprocess or network |
| `scripts/test_compare_reboot_host_observations.py` | 16 tests: the expected reboot; suspicious changes; OR-6; `/run` namespace; host facts; transcript integrity; CLI exit codes; offline-only contract; tmpfiles specs pinned to the deploy assets; digest equality with the real observer (POSIX) |
| `services/authority-dev/tests/test_pr1s_installer_upgrade.py` | OR-6 `P1A-9` status test (§7) |
| `scripts/test_deployer_authority_boundary_proof.py` | OR-6 DR-5 test (§7) |
| `.github/workflows/ci.yml` | runs the new comparator test file |

Not changed: the observer, the installer, the DR-5 script, the needrestart
artifact, any unit, tmpfiles or release file, and `release_file_set.py`
(a build-attestation recipe file).

## 16. Nonclaims

This record does **not**:

- authorize or perform the reboot, the broker start, or any DEV contact;
- accept any new broker baseline, observer baseline, or DR-5 result;
- claim that the new kernel or libc is behaviourally equivalent. Observation
  proves artifact equivalence only;
- establish whole-host or snapshot rollback resistance (OR-1 stays open);
- close DR-3;
- close OR-5 or OR-6. Both close only with live evidence;
- make PR-1B eligible, or change real owner freshness;
- create or authorize K-ROOT, K-WIT, registry, ledger, witness state, hold,
  RecoveryEpoch, or real record 1.

## Explicitly not done

```text
REBOOT NOT YET AUTHORIZED
BROKER START (M-R2) NOT YET AUTHORIZED
NO DEV CONTACT
NO DEV MUTATION
NO PROD CONTACT
NO K-ROOT
NO K-WIT
NO REGISTRY
NO LEDGER
NO WITNESS STATE
NO HOLD
NO RECOVERY EPOCH
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
