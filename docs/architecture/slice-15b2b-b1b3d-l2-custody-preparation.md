# Slice 15B2b-B1b-3d L2 — DEV_SYNTHETIC OWNER_ACTOR Custody Preparation

Status:

- **B1b-3d L2 CUSTODY PREPARATION SOURCE IMPLEMENTED**
- **NOTHING EXECUTED**
- **NO KEY, CREDENTIAL, BLOB, ACCOUNT, DIRECTORY, OR UNIT CREATED**

Base: protected main `c608fc0ffaeee41d7ebf007dc0a66321a1907d31` (includes
the merged [L1 foundation](slice-15b2b-b1b3d-l1-authority-signer-foundation.md);
its post-merge "Deploy LILITH Core API to DEV" run completed with `success`).

This record prepares, and does not execute, the owner ceremonies L0, L1a,
L1b, L1c, L2a, and L2b of the
[B1b-3d design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md) §23. It is
not an acceptance record. It does not claim custody, authority readiness,
real owner authority, B1b-3d acceptance, or First Memory.

```text
source-controlled artifact != installed artifact
installed artifact         != activated service
activated service          != credential custody
credential custody         != accepted authority
```

## 1. Target live property (not proven here)

After L2b, the synthetic OWNER_ACTOR private signing credential is meant to be
available only to the `lilith-authority-dev` service domain, and unavailable
to `lilith`, Hermes and model/tool execution, `lilith-memory-broker`, the
routine DEV deployer, the Core API, and cognitive DB writers.

Nothing in the repository proves this. It is **NOT_YET_LIVE_PROVEN** until
the later denial proofs (design §17 N1–N9, D1–D12, B1–B4) run on DEV.

## 2. Canonical requirements used

| Requirement | Source |
| --- | --- |
| `lilith-authority-dev` system account: nologin, no home, no sudo | design §6, T-1 |
| host-bound `LoadCredentialEncrypted=`, credential name `owner-actor-signing-key` | design §5, §15, T-2 |
| blob `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` `root:root 0600`; directory `root:root 0700` | design §15 |
| K-ACT keyId `test-only.dev-synthetic.actor.b1b3d.1`, Ed25519, on-host keygen piping PKCS#8 to `systemd-creds encrypt --with-key=host --name=…`, `O_EXCL`, public JSON only | design §4, §16 |
| first encrypt needs `/var/lib/systemd/credential.secret`; creating it is its own step (L2a, `systemd-creds setup`) | design §16, §23 |
| release trees `/opt/lilith-authority-dev/releases/<sha>` `root:root 0755`, offline pinned wheels, `current` symlink | design §15 |
| fixed CLIs in `/usr/local/sbin/lilith-authority-*-dev` `root:root 0755` | design §15 |
| units and sockets not boot-enabled; activation is an owner ceremony | T-5 |
| routine deployer sudo, helper, and verifier unchanged | design §7 |
| one mutation per live step, separately owner-authorized; preservation set re-hashed | design §23 |

## 3. Decisions, refinements, and open items

### Recorded decisions and runbook refinements (DEV_SYNTHETIC scope only)

