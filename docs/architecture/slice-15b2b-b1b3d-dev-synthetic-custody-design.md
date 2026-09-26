# Slice 15B2b-B1b-3d — DEV_SYNTHETIC Authority Custody and OS Isolation Design

Status:

- **DESIGN RECORD**
- **NOT IMPLEMENTED**
- **NOT LIVE**
- **NO KEY INSTALLED**
- **NO AUTHORITY ACTIVATED**

Base: protected main `5af5467a1d4e7a1127e0a891cfc301d016e5b7b1`.

This record designs the fourth sub-slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md),
built on [B1b-3a](slice-15b2b-b1b3a-authority-registry-contracts.md),
[B1b-3b](slice-15b2b-b1b3b-broker-signing-l04-v2-adapter.md), and
[B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md). It also reuses the
accepted [B1c routine DEV deployer boundary](slice-15b2b-b1c-acceptance-record.md).

It is not an acceptance record, an implementation authorization, or an
activation instruction. It does **not** mark B1b-3, Level 2 isolation, real
owner authority, First Memory, Privacy custody, or Stage III as complete.

This design task made no change to DEV, PROD, IAM, WIF, systemd, keys,
registries, witnesses, the broker, or Stage III. The only live contact was
the read-only DEV inventory in §2.

The status after the future acceptance of this slice is capped at:

```text
DEV_SYNTHETIC CUSTODY PROVEN
```

It is never `REAL AUTHORITY READY`.

Labels are used as in the B1b-3 design:

- **CANONICAL** — defined by accepted records.
- **IMPLEMENTED** — present in source or installed state.
- **OBSERVED** — read live on DEV on 2026-09-26 (UTC) by the owner
  break-glass session, read-only.
- **PROPOSED** — a design recommendation that still needs review and
  authorization.

## 1. Purpose and target property

This slice designs the first **real DEV OS-custody installation**. It uses
**synthetic** authority material only.

**PROPOSED target property.** The real DEV host (`lilith-dev-01`) may hold a
DEV_SYNTHETIC OWNER_ACTOR signing key and a DEV_SYNTHETIC recovery-witness
signing key. Even so:

1. `lilith` cannot read or write any private authority material.
2. Hermes and application code cannot reach signing custody.
3. The routine DEV deployer cannot read, write, or replace custody.
4. Application deployment cannot replace the authority registry, the trust
   anchors, or the witness.
5. The authority signer can perform only its intended signing operations.
   The witness service can perform only its intended witness operations.
6. Owner/root keeps explicit break-glass and recovery capability.
7. If a stale signer ledger is restored while a current witness survives,
   authority issuance is blocked.

**Not claimed:**

- real owner authority;
- whole-host or whole-disk rollback protection;
- host-root compromise resistance (Level 3);
- Privacy custody (B1b-3f);
- closure of `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT`;
- anything about Stage III.

## 2. Current DEV custody inventory

**OBSERVED**, read-only, over the owner IAP session on 2026-09-26. No writes,
no service actions, and no secret or database contents were read.

### Host

| Item | Value |
| --- | --- |
| Instance | `lilith-dev-01`, `asia-southeast1-b`, project `lilith-agent-260823-27389` |
| machine-id | `ae929170e6fa4c8ab9cc7b9547238d9d` (matches `dev-config.schema.json`) |
| Boot ID | `24d1771d-e1b5-4e5f-816d-da08ad8b367a`, up since 2026-09-13 17:58 UTC (matches the accepted Stage II boot) |
| OS / kernel | Ubuntu 24.04.4 LTS, `6.17.0-1022-gcp` |
| systemd | 255 (255.4-1ubuntu8.17); `systemd-creds` present |
| TPM | `tpm0` present; `systemd-creds has-tpm2` = `partial` (`-libraries`: the TPM2 TSS libraries are not installed) |
| Host credential key | `/var/lib/systemd/credential.secret` **absent**: no host-key-encrypted credential has ever been created |
| Broker venv | Python 3.12.3, `cryptography` 50.0.1 (Ed25519 available) |
| Host python | 3.12.3, `cryptography` 41.0.7 |

### Accounts

| Account | uid:gid | Groups | Shell | sudo |
| --- | --- | --- | --- | --- |
| `lilith` (application) | 1001:1002 | `lilith` | `/bin/bash` | none |
| `lilith-memory-broker` | 999:987 | `lilith-memory-broker` | nologin | none |
| `lilith-memory-relay` | 997:986 | + `lilith-memory-ipc` (988) | nologin | none |
| `sa_112096412008414111981` (routine deployer) | 3826947836 | own group only | `/bin/bash` | exactly `(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, … status` |
| owner | OS Login admin (`google-oslogin` sudoers), root via sudo | — | — | full (break-glass) |
| `ubuntu` | image default | `sudo`, `adm` | — | root-capable by group; `~ubuntu/.ssh/authorized_keys` is 0 bytes |

`google-sudoers` has no members.

`/etc/sudoers.d` contains:

- `90-cloud-init-users`;
- `README`;
- `google-oslogin`;
- `google_sudoers`;
- `lilith-dev-deployer` (`root:root 0440`, SHA-256 `420fa1c7…a6139`).

### Units

| Unit | State | Enablement | Identity |
| --- | --- | --- | --- |
| `lilith-memory-broker.service` | active/running, MainPID 132976, `NRestarts=0`, started 2026-09-26 06:34:09 UTC, InvocationID `42af2691b8d24ee5a92a286197c5444c` | `static` | `lilith-memory-broker`, `ProtectSystem=strict`, `NoNewPrivileges=yes`, RO `/opt/lilith-memory-broker /etc/lilith-memory-broker`, RW `/var/lib/lilith-memory-broker`, no drop-ins, no credentials |
| `lilith-memory-broker.socket` | active/listening, InvocationID `1434eda774ed4d8296bc4e266191bc67` | **`disabled`** | — |
| `lilith-os-api-dev.service` | active/running (restarted 2026-09-26 13:20:43 UTC by routine deploy) | enabled | `lilith` |
| `lilith-stage3-a2-final.service` | **failed** (exit 1, 2026-09-25 14:06:16 UTC) | — | — |

Unit SHA-256s:

- broker service `6a9dca54…d35689`;
- socket `d9f21223…82e793`;
- tmpfiles `e6139f16…4df86e`;
- API unit `cce9dc9e…28a3aa3`.

The three broker hashes equal the git blobs at
`services/memory-broker/deploy/` on `5af5467`. The API unit is outside that
set.

### Paths

| Path | Owner / mode |
| --- | --- |
| `/opt/lilith-memory-broker`, `releases/`, `releases/{817a83e…,4a04f2d…}` | `root:root 0755` |
| `/opt/lilith-memory-broker/current` | → `releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2` (accepted selector, unchanged) |
| `/opt/lilith-stage3-a2-final-v1` | `root:root 0555` |
| `/opt/lilith-trusted-controls/broker-snapshot` | `root:root 0755` |
| `/etc/lilith-memory-broker` | `root:root 0755` (so `lilith` can **list** entry names) |
| `…/dev.json` | `root:lilith-memory-broker 0640` |
| `…/identities.json`, `previous-release`, `b1b2b-*.used.json` | `root:root 0600` |
| `…/b1b2b-stage3-a2-authorization.json` | `root:root 0600`, present (preserved, unconsumed, long expired) |
| `/var/lib/lilith-memory-broker/{owner-control,state}` | `lilith-memory-broker 0700`; DB files 0600 |
| `/run/lilith-memory` | `root:lilith-memory-ipc 0710` |
| `/run/lilith-memory/owner.sock` | `lilith-memory-broker:lilith-memory-ipc 0660` |
| `/run/lilith-memory-stage3`, `/run/lilith-stage3-a2` | absent (no arm, no guard) |
| `/etc/lilith-os-dev` and `activation/` | `root:root 0755`; `activation/` empty (no signer, no grant) |
| `/etc/lilith-os-dev/canonical-runtime.json` | `root:lilith 0640` |
| `/usr/local/sbin/lilith-dev-deploy` | `root:root 0755`, SHA-256 `85b260a2…8755b8` (= B1c acceptance) |
| `/usr/local/sbin/lilith-activation-verify` | `root:root 0755`, SHA-256 `44046cae…ca1a32` |
| `/usr/local/lib/lilith-dev-deploy/*` | `root:root 0644` |
| `/home/lilith` | `lilith:lilith 0750` |

