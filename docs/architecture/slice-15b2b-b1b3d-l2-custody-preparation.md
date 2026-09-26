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

## 3. Unresolved decisions (surfaced, not decided)

| # | Decision | Handling here |
| --- | --- | --- |
| U1 | **Numeric uid/gid** for `lilith-authority-dev`. The design does not pin one. | Not pinned. `useradd --system` allocates it (the broker precedent); the POST evidence records it, and it must be `< 1000`, non-zero, and distinct from `lilith`, `lilith-memory-broker`, and `lilith-memory-relay`. |
| U2 | **`lilith-recovery-witness` account.** Design L1a creates both accounts. The witness is a later slice, outside this OWNER_ACTOR scope. | **STOPPED.** L1a creates only `lilith-authority-dev`. The witness account, key (K-WIT), and paths stay absent and are checked absent. |
| U3 | **Which step creates `/etc/credstore.encrypted`.** The design gives its mode but no step. | Proposed as its own step, L2b.1, before the keygen (L2b.2). |
| U4 | **Splitting design L1b and L1c.** The design groups the tree with `current`, and the CLIs with the units and `daemon-reload`. | Split into L1b.1/L1b.2 and L1c.1/L1c.2/L1c.3, so each is one transition. |
| U5 | **Blob check without decryption.** Proving that the blob decrypts to the published key needs plaintext again. | Not done at L2b. The link is checked at the later activation: the L1 service `HEALTH` reports `publicKeySha256`, which must equal the publication's value. |
| U6 | **`deploy-dev.yml` deny-list extension** (design §7; DR-5). | Not changed. See §10. It must merge before L2b. |
| U7 | **Swap during keygen.** Not in the design. | The keygen refuses while any swap is active (`/proc/swaps`), to keep the plaintext key out of swap. |

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
- no active swap;
- the only reference to the key object is released.

**Memory zeroization and remanence are NOT_PROVEN.** Python bytes are
immutable and cannot be wiped. Neither a pipe closing nor a process exiting
is secure erasure. Root can read any process's memory while it runs.

## 7. Public-material contract

The keygen prints exactly one line on stdout. It is JSON with sorted keys, no
whitespace, ASCII, and a trailing newline. For a given key and blob it is the
same bytes every time; no timestamp is included.

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
- **Transfer.** Copy files with `gcloud compute scp --tunnel-through-iap`.
  Do not pipe scripts over stdin to `gcloud compute ssh` on Windows (a stray
  `y` is injected).
- **Installer invocation.** Copy `services/authority-dev/ceremony/install_authority_dev.py`
  from the reviewed commit and run it:
  `sudo /usr/bin/python3 -I -B /tmp/b1b3d-l2/install_authority_dev.py …`.
  `<SHA>` below is the protected-main commit being installed.
- **Preservation set.** Every step starts by re-running the read-only
  preservation checks:
  - `scripts/verify_broker_dev_current_incarnation.py baseline` equals the
    accepted current-runtime baseline;
  - the B1c helper, library, verifier, and sudoers hashes are unchanged;
  - activation is `NOT_ACCEPTED reason=GRANT_ABSENT`;
  - the Stage III artifacts are unchanged.

  **STOP** on any difference.
- **POST check.** Every step's POST is
  `install_authority_dev.py status --expect <step> [<SHA>]` with
  `"result": "PASS"`, plus the step-specific evidence below. Save every
  transcript to the owner evidence directory.
- **Private material.** Any private-key pattern in any output or journal
  means **STOP**. Delete the affected blob, record the incident, and start
  again from L2a's POST.

### Steps

