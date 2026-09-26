# Slice 15B2b-B1b-3d L1 — DEV_SYNTHETIC Authority-Signer Source Foundation

Status:

- **B1b-3d L1 SOURCE FOUNDATION IMPLEMENTED**
- **NOT INSTALLED**
- **NOT STARTED**
- **NO CREDENTIAL**
- **NO AUTHORITY**

Base: protected main `da35c6258f475427caafdcd6a2a8a6845f31e287`.

This record implements part of Phase **S** (the source PR) of the
[B1b-3d design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md) §23 for one
component: the distinct `lilith-authority-dev` OWNER_ACTOR signer. It is not
an acceptance record. It does not mark B1b-3d, `DEV_SYNTHETIC CUSTODY PROVEN`,
authority readiness, real owner authority, or First Memory as reached.

**Naming.** This task calls itself "L1". In the design ladder (§23), `L1a`–`L1c`
are *live* steps (accounts, release tree, units on DEV). Nothing live is done
here. "L1" in this record means the first source-foundation increment only.

```text
source-controlled artifact != installed service
installed service          != credential custody
credential custody         != accepted authority
signing output             != accepted memory
accepted authority         != truth
```

## 1. What L1 establishes, and what it does not

| Established in the repository | Not established |
| --- | --- |
| The authority-signer software exists as its own package, outside the application, the broker, and the TEST signer | credential custody; a usable signing key |
| Its OS/service boundary is explicit in source: user, group, credential slot, socket owner and mode, sandbox paths | live signing authority; OS caller-denial proof |
| Its install material (unit, socket, tmpfiles) is reviewable and statically verified | broker integration; any broker-facing channel |
| It fails closed without custody material, and it can never report readiness in L1 | recovery witness; durable authority ledger |
| Its source and runtime file sets are exact and scanned for key material | real owner authority; First Memory |

## 2. Canonical requirements used

All from the B1b-3d design record unless stated.

| Requirement | Source |
| --- | --- |
| Separate `lilith-authority-dev` identity; the legacy `lilith-memory-broker` is untouched | §6 |
| K-ACT keyId proposal `test-only.dev-synthetic.actor.b1b3d.1`; `environment: "dev"`; `test-only.` + `dev-synthetic` label | §4 |
| New separately versioned DEV_SYNTHETIC profile; the TEST signer (`BrokerSignerConfigV1`) is not widened | §4 |
| `LoadCredentialEncrypted=owner-actor-signing-key:/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` | §5, §15 |
| Unit sketch: user/group, `StateDirectory` 0700, `ReadOnlyPaths`, `InaccessiblePaths`, hardening | §15 |
| No application-facing socket; the only entry point is the root-only authority owner socket (here: the host-root ceremony/control socket) | §8 |
| `/run/lilith-authority-dev/owner.sock` `root:root 0600`, directory `root:root 0700` | §15 |
| Broker V1 framing: 4-byte length, RFC 8785 JSON, ≤ 16 KiB, closed operation set | §10 |
| Startup failures serve `NOT_READY(reason)`; a missing credential fails the unit before exec | §18 |
| No auto-initialisation: a missing ledger is `AUTHORITY_STATE_MISSING` | §12 |
| Signer refuses FORGET (`PRIVACY_OWNED_OPERATION`); no Privacy key, identity, or socket | §19, B1b-3b |
| Source outside `services/core-api/**` and `services/memory-broker/` | §15 |
| Sockets not enabled at boot | §18, T-5 recommendation |
| `OwnerEvidenceV2`, `AuthorityKeyRecordV1`, `key.registryVersion` = first publication, `key ≤ evidence ≤ verified registry` | B1b-3a |
| Signer derives every signed value; the application sends only `OwnerEvidenceRequestV1` | B1b-3b |

## 3. Design resolutions and open questions

### Owner decisions recorded (2026-09-26, DEV_SYNTHETIC scope only)

These are recorded in design §24. They are not broadened beyond DEV_SYNTHETIC.