Read probes run as `lilith`:

| Probe | Result |
| --- | --- |
| `dev.json`, `identities.json` | DENIED |
| `/var/lib/lilith-memory-broker` | DENIED |
| `/run/lilith-memory` | DENIED |
| write `/etc/lilith-memory-broker` | DENIED |
| list `/etc/lilith-memory-broker` | ALLOWED (names only) |

### Current authority custody

| Artifact | Present on DEV? |
| --- | --- |
| OWNER_ACTOR asymmetric signing key | **no** (D7 still open) |
| Recovery witness / witness key | **no** |
| Authority registry / registry root | **no** |
| Owner WebAuthn credential | no (only the public synthetic `ocred.synthetic` in broker state) |
| Activation signer / grant | no |
| Privacy / containment keys (broker config `custody.*`) | `ABSENT` by schema |

Restart and update authority today:

- Owner break-glass (root) is the only identity that can start, stop, or
  install the broker.
- The routine deployer can restart only `lilith-os-api-dev.service`, through
  the fixed helper.

## 3. Live and docs drift

| # | Drift | Assessment |
| --- | --- | --- |
| DR-1 | **The accepted Stage II broker incarnation is gone.** The accepted profile pins InvocationID `5c1eb955e2dc44e78139c416f0c9469a` and PID 96650 (`trusted_broker_snapshot_installer.py`). The journal shows: started 2026-09-24 06:51; stopped by the Stage III A2 controller 2026-09-25 14:06; owner restart of socket and broker 14:54 (REPORTED in the negative-results register, N-25); **a further broker stop/start 2026-09-26 06:34:09 UTC that no repository record explains**. | The release selector, units, config, and state custody are unchanged. The trusted snapshot validator would now reject the incarnation. This must be acknowledged by the owner before B1b-3d Step L0 and is **not** repaired here. Per the accepted-lifecycle record, a new incarnation needs its own separately approved baseline. |
| DR-2 | The B1c acceptance record says the broker "is active" with an unchanged selector. | Still true. The incarnation differs (DR-1). |
| DR-3 | `ubuntu` is in `sudo` and `adm`. The B1c records do not list it among root-capable identities. | Its `authorized_keys` is empty, so there is no current login path. It remains a residual root-capable local account and is listed in §18. |
| DR-4 | `/etc/lilith-memory-broker` is world-listable (0755). | This is by design (B1c). It is noted because B1b-3d custody must **not** be placed there. |
| DR-5 | The B1c routine deny list checks `sudo -u lilith`. It does not check `sudo -u lilith-memory-broker`, and it does not require a probed path to exist. | A missing path counts as `DENIED`, which is vacuous for new paths. §7 fixes this for B1b-3d paths. |
| DR-6 | The B1b-3c doc says `authority_epoch` in `broker_schema_v1` is static and inert. | Consistent. B1b-3d retires it; see §12. |

No drift was found in:

- the deployer sudo rule;
- the helper and verifier hashes;
- the activation paths;
- the broker unit and socket hashes;
- the Stage III artifacts (the controller is failed, there is no arm or guard, and the authorization is preserved).

## 4. Synthetic key domains

**PROPOSED.** B1b-3d introduces exactly three DEV_SYNTHETIC keys. It
introduces no other key.

| Key | Purpose | Proposed keyId | Private custody | Public location |
| --- | --- | --- | --- | --- |
| **K-ACT** OWNER_ACTOR authority signer | sign `OwnerEvidenceV2` (`OWNER_MEMORY_OPERATION`) | `test-only.dev-synthetic.actor.b1b3d.1` | DEV host, encrypted systemd credential, loaded only into `lilith-authority-dev.service` | registry key record |
| **K-WIT** recovery-witness signer | sign `RecoveryWitnessV1` only | `test-only.witness.dev-synthetic.b1b3d.1` | DEV host, encrypted systemd credential, loaded only into `lilith-recovery-witness.service` | witness anchor file |
| **K-ROOT** authority-registry root | sign `AuthorityRegistryV1` only | `test-only.registry-root.dev-synthetic.b1b3d.1` | **never on DEV.** Owner workstation only | trust-anchor file |

Required distinctness:

- Each of the three keys is distinct from the others.
- Each is distinct from:
  - the B1c activation SSH key (`lilith-canonical-activation`);
  - the owner WebAuthn credential;
  - the B2a synthetic broker keys;
  - the B1b-3a/3b/3c TEST fixture keys;
  - the V1 Actor HMAC secret;
  - the Privacy authority key;
  - the containment PRF key.
- No real owner credential is used. No production key is reused.
- Every record carries `environment: "dev"`.
- Every key ID carries the `test-only.` prefix and the `dev-synthetic` label.

The witness ID keeps the B1b-3c prefix `test-only.witness.`. The key ID
spelling must be confirmed against the B1a identifier validator in the
source slice.

**Contract consequence (source slice).** Two TEST-only constructors refuse
any environment except `test`:

- the B1b-3b signer (`SyntheticBrokerAuthorityV1`);
- the B1b-3c witness writer.

B1b-3d must not widen those TEST contracts in place. It adds a new,
separately versioned **DEV_SYNTHETIC profile**, for example
`DevSyntheticSignerConfigV1` and `DevSyntheticWitnessWriterV1`. That profile:

- admits only `environment=dev`;
- admits only `test-only.` key IDs;
- admits only `.invalid` RP/origin;
- admits only the fixed synthetic owner/access identity and fixture;
- has its own golden vectors;
- refuses `prod` structurally.

## 5. Key custody options

| | A. root-owned file readable by the service account | B. systemd `LoadCredential[Encrypted]=` | C. root helper through a runtime channel | D. TPM2-sealed credential |
| --- | --- | --- | --- | --- |
| App isolation | yes (mode) | yes; source file root 0600 plus a per-unit ramfs copy | yes | yes |
| Routine deployer isolation | yes (mode) | yes | yes | yes |
| Service uid reads source at any time | **yes**: any process under that uid, at any time | **no**: PID 1 reads the source and exposes it only in `$CREDENTIALS_DIRECTORY` of the running unit | no | no |
| Restart behaviour | re-read file | re-delivered at each start. A missing or undecryptable credential fails the unit (fail closed) | a second daemon must be up first | as B |
| Backup exposure | plaintext on disk | `LoadCredential`: plaintext source. `Encrypted` + host key: ciphertext; it decrypts only with `/var/lib/systemd/credential.secret`, which **is on the same disk** | plaintext somewhere root-held | ciphertext bound to the vTPM. Needs the TSS libraries, which are **not installed** (package change) |
| Name binding | none | an encrypted credential embeds its name. A K-WIT blob cannot load as K-ACT | ad hoc | as B |
| Rotation | replace file | replace the blob and restart the unit | custom | as B |
| Auditability | mode and hash | mode, hash, `systemctl show`, journal on failure | custom | as B |
| Recovery | copy file | re-encrypt a new key. A lost host key means every blob is dead, so a new key is needed (acceptable for synthetic) | custom | vTPM-state dependent |
| Complexity | lowest | low; native to systemd 255 | highest | medium, plus a package install |

**Recommendation: B, `LoadCredentialEncrypted=` with `--with-key=host`.**

