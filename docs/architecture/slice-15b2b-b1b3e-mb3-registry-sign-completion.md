# Slice 15B2b-B1b-3e — M-B3 / `SIGN_REGISTRY_V1`: Completion and Owner Acceptance (Attempt 2, 2026-10-06)

Status:

- **`M-B3 / SIGN_REGISTRY_V1 = COMPLETED / ACCEPTED` (attempt 2).
  `REGISTRY_V1 = SIGNED / OWNER-ACCEPTED`.**
  - The real DEV_SYNTHETIC Registry V1 was signed by E-21 K-ROOT on the
    owner's S25, in local Termux. Exactly one SIGN invocation ran.
  - It ran inside the owner-authorized attempt-2 sequence under
    [`MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST`](slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md).
  - It was verified on the S25 and again, independently, on the laptop. The
    owner then accepted it (§9).
- **Accepted Registry V1:**
  - digest `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`;
  - signed file SHA-256 `3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156`;
  - public export SHA-256 `c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8`.
- **Attempt 1 stays historical:**
  - it is `CLOSED / INCIDENT / A_NO_SIGNATURE`;
  - its candidate `b7e24530…0e53` is `HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE`:
    not burned and not reusable.
- **The acceptance covers this exact signed Registry V1 only.** It authorizes
  no modification, substitution or regeneration of it.
- **The registry is signed and accepted, but it is not installed and not
  effective.** No trust is installed and no authority is active.
  M-B4/M-B5 / `INSTALL_TRUST_AND_REGISTRY`, genesis, record 1, First Memory
  and PROD remain **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- **Operational record.** The raw evidence is owner-held outside the
  repository, in the owner-controlled external attempt-2 evidence set on the
  laptop. The S25 holds the authoritative signed copy. No K-ROOT or K-WIT
  private material was read, decrypted or copied off its device. No
  repository file changed during the live sequence.

```text
preparation / re-proof != transfer != PREPARE != SIGN go != one SIGN invocation
  != technical success (REGISTRY_SIGNED) != laptop verification != owner acceptance
REGISTRY_SIGNED + owner acceptance != registry installed != registry effective
M-B3 completion != M-B4/M-B5 authorization
forward K-ROOT baseline != retroactive continuity proof
```

## 1. Identities