| # | Decision or refinement | Rationale |
| --- | --- | --- |
| D-W | **Witness identity deferred.** L1a creates only `lilith-authority-dev`. Creating the `lilith-recovery-witness` identity is deferred to the L3 witness slice. Witness paths and the K-WIT blob stay absent throughout L2, and the installer checks that they are absent. | A deliberate DEV_SYNTHETIC sequencing refinement of design §23 L1a, not a mismatch. The OWNER_ACTOR custody slice needs no witness identity, and an unused root-created principal is avoidable surface. |
| D-S | **No active swap during L2b.2** is an accepted ceremony requirement. The keygen refuses while `/proc/swaps` lists any swap. | The Ed25519 private key exists briefly in process memory. Active swap would add an avoidable path for those memory pages to be written to disk. **Limit:** this removes only the swap persistence path during the ceremony. It does not prove memory zeroization. It does not prove the plaintext never existed in RAM. It gives no snapshot or host-root protection. |
| R-1 | **`/etc/credstore.encrypted` is handled in its own step, L2b.1**, before the keygen (L2b.2). **Corrected after run 36264031829:** L2a and L2b.1 are host-prerequisite ceremonies, not LILITH maturity. See R-4. | The design gives the directory's mode but no step. Preparing a root-only custody directory and creating the key blob are two state transitions. Keeping them apart preserves the one-transition-per-step invariant (design §23). |
| R-4 | **Host prerequisites: create-or-adopt.** `/var/lib/systemd/credential.secret` (L2a) and `/etc/credstore.encrypted` (L2b.1) are generic systemd infrastructure. They may pre-exist, and on DEV the credstore already existed as `root:root 0700`, empty. Each is ABSENT (create it in its own authorized step), PRESENT_SECURE (validate and adopt: **zero mutation**), or PRESENT_UNSAFE (STOP). | `AMBIENT HOST PREREQUISITE != LILITH CEREMONY ARTIFACT != LILITH MATURITY EVIDENCE`. A pre-existing prerequisite is not evidence that a LILITH ceremony ran. LILITH does not own the generic credstore namespace. |
| R-2 | **L1b and L1c are subdivided:** L1b.1 (tree) and L1b.2 (`current`); L1c.1 (unit files), L1c.2 (`daemon-reload`), and L1c.3 (CLI). | Each is a distinct state transition with its own POST and rollback. Combining them would break the one-transition-per-step invariant. |
| R-3 | **Read-only observation ≠ staging ≠ installation** (§9). | Copying any file to the host, even to `/tmp`, is a host mutation. |

### Open items

| # | Decision | Handling here |
| --- | --- | --- |
| U1 | **Numeric uid/gid** for `lilith-authority-dev`. The design does not pin one. | Not pinned. `useradd --system` allocates it (the broker precedent); the POST evidence records it, and it must be `< 1000`, non-zero, and distinct from `lilith`, `lilith-memory-broker`, and `lilith-memory-relay`. |
| U5 | **Blob check without decryption.** Proving that the blob decrypts to the published key needs plaintext again. | Not done at L2b. The link is checked at the later activation: the L1 service `HEALTH` reports `publicKeySha256`, which must equal the publication's value. |
| U6 | **`deploy-dev.yml` deny-list extension** (design §7; DR-5). | Not changed here. It is a **prerequisite of live L1a**, not of L2b (§10). DR-5 stays OPEN. |

## 4. Files

| Path | Role |
| --- | --- |
| `services/authority-dev/ceremony/lilith_authority_keygen_dev.py` | keygen ceremony CLI; installed as `/usr/local/sbin/lilith-authority-keygen-dev` |
| `services/authority-dev/ceremony/install_authority_dev.py` | owner installer: one stage per transition, read-only `status --expect`, archive verifier |
| `services/authority-dev/ceremony/build_authority_dev_release.py` | workstation-side deterministic release archive builder |
| `services/authority-dev/tests/test_custody_preparation.py` | repository tests (run by the existing L1 CI step) |
| `services/authority-dev/release_file_set.py` | exact source set extended with the ceremony and test files; runtime payload unchanged |

**Location.** The design (§15, §23) proposes `scripts/authority_dev/` for
the CLIs. They live in `services/authority-dev/ceremony/` instead. The
accepted B1b-3b structural-isolation test forbids any `scripts/**` code from
naming `lilith_owner_memory` or the TEST signer package. This tooling names
those modules as release-layout paths, and as forbidden markers. Moving the
tooling keeps that invariant intact without weakening it.

## 5. Keygen CLI contract

```text
lilith-authority-keygen-dev actor
```

- **The only accepted form.** `witness` → `WITNESS_NOT_IN_SCOPE`. Anything
  else, including any option → `USAGE_ONLY_ACTOR`. Exit `2`, nothing done.
- **Fixed values:**
  - profile `DEV_SYNTHETIC`, environment `dev`;
  - keyId `test-only.dev-synthetic.actor.b1b3d.1`;
  - `OWNER_ACTOR` / `OWNER_MEMORY_OPERATION`, Ed25519;
  - credential name, path, and `--with-key=host`.
- **No option for** algorithm, domain, PRIVACY, prod, key ID, path, output,
  export, seed, or force.
- **Refuses** (exit `2`, nothing generated) unless all of these hold:
  - it runs as root;
  - the interpreter is isolated (`-I`);
  - the host is DEV (machine-id and hostname);
  - no swap is active;
  - `/var/lib/systemd/credential.secret` is `root:root 0400` (checked with
    `lstat` only; never read);
  - `/usr/bin/systemd-creds` is `root:root 0755`;
  - `/etc/credstore.encrypted` exists `root:root 0700` and is empty;
  - the blob path does not exist.