The fallback is plain `LoadCredential=` from a `root:root 0600` source.

B is the smallest native mechanism for three reasons:

- the service identity can never read the long-lived source;
- the key is name-bound to its unit slot;
- a missing or undecryptable credential fails closed at unit start.

TPM2 sealing (D) is **deferred**. It requires installing TSS libraries on
DEV, and it adds recovery coupling to vTPM state. Neither is needed to prove
this slice.

Honest limits:

- Host-key encryption protects against copying the credential file alone.
  It does **not** protect against a whole-disk snapshot, which contains both
  the blob and `credential.secret`.
- Root can decrypt everything. Level 3 remains out of scope.
- Any process running as the signer uid can read
  `/run/credentials/lilith-authority-dev.service/` while the unit runs. No
  person or other unit can become that uid: nologin, no sudo rule, and not in
  any deployer path.

## 6. Service identity layout

**PROPOSED.** This is a recommendation for owner decision T-1.

B1b-3d adds a **new DEV_SYNTHETIC authority signer** as its own service
identity. It does **not** install signing into the accepted synthetic memory
broker.

| Why not modify `lilith-memory-broker` | Consequence |
| --- | --- |
| Its release (`817a83e…`), units, `dev.json`, and `owner_control.db` rows are pinned Stage II accepted evidence. Stage III's preserved authorization binds the accepted Stage II digest and candidate `4a04f2d…`. | A new broker release or a schema migration there would silently invalidate the accepted Stage II state and the preserved Stage III preconditions. |
| B1b-3 decision 4 (memory broker holds both domains, vs. separate identities) is open. | A separate authority identity keeps OWNER_ACTOR custody away from legacy broker state. It also avoids coupling a future Privacy identity (B1b-3f) to it. |

New identities (system accounts: nologin, no home, no sudo):

| Account | Runs | Holds |
| --- | --- | --- |
| `lilith-authority-dev` | `lilith-authority-dev.service` (the "authority broker", from the B1b-3b "broker / authority signer" role) | K-ACT (runtime credential only); the durable authority ledger |
| `lilith-recovery-witness` | `lilith-recovery-witness.service` | K-WIT (runtime credential only); the witness chain |

The existing `lilith-memory-broker` is untouched. It keeps its synthetic B1b-2
behaviour.

## 7. Routine deployer boundary

**CANONICAL (B1c).** The deployer's only root path is
`/usr/local/sbin/lilith-dev-deploy {deploy <40-hex> | status}`:

- it takes no paths, units, interpreters, or environment;
- root only buffers stdin, drops to `lilith`, and restarts
  `lilith-os-api-dev.service`.

**B1b-3d does not change the sudoers rule, the helper, its library, or the
activation verifier.** If any B1b-3d step turns out to need a wider deployer
rule: **STOP and report**.

Denial by design:

| Action | Denied because |
| --- | --- |
| read K-ACT / K-WIT (source blob) | `/etc/credstore.encrypted` is `root:root 0700`, blobs are 0600, and the deployer is in no group |
| read K-ACT / K-WIT (runtime) | `/run/credentials/<unit>/` is reachable only by the unit uid |
| rewrite witness | `/var/lib/lilith-recovery-witness` is `lilith-recovery-witness:lilith-authority-dev 0750`; the deployer is neither |
| replace registry or trust anchors | `/etc/lilith-authority-dev/**` is root-owned, no group or other write |
| invoke epoch advance | the witness owner socket is `root:root 0600` and the service checks `SO_PEERCRED uid == 0` |
| replace the custody helper or CLIs | `/usr/local/sbin/lilith-authority-*` is `root:root 0755`, beneath root-owned parents |
| restart the signer or witness | sudo allows only the fixed helper, which restarts only the API unit |
| `sudo -u lilith-authority-dev` / `-u lilith-recovery-witness` / `-u lilith-memory-broker` | the rule is `(root)` only, for two exact argument forms |
| modify units | `/etc/systemd/system` is root-owned |

**Proof extension (source slice).** Extend the routine deny list in
`deploy-dev.yml`. This adds proof only; it adds no privilege.

- Add `deny sudo -n -u lilith-authority-dev true`,
  `-u lilith-recovery-witness`, and `-u lilith-memory-broker`.
- Add `deny sudo -n /usr/bin/systemctl restart lilith-authority-dev.service`,
  and the same for `lilith-recovery-witness.service`.
- Add `test -r` / `test -w` denials for every B1b-3d path in §15.
- Fix DR-5. Once the root-owned marker `/etc/lilith-authority-dev/INSTALLED`
  exists, every listed B1b-3d path **must exist**. A missing path then fails
  the deploy instead of counting as `DENIED`.

## 8. Application (`lilith`) boundary

- `lilith` gets **no** new group, socket, or path access.
- B1b-3d exposes **no application-facing socket**. The only signing entry
  point is the root-only authority owner socket, used by the owner for the
  synthetic proof.
- A future app-facing request path, which B1b-3b's
  `OwnerEvidenceRequestV1` would need, is a separate slice with its own
  strict protocol review. No private key bytes cross into any client
  process: every socket returns only signed artifacts and public facts.

Designed denials, tested in §15:

- `lilith` cannot read key blobs or runtime credentials.
- It cannot write `/etc/credstore.encrypted` or `/etc/lilith-authority-dev`.
- It cannot read the witness state or write the witness.
- It cannot connect to either witness socket or to the authority owner socket.
- It cannot connect to the legacy `owner.sock`.
- It cannot read or write the authority ledger, so it cannot reset
  evidence-use state or the recovery epoch.
- It cannot downgrade the registry or witness, because both are
  root-controlled or witness-controlled.

A forged `OwnerEvidenceV2` that `lilith` writes into its own DB fails the
B1b-3a verifier against the owner-signed registry (B1b-3a/3b, TEST-proven).

The public registry and the trust-anchor files are **world-readable by
design**. They are public verification material that a future L04 V2 adapter
needs. They are not writable by `lilith`.

## 9. Service permissions matrix

**PROPOSED.** Least privilege. `READ` means a filesystem read. `SIGN` means
use of the loaded private key in memory.

| Artifact | `lilith-authority-dev` | `lilith-recovery-witness` | `lilith` | routine deployer | owner/root |
| --- | --- | --- | --- | --- | --- |
| K-ACT private (source blob) | NONE (`InaccessiblePaths`) | NONE | NONE | NONE | WRITE (install/rotate); never printed |
| K-ACT private (runtime) | SIGN (read once from `$CREDENTIALS_DIRECTORY` at start) | NONE | NONE | NONE | root can read (Level 3) |
| K-WIT private | NONE | SIGN (runtime credential) | NONE | NONE | as above |
| K-ROOT private | NONE (not on host) | NONE | NONE | NONE | owner workstation only |
| Public registry, trust anchors | READ, VERIFY | READ, VERIFY | READ | READ | WRITE |
| `RecoveryWitnessV1` (current + chain) | READ, VERIFY, REQUEST ledger-advance over socket | READ, WRITE, SIGN | NONE | NONE | READ; epoch/floor advance only through the witness owner socket |
| Authority ledger (`authority_ledger.db`) | READ, WRITE | NONE | NONE | NONE | READ (forensics, service stopped) |
| Legacy `owner_control.db` / `synthetic_evidence.db` | NONE (`InaccessiblePaths`) | NONE | NONE | NONE | unchanged |
| Signer / witness config | READ | READ (own) | NONE | NONE | WRITE |
| Privacy key / DB | NONE | NONE | (unchanged, D2/D4 debt) | NONE | — |

**Witness signing lives outside the authority signer.** If the signer held
K-WIT, code running as the signer uid could do two things:

1. rewrite its own ledger to reopen a consumed challenge;
2. re-sign a witness that matches the rewritten ledger.

