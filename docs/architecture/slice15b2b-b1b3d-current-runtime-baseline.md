# 15B2b-B1b-3d — Current DEV Runtime Baseline Acceptance and needrestart Control

**Status:** CURRENT RUNTIME BASELINE ACCEPTED FOR B1b-3d DEV_SYNTHETIC ENTRY.
The needrestart control is DESIGNED and NOT INSTALLED.
**Owner decision date:** 2026-09-26 UTC. **Host:** `lilith-dev-01` only.

This record is **not** a Stage II acceptance. It does not mean:

- `STAGE_II_ACCEPTED`;
- real authority is ready;
- runtime behaviour is fully proven;
- whole-host root isolation;
- DR-3 or DR-5 is closed.

The historical Stage II record
([slice15b2b-accepted-stage2-lifecycle.md](slice15b2b-accepted-stage2-lifecycle.md))
is unchanged. It covers release `817a83e`, InvocationID `5c1eb955…`, and
PID 96650. It is not extended to the incarnation accepted below.

## 1. History

- The accepted Stage II broker process ended on 2026-09-25 when the Stage III
  A2 controller stopped it.
- The owner started the broker again (incarnation `42a0608f…`).
- On 2026-09-26 at 06:34:09 UTC, `unattended-upgrades` installed a `libexpat1`
  security update, and `needrestart` then restarted the broker. That produced
  the current incarnation.
- DR-1 classified this as `DR1-EXPLAINED_UNRECORDED`: state-equivalent,
  process-only, with incomplete evidence. Full evidence:
  [slice15b2b-dr1-broker-restart-forensics.md](slice15b2b-dr1-broker-restart-forensics.md).
- DR-1 §11 gates B1b-3d on:
  1. a read-only revalidation;
  2. explicit acceptance of the resulting baseline;
  3. a needrestart decision.

## 2. Read-only revalidation (2026-09-26)

| Item | Value |
| --- | --- |
| Protected main | `ab9efccc5d640495f8b786f1a7a8ae2c58ccb210` |
| Verifier | [`scripts/verify_broker_dev_current_incarnation.py`](../../scripts/verify_broker_dev_current_incarnation.py), SHA-256 `a4bf3ebcdfa9a292cebafb823376e67b785cb8444a77e0aaf5762ebafb373d75` (hashed locally and again on the host from the executed bytes) |
| Target | `lilith-dev-01`, project `lilith-agent-260823-27389`, zone `asia-southeast1-b`. Hostname, FQDN, machine-id, and GCE instance name and ID were checked before any privileged read |
| Mode | `sudo -n /usr/bin/python3 -I -B - baseline`; exit code 0 |
| Verdict | `CURRENT_RUNTIME_BASELINE=PASS`, `failures=[]` |

**Transport note.** The first attempt piped the script over stdin through
gcloud/plink on Windows. A stray `y` arrived first on stdin, so Python stopped
with `NameError` on line 1, before any import or read. The same bytes were then
embedded, gzip+base64, in the SSH command. Future runbooks must use the
embedded form.

### Equivalence (all true)