| # | Decision |
| --- | --- |
| T-1 | A distinct `lilith-authority-dev` OS identity. Signing is not placed inside `lilith-memory-broker`. |
| T-2 | `LoadCredentialEncrypted=` with a host-bound encrypted credential is accepted for DEV_SYNTHETIC custody only. **Limitation:** it is not whole-host or snapshot rollback protection (a disk snapshot contains both the blob and `/var/lib/systemd/credential.secret`), and it is not a claim of real-owner-grade custody. |
| T-5 | Neither the signer service nor its socket is boot-enabled. Every activation is an explicit owner-controlled ceremony. The units carry no `[Install]` section. |

### Questions

| # | Question | L1 handling |
| --- | --- | --- |
| Q1 | **Broker → signer channel.** The task topology shows the Memory Broker sending constrained authority requests to the signer. The design (§8) says B1b-3d exposes **no** application-facing socket, and a future request path (for `OwnerEvidenceRequestV1`) "is a separate slice with its own strict protocol review". No socket path, peer uid, group, or protocol is designed for it. | **EXPLICITLY DEFERRED.** No Memory Broker → authority signer runtime channel is added during L1/L2 custody establishment. Rationale: prove signer identity isolation, credential custody, and the live denial properties independently first. A constrained broker runtime channel is a later integration boundary and needs its own request, authorization, replay, and caller-security design. Only the host-root ceremony/control socket exists. |
| Q2 | T-1, T-2, and T-5 were listed as unresolved owner decisions in design §24. | **RESOLVED** for DEV_SYNTHETIC scope (see above). The L1 source already matched these decisions, so no runtime change was needed. |
| Q3 | **`signer.json` contents** (§15 lists the file, `root:lilith-authority-dev 0640`) are not specified. | Not defined and not read in L1. The profile contract (`DevSyntheticSignerProfileV1`) exists; its file encoding is deferred. |
| Q4 | **Peer check on the authority owner socket.** The design states `SO_PEERCRED uid == 0` explicitly for the witness owner socket; for the authority owner socket it says "root-only" and `root:root 0600`. | L1 enforces `SO_PEERCRED uid == 0` as well, in addition to the socket mode. This is narrower than, and consistent with, "root-only". |
| Q5 | **Operation names** for the owner socket (PREPARE / CONSUME / ISSUE / RECONCILE_DECISION in the design text) are not fixed strings. | L1 defines only `HEALTH` and `ISSUE_OWNER_EVIDENCE`. The ledger operations need the durable ledger and are not defined. |
| Q6 | **Release packaging** (offline pinned wheels, venv build, installer CLIs) | Not in L1. Only the exact file-set contract exists. |

## 4. Files

| Path | Role |
| --- | --- |
| `services/authority-dev/lilith_authority_dev/__init__.py` | package statement; no side effects |
| `services/authority-dev/lilith_authority_dev/profile.py` | DEV_SYNTHETIC profile, fixed identity and paths |
| `services/authority-dev/lilith_authority_dev/credential.py` | fail-closed credential inspection |
| `services/authority-dev/lilith_authority_dev/evidence_minter.py` | structured-only `OwnerEvidenceV2` minter (not wired) |
| `services/authority-dev/lilith_authority_dev/protocol.py` | closed owner-socket protocol |
| `services/authority-dev/lilith_authority_dev/core.py` | dispatch and L1 readiness |
| `services/authority-dev/lilith_authority_dev/server.py` | inherited-socket, root-peer-only adapter; entrypoint |
| `services/authority-dev/deploy/lilith-authority-dev.service` | unit |
| `services/authority-dev/deploy/lilith-authority-dev.socket` | host-root ceremony/control socket |
| `services/authority-dev/deploy/lilith-authority-dev.tmpfiles.conf` | `/run/lilith-authority-dev` |
| `services/authority-dev/release_file_set.py` | exact source/runtime file-set contract |
| `services/authority-dev/tests/test_authority_dev_foundation.py` | repository tests |
| `services/authority-dev/README.md` | component README |
| `.github/workflows/ci.yml` | two steps: run the tests; `systemd-analyze verify` the units |

## 5. Responsibility boundary

The signer has one responsibility: produce `OwnerEvidenceV2` for approved,
structured owner operations, with a key the application domain cannot reach.

It is **not**:

- a generic signing oracle (no byte, text, or digest signing operation);
- an identity store or WebAuthn enrollment;
- a policy engine or memory truth oracle;
- a writer of database authority flags;
- an owner-consent substitute (it will sign only after its own verification
  of a consumed owner proof, in a later slice);