- **Key source.** It uses only `Ed25519PrivateKey.generate()`. It has no seed,
  fixture, embedded, fallback, or deterministic key.
- **No other effects.** No network, database, registry, unit, or signing
  operation.
- **Failure after generation.** Exit `3` (`FAILED …`). stderr carries a fixed
  reason only; `systemd-creds` stderr is never echoed.

## 6. Plaintext private-material exposure

```text
generate (process memory)
  -> PKCS#8 DER bytes (process memory)
  -> stdin pipe of: systemd-creds encrypt --with-key=host --name=owner-actor-signing-key - -
  -> ciphertext on the child's stdout -> keygen memory
  -> O_EXCL write, fsync, directory fsync: /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred
```

| Location | Plaintext? |
| --- | --- |
| any file, argument, environment variable, terminal, log, journal, or network | **never** |
| keygen process memory | yes, until exit |
| kernel pipe buffer | yes, transiently |
| `systemd-creds` process memory | yes, until exit |
| blob on disk | ciphertext only. The keygen refuses a result that contains the DER bytes or their base64 |

Narrowing controls:

- `RLIMIT_CORE=0` and `PR_SET_DUMPABLE=0` for the keygen;
- no active swap (D-S). This removes only the swap persistence path. It
  is not zeroization, not proof that plaintext never existed in RAM, and not
  snapshot or host-root protection;
- the only reference to the key object is released.

**Memory zeroization and remanence are NOT_PROVEN.** Python bytes are
immutable and cannot be wiped. Neither a pipe closing nor a process exiting
is secure erasure. Root can read any process's memory while it runs.

## 7. Public-material contract

The keygen prints exactly one line on stdout. It is JSON with sorted keys, no
whitespace, ASCII, and a trailing newline.

**Deterministic serialization.** For one generated key and one ceremony
result (its blob), the serialization is canonical: the same inputs always give
the same bytes, and no timestamp is included. Repeated key-generation runs
do **not** give the same values. `Ed25519PrivateKey.generate()` is
intentionally random, so each run has a new `publicKey`, `publicKeySha256`,
and blob hash.

```json
{"custodyEvidence":{"blobByteSize":<int>,"blobSha256":"<hex64>","credentialName":"owner-actor-signing-key","credentialPath":"/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred","machineId":"ae929170e6fa4c8ab9cc7b9547238d9d","withKey":"host"},"profile":"DEV_SYNTHETIC","publicVerificationMaterial":{"algorithm":"Ed25519","environment":"dev","evidenceTypes":["OWNER_MEMORY_OPERATION"],"keyId":"test-only.dev-synthetic.actor.b1b3d.1","publicKey":"<base64url 32 bytes>","publicKeySha256":"<hex64>","signingDomain":"OWNER_ACTOR"},"publicationType":"LILITH_AUTHORITY_KEY_PUBLICATION","schemaVersion":1}
```

```text
private custody material             != public verification material
custodyEvidence (where, hash)        != registry content
publicVerificationMaterial           -> later AuthorityKeyRecordV1 (L3a, offline, owner-signed)
```

- The later registry record adds its own `createdAt`, `notBefore`,
  `recoveryEpoch`, `policyVersion`, and `registryVersion`. The keygen chooses
  none of them.
- `publicKeySha256` is the same value the L1 service reports in `HEALTH`.
- Nothing is published to any registry here.

## 8. systemd credential semantics (T-2, DEV_SYNTHETIC only)

- The unit loads the blob with
  `LoadCredentialEncrypted=owner-actor-signing-key:/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`.
  The embedded name must match.
- **What it protects against:** ordinary access by the application and the
  routine deployer. The blob is root-only and ciphertext, and the plaintext
  exists only in `/run/credentials/lilith-authority-dev.service/` of the
  running unit.
- **What it is not:**
  - It is **not** whole-host or snapshot rollback protection. A disk snapshot
    holds both the blob and `/var/lib/systemd/credential.secret`, so the blob
    decrypts from the snapshot.
  - It is **not** real-owner-grade custody. Root can decrypt it (Level 3 is
    out of scope).