| Predicate | What it covers |
| --- | --- |
| `releaseEquivalent` | selector `releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, root:root; manifest `7a46ac83…4614`; no payload mismatches; the process's cwd and command line are on that release |
| `configEquivalent` | unit, socket and tmpfiles files; `dev.json`; `identities.json`; three `.used` authorization files; directory custody (hash, owner, mode) |
| `stateEquivalent` | `owner_control.db` and `synthetic_evidence.db`, hashed as bytes and never opened as SQLite |
| `identityBoundaryEquivalent` | broker account 999:987 with nologin; `lilith-memory-ipc` 988 has only `lilith-memory-relay`; process uid and gid are 999/987 on all four fields; NoNewPrivs=1; all capability sets are zero; the full systemd sandbox matches |
| `socketBoundaryEquivalent` | socket unit; `/run/lilith-memory` is 0:988 0710; `owner.sock` is 999:988 0660 and listening (read from `/proc/net/unix`, no connection) |
| `stageIIIUntouched` | only `000-INTENT.json` in the journal; no arm, guard, `activation.ready`, or guard claim; authorization not consumed; controller `failed/exit-code`; tombstones match their pinned hashes |
| `deployerPolicyTextEquivalent` | B1c sudoers text and helper hash. This is policy text only, not proof of any denial |
| `incarnationHealthy` | active/running, `NRestarts=0`, one broker process, MainPID consistent |
| Runtime substrate | 25 file-backed mappings, none deleted, every inode matches the file on disk. This includes the patched `libexpat.so.1.9.1` |

### Continuity and behaviour

- `processContinuity=false`.
- `runtimeBehavioralEquivalence=NOT_PROVEN_BY_OBSERVATION`.
- `stageIIAcceptance=HISTORICAL_RECORD_UNCHANGED_NOT_EXTENDED_TO_THIS_INCARNATION`.
- All 11 planned custody paths are `NOT_YET_PRESENT`, never `DENIED`.
- The output contains no `STAGE_II_ACCEPTED` token.

## 3. Accepted incarnation

| Field | Value |
| --- | --- |
| InvocationID | `42af2691b8d24ee5a92a286197c5444c` |
| PID | `132976` (ppid 1) |
| Boot ID | `24d1771d-e1b5-4e5f-816d-da08ad8b367a` |
| Start ticks | `108213277` |
| Start time | `2026-09-26T06:34:08Z` (from ticks; systemd reports `Sat 2026-09-26 06:34:09 UTC`, the gap is rounding down to whole seconds) |
| NRestarts | `0` |
| Release | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, manifest `7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614` |
| Shared-library set digest | `40e68a1c27328c27b811da19bb17a1262cbacff18dcd7ab397e06bebb17a87bd` |
| `baselineCandidate` SHA-256 | `3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5` (recomputed independently from the output) |

**Owner acceptance scope.** The owner accepts this incarnation as the starting
DEV runtime baseline for 15B2b-B1b-3d DEV_SYNTHETIC work, and for nothing
else.

- Any process replacement ends this acceptance. That includes a restart by
  needrestart, the owner, `Restart=on-failure`, or a reboot.
- A replacement needs a new read-only revalidation and a new explicit
  acceptance (§7).

## 4. needrestart mechanism (read-only discovery on DEV)

| Fact | Observed |
| --- | --- |
| Package | `needrestart 3.6-7ubuntu4.5`; `unattended-upgrades 2.9.1+nmu4ubuntu1` |
| Unattended upgrades | `APT::Periodic::Update-Package-Lists "1"`, `APT::Periodic::Unattended-Upgrade "1"` |
| Hook | `/etc/apt/apt.conf.d/99needrestart`: `DPkg::Post-Invoke` → `/usr/lib/needrestart/apt-pinvoke -m u` → `/usr/sbin/needrestart -m u` |
| Restart mode | `$nrconf{restart}` commented. Per the conf file and `README.Ubuntu`, the APT-hook default on 24.04 is `a` (restart automatically) |
| Main config | `/etc/needrestart/needrestart.conf`, root:root 0644, SHA-256 `baacdd683222532d35770efbf7cd83360fc33a4c49ef010787628f0da778f7ee` |
| conf.d | `/etc/needrestart/conf.d/` holds only `README.needrestart` (SHA-256 `7d6b97614b312a84399ea53794de7f612e03a730379535bb147ae6a2af62b6ef`) |
| Snippet loading | the main conf runs `foreach my $fn (sort </etc/needrestart/conf.d/*.conf>) { eval do { local(@ARGV, $/) = $fn; <>}; die … if($@); }`, after it assigns the default `$nrconf{override_rc} = { … }` hash |
| Matching | `/usr/sbin/needrestart` lines 1092–1101: for each unit, `foreach my $re (keys %{$nrconf{override_rc}}) { next unless($rc =~ /$re/); $restart = $nrconf{override_rc}->{$re}; last; }`; a falsy value puts the unit in `@skipped_services` ("Service restarts being deferred") |
| Unit names | `$rc` is the full unit name, for example `lilith-memory-broker.service`, as in the DR-1 dpkg log |

### Selected mechanism

Additive, service-specific `override_rc` keys, with value `0`, in a new
conf.d snippet.

**Why:**

- Security packages still install.
- Every other service keeps the distribution default.
- The deferred restart is logged, not hidden.

**Rejected:**

- `blacklist_rc`: it ignores the unit completely, so it would hide staleness.
- A global `$nrconf{restart}` change: it affects every service.
- An unattended-upgrades package blacklist: it blocks security fixes.

**Constraints:**

- Hash iteration order is random and the first match wins. So each LILITH
  unit must be matched by exactly one regex. No distribution default regex
  matches `lilith-`.
- One literal unit name per line keeps the existing baseline observer's
  `parse_needrestart` able to report each service.

## 5. Proposed artifact (source-controlled, not installed)

- **Source:** [`services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf`](../../services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf)
- **Install path:** `/etc/needrestart/conf.d/lilith-authority-sensitive.conf`, root:root `0644`. This matches the package's own files.
- **Size:** 1398 bytes.
- **SHA-256:** `503279315ccc884d8a68505c86b51dfd09387b393c9becba684b1fa1c28068d2`.

The only non-comment lines:

```perl
$nrconf{override_rc}{qr(^lilith-memory-broker\.service$)} = 0;
$nrconf{override_rc}{qr(^lilith-authority-dev\.service$)} = 0;
$nrconf{override_rc}{qr(^lilith-recovery-witness\.service$)} = 0;
```

**Packaging boundary.** The file is SOURCE-CONTROLLED INSTALL MATERIAL, not
AUTOMATIC BROKER RUNTIME PAYLOAD. The chain is: source-controlled artifact ≠
deployed artifact ≠ installed configuration ≠ activated control.

- The broker file-set contract in
  [`scripts/memory_broker_validation.py`](../../scripts/memory_broker_validation.py)
  lists it as the only `SOURCE_ONLY_BROKER_FILES` entry.
  - The file is accepted only as an exact addition to the B1b-2a tree.
  - It is never packed into the runner-only validation artifact. The archive
    stays byte-identical, and a copy injected into the archive is rejected.
  - Any other extra file still fails with `BROKER_FILE_SET_MISMATCH`.
- It is not in the broker OS release, which pins its own `ASSET_HASHES`.
- It is not in the Core API bundle or any deployment workflow or helper.
- It is not in the PROD `deploy.yml` path filter.
- The DEV classifier gives it no special lane: fail-closed `DEPLOY_REQUIRED`
  runs the routine Core API deployment only.

**Read-only probe:**
[`scripts/probe_needrestart_lilith_override.py`](../../scripts/probe_needrestart_lilith_override.py).

- It loads `needrestart.conf` with the same string-eval form needrestart uses,
  so conf.d is loaded by the main file itself.
- It lists every `override_rc` regex that matches each unit.
- It reports `EXCLUDED` only when exactly one regex matches with value `0`.
- It fails if any control unit is matched by a LILITH regex, or if
  `blacklist_rc` is non-empty.
- Its only subprocess is `/usr/bin/perl` with a fixed program. It does not run
  needrestart.

**Tests:**
[`scripts/test_needrestart_lilith_override.py`](../../scripts/test_needrestart_lilith_override.py).
They check:

- the pinned hash, LF-only ASCII content, and exactly three additive
  statements;
- each unit is covered exactly once;
- unrelated units are not covered: `lilith-os-api-dev`, `lilith-os-api`,
  `polkit`, `ssh`, `cron`, the broker socket, prefixes and suffixes;
- no global restart, UI, blacklist, whole-hash assignment, or
  APT/unattended-upgrades setting;
- no command, key, credential, sudo, systemctl, or path in the code;
- the existing baseline observer recognises all three services;
- real-Perl semantics through a fixture that reproduces the loader form of the
  observed main conf:
  - the three units are excluded and distribution defaults are preserved;
  - with no artifact, the units keep the default restart;
  - a conflicting later snippet is detected as ambiguous;
  - a parse error fails closed.

## 6. Owner-controlled install and rollback runbook (NOT EXECUTED)

This is one mutation: installing one root-owned file.

- **Operator:** the owner's local gcloud/IAP session.
- **Automation:** none. No GitHub Actions runner or deployer identity takes
  part.
- **Scripts:** from protected main after this record is merged.
- **Transport:** embed scripts in the SSH command; never pipe them over stdin
  (§2).

```bash
DEV=lilith-dev-01; ZONE=asia-southeast1-b; PROJECT=lilith-agent-260823-27389
SHA=503279315ccc884d8a68505c86b51dfd09387b393c9becba684b1fa1c28068d2
F=/etc/needrestart/conf.d/lilith-authority-sensitive.conf
T=/etc/needrestart/conf.d/.lilith-authority-sensitive.conf.new
b64() { git show "origin/main:$1" | gzip -9n | base64 -w0; }
dev() { gcloud compute ssh "$DEV" --zone="$ZONE" --project="$PROJECT" --tunnel-through-iap \
          --command="test \"\$(hostname)\" = lilith-dev-01 || exit 97; $1" </dev/null; }
V=$(b64 scripts/verify_broker_dev_current_incarnation.py)
P=$(b64 scripts/probe_needrestart_lilith_override.py)
A=$(b64 services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf)
```

### PRE (read only)

1. **Target.** Every command starts with the hostname guard. Exit 97 means
   STOP. Never name `lilith-01`.
2. **Baseline.**

   ```bash
   dev "printf %s $V | base64 -d | gunzip | sudo -n /usr/bin/python3 -I -B - baseline"
   ```

   Require all of:
   - `CURRENT_RUNTIME_BASELINE=PASS`;
   - `runtimeIncarnation=42af2691b8d24ee5a92a286197c5444c`;
   - `baselineCandidateSha256=3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5`.

   Any difference means the baseline changed. STOP: this install waits for a
   new revalidation and a new acceptance (§7).
3. **needrestart inventory.** Require:
   - `dpkg-query -W needrestart` = `3.6-7ubuntu4.5`;
   - `sha256sum /etc/needrestart/needrestart.conf` = `baacdd68…f7ee`;
   - `ls -A /etc/needrestart/conf.d` = `README.needrestart` only;
   - `$F` and `$T` absent.

   A version change, a different main conf, or any unknown conf.d file means
   STOP. Syntax and semantics were established for this exact version only.
4. **Probe before installing.**

   ```bash
   dev "printf %s $P | base64 -d | gunzip | sudo -n /usr/bin/python3 -I -B - probe"
   ```

   Expect `FAIL` with all three units `DEFAULT` and `installedFile.present=false`.
   This shows the probe tells the two states apart on the real config.
5. **Intended bytes.** Require:

   ```bash
   dev "printf %s $A | base64 -d | gunzip | sha256sum"
   ```

   to output `$SHA`.

### MUTATION (one step)

```bash
dev "set -e; test ! -e $F; test ! -e $T; \
     printf %s $A | base64 -d | gunzip | sudo -n install -o root -g root -m 0644 /dev/stdin $T; \
     echo '$SHA  $T' | sudo -n sha256sum -c -; \
     sudo -n mv -n -T $T $F"
```

- The temporary name does not end in `.conf`, so needrestart never parses it.
- `mv -T` in the same directory is an atomic `rename(2)`.
- No service is started, stopped, restarted, or reloaded, and there is no
  `daemon-reload`.
- If the hash check fails, `set -e` stops before the rename. Remove only `$T`,
  then STOP.

### POST (read only)

1. `sudo -n stat -c '%U:%G %a %s' $F` = `root:root 644 1398`.
   `sudo -n sha256sum $F` = `$SHA`.
   `ls -A /etc/needrestart/conf.d` = `README.needrestart` plus
   `lilith-authority-sensitive.conf`.
2. The probe returns `NEEDRESTART_LILITH_OVERRIDE=PASS`:
   - the three units are `EXCLUDED`;
   - all control units are `DEFAULT`;
   - `restartMode=DEFAULT`;
   - `installedFile.matchesArtifact=true`.
3. `systemctl show lilith-memory-broker.service -p InvocationID,MainPID,NRestarts`
   still reports `42af2691…`, `132976`, and `0`. The install did not restart
   the broker.
4. The verifier re-run returns `PASS` with the **same**
   `baselineCandidateSha256`, and `informational.needrestart.serviceSpecificExclusion`
   is true for all three.

**Do not run `needrestart` to "test" the file.** Under the APT-hook default it
would restart other services. The live effect shows only at the next upgrade
that touches a broker library: the dpkg log then lists the broker under
"Service restarts being deferred" and does not restart it. Until then, the
proof is the probe plus the source-level semantics in §4.

### STOP conditions

- the target is not `lilith-dev-01`;
- the baseline digest or incarnation changed;
- the needrestart version or main conf changed, or an unknown conf.d file
  exists;
- `$F` or `$T` already exists;
- the probe or hash disagrees;
- the broker's InvocationID, MainPID, or NRestarts changed at any point.

After a STOP, repair nothing automatically. Report, and roll back only if the
file was installed.

### ROLLBACK

```bash
dev "set -e; echo '$SHA  $F' | sudo -n sha256sum -c -; sudo -n rm -- $F; sudo -n rm -f -- $T"
```

- It removes only the exact installed file, and only when its hash is the
  pinned one. If the hash differs, STOP: an unknown file is never removed.
- After rollback:
  - conf.d is `README.needrestart` only;
  - the probe returns `FAIL` with the three units `DEFAULT`;
  - the broker's InvocationID and MainPID are unchanged.
- No service is restarted.
- Rollback brings the DR-1 §8 exposure back.

## 7. Maintenance ceremony (future, owner-controlled)

Two rules hold throughout:

- **automatic restart ≠ unauthorized authority mutation**;
- **process replacement requires revalidation evidence.**

After the exclusion is installed, a security update can leave an
authority-sensitive service running an old library. That condition must be
visible, and it must be closed only by ceremony:

1. **Security update installed.** unattended-upgrades runs unchanged.
   needrestart lists the LILITH unit as deferred.
2. **Unit marked for controlled maintenance.** The verifier reports
   `RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE`, because a mapping is deleted or its
   inode differs from the file on disk. The dpkg log shows the deferral. The
   baseline is no longer `PASS`.
3. **Authority issuance held.** The owner places the B1b-3d `hold` marker, or,
   before authority exists, performs no owner or Stage III operation.
4. **The owner restarts the unit explicitly**, one unit at a time:
   `sudo systemctl restart <unit>` from the owner session. There is no
   combined restart and no automation.
5. **Read-only verifier runs** against the new incarnation (§2 mode).
6. **A new incarnation baseline is generated**, with a new InvocationID, PID,
   start ticks, and candidate digest.
7. **The owner explicitly accepts** it in a new record. Earlier records are
   never edited.
8. **Authority issuance resumes.** The hold is released only after step 7.

A reboot, `Restart=on-failure`, or any unplanned replacement enters the same
ceremony at step 5. Issuance stays held until step 7. The units stay `static`
and not enabled, so a reboot leaves them down, which fails closed.

## 8. Open debt (unchanged)

- **DR-3 (open).** `ubuntu` is in `adm`, `cdrom`, `dip`, `lxd`, `sudo`, and
  `ubuntu`. Both `sudo` and `lxd` are root-equivalent. The password is locked
  and `authorized_keys` is empty (0 bytes). Nothing was changed, and no
  stronger host-root isolation is claimed.
- **DR-5 (open).** `sudoAsBrokerDenial=NOT_TESTED_DR5_OPEN`. The
  `sudo -n -u lilith-memory-broker` denial must be proven explicitly at
  B1b-3d live acceptance (`PATH_EXISTS`, then `ACCESS_DENIED`). A missing path
  is never a denial.

## 9. Live-entry gates remaining (DR-1 §11)

| Gate | State |
| --- | --- |
| 1. DR-1 forensic record merged | DONE |
| 2. Read-only revalidation `PASS` | DONE (§2) |
| 3. Owner acceptance recorded separately | RECORDED HERE; effective once merged to protected main |
| 4. needrestart handling decided | DECIDED (§4–§5); **installation pending** a separate owner-authorized run of §6 with a passing POST |

B1b-3d custody installation (design L1 onwards) must not start before gate 4
has been installed and post-verified. Until then, the next library update
mapped by the broker can restart it again and end this acceptance.

## Evidence limitations

- The observation is point-in-time. No file-integrity monitoring ran between
  Stage II and 2026-09-26.
- The observer runs as root on a host where root, including DR-3's `ubuntu`,
  could alter what it reads.
- It shows the artifacts and the boundary are equivalent. It does not show
  behavioural equivalence.
- The deployer boundary evidence is policy text only.
- The needrestart semantics were read from the installed 3.6 source and
  config. They were not demonstrated by a live deferred upgrade, and the probe
  emulates the loader rather than running needrestart.
- Whether unattended-upgrades is configured to reboot automatically was not
  inspected.

## Explicitly not done

- No needrestart, unattended-upgrades, systemd, sudoers, IAM, WIF, or
  `ubuntu` change.
- No restart, start, stop, reload, or `daemon-reload`.
- No key, credential, or custody path created. No authority activated.
- No Stage III retry. No authorization consumed.
- No PROD contact.