| Step | PRE | Exact authorized mutation | POST evidence | STOP if | Rollback boundary |
| --- | --- | --- | --- | --- | --- |
| **L0** | owner authorization; files copied to `/tmp/b1b3d-l2/` | none: `install_authority_dev.py preflight` | `status L0` PASS: account and all paths absent, needrestart control hash `503279…68d2`, units not found/inactive | anything present; needrestart changed; preservation diff | — |
| **L1a** | L0 PASS | `install_authority_dev.py accounts` → `useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin lilith-authority-dev` | `status L1a` PASS: uid/gid recorded (U1), primary group only, password locked, `sudo -l -U` not allowed, `/nonexistent` absent | the name exists; any contract check fails | `userdel lilith-authority-dev` (removes the user group), only if nothing later ran |
| **L1b.1** | L1a PASS; archive and attestation built on the workstation by `ceremony/build_authority_dev_release.py` from clean `<SHA>`; archive SHA-256 recorded | `install_authority_dev.py release <SHA> <archive> <attestation>`: verify the archive, stage, create an offline pinned venv, import-check as `lilith-authority-dev`, rename to `releases/<SHA>` | `status L1b.1 <SHA>` PASS; manifest hash; tree `root:root`, dirs 0755 | verification or import check fails; staging or target exists | `rm -rf /opt/lilith-authority-dev/releases/<SHA>` (and the empty parents if this created them) |
| **L1b.2** | L1b.1 PASS | `install_authority_dev.py select <SHA>` → `current -> releases/<SHA>` | `status L1b.2 <SHA>` PASS | `current` exists | `rm /opt/lilith-authority-dev/current` |
| **L1c.1** | L1b.2 PASS | `install_authority_dev.py units <SHA>` → unit, socket, and tmpfiles files `root:root 0644` from the release (no reload, no enable, no `systemd-tmpfiles --create`) | `status L1c.1 <SHA>` PASS: bytes equal the release assets; units not active, not enabled | any target exists | remove the three files |
| **L1c.2** | L1c.1 PASS | `systemctl daemon-reload` (nothing else) | `status L1c.2 <SHA>` PASS: both units `LoadState=loaded`, `ActiveState=inactive`, `UnitFileState=static`, `NeedDaemonReload=no` | any unit active or enabled | remove the L1c.1 files, then `daemon-reload` |
| **L1c.3** | L1c.2 PASS | `install_authority_dev.py cli <SHA>` → `/usr/local/sbin/lilith-authority-keygen-dev` `root:root 0755` from the release | `status L1c.3 <SHA>` PASS; CLI hash equals the release copy | target exists | remove the CLI |
| **L2a** | L1c.3 PASS; `/var/lib/systemd/credential.secret` absent; no credential anywhere | `systemd-creds setup` (nothing else) | `status L2a <SHA>` PASS: host key `root:root 0400` (stat only; never printed or copied) | the host key already exists; any other credential present | remove `/var/lib/systemd/credential.secret`, only while no blob exists |
| **L2b.1** | L2a PASS; `deploy-dev.yml` deny-list extension merged (§10) | `install_authority_dev.py credstore <SHA>` → `/etc/credstore.encrypted` `root:root 0700` | `status L2b.1 <SHA>` PASS: directory empty | the directory exists | `rmdir /etc/credstore.encrypted` (only if empty) |
| **L2b.2** | L2b.1 PASS; `swapon --show` empty | `lilith-authority-keygen-dev actor > /root/b1b3d-l2b-publication.json` | publication JSON; `status L2b.2 <SHA>` PASS with `credentialBlobSha256` equal to `blobSha256`; `journalctl` and transcript scans clean | exit ≠ 0; any private-key pattern anywhere; hash mismatch | delete the blob (synthetic; re-keying is recovery, design §16) |

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

| Path | Kind | Owner | Mode | Created at |
| --- | --- | --- | --- | --- |
| `/opt/lilith-authority-dev` | dir | root:root | 0755 | L1b.1 |
| `/opt/lilith-authority-dev/releases` | dir | root:root | 0755 | L1b.1 |
| `/opt/lilith-authority-dev/releases/<SHA>` | dir | root:root | 0755 | L1b.1 |
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

## 10. Deployer boundary and DR-5

This slice does not change:

- the routine deployer's sudoers rule, helper, library, or verifier;
- `deploy-dev.yml`;
- the Core API bundle.

The routine deployment never packages anything from `services/authority-dev/`
or any credential. The release archive refuses custody-looking members.

**Required before L2b (a separate PR; design §7).** Extend the routine
deny list in `deploy-dev.yml` with proof-only checks:

```text
deny sudo -n -u lilith-authority-dev true
deny sudo -n /usr/bin/systemctl restart lilith-authority-dev.service
deny sudo -n /usr/bin/systemctl start lilith-authority-dev.socket
deny sudo -n /usr/local/sbin/lilith-authority-keygen-dev actor
deny test -r / test -w / test -x   /etc/credstore.encrypted
deny test -r / test -w             /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred
deny test -r                       /var/lib/systemd/credential.secret
deny test -w                       /opt/lilith-authority-dev  /opt/lilith-authority-dev/current
deny test -w                       /usr/local/sbin/lilith-authority-keygen-dev
deny test -w                       /etc/systemd/system/lilith-authority-dev.service (and .socket)
```

**Relationship to DR-5.** A missing path currently counts as `DENIED`, which
proves nothing. The fix is an existence rule: every listed path whose owner
step has completed must exist, or the deploy fails. The design keys this on
the `INSTALLED` marker (L4). That marker comes too late for the L2b blob. So
the extension must at least require the credstore paths once
`/etc/credstore.encrypted` exists.

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
- the public output is deterministic and yields a valid B1b-3a
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