That defeats ledger-rollback detection exactly where it matters. B1b-3c §17
option B already requires the witness key to be outside the broker identity.
Holding K-WIT in a separate identity means a compromised signer can cause
**availability** loss only: it can push garbage ledger heads, and readiness
then fails closed. It cannot:

- rewind the witness;
- advance the epoch;
- lower the registry floor.

The witness service is an **unprivileged dedicated identity**, not root. Root
is needed only to invoke owner ceremony operations over the root-only socket.

## 10. Witness design

**PROPOSED.** The payload is the B1b-3c `RecoveryWitnessV1`, unchanged. It
is signed with `LILITH_RECOVERY_WITNESS_V1\0` under K-WIT through the
DEV_SYNTHETIC writer profile.

| Item | Design |
| --- | --- |
| Current witness | `/var/lib/lilith-recovery-witness/witness.json`, `lilith-recovery-witness:lilith-authority-dev 0640` |
| Witness chain | `/var/lib/lilith-recovery-witness/chain/<witnessVersion>.json`, 0640, append-only (never deleted, never overwritten; `O_EXCL`) |
| State dir | `StateDirectory=lilith-recovery-witness`, mode `0750`, group `lilith-authority-dev` (so the signer can read and verify it) |
| Witness public anchor | `/etc/lilith-authority-dev/trust/witness-anchor.json`, `root:root 0644` (`TrustedWitnessAnchorV1`) |
| Registry-root anchor | `/etc/lilith-authority-dev/trust/registry-root.json`, `root:root 0644` (`TrustedRegistryRootV1`) |
| Signer socket | `/run/lilith-recovery-witness/signer.sock`, `lilith-recovery-witness:lilith-authority-dev 0660`, dir `root:lilith-authority-dev 0710`. Operations: `READ_WITNESS`, `RECORD_LEDGER_ADVANCE`. The service requires `SO_PEERCRED uid == uid(lilith-authority-dev)` |
| Owner socket | `/run/lilith-recovery-witness/owner.sock`, `root:root 0600`. Operations: `READ_WITNESS`, `BOOTSTRAP`, `RAISE_REGISTRY_FLOOR`, `ADVANCE_EPOCH`. The service requires `SO_PEERCRED uid == 0` |
| Framing | the broker's V1 framing: 4-byte big-endian length, RFC 8785 JSON, ≤ 16 KiB, closed operation set |

### Signer-path operation

`RECORD_LEDGER_ADVANCE {previousWitnessDigest, ledgerSequence, ledgerHead}`:

- **Accepted** only if all of these hold:
  - `previousWitnessDigest` equals the current witness digest;
  - the epoch is unchanged;
  - `ledgerSequence` is strictly greater than the current value.
- **The payload cannot change** `currentRecoveryEpoch`,
  `minimumRegistryVersion`, or `policyVersion`.
- On success, `witnessVersion` goes up by 1 and `updatedAt` advances
  monotonically.

### Owner-path operations

- `BOOTSTRAP` is allowed only when `witness.json` and `chain/` are both
  absent. It writes version 1 with:
  - `previousWitnessDigest = null`;
  - epoch E0 from a registry verified under the pinned root;
  - a floor equal to that registry's version;
  - `ledgerSequence = 0` and the genesis head.
- `RAISE_REGISTRY_FLOOR {registry}`:
  - the registry must verify under K-ROOT;
  - its version must be above the current floor;
  - its epoch must equal the current epoch.
- `ADVANCE_EPOCH {registry, restoredLedgerSequence, restoredLedgerHead, reason}`
  follows the B1b-3c succession rules:
  - counter + 1;
  - a random value never seen before (the witness keeps the epoch history in
    its chain);
  - the registry verifies under K-ROOT at the new epoch;
  - `registryVersion` is above the floor;
  - at least one current OWNER_ACTOR key exists at the new epoch;
  - the reason is in the closed `SUCCESSION_REASONS`.

### Atomic update and locking

The service runs one instance (`Accept=no`) and serialises requests. It also
holds `flock` on `…/witness.lock` for defence in depth.

Each update runs these steps in order:

1. verify succession;
2. sign;
3. write `chain/<v>.json` with `O_EXCL`, then `fsync`;
4. write `.witness.json.tmp`, then `fsync`;
5. `rename` it to `witness.json`;
6. `fsync` the directory.

Only after the directory fsync does the service reply with the signed
witness.

### Signer ordering and durability

For every authority-creating transition, the signer does the following:

1. evaluate readiness (B1b-3c rule 1), bound to the exact sequence and head;
2. commit the ledger transaction (`synchronous=FULL`, WAL);
3. call `RECORD_LEDGER_ADVANCE` and verify the returned witness;
4. only then return the result.

A crash or a witness outage between steps 2 and 3 leaves
`LEDGER_AHEAD_OF_WITNESS`. That is fail-closed, and it is resolved only by an
epoch advance, exactly as B1b-3c defines. This is the availability cost of
per-transition witnessing (B1b-3c open decision 5). It is accepted for
DEV_SYNTHETIC and revisited in B1b-3e.

### Invariants kept

- `witness != authority`: K-WIT signs no evidence, registry, or challenge.
  The verifier rejects any authority artifact signed by it
  (`WITNESS_KEY_IS_AUTHORITY_KEY`).
- Same-host witness: it detects **ledger-only** rollback, and only while the
  witness survives. Whole-host rollback is **not** detected.

## 11. Who may advance the epoch

**PROPOSED for DEV_SYNTHETIC only.** Production semantics are not decided here.

| Role | Holder | Mechanism |
| --- | --- | --- |
| REQUEST | the owner. The signer may only **report** `NOT_READY(reason)` | The application has no path. The signer has no epoch-advance operation and no witness owner-socket access |
| AUTHORIZE | the owner, **offline**, by signing registry v(N+1) at epoch (counter+1, fresh random) with K-ROOT | the K-ROOT signature is the authorization. It is never present on the host |
| EXECUTE | the witness service, on the root-only owner socket | the `ADVANCE_EPOCH` succession checks |
| VERIFY | an independent root-run read-only verifier CLI (`lilith-authority-verify-dev`), using the pure B1b-3a/3c verifiers against the ledger (opened read-only), the witness, the registry, and the anchors | it must print `RESTORE_READY` before issuance resumes |

**Is owner-root invocation alone sufficient?** No.

Host root alone must not be able to advance the epoch, because the
authorization must come from outside the host. The K-ROOT-signed registry
already is that owner signature, following the B1b-3c ceremony. No
**additional** ceremony signature is required for DEV_SYNTHETIC.

The consequence is two independent factors:

- host root (execution);
- the offline registry root (authorization).

Honest limit: host root can still forge `witness.json` directly, using K-WIT
from the runtime credential. Level 3 is out of scope.

## 12. Schema states and ledger persistence

**Decision: yes.** B1b-3d must make these states durable:

- `VOIDED_BY_RECOVERY`;
- `QUARANTINED_BY_RECOVERY`;
- `FAILED`;
- `ABANDONED`.

It must also make durable the per-transition journal (`ledgerSequence`,
`ledgerHead`). The live stale-ledger and restart tests depend on it.
Faking durability is not acceptable.

**Smallest migration: no migration.**

The accepted `owner_control.db` is not altered. Its rows and schema
fingerprints are pinned Stage II evidence. Instead, the new signer owns a new
additive database:

`/var/lib/lilith-authority-dev/authority_ledger.db` (`lilith-authority-dev 0600`).

It has WAL, `synchronous=FULL`, foreign keys, and exact schema-fingerprint
checks, following the broker's pattern. Tables:

| Table | Content |
| --- | --- |
| `authority_meta_v1` | schema version, fingerprint, `environment='dev'`, `profile='DEV_SYNTHETIC'`, created-at |
| `authority_journal_v1` | append-only; `seq` strictly +1; entry type (closed enum); JCS payload; `head = sha256(sep ‖ prevHead ‖ seq ‖ payload)`; ledger epoch |
| `authority_epoch_v1` | adopted epochs with digests and adoption sequence |
| `authority_challenge_v2` | `state CHECK IN (PREPARED, CONSUMED, CANCELLED, EXPIRED, FAILED, VOIDED_BY_RECOVERY)`, `ledgerEpoch`, evidence-issued flag |
| `authority_evidence_v2` | `evidenceId` PK, `challengeId` UNIQUE, issuing epoch digest, keyId, signed bytes |
| `authority_evidence_use_v1` | `state CHECK IN (RESERVED, CONSUMED, ABANDONED, QUARANTINED_BY_RECOVERY)`; `reconciliationOutcome CHECK IN (NULL, ABANDON, REQUIRE_OWNER_REAUTHORIZATION)` |

Triggers forbid backward transitions and any edit of a terminal row. As in
B1b-3c, the journal is authoritative over materialised rows.

Provisioning:

- There is no auto-initialisation. A missing ledger is `AUTHORITY_STATE_MISSING`.
- One explicit owner provisioning step creates the ledger at E0.

The static legacy `broker_schema_v1.authority_epoch` is **retired**. It is
declared non-authoritative history and is not redefined, because redefining
it would change pinned rows. This resolves B1b-3c open decision 2.

## 13. Recovery ceremony (designed; live rehearsal belongs to B1b-3e)

**PROPOSED.** Source-implemented and TEST-proven in the source slice. It is
**not** executed live in B1b-3d.

A live epoch advance forces key rotation, because a key belongs to one epoch.
That makes it a rotation and restore rehearsal, which is B1b-3e scope.

| # | Step | Actor | Mutation | Evidence | Rollback | Failure state |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Invoke `lilith-authority-recovery-dev begin --reason <closed>` | owner (root) | write the root-owned hold `/etc/lilith-authority-dev/hold` (0644). The signer refuses every creating operation while it exists | hold file hash; journal line | remove the hold, only if nothing after step 2 ran | hold present: issuance blocked (safe) |
| 2 | Stop old issuance | owner | stop the signer socket and service | `systemctl` inactive; no signer-uid process | start again (the hold still blocks creation) | stopped (safe) |
| 3 | Inspect the ledger | verifier CLI (root, read-only; the DB is copied and opened `mode=ro`) | none | ledger summary: seq, head, epoch, nonterminal counts, integrity | — | `LEDGER_INTEGRITY_FAILED` → STOP; preserve; owner decides whether to re-provision (the old file is kept as evidence) |
| 4 | Verify the current witness | verifier CLI + witness `READ_WITNESS` | none | witness digest and version, anchor match | — | `WITNESS_INVALID`/`MISSING` → STOP (no auto-bootstrap over an existing chain) |
| 5a | Generate the new K-ACT at E(n+1) | owner (root), fixed keygen CLI | new encrypted blob `…owner-actor.next.cred` (not yet referenced by the unit) | public key and fingerprint only | delete the `.next` blob | no blob: stop |
| 5b | Build and sign registry v(N+1) at (counter+1, fresh random): new K-ACT current, every E(n) key retired at the recovery instant | owner, **offline**, K-ROOT | none on host | signed registry and digest | discard | not signed: stop |
| 6 | Install registry v(N+1) (atomic rename; old versions retained) | owner | registry pointer | registry hash | revert the pointer (the witness floor is still N) | — |
| 7 | `ADVANCE_EPOCH` | witness service over the owner socket | witness v+1: new epoch, floor N+1, the restored ledger seq/head. **Point of no return** | new witness, chain entry | **none** (forward only; fix forward with another epoch) | refusal reason from B1b-3c; the state is unchanged |
| 8 | Swap the key: `.next.cred` → `owner-actor.cred` (atomic); remove the old private blob | owner | credential blob | blob hash; old blob gone | — | unit fails to start → issuance absent (safe) |
| 9 | Start the signer (hold still present). It adopts E(n+1): PREPARED → `VOIDED_BY_RECOVERY`, RESERVED → `QUARANTINED_BY_RECOVERY`. It journals the adoption, then calls `RECORD_LEDGER_ADVANCE` | signer (destroy-only; no readiness needed, per B1b-3c rule 1) | ledger + witness | `RecoveryEpochTransitionV1` exported | — | crash → `NONTERMINAL_PRE_RECOVERY_WORK` until the adoption completes on restart |
| 10 | Verify, then resume | verifier CLI → `RESTORE_READY`; owner removes the hold | hold removed | readiness JSON (`rollbackDetectionScope: LEDGER_ONLY`, `wholeHostRollbackProtected: false`) | recreate the hold | anything except `RESTORE_READY` → the hold stays |

## 14. Orphan and quarantine reconciliation

**PROPOSED DEV_SYNTHETIC policy.**

- **The authority ledger owns the decision.** Application databases are
  never consulted (B1b-3c). The owner makes the decision explicitly. Nothing
  is automatic.
- **Default is QUARANTINE.** A `QUARANTINED_BY_RECOVERY` use stays
  quarantined until the owner acts.
- **Owner outcomes.** The owner acts through the authority owner socket
  operation `RECONCILE_DECISION {useId, outcome}`. It is destroy-only, so no
  readiness is needed. The allowed outcomes:
  - `ABANDON` → terminal `ABANDONED`, `reconciliationOutcome=ABANDON`;
  - `REQUIRE_OWNER_REAUTHORIZATION` → terminal `ABANDONED`,
    `reconciliationOutcome=REQUIRE_OWNER_REAUTHORIZATION`. Any new admission
    needs a fresh E(n+1) owner challenge.
- **`RECONCILE` is not available in B1b-3d.** It means labelling a row
  historically valid under the old epoch. Per B1b-3c §15 it needs a separate
  owner-approved design, and it can never create new authority.
- **Stored-but-unaccepted L04 rows** stay non-authoritative forever. They
  are never deleted by this policy.
  - **Known hazard for future work:** L04's UNIQUE
    `learning_candidate_v2.action_digest` and UNIQUE
    `memory_revision.created_from_proposal_ref_id` can block re-admission of
    the same action after re-authorization.
- **Honest scope.** No live L04 V2 path exists in B1b-3d. Live orphaned L04
  rows therefore cannot arise here. The only live RESERVED uses come from the
  owner-driven synthetic harness. Crash testing of A6/A7 belongs to the fresh
  A1–A7 rehearsal.

## 15. Installation and deployment separation

**PROPOSED.**

```text
software deployment  !=  authority custody installation  !=  activation
```

### Routine GitHub deployment

`deploy-dev.yml` keeps shipping only the Core API bundle, through the fixed
helper. It gains read-only deny proofs (§7). It never carries:

- key material;
- registries or anchors;
- units, accounts, or helpers of the authority or witness services.

B1b-3d source lives outside `services/core-api/**` (so it does not trigger
the PROD path filter). It also lives outside `services/memory-broker/` (so
the broker file set is unchanged). Proposed locations:

- `services/authority-dev/`;
- `scripts/authority_dev/`.

A merge is `DEPLOY_REQUIRED` for the routine Core API only. Nothing from it
ships in the bundle.

### Custody package (owner-installed)

The owner installs it through break-glass IAP from a reviewed commit, with
per-file hash pins, in the same way as the B1c boundary installer. It
consists of:

- release trees under `/opt/lilith-authority-dev/releases/<sha>`
  (`root:root 0755`, offline pinned wheels, immutable after rename);
- a `current` symlink;
- units and tmpfiles;
- the fixed CLIs in `/usr/local/sbin/lilith-authority-{keygen,recovery,verify}-dev`
  (`root:root 0755`).

Routine application releases cannot replace any of it.

No secret material ever appears in GitHub Actions, the repository, artifacts,
or logs:

- K-ACT and K-WIT are generated on-host into an encrypted blob;
- K-ROOT stays on the owner workstation;
- only public keys and fingerprints are recorded.

### Proposed paths

| Path | Owner / mode |
| --- | --- |
| `/etc/credstore.encrypted/` | `root:root 0700` |
| `…/lilith-authority-dev.owner-actor.cred` | `root:root 0600` (name `owner-actor-signing-key`) |
| `…/lilith-recovery-witness.witness.cred` | `root:root 0600` (name `recovery-witness-signing-key`) |
| `/etc/lilith-authority-dev/` | `root:root 0755` |
| `…/INSTALLED` | `root:root 0644` (marker for the §7 existence rule) |
| `…/trust/{registry-root,witness-anchor}.json` | `root:root 0644` |
| `…/registry/authority-registry.v<N>.json` + `current` | `root:root 0644`; all versions retained |
| `…/signer.json` | `root:lilith-authority-dev 0640` |
| `…/witness.json` (witness service config) | `root:lilith-recovery-witness 0640` |
| `…/hold` | `root:root 0644`, present only during a ceremony |
| `/var/lib/lilith-authority-dev/` | `lilith-authority-dev 0700` |
| `/var/lib/lilith-recovery-witness/` | `lilith-recovery-witness:lilith-authority-dev 0750` |
| `/run/lilith-authority-dev/owner.sock` | `root:root 0600`, dir `root:root 0700` |
| `/run/lilith-recovery-witness/{signer,owner}.sock` | see §10 |
| `/usr/local/sbin/lilith-authority-*-dev` | `root:root 0755` |

### Signer unit sketch

This is proposed and not yet written. The hardening follows the existing
broker unit.

```ini
[Service]
User=lilith-authority-dev
Group=lilith-authority-dev
LoadCredentialEncrypted=owner-actor-signing-key:/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred
StateDirectory=lilith-authority-dev
StateDirectoryMode=0700
ReadOnlyPaths=/opt/lilith-authority-dev /etc/lilith-authority-dev /var/lib/lilith-recovery-witness
InaccessiblePaths=/etc/credstore.encrypted /etc/lilith-memory-broker /var/lib/lilith-memory-broker /etc/lilith-os-dev
ProtectSystem=strict
ProtectHome=yes
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
CapabilityBoundingSet=
RestrictAddressFamilies=AF_UNIX
IPAddressDeny=any
UMask=0077
Restart=on-failure
```

The witness unit is symmetric. It has:

- `User=lilith-recovery-witness`;
- `LoadCredentialEncrypted=recovery-witness-signing-key:…`;
- its own `StateDirectory`;
- no access to the authority ledger.

## 16. Synthetic key generation ceremony

**PROPOSED.** Nothing is generated by this record.

### K-ACT and K-WIT (on-host)

These keys are generated on the host, inside the owner's root session, by the
reviewed fixed CLI `lilith-authority-keygen-dev <actor|witness>`. The CLI has
a pinned SHA-256.

1. It generates Ed25519 in memory, using host python `cryptography`, which
   is present.
2. It pipes the PKCS#8 bytes on stdin to
   `systemd-creds encrypt --with-key=host --name=<fixed name> - <blob>`.
3. It writes the blob with `O_EXCL`, `root:root 0600`.
4. It prints only JSON of `{keyId, publicKey (base64url), sha256(publicKey), blobSha256}`.

The private bytes never touch persistent plaintext storage, a terminal, a
log, or the network. They never leave the host.

The first encrypt creates `/var/lib/systemd/credential.secret`
(`root:root 0400`). That is a separate, visible mutation (Step L2a).

### K-ROOT (owner workstation)

K-ROOT is generated on the owner workstation. It is never copied to DEV,
GitHub, or the repository. Only `TrustedRegistryRootV1` (the public key) is
installed. Registries are built and signed on the workstation from public
inputs.

### Backup policy (DEV_SYNTHETIC)

- **K-ACT and K-WIT: no backup.** Loss or undecryptability means an owner
  recovery ceremony with fresh keys. Re-keying *is* recovery for synthetic
  material.
- **K-ROOT:** the owner's choice of an encrypted workstation backup. Loss
  means re-bootstrapping DEV_SYNTHETIC trust, which is a new trust anchor
  and a new witness chain, and is acceptable for synthetic.

### Records

Record fingerprints and blob hashes in the acceptance record. Never commit
any private key or blob.

## 17. Live negative and positive test plan

This plan is for later execution. The routine deployer is tested three ways:

- its own in-run deny list (§7);
- the owner-mode effective sudo proof;
- as root, `sudo -u sa_… test …` for filesystem probes.

`DENIED` requires the path to exist.

| # | As | Action | Expected |
| --- | --- | --- | --- |
| N1 | `lilith` | read both `.cred` blobs; list `/etc/credstore.encrypted` | DENIED |
| N2 | `lilith` | write `/etc/credstore.encrypted`, `/etc/lilith-authority-dev`, `registry/`, `trust/` | DENIED |
| N3 | `lilith` | read `/run/credentials/lilith-{authority-dev,recovery-witness}.service/*` | DENIED |
| N4 | `lilith` | read or write `/var/lib/lilith-recovery-witness/*` | DENIED |
| N5 | `lilith` | connect to the witness `signer.sock` / `owner.sock` and the authority `owner.sock` | DENIED (directory traversal) |
| N6 | `lilith` | run `lilith-authority-recovery-dev` (non-root) | refused (root check) and no effect |
| N7 | `lilith` | connect to the legacy `/run/lilith-memory/owner.sock` | DENIED (unchanged) |
| N8 | `lilith` | read or write `/var/lib/lilith-authority-dev/*` | DENIED |
| N9 | `lilith` | read `signer.json` | DENIED |
| D1–D9 | routine deployer | the same set as N1–N9 | DENIED |
| D10 | routine deployer | `sudo -n -u lilith-authority-dev true`, `-u lilith-recovery-witness`, `-u lilith-memory-broker` | DENIED |
| D11 | routine deployer | `sudo -n systemctl restart lilith-authority-dev.service` / `lilith-recovery-witness.service` | DENIED |
| D12 | routine deployer | effective sudo | exactly the fixed helper (`SUDO_EFFECTIVE_PROOF=PASS`) |
| B1 | signer uid | read `/etc/credstore.encrypted/*`, `/var/lib/lilith-memory-broker`, `/etc/lilith-memory-broker/identities.json` | DENIED (`InaccessiblePaths`/mode) |
| B2 | signer uid | write `/var/lib/lilith-recovery-witness/witness.json` | DENIED |
| B3 | signer uid | connect to the witness `owner.sock` | DENIED |
| B4 | witness uid | read the authority ledger, the K-ACT blob, or the K-ACT runtime credential | DENIED |
| P1 | owner via the authority owner socket | `HEALTH` → `RESTORE_READY` | ready |
| P2 | owner | synthetic `PREPARE` → `CONSUME` (the `.invalid` synthetic assertion) → `ISSUE` | an `OwnerEvidenceV2` that verifies against registry v1 with the B1b-3a verifier, offline on the owner workstation; the witness advanced to the new seq/head |
| P3 | owner | issue a second time for the same challenge | refused (single issuance) |
| P4 | owner | a signing request with a caller-chosen digest or domain | refused (closed protocol) |

### Recovery tests

Each test preserves the current ledger first:

- stop the signer;
- checkpoint the WAL;
- copy the database to a root-only evidence directory;
- hash it.

Every test ends by restoring the preserved current ledger.