| Item | Value |
| --- | --- |
| repository control | `ea74e1b36ee36c372b434be38d1eae34e5a1bb78` (merge of PR #157, the [disposition completion](slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md)); unchanged through the sequence |
| package source / PREPARE `--control-sha` | `f9fb9e14dc6a14ac796379938d3092f6214194cb` (bundle `SOURCE_COMMIT`; [replacement pins](slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md)) |
| bundle | `lilith-mb3-registry-f9fb9e1.tar`, SHA-256 `ad37758ebf892e773a7019cb2c084d4d30920e34fb5318ba9f82999f48ffa736`; `SHA256SUMS` `58eb1b8269f8a54dd4153d1bde68f1bf1440cb7d52459081f81884599240f683` |
| phone script | `mb3_phone_ceremony.py`, SHA-256 `b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7` |
| E-21 K-ROOT | `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`; root keyId `test-only.registry-root.dev-synthetic.b1b3d.1`; public anchor SHA-256 `300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f` |
| K-ACT | keyId `test-only.dev-synthetic.actor.b1b3d.1`; `publicKeySha256=dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed`; blob `6a61c350…73f3`; publication SHA-256 `d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032` (freshly captured in this sequence) |
| K-WIT | keyId `test-only.witness.dev-synthetic.b1b3d.1`; `publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`; publication SHA-256 `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472` |
| attempt-2 manifest | `mb3-inputs.json`, SHA-256 `9ce94816a28cac159b768f998d072c829b4a7fdd36d1dba3b88c2e57572aa319` |
| `epochRandom` / `issuedAt` / `policyVersion` | `11f184889f333dece054f3b91a301632` / `2026-10-06T15:16:21Z` / `policy.dev-synthetic.v1` |
| unsigned registry | SHA-256 `3b831167cfc3207a7263188f1ddfb23ca48b65a79aaae3185c77a9de757a3bdc` |
| PREPARE readback | SHA-256 `eda0d4099365df740534b7c1e40a8755661fb7d2a6830d1251e1b3335d2382cf` (phone = laptop) |
| **Registry V1 digest** | **`fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`** |
| **signed Registry V1** | `~/lilith-mb3-registry-public/authority-registry.v1.json` on the S25 (authoritative), SHA-256 **`3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156`** |
| **public export** | `lilith-mb3-export.tar`, SHA-256 **`c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8`** (phone = laptop) |
| external evidence set | owner-held; location not published |

## 2. History before attempt 2 (unchanged)

| Record | State |
| --- | --- |
| [attempt-1 incident](slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md) | M-B3 SIGN attempt 1 = `CLOSED / INCIDENT / A_NO_SIGNATURE`. It stopped in `_tty_confirm` before the signer was invoked: no signature, no passphrase prompt, `NO_REAL_REGISTRY_BURN`. Its go was consumed and its sequence ended |
| attempt-1 candidate | `b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53` = `HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE`: never signed, **not burned, not reusable** |
| fix | the reviewed `_tty_confirm` correction (separate write-only / read-only `/dev/tty` handles), merged as `f9fb9e1` (PR #155) |
| [replacement pins](slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md) | bundle `ad37758e…a736`, script `b58b9321…ecc7` (PR #156) |
| [disposition completion](slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md) | phone incident disposition **COMPLETED / ACCEPTED**: attempt-1 state archived in `~/lilith-mb3-incident-attempt1` (manifest `94483e8b…181d`); active M-B3 paths cleared; K-ROOT custody preserved (PR #157) |

## 3. Owner authorizations in attempt 2 (each separate, in order)

1. **Preparation / re-proof only.** Bound to control `ea74e1b`, the
   replacement pins, and the rule that the attempt-1 K-ACT publication pin
   must not be reused as currentness evidence.
2. **Transfer + S25 read-only verification only.** Bound to the re-proof that
   ended `14:26:58Z`.
3. **K-ROOT custody metadata rebaseline** (§5).
4. **PREPARE only.** `--control-sha` must stay `f9fb9e1`.
5. **One-attempt SIGN go.** Bound to manifest `9ce94816…a319`, digest
   `fa662721…14fc`, `epochRandom`, `issuedAt`, policy, root keyId, bundle,
   script, K-ACT publication, unsigned-registry and readback hashes.
6. **Acceptance** of the verified result (§9).

None of them authorized M-B4/M-B5 or anything later.

## 4. Fresh re-proof, transfer and gates (all read-only on DEV)

All times are UTC on 2026-10-06. Every DEV check was on `lilith-dev-01` only.

| Step | Result |
| --- | --- |
| control | `origin/main = HEAD = ea74e1b`, clean; `f9fb9e1..ea74e1b` changes docs and tests only (no bundled or tool file) |
| DEV deployment relationship | latest applicable deploy `37475815074` (`ea74e1b`, created `14:03:43Z`) **precedes** the re-proof; no later run; nothing queued or in progress at any gate |
| B-5 | grant usable; no §9 stop; no G-1 … G-8 invalidator; no runtime / authority / deploy drift since the packet base |
| host re-proof (`14:21:23Z`–`14:22:09Z`) | **PASS**: machine `ae929170…`, boot `eea461c3…`, no reboot pending; K-ACT CURRENT (`6a61c350…`, inode and times unchanged, credstore one entry); `status --expect P1B-2 aee323e…` PASS; K-WIT preserved (`f8759370…`, sole credential, `0600`); broker preservation PASS (`c4b9cb38…` / `a30bd7d6…`); observer `94cb28f0…`; units inactive; `GRANT_ABSENT` |
| fresh K-ACT publication | the host's K-ACT L2b.2 publication file, read read-only by root **in this re-proof**; SHA-256 `d7647976…b032` (744 bytes). The bytes equal the attempt-1 capture because the file is unchanged; the pin comes from this capture, not from attempt 1. The bundled library recomputed the fingerprint `dd13a1fb…01ed` from the public key |
| exposure / IAM / topology | 12 cloud captures byte-identical to the attempt-1 window; Admin Activity holds only `iam.serviceAccounts.actAs` (owner IAP sessions; the deployer during the reviewed deploys) |
| package | bundle `ad37758e…` 75 files, `SHA256SUMS` 74/74; script `b58b9321…`; library, builder and laptop verifier pins equal at `f9fb9e1` and `ea74e1b`; focused M-B3 tests PASS |
| closing gates | `14:26:22Z`–`14:26:58Z`; before transfer `14:35:16Z`–`14:36:36Z` and `14:55:08Z`–`14:57:37Z`; before PREPARE `15:10:43Z`–`15:13:11Z`; **final pre-SIGN `15:52:06Z`–`15:54:29Z`**. Each: same boot, K-ACT / publication / K-WIT / status / broker / observer / activation unchanged, cloud 12/12 identical, audit `actAs` only, no new deploy. **No terminator M3-T1 … M3-T11 observed** |
| transfer | a **new** laptop folder; the attempt-1 transfer folder was not reused. Exactly four files by owner-controlled USB / MTP into Download. The S25 hashes equal the pins. USB was unplugged afterwards and airplane mode turned ON; USB and wireless debugging OFF |

## 5. K-ROOT forward custody baseline (owner rebaseline)

The S25 pre-transfer check C2 found:

- directory `0700`;
- exactly one entry, `k-root.der`;
- file `0600`, size `166`, mtime `1791270756`.

No earlier record held the file's size or mtime. The attempt-1 disposition
compared them before and after on the phone, but never printed or exported
them. The historical comparison was therefore **NOT ESTABLISHED**, and the
transfer gate stayed closed.

The owner then accepted these values as the **forward** custody baseline:

```text
KROOT_FORWARD_BASELINE = 0700 / only k-root.der / 0600 / 166 / 1791270756
```

- This **does not** retroactively prove the metadata unchanged since M-B1.
- From that decision on, any change without an accepted ceremony or explicit
  owner authorization is a custody anomaly / revalidation condition.
- K-ROOT contents were never read by these checks.
- The baseline was re-checked equal before PREPARE, after PREPARE, and before
  SIGN.

## 6. PREPARE (one invocation) and the evidence-recording gap

- **One PREPARE** ran in local Termux with `--control-sha f9fb9e1…`,
  `--bundle-sha256 ad37758e…` and `--kact-publication-sha256 d7647976…`.
- It printed all 22 tokens and `MB3_PREPARED`, and it froze:
  - manifest `9ce94816…a319`;
  - expected digest `fa662721…14fc`;
  - `epochRandom` `11f184889f333dece054f3b91a301632`;
  - `issuedAt` `2026-10-06T15:16:21Z`.
- It printed "K-ROOT WAS NOT ACCESSED. NO PASSPHRASE WAS REQUESTED. NOTHING
  WAS SIGNED." The signer was not invoked.
- **Readback** `eda0d409…82cf` (10 entries) was rebuilt offline with the
  bundled library and owner tool and a key-less capture signer. The manifest,
  unsigned registry and 883 signing bytes are byte-identical. The digest is
  not the attempt-1 candidate.

**Evidence-recording gap.** The reviewed pre-PREPARE checks were:

- P1: the Download listing;
- P3: the K-ROOT forward-baseline metadata.

Their original screen output was not captured.

- **Recovery.** The same Termux session's shell history shows the P3
  commands (entries 290–292) and the P1 listing (303, 310) **before** the
  single attempt-2 PREPARE (311). Entry 262 is attempt 1's PREPARE.
- **What else was covered.** P2 (the four file pins) and P4 (local, clean
  session) were enforced by PREPARE itself at run time.
- **Post-PREPARE revalidation** matched the accepted state:
  - K-ROOT `700 / k-root.der / 600 166 1791270756`;
  - no SIGN outputs and no `sign/` marker;
  - the phone readback hash equals the laptop copy.

The owner classified this as an **EVIDENCE-RECORDING GAP, NOT a protocol
deviation**. That classification rests on command order plus post-PREPARE
state. It is **not** a capture of the original P1 / P3 values, and this
record does not treat it as one.

## 7. SIGN (exactly one invocation)

| Fact | Value |
| --- | --- |
| final local checks | airplane ON, USB unplugged, USB and wireless debugging OFF, local Termux, no `sshd` / `adbd`, K-ROOT forward baseline equal (metadata only), manifest and signing bytes equal, script `b58b9321…`, no prior SIGN output |
| command | `mb3_phone_ceremony.py sign --control-sha f9fb9e1… --bundle-sha256 ad37758e… --manifest-sha256 9ce94816…` |
| attempt marker | `sign/attempt.json`, `attemptStartedAt 2026-10-06T16:02:18Z` (after the final pre-SIGN gate); binds the manifest, bundle and control-sha; `invocationsPermitted 1` |
| invocations | **exactly one**; no retry |
| signer exit | **0**; signer stderr **empty** |
| S25 verification | `KROOT_SIGNATURE_VERIFIED`, `OWNER_TOOL_RECONSTRUCTION_EQUAL`, `VERIFIED=True` |
| outcome before acceptance | `B_SIGNED_PENDING_OWNER_ACCEPTANCE`; `MB3_TECHNICAL_STATE=REGISTRY_SIGNED` |
| burn | **none** |

## 8. Independent offline laptop verification

| Check | Result |
| --- | --- |
| export | SHA-256 `c4ea3d66…64d8` = phone value; **exactly the 16-file success allowlist**; no key material |
| reviewed verifier | `verify_mb3_registry.py` (`e710cfa6…`) with every pin from the go: **`MB3_LAPTOP_VERIFIED`**, exit 0. Tokens: `EXPORT_EXACT_PUBLIC_ALLOWLIST`, `MANIFEST_EQUALS_GO_PINS`, `KROOT_SIGNATURE_VERIFIED`, `SINGLE_CURRENT_KACT`, `KACT_RECORD_EQUALS_PUBLICATION`, `KWIT_NOT_IN_REGISTRY`, `KWIT_KACT_KROOT_DISTINCT`, `NOT_A_BURNED_IDENTITY`, `NOT_A_KNOWN_REAL_REGISTRY_BURN`, `OWNER_TOOL_RECONSTRUCTION_EQUAL`, `S25_DIGEST_FILE_EQUAL` and the rest of §10 of the package |
| independent check | raw Ed25519 verification under the E-21 anchor key: **PASS**. Signed file = RFC 8785 JCS + newline; exactly one 64-byte signature; unsigned fields = the frozen PREPARE candidate; signing bytes rebuilt = frozen; digest = expected = phone digest file; exactly one key (K-ACT, not revoked / retired / compromised); K-WIT absent; K-ROOT not a registry key |
| frozen inputs | the manifest, unsigned registry, signing bytes, PREPARE evidence and four inputs in the export are byte-equal to the PREPARE readback; the phone `evidence.sha256` verifies 10/10 |
| candidate substitution | **none** |

## 9. Owner acceptance (verbatim excerpt)

The full owner decision is held in the external evidence set. The binding
lines:

> I accept the independently verified M-B3 attempt-2 SIGN_REGISTRY_V1 result.
> M-B3 / SIGN_REGISTRY_V1 = COMPLETED / ACCEPTED
> REGISTRY_V1 = SIGNED / OWNER-ACCEPTED
> This acceptance applies ONLY to the exact signed Registry V1 identified by the hashes above.
> It does NOT authorize modification, substitution or regeneration of that Registry V1.
> The earlier P1/P3 evidence issue is accepted as an EVIDENCE-RECORDING GAP, not a protocol deviation.
> Owner acceptance of M-B3 does NOT mean:
> registry installed
> registry effective
> trust installed
> authority active
> genesis created
> record 1 created
> First Memory created
> PROD authorized

The hashes it names are §1: manifest `9ce94816…a319`, digest
`fa662721…14fc`, signed registry `3f0a59c0…6156`, export `c4ea3d66…64d8`.

## 10. What remains

- **M-B4/M-B5 / `INSTALL_TRUST_AND_REGISTRY`** is the next stage
  (`REGISTRY_SIGNED → TRUST_INSTALLED`). It needs its own reviewed procedure,
  fresh DEV evidence and a separate explicit owner authorization. **M-B3
  completion does not authorize it.**
- **Evidence from this sequence is not reusable.** That covers the gates, the
  K-ACT capture and the transfer, which were bounded to this sequence. A
  later step re-proves what it needs.
- The K-ROOT forward baseline (§5) is the custody reference for later S25
  steps.
- C-4 `KNOWN_CUSTODY_DEBT` (M-B2) is unchanged.

## 11. State

```text
M-B3 / SIGN_REGISTRY_V1 = COMPLETED / ACCEPTED (ATTEMPT 2)
REGISTRY_V1 = SIGNED / OWNER-ACCEPTED
TECHNICAL_STATE = REGISTRY_SIGNED
OUTCOME = B_SIGNED_PENDING_OWNER_ACCEPTANCE -> OWNER-ACCEPTED
REGISTRY_V1_DIGEST = fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc
SIGNED_REGISTRY_SHA256 = 3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156
EXPORT_SHA256 = c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8
MANIFEST_SHA256 = 9ce94816a28cac159b768f998d072c829b4a7fdd36d1dba3b88c2e57572aa319
PREPARE_READBACK_SHA256 = eda0d4099365df740534b7c1e40a8755661fb7d2a6830d1251e1b3335d2382cf
EPOCH_RANDOM = 11f184889f333dece054f3b91a301632
ISSUED_AT = 2026-10-06T15:16:21Z
POLICY_VERSION = policy.dev-synthetic.v1
ROOT_KEY_ID = test-only.registry-root.dev-synthetic.b1b3d.1
E-21 publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf
K-ACT test-only.dev-synthetic.actor.b1b3d.1 publicKeySha256=dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed (SOLE CURRENT KEY)
K-WIT test-only.witness.dev-synthetic.b1b3d.1 publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf (NOT IN REGISTRY V1)
K-ROOT, K-ACT, K-WIT DISTINCT
PREPARE INVOCATIONS = 1
EXACTLY ONE ATTEMPT-2 SIGN INVOCATION; SIGNER EXIT 0; SIGNER STDERR EMPTY
SIGNATURE COUNT = 1
SIGNATURE VERIFIED UNDER E-21 (S25, REVIEWED LAPTOP VERIFIER, INDEPENDENT ED25519)
MB3_LAPTOP_VERIFIED
OWNER_TOOL_RECONSTRUCTION_EQUAL
NO CANDIDATE SUBSTITUTION
BURN = NONE
ATTEMPT 1 = CLOSED / INCIDENT / A_NO_SIGNATURE
ATTEMPT-1 CANDIDATE b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53 = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE; NOT BURNED; NOT REUSABLE
ATTEMPT-1 PHONE DISPOSITION = COMPLETED / ACCEPTED
P1/P3 ORIGINAL OUTPUT = EVIDENCE-RECORDING GAP; NOT A PROTOCOL DEVIATION
KROOT_FORWARD_BASELINE = 0700 / only k-root.der / 0600 / 166 / 1791270756
KROOT FORWARD BASELINE IS NOT RETROACTIVE TO M-B1
KROOT PRIVATE MATERIAL STAYED IN S25 TERMUX PRIVATE STORAGE
REGISTRY_EFFECTIVE = NO
TRUST_INSTALLED = NO
AUTHORITY ACTIVE = NO
M-B4/M-B5 = NOT AUTHORIZED
INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO RUNTIME, SIGNER, PACKAGE, WORKFLOW OR INFRASTRUCTURE CHANGE
```

> **Later current state (2026-10-07, pointer only; the text above is
> preserved as written).** The owner recorded a governed derivation of the
> installable representations
> ([owner decision](slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md)).
> Registry V1 is installed as the signed transport file `3f0a59c0…6156`
> minus exactly one terminal LF (representation pin `46b0bfc5…8b1e`). Its
> identity (digest `fa662721…14fc`, E-21 signature) is unchanged and the
> transport file is preserved. A repository-only
> [remediation](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md)
> added the derivation tooling, tests, a read-only content verifier and a
> bounded removal tool. Nothing is installed. M-B4/M-B5, genesis, record 1,
> First Memory and PROD remain NOT AUTHORIZED, and FRESHNESS is UNKNOWN.