- **Syntax check.** The `encrypt INPUT OUTPUT`, `--with-key=host`,
  `--name=`, and `setup` syntax was checked against the systemd 255 help
  text in a local WSL instance. `systemd-creds` was never run for
  encryption, and never on DEV. Whether `-` works for both input and output
  on DEV is **NOT_YET_LIVE_PROVEN**; a failure stops L2b.2 with nothing
  written.

## 9. Owner ceremony runbook

### Common rules

- **Who and how.** The owner runs each step, as root, on `lilith-dev-01`,
  over the owner's own IAP session. There is exactly one mutation per step,
  and each step is separately authorized. Never run from GitHub Actions or as
  the deployer.
- **Three kinds of step (R-3):**

  ```text
  READ_ONLY OBSERVATION  !=  STAGING  !=  INSTALLATION
  ```

  - A **read-only observation** writes no file on DEV. The script runs
    through a pipe, never as a staged file.
  - **Staging** copies bytes onto the host. It is a host mutation, even into
    `/tmp` or a home directory. It is its own separately authorized step
    (S-1), with its own cleanup step (S-2).
  - An **installation** is a ladder step (L1a…L2b) that changes custody
    state.
- **Streamed execution (no staging).** Both
  `services/authority-dev/ceremony/install_authority_dev.py` and
  `scripts/verify_broker_dev_current_incarnation.py` run from standard input
  as `python3 -I -B - <args>`. Neither reads `__file__` nor a sibling module.
  On the owner workstation, from the reviewed commit, embed one tool per
  command. It is about 11 KiB and 14.5 KiB as gzip+base64, within command-line
  limits. Run:

  ```text
  B64=$(gzip -9n < <tool.py> | base64 -w0)
  gcloud compute ssh lilith-dev-01 --zone=asia-southeast1-b --project=lilith-agent-260823-27389 \
    --tunnel-through-iap --command="echo $B64 | base64 -d | gunzip | sudo /usr/bin/python3 -I -B - <args>"
  ```

  This creates no file, and `-B` writes no bytecode. Output returns to the
  owner terminal and is saved on the workstation. Do not pipe the script
  over `gcloud compute ssh` standard input on Windows, because a stray `y`
  is injected. Embed it in `--command` instead.
  - **Unavoidable side effects**, not custody state: the IAP/OS Login
    session and `sudo` produce login and journal accounting records, as in
    every earlier read-only inspection.
  - A local check streamed the installer this way on a non-DEV Linux host.
    It refused with `NOT_DEV_HOST` and left no file behind.
- **Installer invocation.** Every installer stage below, including the
  mutating ones, uses the streamed form above with `<args>` =
  `<stage> …`. Only L1b.1 also needs the staged archive (S-1).
  `<RELEASE_SHA>` below is the installed signer release (see *Provenance*).
- **Provenance (N-45).** Two commits are distinguished:
  - `RELEASE_SHA`: the protected-main commit that the installed, immutable
    signer release was built from. Every installer stage and every `status`
    takes it. Live value after L1b.1:
    `9ac7de22bf977385ceb954624677e33f0bae062b`.
  - `CONTROL_SHA`: the protected-main commit whose ceremony controls
    (installer, verifiers, and this runbook) are streamed. It may be newer
    than `RELEASE_SHA`, and each transcript records it (`git rev-parse HEAD`
    of the workstation checkout used).

  A control-only change (installer, verifier, runbook, DR-5 proof) **never**
  requires rebuilding or reinstalling `RELEASE_SHA`. Only a change to the
  signer release payload does: the runtime modules, the unit and socket
  assets, the keygen CLI, or the pinned wheels. That needs a new release
  and its own ladder steps.