- an activation authority;
- a Privacy signer.

## 6. Service identity and paths

| Item | Value |
| --- | --- |
| Unit | `lilith-authority-dev.service`, `lilith-authority-dev.socket` |
| User / Group | `lilith-authority-dev` / `lilith-authority-dev`; no supplementary groups |
| Release | `/opt/lilith-authority-dev/current` (read-only) |
| Config | `/etc/lilith-authority-dev` (read-only) |
| Runtime | `/run/lilith-authority-dev` `root:root 0700` (tmpfiles) |
| State | `/var/lib/lilith-authority-dev` `0700` (`StateDirectory`) |
| Credential | name `owner-actor-signing-key`; source `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`; exposed only in `/run/credentials/lilith-authority-dev.service/` |
| Inaccessible | `/etc/credstore.encrypted`, `/etc/lilith-memory-broker`, `/var/lib/lilith-memory-broker`, `/etc/lilith-os-dev` |

Neither unit has an `[Install]` section, so neither can be enabled at boot
from this material (T-5). The entrypoint refuses to run as root, as any uid
other than `lilith-authority-dev`, as a uid shared with `lilith`,
`lilith-memory-broker`, `lilith-memory-relay`, or `lilith-recovery-witness`,
or with supplementary groups.

## 7. IPC and caller boundary

```text
LILITH / Hermes / model / Core API      no socket, no group, no path (none added)
Memory Broker                           no channel (Q1, EXPLICITLY DEFERRED)
host root  --owner.sock 0600-->         lilith-authority-dev   (SO_PEERCRED uid == 0)
```

`owner.sock` keeps the design's file name, but it is a **host-root
ceremony/control socket**. A peer uid of 0 proves only host-root execution.
It is **not** proof of human-owner authentication, and any root-equivalent
principal can use it. DR-3 stays **OPEN**: the local `ubuntu` account is still
root-equivalent through `sudo` and `lxd`.

- The adapter never binds; it accepts exactly one systemd listener whose
  name is `/run/lilith-authority-dev/owner.sock`.
- It checks the kernel peer uid before reading a byte. Any other peer gets
  no response.
- One canonical frame in, one response out, then close. Pipelined bytes,
  non-canonical JSON, duplicate keys, JSON constants, and unknown fields fail
  closed with no response.

Whether the kernel and systemd actually enforce this on DEV is
**NOT_YET_LIVE_PROVEN** (design §17 N5, D-series, B1–B4).

## 8. No-credential behaviour

| State | Meaning | Behaviour |
| --- | --- | --- |
| `CREDENTIAL_ABSENT` | `$CREDENTIALS_DIRECTORY` unset, or no `owner-actor-signing-key` in it | entrypoint exits `3` before serving; nothing is created |
| `CREDENTIAL_INVALID` | wrong directory, symlink, non-regular, oversized, not DER, encrypted PKCS#8, not Ed25519 | entrypoint exits `4` before serving |
| `CREDENTIAL_PRESENT_UNVERIFIED` | parseable Ed25519 PKCS#8 | public-key SHA-256 kept; no reference to the private-key object is retained; serves `HEALTH` as `NOT_READY` |

Other startup refusals exit `2`. None of these is a signer failure. In a live
unit, systemd fails the start earlier if the encrypted blob is missing
(`LoadCredentialEncrypted=`); that is **NOT_YET_LIVE_PROVEN**.

There is no fallback of any kind: no generated, ephemeral, repository, TEST,
default, environment, or database key.

`HEALTH` always returns:

```text
service   = SERVICE_AVAILABLE
signing   = SIGNING_NOT_AVAILABLE
readiness = NOT_READY
reasons   = [credential state if not present,] REGISTRY_MISSING, WITNESS_MISSING, AUTHORITY_STATE_MISSING
```

`ISSUE_OWNER_EVIDENCE` is structurally validated and then always refused
with `SIGNING_NOT_AVAILABLE`. "Process running" is never "authority ready".

Key-retention properties, stated narrowly:

- no signing-capable private-key object is retained after L1 initialization.
  The credential inspection derives the public fingerprint and releases its
  only reference, and the core stores only the credential status;
