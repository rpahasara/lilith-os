# Slice 15B2b-B1b-3e — PR-1A Reproducible Build / Attestation Gate

Status:

- **REPRODUCIBLE BUILD / ATTESTATION**
- **NO DEV MUTATION** (no DEV or PROD contact of any kind)
- **PR-1A PASS 2 NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**; **REAL AUTHORITY ABSENT**
- Result: **`PR1A_BUILD_ATTESTATION_PASS`**

Branch `claude/15b2b-b1b3e-pr1a-build-attestation`, base protected main
`aee323e94412accbe321bc84eae78c5b8cf95afc` (the merge of the
[read-only preflight](slice-15b2b-b1b3e-pr1a-readonly-preflight.md), PR #91).
Since `3848ab0` (PR-1S), main has changed only in docs, so the candidate's
installable source is exactly the reviewed PR-1S source.

This gate proves one thing:

```text
same source + same declared build inputs = same install artifact
```

That result identifies the one archive PR-1A Pass 2 may later install. It
is build provenance only:

```text
build attestation != authority     != K-ROOT
build attestation != owner acceptance
reproduced        != installed     != activated
artifact digest   != live preflight
```

## 1. Source identity

| Item | Value |
| --- | --- |
| `SOURCE_SHA` (built) | `aee323e94412accbe321bc84eae78c5b8cf95afc` (pristine merged main) |
| Source changed during this gate | yes. Ceremony tooling only, in commit `bf866b2b803b57dee7ba04594575351f419581f3` (§12). It is **not** release payload, so the candidate is still built from `aee323e` |
| Clean-source check | before each build: `git rev-parse HEAD` = `SOURCE_SHA` and `git status --short --untracked-files=all` empty. The builder re-checks this itself (`require_exact_clean`) |
| Line endings | repository/user `core.autocrlf=false`. The system `gitconfig` has `true`, but it is overridden. BUILD_B sets `false` explicitly. The source runtime digests equal the PR-1S record §3 |

## 2. What PR-1A installs (actual builder structure)

`ceremony/build_authority_dev_release.py` produces **one** deterministic
`tar.gz` plus the builder stamp (`…attestation.json`, fields
`schemaVersion, artifactRole, candidateSha, archiveByteSize, archiveSha256,
manifestSha256`). The installer's `upgrade-stage` (M-A1) accepts only this
pair (`verify_archive`) and writes each member into `releases/<SHA>`.

The archive holds 65 payload files plus `release-manifest.json`:

| Group (prompt §6) | In the archive as | Members |
| --- | --- | --- |
| A. authority-dev release | `lilith_authority_dev/`, `lilith_authority_host/`, pinned shared `lilith_memory/`, `lilith_owner_memory/` | 11 + 4 + 3 + 12 modules |
| B. root tooling / CLIs | `lilith_authority_root/` (8 modules) + `cli/` (6 fixed CLIs) | exactly `I.CLI_TARGETS`; nothing else is installed `0755` |
| C. recovery witness | `lilith_recovery_witness/` (8 modules) + its 4 `assets/` | own manifest digest |
| D. unit assets | `assets/` (7: signer unit, socket, tmpfiles; witness unit, 2 sockets, tmpfiles) | |
| E. installer | **not an install artifact.** `install_authority_dev.py` is streamed ceremony control (N-45: `RELEASE_SHA != CONTROL_SHA`) | recorded in the build recipe digest |
| F. manifest / attestation | `release-manifest.json` (member) + builder stamp (beside the archive) + this gate's attestation | |
| dependencies | `wheels/` (5 hash-pinned wheels) + `requirements.lock` | §8 |

## 3. Builds

Wheelhouse (both builds):

- a separate copy per build of the five wheels from the accepted
  `9ac7de2` build wheelhouse;
- each copy checked with `sha256sum -c` against the pinned
  `install_authority_dev.WHEEL_HASHES` (all `OK`);
- no download, and no shared output directory.

| | BUILD_A | BUILD_B |
| --- | --- | --- |
| Host / OS | Windows 11 Pro 10.0.26200 | WSL2 Ubuntu 24.04.5 LTS (kernel 6.6.87.2-microsoft-standard-WSL2) |
| Python / zlib | CPython 3.13.5 / zlib 1.3.1 | CPython 3.12.3 / zlib 1.3 |
| git | 2.50.0.windows.2 | 2.43.0 |
| Clean source | new detached `git worktree add --detach <A>/src aee323e` | new empty repo; `git fetch <bundle> refs/remotes/origin/main:refs/heads/candidate` from a `git bundle` of `origin/main`; `git fsck --full`; `checkout --detach aee323e`. The private repository is not reachable from WSL without credentials, and none were added |
| Environment | ambient user shell | `env -i PATH=/usr/bin:/bin LANG=C.UTF-8 python3 -I -B` |
| Locale / TZ | cp1252 / +0530 | C.UTF-8 / +0530 |
| `SOURCE_DATE_EPOCH` | unset | unset |
| Started (UTC) | 2026-09-28T11:45:48Z | 2026-09-28T11:46:28Z |

- The timezone does not matter: the builder pins every tar mtime to 0 and
  the gzip mtime to 0.
- System `tar` and `gzip` (GNU tar 1.35; gzip 1.14 / 1.12) are **not
  used**. The builder uses Python `tarfile` and `gzip`.
- pip is not used by the build.

The exact command in each build (with `<X>` = the build's directory):

```text
python services/authority-dev/ceremony/build_authority_dev_release.py \
  --candidate-sha aee323e94412accbe321bc84eae78c5b8cf95afc --wheelhouse <X>/wheelhouse \
  --archive <X>/out/lilith-authority-dev-release.tar.gz \
  --attestation <X>/out/lilith-authority-dev-release.attestation.json
python services/authority-dev/ceremony/attest_authority_dev_build.py inspect \
  --sha aee323e94412accbe321bc84eae78c5b8cf95afc --source-root <X>/src \
  --archive <X>/out/lilith-authority-dev-release.tar.gz \
  --stamp <X>/out/lilith-authority-dev-release.attestation.json --out <X>/inspection.json
python services/authority-dev/ceremony/attest_authority_dev_build.py attest \
  --a <A>/inspection-a.json --b <B>/inspection-b.json --out candidate/pr1a-build-attestation.json
```

The attestation tool is the gate-branch version, SHA-256 `709cd552…d3e3`,
byte-identical on both hosts.

## 4. BUILD_A vs BUILD_B

**Byte-identical.** Different OS, Python, zlib, and git produced the same
bytes. `cmp` of both archives and both stamps: equal. The inspections'
`identitySha256` are equal. `attest` found zero differing identity paths.

| Item | BUILD_A | BUILD_B |
| --- | --- | --- |
| archive SHA-256 | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` | same |
| archive size | 5 354 725 | same |
| uncompressed tar SHA-256 | `4ea785ae062eaa6d1dd3cd1e8228d5e45d2f6299e0553d6cc5380a0767b35cc8` | same |
| gzip header | method 8, flags 0, mtime 0, xfl 2, OS 255 | same |
| builder stamp SHA-256 | `9441c985ab5724f68bd9e0199ac98593b930236150ef10778c242f673bdb1b42` | same |
| `manifestSha256` (`release-manifest.json`) | `1d578ca707a95134dab218c826408b4380e7af0b5839160f47ede37232b94e8f` | same |
| inspection `identitySha256` | `60cf0c7e35d782ceea510d949d60b164bfb0210db33332ea778bb2b93d4d6824` | same |
| authority digest | `4b32f169fb5d83873d574845fb8a38bbae31a904be941fc2411b0d4202a9671b` | same |
| root-tooling digest | `28e9d6cbdb0d2642074d10c4d8dc9e83c9c7b19f90c6676248b920cd6c47b903` | same |
| recovery-witness digest | `5137ddb03c3c1b17fceb400cee70a5e0b057c02f1c9138722f1260db1564d3c3` | same |
| payload digest (JCS `{path: sha256}`, 65 files) | `c2e36edce458c3dcdba1a75a3c7252b603b0307f24a28cad71e18a0fde7600b7` | same |
| dependency inventory | `a34972dd25788f400fd22e39179bba9f3d413fe5763bfba67ad24a6205842a0a` | same |
| build recipe | `be8edf6482ee9f4c8e94765e84492ffd3225e0e665d68a0730b86800acb02246` | same |

**What the comparison covers.** The inspection identity covers:

- every tar member header: name, type, mode `0600`, uid/gid 0, empty
  uname/gname, mtime 0, size, link name, and PAX headers;
- member order;
- every payload file's SHA-256, size, and install mode;
- the manifest header;
- the stamp document;
- the gzip header.

It also rejects:

- absolute member paths and `..`;
- any member set other than `EXPECTED_PATHS` plus the manifest.

Only `environment` (Python, platform, zlib) is provenance. It is outside
the identity. **No field was excluded to make the builds match.**

The authority, witness, and root-tooling digests equal the PR-1S source
identity (PR-1S §3) and the preflight §14 candidate values.

## 5. Unit bytes

| Asset | Host target | SHA-256 |
| --- | --- | --- |
| `assets/lilith-authority-dev.service` | `/etc/systemd/system/lilith-authority-dev.service` | `11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254` |
| `assets/lilith-authority-dev.socket` | `/etc/systemd/system/lilith-authority-dev.socket` | `bff5e9275ad1478dd068855465d65542ceb338e5e9236e43d1bd43d7c50c194f` |
| `assets/lilith-authority-dev.tmpfiles.conf` | `/etc/tmpfiles.d/lilith-authority-dev.conf` | `2a1891ef3c4e3e0c2916eece828c37f98f6edace9bb5bf27846c4eb28944a51e` |
| `assets/lilith-recovery-witness.service` | `/etc/systemd/system/lilith-recovery-witness.service` | `9f78130c06491d184aff7066de99f804bf3816e171c63d6f70b734b1c6e85d7d` |
| `assets/lilith-recovery-witness-owner.socket` | `/etc/systemd/system/lilith-recovery-witness-owner.socket` | `d260917fb31e9c76341fba131bafdc2802b80c0cf2fdcffb8cecc6e176440beb` |
| `assets/lilith-recovery-witness-signer.socket` | `/etc/systemd/system/lilith-recovery-witness-signer.socket` | `ad345d18747c30a7c2a93cb18d5be310dc091f5efe07fc6e1606efbc099bb9c7` |
| `assets/lilith-recovery-witness.tmpfiles.conf` | `/etc/tmpfiles.d/lilith-recovery-witness.conf` | `c3491d517aa70ff960e1dba4410378efcecc134737282136aad77a5a9d200be0` |

`systemd-analyze --man=no verify` (systemd 255.4-1ubuntu8.17) ran on the
**exact bytes extracted from the candidate archive**. It used the
repository's own stub convention: the one pinned `ExecStart` is replaced by
`/usr/bin/true`, as CI does.
- Witness service + two sockets: exit 0, no diagnostic naming a unit. This
  uses `test_recovery_witness_units.stage/verify`.
- Signer service + socket: exit 0, no diagnostic. This is the `ci.yml` step
  form.

## 6. CLI bytes (fixed list = `install_authority_dev.CLI_TARGETS`)

| Member | Host target (install mode `0755`) | SHA-256 |
| --- | --- | --- |
| `cli/lilith-authority-keygen-dev` | `/usr/local/sbin/lilith-authority-keygen-dev` (replaced) | `1fa50327bb9cb402dc38f6e8a3742362901ba4dbd5c48f8474dc7c6c4e134472` |
| `cli/lilith-authority-ledger-dev` | `/usr/local/sbin/lilith-authority-ledger-dev` | `fda779cd0dcecdc26e371082078306978f97e4f7097acae780fa6f38180fc45b` |
| `cli/lilith-authority-hold-dev` | `/usr/local/sbin/lilith-authority-hold-dev` | `ad3fbc9442db715595683f4602e8b2fd62d22697703e888eda2ef30c0121da1b` |
| `cli/lilith-authority-verify-dev` | `/usr/local/sbin/lilith-authority-verify-dev` | `bc331636eedbbae22a53667aa230ba0672fb1e22b8a5bd4975ac9f8557a400a4` |
| `cli/lilith-authority-recovery-dev` | `/usr/local/sbin/lilith-authority-recovery-dev` | `ad928f8d56062763da156084f5375c23dabfdcced396a065ba4cc2719e01cc74` |
| `cli/lilith-recovery-witness-owner-dev` | `/usr/local/sbin/lilith-recovery-witness-owner-dev` | `9fce2e460a9c279f99b59c6e251b813375a1be404ae611d379fed5cd812f16ab` |

- The inspection refuses (`EXECUTABLE_SET`) unless the set of `0755`
  members is exactly this list.
- The release file set (`release_file_set.CLI_FILES`) fixes the list. No
  wildcard or generic command utility is shipped.
- Each is a closed dispatcher wrapper (PR-1S S-11).

## 7. Attestation

| Item | Value |
| --- | --- |
| Type | `LILITH_AUTHORITY_DEV_PR1A_BUILD_ATTESTATION`, schema 1, `artifactRole=lilith-authority-dev-pr1a-install-candidate` |
| Canonical form | compact, sorted, ASCII JSON. This is JCS for this string/int/object data, the convention of `pr1_acceptance`. Written with a trailing newline, and `check` requires exactly that form |
| Digest | `SHA-256("LILITH_PR1A_BUILD_ATTESTATION_V1\0" ‖ canonical)`, a new domain separator after `LILITH_PR1_OWNER_ACCEPTANCE_PACKAGE_V1\0` |
| **`CANDIDATE_ATTESTATION_DIGEST`** | **`86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683`** |
| File SHA-256 (`pr1a-build-attestation.json`) | `3a6c8a3a9eacac2278c8eefeaf4712b6ac012b6cd956822d1e7ce5f16febbcb6` |
| Content | `sourceCommit`, `releaseRole`, `buildRecipeSha256` (with its 4 files), archive / tar / stamp / manifest / payload digests, the 3 runtime digests, `unitDigests`, `cliDigests`, `hostTargets` (target → member, SHA-256, mode), the dependency inventory, and `reproducibility` (2 builds, both identity and archive digests) |
| Nonclaims (in the document) | `NOT_AUTHORITY`, `NOT_K_ROOT`, `NOT_OWNER_ACCEPTANCE`, `NOT_INSTALL_AUTHORIZATION`, `NOT_LIVE_EVIDENCE`, `VENV_BUILT_ON_HOST_NOT_ATTESTED_AS_BYTES` |
| Signature | none. No accepted design calls for one, so this record is not another authority root |
| No timestamps | the identity has no build time. The start times above are human provenance only |

`attest … check` re-inspected the stored candidate against the attestation:
`{"failures": [], "result": "PASS"}`.

## 8. Dependencies and the venv

**How PR-1S represents dependencies.**

- The archive carries the five wheels, each pinned by SHA-256 in source
  (`WHEEL_HASHES`, equal to the broker's), plus `requirements.lock` with
  the same `--hash` pins. Its SHA-256 is `8b5f274c…0e48`.
- These are byte-attested inside the archive. The dependency inventory
  digest is `a34972dd…2a0a`, equal in A and B.

**The venv is not an install artifact.**

- `upgrade-stage` builds it **on the DEV host**:
  `python3 -m venv` + `pip install --no-index --require-hashes
  --find-links wheels -r requirements.lock`.
- That runs inside `releases/.<NEW>.staging` before the rename. It is then
  import-checked as the signer identity.
- The accepted design classifies the venv as **drift detection only**:
  preflight §23 ("the venv is built on-host"); `release_tree_failures` and
  `pr1_acceptance.verify_installed_release` both exclude `venv/`. The
  latter requires only that a venv file-set digest was *observed*
  (`RELEASE_VENV_UNOBSERVED`) and pins no value.
- The PR-1A POST records the new venv digest as the next drift reference,
  as the preflight recorded `03bf7233…` for `9ac7de2`.
- So PR-1A depends on the venv's **inputs** (reproduced exactly), not on
  venv bytes. The pip install can only resolve the hash-pinned wheels, or
  it fails.

**Not proven here (D-2).** A local double venv build was attempted, but
this workstation's WSL has no `python3-venv` / `ensurepip` / pip. Nothing
was downloaded to get them, so venv byte-reproducibility (including `.pyc`
timestamps and embedded staging paths) is **not claimed**. It is a
non-dependency of the install artifact by design.

## 9. Negative reproducibility (tamper) tests

On throwaway copies of the **exact candidate** (harness §17):

| Tamper | Detected as |
| --- | --- |
| one archive byte flipped | `REFUSED_AT_INSPECTION: ARCHIVE_REFUSED` (installer `verify_archive`) |
| one payload byte changed (`core.py`), re-packed validly | `NOT_REPRODUCED` (archive, tar, stamp, payload, and authority digests differ) |
| extra payload file | `REFUSED_AT_INSPECTION` (member set) |
| removed CLI | `REFUSED_AT_INSPECTION` (member set) |
| changed tar member mode | `NOT_REPRODUCED` (`tarMembers[…].mode`) |
| changed witness-socket unit byte | `NOT_REPRODUCED` (`unitDigests`, `hostTargets`) |
| changed CLI byte | `NOT_REPRODUCED` (`cliDigests`, `hostTargets`) |
| identical re-pack | not a difference: it *is* the candidate (control) |

The committed tests (`test_pr1a_build_attestation.py`) repeat these with
stand-in wheels. They also cover a gzip-mtime change, the check mismatch
list, and a forged inspection.

## 10. Installed-release verifier, synthetic

This ran on the synthetic host tree after the synthetic upgrade (§11), with
the exact candidate. The verifier was
`lilith_authority_root.observers.observe_installed_release` +
`pr1_acceptance.verify_installed_release`. It used the attested
`manifestSha256` and the reviewed runtime digests, over the signer unit,
socket, and tmpfiles files and the six CLIs.

| Case | Result |
| --- | --- |
| exact candidate | **verified**; runtime digests = the attested three |
| one byte of `lilith_recovery_witness/writer.py` in the release tree | refused `RELEASE_TREE_FILE_MISMATCH` |
| restored | verified |
| one byte of the installed `/usr/local/sbin/lilith-authority-verify-dev` | refused `HOST_FILE_BYTES_MISMATCH` |
| wrong attested manifest digest | refused `RELEASE_MANIFEST_HASH_MISMATCH` |
| installer `release_tree_failures` after the upgrade | `[]` |

## 11. Upgrade installer, synthetic

The fixture is the PR-1S `old_host`: a temporary root at exactly
`status --expect L2b.2 9ac7de2`. It has:

- the accepted OLD SHA string;
- a stand-in CURRENT blob in a `0700` credstore;
- a stand-in host key;
- the signer account;
- no PR-1 object.

The baseline comes from `upgrade-baseline`. The stages ran against the real
candidate archive and stamp, with NEW = `aee323e…`. It used the `FakeHost`
command seam: the manager, `pip`, and `runuser` are fakes, and the owner's
daemon-reload is `FakeHost.daemon_reload`.

| Check | Result |
| --- | --- |
| stage → select → units → (reload needed) → reload → cli → retire-old | `STAGED_NEW_RELEASE`, `SELECTED_NEW_RELEASE`, `UNITS_RELOADED`, `UNITS_UPDATED`, `CLI_UPDATED`, `COMPLETE_NEW_RELEASE`; every report `PASS` |
| staged tree (`release_tree_failures`) | `[]` |
| final `status --expect L2b.2 <NEW>` | `PASS` |
| installed units + CLIs (9 host files) = attested `hostTargets` bytes | yes |
| CURRENT | unchanged: kind, uid, gid, mode, device, inode, size, mtime ns, ctime ns, SHA-256 |
| commands the stages ran | only `systemctl show`, `sudo -n -l -U` (the account-contract query), `python3 -m venv`, `pip install`, `runuser` (import check). No `systemctl start/enable/daemon-reload`, `systemd-creds`, `useradd`, or keygen |
| PR-1 objects created | none: no witness, ledger, hold, custody root, K-WIT, or skeleton path; no witness account |
| release set after retire | exactly `[aee323e…]` |

No real DEV path was used.

## 12. Reviewed host observer (the ad-hoc probe)

**Decision.** PASS 2 must not rely on the scratch probe from the preflight
(its D-8). The reviewed tooling (installer `status` / `upgrade-baseline` /
`upgrade-status`) already covers most facts:

- CURRENT identity and hash;
- the credstore name set;
- the host-key stat;
- the signer uid/gid;
- PR-1 path absence;
- unit load/active state;
- needrestart.

It does **not** cover:

- the boot ID and kernel;
- the full per-release manifest/tree check outside an upgrade stage;
- the venv digest;
- unit runtime facts (NRestarts, InvocationID, start timestamps,
  enablement links and drop-ins);
- per-entry credstore metadata;
- the future-path `st_dev` relation;
- the LILITH namespace inventory.

So this gate adds the minimum fixed observer:
`services/authority-dev/ceremony/observe_authority_dev_host.py`, commit
`bf866b2`.

- **Invocation.** It is streamed like the installer, as `observe` with no
  other argument. It refuses a non-root caller or a non-DEV machine-id or
  hostname.
- **Scope.** It observes only a fixed path set: no arbitrary-path
  inspection and no network. Unlike the scratch probe, it drops the GCE
  metadata call and the `/root` listing.
- **Reads.** It uses `O_NOATIME` everywhere, which removes the preflight's
  D-1 atime side effect for its own reads. It never opens
  `credential.secret` (a hard refusal in code).
- **No verdict.** It judges nothing. It emits `stableSha256`, with only
  `host.utcNow` and `host.uptimeSeconds` excluded as volatile, plus a
  per-section `sectionSha256`. PRE and POST can therefore be compared exactly
  and per section across the intended upgrade change.

It is ceremony tooling, listed in `release_file_set.CEREMONY_FILES`, and
**not** release payload. A control build at `bf866b2` (BUILD_C) produced
the **same 65 payload files**, runtime digests, unit/CLI/host-target
digests, and dependency inventory as the candidate. Only two things
differed: the manifest's stamped `candidateSha`, and the non-payload recipe
file `release_file_set.py`. Therefore the candidate stays the `aee323e`
build and was not rebuilt. The observer is a CONTROL_SHA tool (N-45), not
a RELEASE_SHA change.

## 13. Candidate identity and storage

```text
CANDIDATE_ARTIFACT_DIGEST    = 25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a
                               (lilith-authority-dev-release.tar.gz, 5 354 725 bytes)
builder stamp SHA-256        = 9441c985ab5724f68bd9e0199ac98593b930236150ef10778c242f673bdb1b42
CANDIDATE_ATTESTATION_DIGEST = 86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683
RELEASE_SHA (NEW)            = aee323e94412accbe321bc84eae78c5b8cf95afc
```

Future installation uses the artifact with this digest, never "the latest
build" or a `dist/` directory.

- **Storage.** The candidate lives on the owner workstation, outside git, at
  `C:\Users\edufo\lilith-b1b3e-pr1a-aee323e94412accbe321bc84eae78c5b8cf95afc\candidate\`.
  It holds the archive, the stamp, the attestation, `SHA256SUMS`,
  `PROVENANCE.txt`, and the harness result.
- **Build dirs.** Build dirs A and C are beside it. B stays in WSL under
  `~/lilith-b1b3e-pr1a-<SHA>/build-b/`.
- **Precedent.** This follows the accepted B1b-3d S-1 precedent: the
  `9ac7de2` archive and stamp were built on this workstation under
  `~/lilith-b1b3d-s1-<SHA>…/artifacts` and staged from there. Binary
  archives are not committed, per repository practice.
- **Persistence.** The archive is reproducible byte for byte from
  `aee323e` + the five hash-pinned wheels. If the stored copy is lost or
  doubted, a rebuild must reproduce the recorded digest. Otherwise it is not
  the candidate. This is not a blocker (D-3).

## 14. Source-freeze rule

Once the owner accepts `CANDIDATE_ARTIFACT_DIGEST` for PR-1A:

1. PR-1A installs **only** the artifact with that digest.
   `upgrade-stage <OLD> aee323e…` takes exactly that archive and stamp, and
   `check` against this attestation must PASS immediately before M-A1.
2. **Installable source** means:
   - every file `release_file_set.RUNTIME_SOURCE_MAP` / `CLI_SOURCES` maps
     into the payload, including the pinned shared contracts;
   - the unit assets;
   - `WHEEL_HASHES` / `LOCK`;
   - the archive format in `install_authority_dev.py` (`write_archive`,
     `manifest_for`, `ROLE`, `EXPECTED_PATHS`).

   Any change to it on main invalidates the artifact. A new candidate needs
   a new gate.
3. Main moving for docs or ceremony/control tooling does not change the
   artifact. Examples: this gate's observer and attestation tool, the
   installer's stage logic, DR-5, the broker verifier. The ceremony still
   pins `RELEASE_SHA=aee323e…` and the artifact digest explicitly, and
   records the CONTROL_SHA of every streamed tool.
4. **Moving main is never the installation identity.**

## 15. Reboot / fresh-preflight rule

The accepted read-only baseline (`PR1A_PREFLIGHT_PASS`, 2026-09-28
`10:38`–`10:47Z`) is stale on any DEV reboot or broker restart. A kernel
reboot is pending (preflight D-6). **Before the first live mutation (M-A1),
a fresh read-only preflight is mandatory.** It uses the reviewed observer
(§12) plus the installer `upgrade-baseline` / `status --expect L2b.2
9ac7de2`, broker `preservation`, the needrestart probe, activation, and a
current DR-5 run. It must prove:

- the same host (machine-id, hostname), with the boot ID equal to the
  accepted one, or an owner-accepted new baseline;
- the old release is `9ac7de2`, with its tree equal to its manifest;
- CURRENT is preserved (device, inode, size, mtime/ctime ns, SHA-256
  `6a61c350…`);
- the credstore holds exactly CURRENT;
- DR-5 `PR1_ABSENT` on `L1c.3`, and no new PR-1 object;
- `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`;
- broker `PASS` at incarnation `42af2691…`.

Artifact reproducibility does not replace live preflight.

## 16. Discrepancies and non-determinism found

| # | Finding | Classification |
| --- | --- | --- |
| D-1 | None in the archive. Byte-identical across two OSes, Pythons (3.13.5 / 3.12.3), and zlib versions (1.3.1 / 1.3) | no nondeterminism found. Cross-zlib agreement is observed, not guaranteed. A future builder with a different deflate implementation (for example zlib-ng) could differ, and would then be `NOT_REPRODUCED`, never silently accepted. The uncompressed tar digest is recorded to localise such a case |
| D-2 | venv bytes not reproduced locally (no `python3-venv` / pip in WSL; nothing downloaded) | venv is on-host, drift-only by accepted design (§8), so it is not a dependency of the attested artifact. Venv byte-reproducibility is not claimed |
| D-3 | No repository artifact channel for binaries | the owner-workstation storage precedent (B1b-3d S-1) plus byte reproducibility. Not a blocker. Pass 2 must `check` the stored bytes before staging |
| D-4 | The private repository cannot be cloned in WSL without credentials | BUILD_B used a `git bundle` of `origin/main` (`git fsck --full` clean): independent checkout, process, OS, and toolchain, but the same object source |
| D-5 | The builder stamp's `artifactRole` is `lilith-authority-dev-synthetic-owner-actor-release-v1` (installer `ROLE`, unchanged since B1b-3d), while the source manifest role is `…release-source-v2` | naming only. The installer requires this `ROLE`. Recorded, not changed |
| D-6 | WSL builds ran as root in the WSL VM (the local default user) | local sandbox only. The builder writes only its two output files |
| D-7 | The synthetic upgrade uses fake systemd, pip, and runuser | proves stage logic and bytes, not host behaviour. Live behaviour is Pass 2's POST evidence |

## 17. Validation

| Check | Result |
| --- | --- |
| `services/authority-dev/tests` (WSL, POSIX) | 240 OK (226 + 14 new) |
| `services/recovery-witness/tests` | 44 OK |
| `services/owner-memory-control/tests` | 489 OK |
| `compileall` (ceremony, tests) | OK |
| `systemd-analyze verify` on the exact candidate units | clean (§5) |
| candidate harness (tamper, verifier, upgrade, units) | `PR1A_CANDIDATE_HARNESS=PASS`. The harness is local evidence tooling (SHA-256 `422cfd78…c1af`), stored with the candidate, not repository source |
| `git diff --check`, `scripts/validate_repository.py` | PASS |

## 18. Result

```text
PR1A_BUILD_ATTESTATION_PASS
```

Every artifact PR-1A installs is reproduced byte for byte and identified by
digest: the archive, its manifest and stamp, all 65 payload files, the 7
unit assets, the 6 fixed CLIs, and the dependency inventory. The installed
bytes of the synthetic upgrade equal the attestation, and the root verifier
accepts exactly this candidate.

## 19. Nonclaims

- No DEV or PROD contact.
- No install, transfer, `systemctl`, `systemd-creds`, or sudo on any live
  host.
- No K-WIT, successor K-ACT, ledger, witness, hold, owner material, or
  registry change.
- No key rotation.
- No L04, broker, IAM, WIF, or sudoers change.
- Not authority, K-ROOT, owner acceptance, or install authorization.
- No venv byte-reproducibility claim.
- No snapshot inventory (PR-2) and no off-host register (PR-3).
- PR-1A Pass 2 is **not** authorized. B1b-3e live rehearsal is **not**
  authorized.