- **Preservation set (phase-aware; corrected by N-45).** Every step starts
  by re-running the read-only preservation checks (streamed):
  - **Before any custody path exists (L0, L1a):**
    `verify_broker_dev_current_incarnation.py baseline` equals the accepted
    current-runtime baseline. This is the historical pre-custody operation.
  - **From L1b.1 on** (S-2, L1b.2, and all later steps), **all** of:
    1. `verify_broker_dev_current_incarnation.py preservation` shows
       `BROKER_PRESERVATION=PASS`. That means the same broker incarnation
       (`42af2691b8d24ee5a92a286197c5444c`) and the same `baselineCandidate`
       SHA-256 (`3549585487ad…a7eee5`). The same PID, start ticks, boot ID,
       NRestarts, release and manifest, shared libraries, config, state,
       identity and socket boundary, Stage III, and B1c policy all hold.
    2. `install_authority_dev.py status --expect <stage> <RELEASE_SHA>` shows
       `PASS` for the current authority ladder stage. This alone owns exact
       authority state. It fails on any unexpected or out-of-order authority
       object, including a second release directory.
    3. DR-5 evidence where the ladder requires it (a routine or control-only
       run with `AUTHORITY_BOUNDARY_PROOF=PASS maturity=<stage>`).

    The broker verifier does **not** own authority custody. `preservation`
    reports custody paths verbatim and never judges them or derives a
    maturity. Custody presence is never read as broker drift, nor as
    authority progress.
  - Always: the B1c helper, library, verifier, and sudoers hashes are
    unchanged; activation is `NOT_ACCEPTED reason=GRANT_ABSENT`; the Stage
    III artifacts are unchanged.

  **STOP** on any difference. `baseline` is not used after L1b.1: it
  correctly fails there with `CUSTODY_PATH_PRESENT_BEFORE_B1B3D`, and its
  historical meaning is not reinterpreted.
- **POST check.** Every step's POST is
  `install_authority_dev.py status --expect <step> [<RELEASE_SHA>]` with
  `"result": "PASS"`, plus the step-specific evidence below. Save every
  transcript to the owner evidence directory.
- **Private material.** Any private-key pattern in any output or journal
  means **STOP**. Delete the affected blob, record the incident, and start
  again from L2a's POST.

### Steps

| Step | PRE | Exact authorized mutation | POST evidence | STOP if | Rollback boundary |
| --- | --- | --- | --- | --- | --- |
| **L0** | owner authorization; §10 prerequisites met | **none (READ_ONLY OBSERVATION):** streamed `install_authority_dev.py preflight` and streamed `verify_broker_dev_current_incarnation.py baseline`; no file is copied to DEV | `status L0` PASS: account and all LILITH paths absent; host prerequisites ABSENT or PRESENT_SECURE (current DEV: host key ABSENT, credstore PRESENT_SECURE and empty); needrestart control hash `503279…68d2`; units not found/inactive; baseline equals the accepted current-runtime baseline | any LILITH object present; a prerequisite PRESENT_UNSAFE or the credstore not empty; needrestart changed; baseline or preservation diff | — (nothing changed) |
| **L1a** | L0 PASS; the §10 deployer/DR-5 hardening merged and its live denial prerequisites passed on a real routine deployment | `install_authority_dev.py accounts` → `useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin lilith-authority-dev` | `status L1a` PASS: uid/gid recorded (U1), primary group only, password locked, `sudo -l -U` not allowed, `/nonexistent` absent | the name exists; any contract check fails | `userdel lilith-authority-dev` (removes the user group), only if nothing later ran |
| **S-1** (staging) | L1a PASS; archive and attestation built on the workstation by `ceremony/build_authority_dev_release.py` from clean `<RELEASE_SHA>`; their SHA-256 recorded | **STAGING only:** `mkdir -m 0700 ~/b1b3d-l2-stage` (as the owner, not root), then `gcloud compute scp --tunnel-through-iap` of exactly the archive and attestation into it | on-host `sha256sum` of both equals the workstation values; directory owner-only 0700; nothing else in it | any hash mismatch; the directory already exists | `rm -rf ~/b1b3d-l2-stage` |
| **L1b.1** | L1a PASS; S-1 POST PASS | streamed `install_authority_dev.py release <RELEASE_SHA> <staged archive> <staged attestation>` (it reads each file once and verifies from memory): verify the archive, stage, create an offline pinned venv, import-check as `lilith-authority-dev`, rename to `releases/<RELEASE_SHA>` | `status L1b.1 <RELEASE_SHA>` PASS; manifest hash; tree `root:root`, dirs 0755 | verification or import check fails; staging or target exists | `rm -rf /opt/lilith-authority-dev/releases/<RELEASE_SHA>` (and the empty parents if this created them) |
| **S-2** (unstaging) | L1b.1 PASS | `rm -rf ~/b1b3d-l2-stage` (nothing else) | the directory is absent | — | — |
| **L1b.2** | L1b.1 PASS; S-2 done | `install_authority_dev.py select <RELEASE_SHA>` → `current -> releases/<RELEASE_SHA>` | `status L1b.2 <RELEASE_SHA>` PASS | `current` exists | `rm /opt/lilith-authority-dev/current` |
| **L1c.1** | L1b.2 PASS | `install_authority_dev.py units <RELEASE_SHA>` → unit, socket, and tmpfiles files `root:root 0644` from the release (no reload, no enable, no `systemd-tmpfiles --create`) | `status L1c.1 <RELEASE_SHA>` PASS: bytes equal the release assets; units not active, not enabled | any target exists | remove the three files |
| **L1c.2** | L1c.1 PASS | `systemctl daemon-reload` (nothing else) | `status L1c.2 <RELEASE_SHA>` PASS: both units `LoadState=loaded`, `ActiveState=inactive`, `UnitFileState=static`, `NeedDaemonReload=no` | any unit active or enabled | remove the L1c.1 files, then `daemon-reload` |
| **L1c.3** | L1c.2 PASS | `install_authority_dev.py cli <RELEASE_SHA>` → `/usr/local/sbin/lilith-authority-keygen-dev` `root:root 0755` from the release | `status L1c.3 <RELEASE_SHA>` PASS; CLI hash equals the release copy | target exists | remove the CLI |
| **L2a** (host prerequisite) | L1c.3 PASS; read `observed.hostPrerequisites` from it | **If ABSENT:** `systemd-creds setup` (nothing else). **If PRESENT_SECURE:** adopt it, **no mutation**. **If PRESENT_UNSAFE:** STOP (L1c.3 already FAILs) | `status L2a <RELEASE_SHA>` PASS: host key `root:root 0400` (stat only; never printed or copied); record CREATED or ADOPTED | unsafe owner, mode, or type; the credstore not empty | only if this step CREATED it and no blob exists: remove it. An adopted key is never removed |
| **L2b.1** (host prerequisite) | L2a PASS; the §10 denials for every LILITH path created so far are non-vacuous on the latest routine deployment | streamed `install_authority_dev.py credstore <RELEASE_SHA>`: **if ABSENT**, create `/etc/credstore.encrypted` `root:root 0700`; **if PRESENT_SECURE and empty** (current DEV), adopt it, **no mutation** (`"mutation": "ADOPTED_NO_MUTATION"`) | `status L2b.1 <RELEASE_SHA>` PASS: directory `root:root 0700`, empty | PRESENT_UNSAFE; not empty | only if CREATED: `rmdir` (if empty). An adopted credstore is never removed |
| **L2b.2** | L2b.1 PASS; re-check both host prerequisites PRESENT_SECURE and the credstore empty (`status --expect L2b.1`, and again by the keygen preflight); `swapon --show` empty | `lilith-authority-keygen-dev actor > /root/b1b3d-l2b-publication.json` | publication JSON; `status L2b.2 <RELEASE_SHA>` PASS with `credentialBlobSha256` equal to `blobSha256`; `journalctl` and transcript scans clean | exit ≠ 0; any private-key pattern anywhere; hash mismatch | delete the blob (synthetic; re-keying is recovery, design §16) |