- no minter or signing execution path is reachable by the running L1
  service. Nothing in `core.py` or `server.py` constructs or imports the
  minter;
- process-memory zeroization and remanence are **NOT_PROVEN**. Python gives
  no guarantee that credential bytes or key material are erased from process
  memory. This is not an L1 acceptance property.

## 9. Signing contract reused

- Artifact: B1b-3a `OwnerEvidenceV2` only. Bytes:
  `LILITH_ACTOR_EVIDENCE_V2\0 || RFC8785(unsigned fields)`, produced by
  `authority_contracts.owner_evidence_signing_bytes`.
- Field validation: `OwnerEvidenceV2.from_dict`, unchanged.
- Refuse-to-sign guards, against the minter's own `AuthorityKeyRecordV1`:
  keyId, `OWNER_ACTOR`, `{OWNER_MEMORY_OPERATION}`, `dev`, public key,
  current, recovery epoch, policy, `issuedAt ≥ notBefore`,
  `evidenceNonce == challengeId`, and
  `key.registryVersion ≤ evidence.registryVersion`.
- The upper bound `evidence.registryVersion ≤ verified registry.registryVersion`,
  downgrade, compromise, and revocation stay exclusively in the B1b-3a
  verifier. A test shows evidence minted at a version above the registry is
  `NOT_ACCEPTED` by that verifier.
- No contract was changed. No mismatch with a production-shaped boundary
  was found for the minter. The missing pieces (registry-derived version and
  epoch, ledger, witness) are components, not contract changes.

## 10. Arbitrary-signing prevention

- The protocol has two operations. `SIGN`, `SIGN_BYTES`, `SIGN_DIGEST`,
  `EXPORT_KEY`, and similar are `UNSUPPORTED_OPERATION`.
- `ISSUE_OWNER_EVIDENCE` has exactly `challengeId`, `action`, `assertion`,
  `ownerCredential`. Any digest, domain, key, epoch, version, or message field
  is `INVALID_PAYLOAD_FIELDS`.
- The minter's only public methods are `mint` and `key_id`. `mint` refuses
  bytes, text, and non-mappings, and re-derives the signed bytes itself.
- The minter refuses pickling and copying and has no key accessor.

## 11. OWNER_ACTOR vs PRIVACY

- The profile and minter admit only `signingDomain = OWNER_ACTOR` and
  `evidenceType = OWNER_MEMORY_OPERATION`.
- A `PRIVACY` signing domain is `SIGNING_DOMAIN_REFUSED`; a Privacy evidence
  type is `EVIDENCE_TYPE_REFUSED`; a `PrivacyAuthorizationV2` field set is
  `MINT_FIELDS_MISMATCH`; a Privacy key record fails construction.
- A FORGET action is `PRIVACY_OWNED_OPERATION` at the protocol.
- No Privacy identity, credential, socket, or path is defined. B1b-3f is
  separate.

## 12. Packaging and repository validation

- `release_file_set.py` fixes the exact source tree of `services/authority-dev/`
  and the exact runtime payload: the seven runtime modules, the six accepted
  shared contract modules (SHA-256 pinned), and the three deploy assets.
- Tests, the file-set contract, the README, and every TEST fixture are never
  runtime payload. The B1b-3b TEST signer package is never included or
  imported.
- Runtime payloads are scanned for PEM/OpenSSH private-key headers, TEST seed
  markers, key-generation and raw-key-import calls, and TEST fixture imports,
  and for the actual bytes, base64url, and hex of every B1b-3a TEST seed.
- `scripts/validate_repository.py` is unchanged; it covers this record.
- The tree is outside the PROD `deploy.yml` path filter and the broker file
  set. The DEV classifier treats it as an unfamiliar path: fail-closed
  `DEPLOY_REQUIRED` for the routine Core API only. Nothing from it ships in
  the Core API bundle.

## 13. Tests

`services/authority-dev/tests/test_authority_dev_foundation.py` (44 tests).
TEST keys come only from the existing B1b-3a fixture seeds; no key is
generated.