| # | Scenario | Expected |
| --- | --- | --- |
| R1 | stale ledger (a snapshot taken before P2's consume) + current witness | `NOT_READY(LEDGER_BEHIND_WITNESS)`; issuance refused |
| R2 | old registry: publish v2 and `RAISE_REGISTRY_FLOOR` to 2, then point `current` back at v1 | `NOT_READY(REGISTRY_DOWNGRADE)` |
| R3 | a consumed challenge reopened by a row edit in a copy (CONSUMED → PREPARED, journal unchanged) | `NOT_READY(TERMINAL_STATE_REOPENED)` |
| R4 | the current ledger restored + a valid witness | `RESTORE_READY` |
| R5 | a signer loaded with the wrong key: registry v2 names a different K-ACT fingerprint at the same epoch | `NOT_READY(REQUIRED_KEY_UNAVAILABLE)` |

There is **no** whole-host rollback test and no whole-host claim.

### Secret hygiene checks

- scan `journalctl` for both units, the ceremony transcripts, and the
  workflow logs for PEM, PKCS#8, and base64 private-key patterns: **zero
  hits**;
- run `git grep` for private-key patterns: zero hits.

## 18. Restart and reboot behaviour

| Event | Behaviour (fail closed) |
| --- | --- |
| Signer restart | The credential is re-delivered. Startup then runs these checks in order: custody preflight (modes and owners of config, registry, anchors, witness); key fingerprint vs registry; witness verified under the anchor; B1b-3c readiness. Any failure → it serves `HEALTH` with `NOT_READY(reason)` and refuses every creating operation |
| Socket restart | Sockets are `RemoveOnStop`, and the directories are recreated by tmpfiles. No state is lost |
| Witness restart | Re-verifies its own chain head vs `witness.json` before answering. A mismatch → refuses all writes |
| Failed key load (blob missing, undecryptable, or `credential.secret` missing) | systemd fails the unit before exec. No socket service, no issuance |
| Missing witness | `WITNESS_MISSING`. Never auto-bootstrapped while a chain or ledger exists |
| Malformed or badly signed witness | `WITNESS_INVALID` |
| Wrong permissions | `CUSTODY_PREFLIGHT_FAILED` (a new, closed startup reason set, evaluated before the B1b-3c taxonomy) |
| Wrong key fingerprint | `REQUIRED_KEY_UNAVAILABLE` |
| Registry downgrade | `REGISTRY_DOWNGRADE` |
| Witness unavailable during an operation | the operation does not return a result. At the next readiness check: `LEDGER_AHEAD_OF_WITNESS` → recovery ceremony |
| VM reboot | Custody persists on disk (blobs, host key, ledger, witness chain). Services start only if enabled |

### Historical socket and reboot concern: still relevant

The legacy broker socket is `disabled` and the service is `static`. A VM
reboot therefore brings the accepted legacy broker back **down**, and it
changes the incarnation again.

For B1b-3d:

- the new sockets are also installed **not enabled** at first;
- a reboot test therefore proves that issuance is absent after boot, which
  is fail closed;
- after a manual start, `RESTORE_READY` with the same ledger and witness.

Two things are left to the owner:

- whether to enable the new sockets at boot (T-5);
- whether a VM reboot test belongs in B1b-3d at all (T-6), since it also
  takes down the legacy broker.

This design does not change the legacy units.

## 19. Privacy

- Privacy custody does not move. B1b-3f stays separate. D2 and D4 remain
  open.
- OWNER_ACTOR custody (`lilith-authority-dev`, K-ACT) is a different thing
  from Privacy authority custody. B1b-3d creates no Privacy key, domain
  identity, or socket.
- K-ACT's registry record admits only `OWNER_MEMORY_OPERATION`. The signer
  refuses FORGET (`PRIVACY_OWNED_OPERATION`, B1b-3b). No Actor key can sign
  `PRIVACY_ERASURE_AUTHORIZATION`, because B1b-3a rejects cross-domain use.
- The layout leaves room for later separation. B1b-3f can add
  `lilith-privacy-authority-dev` with its own credential, blob, state
  directory, and socket, without touching the authority signer.
- The witness readiness input `PrivacyBoundaryObservationV1` stays
  `TEST_SYNTHETIC`/`NOT_MODELLED` on DEV. Readiness must accept a declared
  `NOT_MODELLED` only under the DEV_SYNTHETIC profile. That relaxation is
  recorded, not silent, and is flagged as B1b-3f debt.

## 20. PROD authority debt dependency

`CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT` remains **OPEN**. It is not closed by
this slice, and B1d is not closed automatically.

**Rule:**

- **DEV_SYNTHETIC custody proof may proceed** while the debt is open, for
  three reasons:
  - the keys carry no real authority;
  - B1b-3d explicitly excludes root from its claim;
  - no PROD run or PROD login change is needed.
- **Real owner authority, a real registry root, and real First Memory stay
  blocked** until the debt is resolved (and B1d, or its successor, is
  defined).

The B1b-3d acceptance must list every root-capable identity on DEV that can
defeat custody:

- the owner (OS Login admin, break-glass);
- the legacy PROD deployer, via project-level `osAdminLogin` (federation
  limited to `deploy.yml` on main);
- the local `ubuntu` account in `sudo` (no authorized keys today, DR-3).

## 21. Stage III dependency

- Stage III is not retried or armed.
- B1b-3d does not touch Stage III artifacts:
  - the failed `lilith-stage3-a2-final.service`;
  - `/opt/lilith-stage3-a2-final-v1`;
  - the preserved `b1b2b-stage3-a2-authorization.json`;
  - candidate release `4a04f2d…`;
  - the accepted selector `817a83e…`.
- Every live step re-hashes these artifacts and STOPs on any change.
- The B1b-3b/3c S1–S6 and A1–A7 models are only input to a **fresh** crash
  rehearsal. The order is B1b-3d (custody), then B1b-3e (rotation, epoch
  advance, restore rehearsals), then owner acceptance, and only then the
  fresh A1–A7 design.
- DR-1 (the lost accepted incarnation) must be resolved by an owner-approved
  new incarnation baseline before any future Stage III work. B1b-3d does not
  do it.

## 22. Acceptance criteria

B1b-3d is **ACCEPTED as `DEV_SYNTHETIC CUSTODY PROVEN`** only if every item
below holds.

**Custody**

1. K-ACT and K-WIT exist on `lilith-dev-01` only as `root:root 0600`
   host-key-encrypted credential blobs, with the recorded fingerprints.
2. K-ROOT is absent from DEV, GitHub, and the repository.
3. `lilith-authority-dev` signs with K-ACT (P2). The signed evidence verifies
   offline against the owner-signed registry.
4. `lilith-recovery-witness` signs witnesses with K-WIT, and only witnesses.

**Denials**

5. `lilith` is DENIED for all of N1–N9, with every probed path existing.
6. The routine deployer is DENIED for all of D1–D11.
7. The routine deployer's effective sudo is exactly the fixed helper (D12).
8. The routine deployer's in-run deny list passes on a real routine
   deployment after installation.
9. No application socket or path can obtain a signature. The application
   cannot mint `OwnerEvidenceV2`.
10. B1–B4 hold.

**Witness and recovery**

11. The witness exists, verifies under the anchor, and has an intact chain
    from v1.
12. `lilith` and the deployer cannot modify the witness.
13. R1 (stale ledger) → `NOT_READY`.
14. R2 (registry downgrade) → `NOT_READY`.
15. R3 (reopened consumed challenge) → `NOT_READY`.
16. R4 (current ledger) → `RESTORE_READY`.

**Restart and hygiene**

17. A service restart and a socket restart each preserve custody and
    readiness.
18. A failed-key-load simulation fails closed. If T-6 is approved, a VM
    reboot yields no issuance until a manual start, then `RESTORE_READY`.
19. No authority material appears in journals, workflow logs, artifacts, or
    the repository (§17 scans).

**Preservation**

20. The B1c boundary is unchanged: helper, library, verifier, sudoers,
    activation `NOT_ACCEPTED reason=GRANT_ABSENT`.
21. The legacy broker is unchanged: release, selector, units, config, state
    hashes, with DR-1 recorded.
22. Stage III artifacts are unchanged. PROD is untouched. IAM/WIF is
    unchanged.

**Status recorded after acceptance:** `DEV_SYNTHETIC CUSTODY PROVEN`. It is
explicitly **not** `REAL AUTHORITY READY`.

## 23. Implementation ladder

The ladder has two phases:

- **Phase S** is a source PR, TEST-proven, with no DEV contact.
- **Phase L** is live. It is owner break-glass, **one mutation per step**,
  and each step is separately owner-authorized.

Every live step starts by re-hashing the **preservation set**:

- the B1c helper, library, verifier, and sudoers;
- activation;
- the legacy broker release, selector, units, `dev.json`, and state file
  metadata;
- the Stage III artifacts;
- the API unit.

If any of those changed: **STOP**.

| Step | Mutation | Expected state | Verification | Rollback | STOP if |
| --- | --- | --- | --- | --- | --- |
| **S** | Source PR: `services/authority-dev/` (signer runtime, durable ledger, witness service, DEV_SYNTHETIC profile contracts + vectors), `scripts/authority_dev/` (installer, keygen, recovery, verify, inventory CLIs), units/tmpfiles, `deploy-dev.yml` deny-list extension with the existence rule, tests (incl. §17 as Linux tests with fake users) | merged; routine deploy green; nothing installed | CI; hash manifest of the release | revert the PR | any change to `services/core-api/**`, `services/memory-broker/**`, sudoers template, helper, or verifier |
| **L0** | none (read-only preflight) | the §2 inventory is reproduced; DR-1 acknowledged in writing by the owner | inventory diff = expected | — | new unexplained drift; a live Stage III arm or guard; a changed deployer rule |
| **L1a** | create the system accounts `lilith-authority-dev` and `lilith-recovery-witness` (nologin, no home) | accounts exist, in no extra groups | `id`, `getent`, `sudo -l -U` = not allowed | `userdel` both | either name already exists |
| **L1b** | install the release tree `/opt/lilith-authority-dev/releases/<sha>` + `current` | immutable root 0755 tree | manifest hashes | remove the tree | hash mismatch |
| **L1c** | install the CLIs in `/usr/local/sbin`, the units, the tmpfiles, and `daemon-reload`; nothing started or enabled | units loaded and inactive; `INSTALLED` marker **not** yet written | `systemctl show`, hashes | remove the files + `daemon-reload` | any unit active |
| **L2a** | create the host credential key (first `systemd-creds setup`) | `/var/lib/systemd/credential.secret` `root 0400` | stat | remove the file (no blobs exist yet) | any other credential already present |
| **L2b** | keygen K-ACT → blob | blob `root 0600`; public JSON recorded | stat, blob hash; no private output | delete the blob | any private-key pattern in output or journal |
| **L2c** | keygen K-WIT → blob | as L2b | as L2b | delete the blob | as L2b |
| **L3a** | install the trust anchors + registry v1 (signed offline, epoch E0, K-ACT current) + configs | public files root 0644, configs 0640 | offline + on-host registry verify | remove the files | the registry fails to verify, or the root key ID is not `test-only.` |
| **L3b** | start the witness sockets (not enabled) + `BOOTSTRAP` | witness v1, floor 1, seq 0 | verifier CLI; chain v1 | stop; remove the state dir (nothing depends on it yet) | bootstrap is refused or the witness fails to verify |
| **L3c** | provision the authority ledger at E0 (fixed provisioning as the signer uid) | `authority_ledger.db` genesis, head = witness head | read-only inspect | stop; remove the DB | a schema-fingerprint mismatch |
| **L4** | start the signer socket (not enabled); write the `INSTALLED` marker | P1 `RESTORE_READY` | HEALTH; B1–B4 | stop the socket; remove the marker | anything except `RESTORE_READY` |
| **L5** | none (denial proofs as `lilith` and the deployer), then the **next routine deployment** with the extended deny list | N1–N9, D1–D12 DENIED/PASS | transcripts, run URL | — | any `ALLOWED(unexpected)` or a vacuous (missing-path) denial |
| **L6** | positive synthetic signing P2–P4 (ledger + witness advance) | one evidence issued; witness seq advanced | offline verify; witness chain | none (synthetic history is kept) | the evidence fails to verify; a second issuance succeeds |
| **L7** | R1–R5, each: preserve → substitute → start → observe → restore the preserved current ledger/registry | R1–R3, R5 `NOT_READY`; R4 `RESTORE_READY` | readiness JSON per case | restore the preserved copies (hash-verified) | any `RESTORE_READY` on a stale or tampered state; the preserved copy does not restore to READY |
| **L8** | service restart, socket restart, failed-key-load simulation (a temporary drop-in pointing at a missing blob, then removed); optional VM reboot (T-6) | fail closed where expected; READY after a normal start | readiness, `systemctl` results | remove the drop-in; manual start | custody changed by a restart; issuance without READY |
| **L9** | none (owner gates) | cloud gate unchanged (no IAM/WIF delta); DEV gate: B1c proof, activation `NOT_ACCEPTED`, preservation set equal, secret scans clean | gate transcripts + hashes | — | any gate fails |
| **L10** | documentation only: the acceptance record | status `DEV_SYNTHETIC CUSTODY PROVEN` | review | — | any criterion in §22 unmet |

## 24. Unresolved owner decisions

| # | Decision | Recommendation |
| --- | --- | --- |
| T-1 | Separate `lilith-authority-dev` identity vs. signing inside `lilith-memory-broker` | separate (§6) |
| T-2 | `LoadCredentialEncrypted` (host key) vs. plain `LoadCredential` | encrypted host key; TPM2 deferred |
| T-3 | Acknowledge DR-1 (the lost accepted Stage II incarnation, including the unexplained 2026-09-26 06:34 UTC restart) and decide whether a new incarnation baseline is recorded before L0 | acknowledge before L0; defer the baseline to the Stage III track |
| T-4 | Witness write frequency: per transition (B1b-3c) vs. checkpoints; accept the `LEDGER_AHEAD_OF_WITNESS` → epoch-advance availability cost | per transition for DEV_SYNTHETIC |
| T-5 | Enable the new sockets at boot | not enabled in B1b-3d |
| T-6 | Include a VM reboot test in B1b-3d (it also drops the legacy broker) | defer to B1b-3e unless the owner wants it now |
| T-7 | Live epoch-advance rehearsal in B1b-3d vs. B1b-3e | B1b-3e |
| T-8 | Is the offline K-ROOT registry signature (no extra ceremony signature) sufficient epoch-advance authorization for DEV_SYNTHETIC | yes |
| T-9 | Remove the residual `ubuntu` sudo membership (a DEV change outside B1b-3d) | record now; decide separately |
| T-10 | K-ROOT backup on the owner workstation | the owner's choice; loss means re-bootstrap |
| T-11 | Declared `NOT_MODELLED` Privacy boundary accepted by DEV_SYNTHETIC readiness | accept, recorded as B1b-3f debt |
| T-12 | Retire `broker_schema_v1.authority_epoch` (B1b-3c decision 2) | retire as non-authoritative history |

Carried forward, and not decided here:

- the production registry root;
- the off-host monotonic anchor;
- trusted time and re-attestation;
- the ordering of B1d and the PROD debt;
- the RP, origin, and authenticator ceremony.

## Explicitly not done

- No key, blob, registry, anchor, witness, ledger, account, unit, or helper
  created or installed.
- No DEV mutation. The only DEV contact was the read-only inventory.
- No PROD contact. No IAM, WIF, or systemd change.
- No Stage III retry or arm. The preserved authorization is untouched.
- No real owner authority, real registry root, credential, or memory.
- No claim of whole-host rollback protection, Level 3, or Privacy custody.