Not in this runbook, and **not authorized by it**:

- starting or enabling either unit;
- `systemd-tmpfiles --create`;
- `/etc/lilith-authority-dev`, the `INSTALLED` marker, registry, trust
  anchors, or `signer.json` (L3a);
- the ledger (L3c);
- the witness;
- activation (L4);
- the denial proofs (L5).

### Account and filesystem contract

The installer's `expected_paths` and these rows are pinned to each other by
tests. `svc` is `lilith-authority-dev`.

The last column is the step that **creates** a LILITH object. For the two
host prerequisites (R-4), it is the step from which they are **required**.
Before that step they may be absent or already exactly secure. They are
never LILITH maturity.

| Path | Kind | Owner | Mode | Created at / required from |
| --- | --- | --- | --- | --- |
| `/opt/lilith-authority-dev` | dir | root:root | 0755 | L1b.1 |
| `/opt/lilith-authority-dev/releases` | dir | root:root | 0755 | L1b.1 |
| `/opt/lilith-authority-dev/releases/<RELEASE_SHA>` | dir | root:root | 0755 | L1b.1 |
| `/opt/lilith-authority-dev/current` | symlink | root:root | — | L1b.2 |
| `/etc/systemd/system/lilith-authority-dev.service` | file | root:root | 0644 | L1c.1 |
| `/etc/systemd/system/lilith-authority-dev.socket` | file | root:root | 0644 | L1c.1 |
| `/etc/tmpfiles.d/lilith-authority-dev.conf` | file | root:root | 0644 | L1c.1 |
| `/usr/local/sbin/lilith-authority-keygen-dev` | file | root:root | 0755 | L1c.3 |
| `/var/lib/systemd/credential.secret` | file | root:root | 0400 | L2a |
| `/etc/credstore.encrypted` | dir | root:root | 0700 | L2b.1 |
| `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` | file | root:root | 0600 | L2b.2 |