| Task requirement | Tests |
| --- | --- |
| 1 no signing without credential | `CredentialAbsenceTests`, `ReadinessTests` |
| 2, 14 no embedded key in runtime | `PackagingTests.test_runtime_payload_is_exact_and_clean`, `…forbidden_markers…` |
| 3 no arbitrary signing | `ProtocolTests.test_only_health_and_structured_issue_exist`, `MinterTests.test_no_raw_signing_surface` |
| 4 only structured evidence | `MinterTests.test_minted_evidence_verifies_under_the_accepted_b1b3a_verifier` |
| 5 OWNER_ACTOR | `MinterTests.test_signing_domain_is_owner_actor_only` |
| 6 no PRIVACY | `MinterTests.test_privacy_*`, `ProtocolTests.test_privacy_operation_is_refused` |
| 7 malformed fails closed | `ProtocolTests.test_malformed_requests_fail_closed`, `MinterTests.test_malformed_*` |
| 8 unsupported schema/version | `ProtocolTests.test_unsupported_schema_or_protocol_fails_closed`, `MinterTests.test_malformed_*` |
| 9 non-canonical bytes | `ProtocolTests.test_noncanonical_bytes_are_refused`, `MinterTests.test_no_raw_signing_surface` |
| 10 identifiers required | `MinterTests.test_required_identifiers_cannot_be_omitted` |
| 11 approved files only | `PackagingTests.test_source_tree_is_exact`, `…extra_file…` |
| 12 dedicated identity | `UnitMaterialTests.test_dedicated_identity`, `ServerTests.test_identity_checks` |
| 13 credential not an application path | `UnitMaterialTests.test_credential_delivery_and_isolation`, `…application_and_deployer_paths_never_name_custody`, `…runtime_reads_private_material_only…` |

## 14. Security properties

**Proven by repository tests:**

- no signing-capable private-key object is retained after initialization,
  and no minter or signing path is reachable by the running L1 service;
- absence and invalidity of the credential are distinct, fail closed, and
  create nothing;
- the protocol is closed and canonical, and exposes no raw signing;
- the minter signs only B1b-3a `OwnerEvidenceV2` under OWNER_ACTOR/dev, bound
  to its own published key record, and its output verifies under the
  unchanged B1b-3a verifier;
- PRIVACY is refused at every layer;
- the unit, socket, and tmpfiles material names the dedicated identity,
  host-root ceremony/control socket, encrypted credential slot, and
  inaccessible paths;
- no Core API, broker, deployer, or deployment workflow file names the
  custody paths;
- the runtime payload is exact and contains no private or TEST key material;
- the units pass `systemd-analyze verify` (systemd 255, stand-in `ExecStart`).

**NOT_YET_LIVE_PROVEN:**

- that `lilith`, the routine deployer, and the broker uid cannot connect to
  the owner socket or read the credential (N1–N9, D1–D12, B1–B4);
- that systemd delivers the credential only to the unit uid and fails the
  unit when the blob is missing or undecryptable;
- that `InaccessiblePaths` / `ReadOnlyPaths` / `ProtectSystem=strict` behave
  as intended on `lilith-dev-01`;
- that the accounts exist with no extra groups, no shell, and no sudo;
- that the socket is never enabled at boot;
- everything in design §22.

**NOT_PROVEN, and not an L1 acceptance property:**

- process-memory zeroization or remanence of credential bytes and key
  material;
- human-owner authentication on the ceremony socket (uid 0 is host root
  only; DR-3 open).

## 15. Explicitly not done

- No DEV or PROD contact. No SSH, IAP, service action, or `daemon-reload`.
- No account, directory, unit, credential, blob, registry, anchor, witness,
  or ledger created anywhere.
- No Ed25519 key generated; no `systemd-creds` use.
- No needrestart, unattended-upgrades, IAM, WIF, or Stage III change.
- No `deploy-dev.yml` deny-list extension (design §7); DR-5 stays **OPEN**.
- DR-3 stays **OPEN**.
- No Privacy custody.

## 16. Next step

The next architectural step remains **L2: synthetic OWNER_ACTOR credential
custody and live custody preparation**. It covers design §23 L0 through L2b:
read-only preflight, accounts, release tree and units, the host credential
key, and the K-ACT blob. Each is a separately owner-authorized live step.

It is **not** L4 ledger work. The durable `authority_ledger.db` is not built
in this slice and is not the next step. The Memory Broker channel stays
deferred (Q1).