Account (L1a):

- `lilith-authority-dev`, a system account with uid < 1000, allocated by the
  OS (U1);
- primary group `lilith-authority-dev`, with no members and no supplementary
  groups;
- home `/nonexistent`, not created;
- shell `/usr/sbin/nologin`;
- password locked;
- no sudo.

Must stay **absent** through L2b:

- `/etc/lilith-authority-dev`, `/var/lib/lilith-authority-dev`,
  `/run/lilith-authority-dev`, and
  `/run/credentials/lilith-authority-dev.service`;
- `/var/lib/lilith-recovery-witness`, `/run/lilith-recovery-witness`, and
  the K-WIT blob.

### N-45: `PRESERVATION_VERIFIER_PHASE_MISMATCH`

Recorded 2026-09-27 (register
[N-45](../research/negative-results-register.md#register)).

**What happened.** During the live ladder, L1b.1 had passed
(`RELEASE_SHA=9ac7de2…`; `/opt/lilith-authority-dev`, `releases/`, and
`releases/<RELEASE_SHA>` all `root:root 0755`), and `DR5_L1B1_LIVE_BOUNDARY`
was PASS. `current` was absent, and S-1 staging still held exactly the two
accepted artifacts. The S-2 PRE preservation check then ran
`verify_broker_dev_current_incarnation.py baseline`. It returned
`CURRENT_RUNTIME_BASELINE=FAIL` with only
`failures=["CUSTODY_PATH_PRESENT_BEFORE_B1B3D"]` and
`custodyPaths./opt/lilith-authority-dev=PRESENT`. The broker candidate
itself was still the accepted incarnation.

**Cause.** The runbook used a pre-custody observer as the preservation
check for post-custody steps. `baseline` encodes "no custody path exists
yet", which is correct for L0 and L1a and correctly false from L1b.1 on.

**Correction (source only).**

- `baseline` keeps its exact semantics, and its output is unchanged.
- A separate `preservation` operation runs the same broker checks and pins
  the accepted incarnation and candidate hash. It always produces and hashes
  the candidate. It reports custody without judging it, and it has no
  ignore, allow, or bypass option.
- Exact authority state stays with the installer `status`, and deployer
  denial with DR-5.
- `status` now also refuses any `releases/` entry other than
  `<RELEASE_SHA>`.

**Nothing live changed.** S-2 and L1b.2 remain NOT_EXECUTED until
re-authorized under the corrected preservation rule.

## 10. Deployer boundary and DR-5

This slice does not change:

- the routine deployer's sudoers rule, helper, library, or verifier;
- `deploy-dev.yml`;
- the Core API bundle.

The routine deployment never packages anything from `services/authority-dev/`
or any credential. The release archive refuses custody-looking members.

### Dependency order (corrected)

```text
L2 source preparation (this record)
  -> deployer / DR-5 authority-path hardening (separate PR; deploy-dev.yml)
  -> live denial-proof prerequisites (a real routine deployment passes them)
  -> only then live L1a
```

The deny list must be in place **before live L1a**, not before L2b. The
authority domain must not be created before the routine deployer boundary is
established. Otherwise a compromised routine deployer could pre-position a
modified signer release, CLI, or unit before the credential is introduced,
and the credential would then be loaded by attacker-chosen code.

**Denial-proof prerequisites before L1a.** Most authority paths do not exist
yet. Their denials are vacuous until they do (DR-5). So the prerequisites that
can be proven non-vacuously before L1a are:

- the effective-sudo proof (the deployer can run only the fixed helper,
  D12);
- write denials on the existing parent directories that the ladder will
  populate: `/opt`, `/etc/systemd/system`, `/etc/tmpfiles.d`,
  `/usr/local/sbin`, `/etc`, and `/var/lib/systemd`;
- `sudo -u` denial for the existing `lilith-memory-broker`.

Every path-specific denial below becomes mandatory and non-vacuous as soon as
the ladder step that creates the path completes.

**Required extension (separate PR; design §7; not made here).** Implemented as source in the [deployer authority-boundary record](slice-15b2b-b1b3d-deployer-authority-boundary.md), where maturity is derived from the ladder's own root-owned objects rather than a marker; live denial is still to be proven. Proof-only
checks in `deploy-dev.yml`:

```text
deny sudo -n -u lilith-authority-dev true
deny sudo -n /usr/bin/systemctl restart lilith-authority-dev.service
deny sudo -n /usr/bin/systemctl start lilith-authority-dev.socket
deny sudo -n /usr/local/sbin/lilith-authority-keygen-dev actor
deny test -w                       /opt /etc/systemd/system /etc/tmpfiles.d /usr/local/sbin /etc /var/lib/systemd
deny test -r / test -w / test -x   /etc/credstore.encrypted
deny test -r / test -w             /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred
deny test -r                       /var/lib/systemd/credential.secret
deny test -w                       /opt/lilith-authority-dev  /opt/lilith-authority-dev/releases  /opt/lilith-authority-dev/current
deny test -w                       /usr/local/sbin/lilith-authority-keygen-dev
deny test -w                       /etc/systemd/system/lilith-authority-dev.service (and .socket)
```

It covers:

- `sudo -u lilith-authority-dev`;
- starting and restarting the authority units;
- running `lilith-authority-keygen-dev`;
- writing or replacing the release trees, the CLI, and the unit and socket
  material;
- reading and writing `/etc/credstore.encrypted` and the K-ACT blob;
- reading the host credential key.

**Relationship to DR-5.** A missing path currently counts as `DENIED`, which
proves nothing. The fix is an existence rule: once the ladder step that
creates a listed path has completed, that path must exist, or the deploy
fails. The design keys the rule on the `INSTALLED` marker (L4). That is too
late here, because paths are created from L1a onward. The PR must key each
path's requirement on an earlier, root-controlled fact that the deployer
cannot forge. That mechanism is designed in that PR, not here.

**DR-5 stays OPEN.** It closes only when that extension is merged and a real
routine deployment after L2b shows non-vacuous `DENIED` lines.

## 11. Tests

`services/authority-dev/tests/test_custody_preparation.py` covers the task's
requirements 1–16. Requirements 17–18 are the validator and the existing
suites. Everything runs in temporary directories with injected OS lookups.
Tests never call `Ed25519PrivateKey.generate()` or `systemd-creds`, and never
touch `/`.

## 12. Properties

**Proven in source and tests:**

- the keygen accepts only `actor`, and every value it binds is fixed and
  equal to the L1 profile and the design;
- it has no PRIVACY, prod, export, seed, raw-sign, network, DB, or registry
  path;
- it refuses on every unmet precondition before generating anything;
- plaintext is written only to the encryptor's stdin, and the blob is
  written `O_EXCL` `0600`;
- the public output's serialization is canonical for a given key and
  ceremony result (not across key generations), and yields a valid B1b-3a
  `AuthorityKeyRecordV1`;
- the installer performs one transition per stage, refuses collisions, never
  enables, starts, or reloads a unit, and never runs `systemd-creds`;
- its path contract equals this runbook;
- the release archive is deterministic, pinned (wheels equal to the broker's
  accepted set), and free of custody material;
- no PROD path and no routine-bundle path is introduced.

**NOT_YET_LIVE_PROVEN:**

- every live step and POST on `lilith-dev-01`;
- `systemd-creds` behaviour with `-`/`-`;
- the host-key mode after `systemd-creds setup`;
- that the unit decrypts the blob and exposes it only to its own uid;
- every denial in design §17;
- the DR-5 existence rule.

**NOT_PROVEN (not an acceptance property):** memory zeroization and
remanence; protection against whole-host or snapshot rollback;
real-owner-grade custody.

DR-3 (`ubuntu` root-equivalent) and DR-5 stay **OPEN**.

## 13. Explicitly not done

- No DEV or PROD contact; no SSH or IAP.
- No `systemd-creds` execution for encryption or setup.
- No key generated, and no credential or blob created.
- No account, directory, unit, or `daemon-reload`; nothing started or
  enabled.
- No broker → signer IPC, ledger, witness, or Privacy custody.
- No change to the deployer, `deploy-dev.yml`, needrestart, IAM, WIF, or
  Stage III.
