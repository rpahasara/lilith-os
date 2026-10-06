# Slice 15B2b-B1b-3e — M-B3 / SIGN_REGISTRY_V1: Registry Ceremony Package (S25 Termux, PREPARE / SIGN)

Status:

- **`MB3_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW`.** This record lands the
  reviewed **source and procedure** for the
  [accepted continuity model](slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md)
  (`MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST`).
  It becomes the reviewed procedure when the owner reviews and merges it.
- **The runnable bundle is NOT built yet.** It is built from the merged
  `main` SHA, so its SHA-256 is unknown until then (§1). The phone-script
  SHA-256 below is determinable now; it stays valid only if the script is
  byte-identical at merge.
- **M-B3 / `SIGN_REGISTRY_V1` is NOT AUTHORIZED.** No preparation sequence is
  authorized; no K-ROOT, K-WIT, DEV, GCP, S25 or replica contact occurred; no
  real candidate, `epochRandom`, or registry exists. All tests use throwaway
  TEST keys.

```text
package prepared != package reviewed != preparation sequence authorized != PREPARE
  != owner go != SIGN != REGISTRY_SIGNED != owner acceptance
candidate manifest != authority;  script prompt / flag / token != authorization
```

## 1. Identities and pins

| Item | Value | Determinable now? |
| --- | --- | --- |
| phone script | `services/owner-memory-control/tools/mb3_phone_ceremony.py`, transferred as `mb3_phone_ceremony.py` | — |
| **phone-script SHA-256** | `db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54` | **yes** (pinned by a test; valid only if unchanged at merge) |
| library (bundle member) | `services/owner-memory-control/tools/mb3_registry_ceremony.py` | — |
| builder | `services/owner-memory-control/tools/build_mb3_registry_bundle.py` | — |
| laptop verifier | `services/owner-memory-control/tools/verify_mb3_registry.py` | — |
| signer (unchanged) | `services/authority-dev/ceremony/lilith_authority_owner_dev.py` `registry-v1` | — |
| source commit / control SHA | the merged `main` SHA that contains this record | **no**: after merge |
| bundle | `lilith-mb3-registry-<sha7>.tar`, top `lilith-mb3-registry-<sha7>/` | **no** |
| **bundle SHA-256** | printed by the builder (`tarSha256`); never written inside the bundle | **no**: after merge |
| files in the bundle | **75** = 17 M-B1 closure sources + the library + 55 vendor files + `SOURCE_COMMIT` + `SHA256SUMS` | yes (count) |
| K-ACT publication SHA-256 | from the fresh read-only DEV re-proof (§5) | **no**: live sequence |
| manifest SHA-256, `epochRandom`, `issuedAt`, expected registry digest | from PREPARE on the S25 (§7) | **no**: live sequence |

Accepted public identities compiled into the library (`ACCEPTED`):

| Identity | Value | Source |
| --- | --- | --- |
| E-21 K-ROOT `publicKeySha256` | `cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf` | M-B1 completion |
| registry-root keyId | `test-only.registry-root.dev-synthetic.b1b3d.1` | owner tool `ROOT_KEY_ID` |
| K-WIT `publicKeySha256` | `5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf` | M-B2 completion |
| K-WIT keyId | `test-only.witness.dev-synthetic.b1b3d.1` | M-B2 completion |
| K-WIT blob SHA-256 | `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be` | M-B2 completion |
| K-WIT publication SHA-256 | `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472` (682 bytes) | M-B2 completion §1 |
| K-ACT keyId | `test-only.dev-synthetic.actor.b1b3d.1` | `successor_custody.INITIAL_KEY_ID` |
| K-ACT `publicKeySha256` | `dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed` | M-B2 completion §1 |
| K-ACT CURRENT blob SHA-256 | `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3` | live-install preflight §24 |

## 2. Package contents

**Bundle (built, §3):** the reviewed M-B1 import closure of
`lilith_authority_owner_dev.py` (17 files incl. `burned_identities.py`), plus
`tools/mb3_registry_ceremony.py`, the 55 pure-Python vendor files (`fido2`
2.2.1, `rfc8785` 0.1.4), `SOURCE_COMMIT` and `SHA256SUMS`.

**Not in the bundle:** the phone script (pinned separately); any key,
passphrase, `.der` / `.pem` / `.cred` file; any K-WIT credential; any public
input (they come from the fresh sequence); the keygen; any authority
material; the bundle's own SHA-256.

**Transferred laptop → S25 (and nothing else):**

| File (in Download) | What | Pin |
| --- | --- | --- |
| `lilith-mb3-registry-<sha7>.tar` | the bundle | bundle SHA-256 (§1) |
| `mb3_phone_ceremony.py` | the phone script | phone-script SHA-256 (§1) |
| `mb3-kact-publication.json` | the K-ACT L2b.2 publication bytes captured in the fresh re-proof | K-ACT publication SHA-256 (§5) |
| `mb3-kwit-publication.json` | the accepted K-WIT publication (M-B2 external evidence set) | `9e9dd078…3472` |

The root anchor is **not** transferred: PREPARE reads the authoritative S25
public copy `~/lilith-kroot-dev-synthetic-public/k-root-anchor.json` written
at M-B1.

## 3. Build procedure (laptop, offline, after merge)

1. On a clean checkout at merged `main` (`<CONTROL_SHA>`), with the vendor
   set re-verified against the B-4 bundle `SHA256SUMS` (as M-B1 §1):

   ```bash
   python services/owner-memory-control/tools/build_mb3_registry_bundle.py --repo . --commit <CONTROL_SHA> --vendor-dir <vendor> --out <staging>/lilith-mb3-registry-<sha7>.tar
   ```

2. Run it twice into two outputs; the two tars must be byte-identical.
3. Record `tarSha256`, `sha256sumsSha256`, `files=75`, `sourceCommit` and
   `phoneScriptSha256` in a separate finalization record (M-B1 precedent).
   `phoneScriptSha256` must equal §1.

The builder reads sources with `git show <commit>:<path>`, refuses
key-like or input-like member names, and never embeds the tar's own hash.

## 4. Paths on the S25

| Path | Role | Written by |
| --- | --- | --- |
| `~/lilith-kroot-dev-synthetic/k-root.der` | the only private K-ROOT material | never written; read **only** by the signer in SIGN |
| `~/lilith-kroot-dev-synthetic-public/k-root-anchor.json` | authoritative public E-21 anchor (M-B1) | read only (PREPARE) |
| `~/lilith-mb3/` (`0700`) | staging: the bundle, `inputs/`, `evidence/`, the manifest, `unsigned-registry.json`, `registry-signing-bytes.bin` | PREPARE |
| `~/lilith-mb3/sign/` | **the attempt marker** and the signer's stdout / stderr / exit | SIGN (created first, never removed) |
| `~/lilith-mb3/burn/real-registry-burn.json` | a known burn or tombstone (C / D / E) | SIGN failure path |
| `~/lilith-mb3-registry-public/` | **the authoritative S25 copy** of the signed registry and its digest | SIGN success |
| `~/lilith-mb3-export.tar` / `~/lilith-mb3-failure-export.tar` | public-only exports (§11) | SIGN |

## 5. Preparation sequence (future; NOT authorized)

Each step needs the owner's explicit authorization of **one M-B3 preparation
sequence** (decision D-1). That authorization is not the signing go. Every
check is read-only. Any terminator M3-T1 … M3-T11 ends the sequence.

| # | Step | Required result |
| --- | --- | --- |
| 0 | owner authorizes one M-B3 preparation sequence | explicit statement |
| 1 | clean control checkout; HEAD = `origin/main` = `<CONTROL_SHA>`; this record merged; finalization pins recorded | equal |
| 2 | B-5 grant usable; no B-5 stop; no G-1 … G-9 | none |
| 3 | **K-ACT CURRENT re-proof on DEV** (root, read-only; M-B2 runbook step 6 checks): same boot; §24 CURRENT (path, `root:root 0600`, identity, times, SHA-256 `6a61c350…f3`, credstore one entry); installer `status --expect P1B-2 aee323e…` PASS; units inactive, not enabled; `GRANT_ABSENT`; broker preservation PASS | all equal |
| 4 | **K-ACT publication bytes**: in the same re-proof, root reads `/root/b1b3d-l2b-publication.json` read-only; stdout is captured directly into the external M-B3 evidence set; record its SHA-256 = `<KACT_PUBLICATION_SHA256>`. On the laptop the library check `verify_kact_publication_bytes` must pass: canonical bytes, DEV_SYNTHETIC profile, keyId, **recomputed** fingerprint = `dd13a1fb…01ed`, blob = `6a61c350…f3` | PASS |
| 5 | **K-WIT preservation** (root, read-only): `credentials/` holds only `lilith-recovery-witness.witness.cred`, `root:root 0600`, 219 bytes, root `sha256sum` (ciphertext, never decrypted) = `f8759370…be`; directories `root:root 0700`; witness units inactive. The K-WIT publication file from the M-B2 evidence set has SHA-256 `9e9dd078…72` | equal |
| 6 | posture: same boot as the re-proof, no deployment since it, no broker replacement, no exposure / IAM / topology change | none |
| 7 | **S25 K-ROOT custody attestation** (owner-run, screen-only, local Termux): `~/lilith-kroot-dev-synthetic/` is `0700` and lists only `k-root.der` (`0600`); no SSH / `sshd` / ADB; nothing is read from the key file | owner attests |
| 8 | build or re-verify the bundle against the finalization pins; verify the phone-script SHA-256 | equal |
| 9 | transport (§6), then **PREPARE** (§7) | `MB3_PREPARED` |
| 10 | owner STOP: the owner reads the PREPARE values and decides on the go (§8) | — |

No fresh PR-2 and no full fresh DR-5 are required for M-B3 (D-3).

## 6. Transport (laptop → S25; public files only)

1. Verify the four SHA-256 pins on the laptop (§2).
2. MTP-copy exactly those four files into the phone's Download folder.
3. Unplug USB; airplane mode **ON**; continue in a **local** Termux session.
   No ADB, SSH or automation from here on.

## 7. PREPARE (S25)

```bash
python -B "$HOME/storage/downloads/mb3_phone_ceremony.py" prepare --control-sha <CONTROL_SHA> --bundle-sha256 <BUNDLE_SHA256> --kact-publication-sha256 <KACT_PUBLICATION_SHA256> 2>&1 | tee "$HOME/lilith-mb3-prepare.transcript.txt"
```

First check `sha256sum "$HOME/storage/downloads/mb3_phone_ceremony.py"` equals
the phone-script pin. PREPARE then:

1. **G0 gates:** HOME in Termux private storage; no `SSH_*` variables; no
   `sshd` or `adbd` process; an interactive terminal.
2. Refuses if any earlier M-B3 state exists (`~/lilith-mb3`, the public copy,
   or either export): nothing is reused.
3. Copies the tar into private staging; its SHA-256 must equal
   `--bundle-sha256`; safe extraction; every `SHA256SUMS` line verifies; no
   extra file; `SOURCE_COMMIT` = `--control-sha`.
4. Verifies the public inputs with the bundled library: root anchor
   fingerprint = E-21; K-ACT file SHA-256 = `--kact-publication-sha256`, with
   the fingerprint **recomputed**; K-WIT publication = the accepted bytes.
5. Generates **`epochRandom` once** (`secrets.token_hex(16)`) and **`issuedAt`
   once** (UTC, seconds); fixes `policyVersion = policy.dev-synthetic.v1`.
6. Builds the candidate by calling the bundled owner tool's own
   `registry_v1` with `CaptureSigner`, which holds no key: it records the
   exact signing bytes and returns a placeholder. Ed25519 is deterministic,
   so SIGN signs exactly these bytes.
7. Pre-sign checks (§10 tokens up to `EXPECTED_DIGEST_FROZEN_BEFORE_SIGNING`).
8. Writes, read-only (`0444`), `unsigned-registry.json`,
   `registry-signing-bytes.bin` and the manifest `mb3-inputs.json`, and
   prints `MANIFEST_SHA256`, `EXPECTED_REGISTRY_DIGEST`, `EPOCH_RANDOM`,
   `ISSUED_AT`, `POLICY_VERSION`, the K-ACT values, the bundle and script
   pins, then **STOP**.

**PREPARE never touches K-ROOT.** It does not stat, list, open, load or
decrypt anything under `~/lilith-kroot-dev-synthetic/`, asks for no
passphrase, and signs nothing (test-enforced on the source and in behaviour).
Running PREPARE again is refused.

**Manifest** (`mb3-inputs.json`, RFC 8785 JCS + newline): `manifestType`
`LILITH_MB3_CANDIDATE_MANIFEST`, `continuity`, `profile` `DEV_SYNTHETIC`,
`environment` `dev`, **`authoritative: false`**, **`authorizes: "NOTHING"`**,
`controlSha` = `sourceCommit`, `bundleSha256` (the external pin PREPARE
verified), `scriptSha256`, the E-21 fingerprint and root keyId,
`rootAnchorSha256`, `kactPublicationSha256`, the **recomputed**
`kactPublicKeySha256`, K-ACT keyId and blob, the K-WIT fingerprint, keyId,
blob and publication SHA-256, `witnessAnchorSha256`, `policyVersion`,
`epochRandom`, `issuedAt`, `recoveryEpoch {counter 1, random}`,
`registryVersion 1`, `expectedRegistryDigest`, `unsignedRegistrySha256`,
`signerCommand` (form, argv semantics, key path, `invocations: 1`,
`automaticRetry: false`, passphrase rule), `inputFiles` (four hashes),
`terminalStateOnSuccess` `REGISTRY_SIGNED`, and the PREPARE tokens. It never
names its own hash or the bundle's contents' hash of itself.

## 8. Owner STOP and the go template (TEMPLATE ONLY; not given)

After PREPARE the owner decides. A go is valid only if it names every value
below; placeholders are in angle brackets, everything else is fixed.

> I authorize M-B3 / `SIGN_REGISTRY_V1` now for exactly one attempt within this
> current DEV_SYNTHETIC M-B3 preparation sequence.
>
> Scope: DEV_SYNTHETIC only. Control commit: `<CONTROL_SHA>`.
>
> Reviewed bundle SHA-256: `<BUNDLE_SHA256>`. Reviewed phone-script SHA-256:
> `db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54`.
> Candidate manifest SHA-256: `<MANIFEST_SHA256>`.
>
> K-ACT publication SHA-256: `<KACT_PUBLICATION_SHA256>`; recomputed K-ACT
> `publicKeySha256=dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed`.
> E-21 K-ROOT
> `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`.
> K-WIT `publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`,
> keyId `test-only.witness.dev-synthetic.b1b3d.1` (not a signer).
>
> `policyVersion=policy.dev-synthetic.v1`; `epochRandom=<EPOCH_RANDOM>`;
> `issuedAt=<ISSUED_AT>`; expected registry digest `<EXPECTED_REGISTRY_DIGEST>`.
>
> This authorization permits exactly one invocation, on my S25 in local
> Termux, of `mb3_phone_ceremony.py sign`, which runs once:
> `lilith_authority_owner_dev.py registry-v1 ~/lilith-kroot-dev-synthetic/k-root.der ~/lilith-mb3/inputs/kact-publication.json <EPOCH_RANDOM> policy.dev-synthetic.v1 <ISSUED_AT>`.
> I type the K-ROOT passphrase only into that form's prompt on the S25.
>
> Any `REFUSED`, wrong passphrase, extra prompt, prompt anomaly, failure,
> nonzero exit, unexpected output, STOP, or relevant uncertainty consumes this
> go and ends the sequence. There is no retry.
>
> This authorization does not authorize M-B4/M-B5, registry installation or
> effectiveness, genesis, record 1, First Memory, PROD activity, or any later
> step. `FRESHNESS=UNKNOWN` remains unchanged.

## 9. SIGN (S25; only under the go)

```bash
python -B "$HOME/storage/downloads/mb3_phone_ceremony.py" sign --control-sha <CONTROL_SHA> --bundle-sha256 <BUNDLE_SHA256> --manifest-sha256 <MANIFEST_SHA256> 2>&1 | tee "$HOME/lilith-mb3-sign.transcript.txt"
```

1. **Consumes the attempt on entry:** `~/lilith-mb3/sign/` is created
   (`mkdir`, exclusive) before any gate, with `attempt.json`. If it exists:
   `ATTEMPT_ALREADY_CONSUMED`, and nothing runs.
2. G0 gates; no public copy or export exists yet.
3. Manifest SHA-256 = `--manifest-sha256`; manifest valid and
   non-authoritative; it binds `--control-sha` and `--bundle-sha256`; the
   script is the one PREPARE recorded; staged tar and `SHA256SUMS` re-verify;
   every input file equals its manifest hash; the K-ACT publication re-verifies.
4. Re-captures the candidate from the **frozen** values (no regeneration):
   digest and signing bytes must equal PREPARE's.
5. K-ROOT file custody shape (SIGN only): regular, `0600`, the only entry in
   a `0700` directory, in private storage. It is never opened by the script.
6. Shows the candidate digest, `epochRandom` and `issuedAt` on the phone and
   asks the owner to type `SIGN-ONCE <first 16 hex of the digest>`. This is an
   anti-accident check, **not authorization**. Anything else STOPs and
   consumes the attempt.
7. **Exactly one invocation**: `python -B <bundle>/…/lilith_authority_owner_dev.py registry-v1 <key> <kact> <epochRandom> policy.dev-synthetic.v1 <issuedAt>`,
   with `stdin=/dev/null` (so `getpass` reads only `/dev/tty`), stdout to
   `sign/registry-v1.stdout` (`O_EXCL`, `0600`), stderr to
   `sign/registry-v1.stderr`, the exit code to `sign/registry-v1.exit`, and an
   environment of only `PATH`, `HOME`, `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE`.
   The passphrase is never an argument, a variable, or a file.
8. Classifies the exit (§13), then runs the full verification (§10) on the
   S25 before anything is exported.
9. On a pass: writes the authoritative S25 copy
   `~/lilith-mb3-registry-public/authority-registry.v1.json` (the exact stdout
   bytes) and its `.digest`; shows the **registry digest on the phone**; seals
   the evidence; builds the export (§11); prints `MB3_REGISTRY_DIGEST`,
   `PHONE_SIDE_EXPORT_SHA256`, `MB3_TECHNICAL_STATE=REGISTRY_SIGNED` and
   **STOP: separate owner acceptance is required**.

## 10. Verification (S25 before export; laptop after export)

Both venues run `mb3_registry_ceremony.verify_signed_registry`, from public
bytes only, and rebuild the signing bytes with the owner tool's own
`registry_v1`. Laptop:

```bash
python services/owner-memory-control/tools/verify_mb3_registry.py --export <lilith-mb3-export.tar> --control-sha <CONTROL_SHA> --bundle-sha256 <BUNDLE_SHA256> --manifest-sha256 <MANIFEST_SHA256> --kact-publication-sha256 <KACT_PUBLICATION_SHA256>
```

The laptop takes every pin from the go, reads the tar without extracting it,
and requires the exact allowlist.

| Token | Check | Sequencer evidence |
| --- | --- | --- |
| `MANIFEST_VALID_NON_AUTHORITATIVE` | canonical, exact fields, fixed values, `authoritative: false` | — |
| `ROOT_FINGERPRINT_E21` | anchor hash = manifest; SHA-256 of the raw key = E-21; root keyId, `dev`, `test-only.` | — |
| `KACT_PUBLICATION_PINNED_AND_RECOMPUTED` | file SHA-256 = pin; canonical; profile and keyId; fingerprint recomputed = accepted; blob = CURRENT | — |
| `KWIT_PUBLICATION_ACCEPTED` | publication SHA-256, fingerprint, keyId, blob; witness anchor = manifest | — |
| `REGISTRY_BYTES_CANONICAL` | the signed file is exactly JCS + newline | — |
| `SIGNING_BYTES_AND_DIGEST_EXPECTED` | `LILITH_AUTHORITY_REGISTRY_V1\0 ‖ JCS(unsigned)`; SHA-256 = `registry_digest` = manifest `expectedRegistryDigest` | `registryDigestRecordedOffHost` (with §12) |
| `KROOT_SIGNATURE_VERIFIED` | `authority_verifier.verify_authority_registry` under the E-21 root, `dev`, minimum version 1, E0, `policyVersion` | — |
| `REGISTRY_FIELDS_EXACT` | protocol, schema 1, `dev`, `registryVersion` 1, E0 `{1, epochRandom}`, policy, root keyId, `issuedAt` = manifest | — |
| `REGISTRY_SCHEMA_VALID` | `AuthorityRegistryV1` field constraints | — |
| `SINGLE_CURRENT_KACT` | `single_current_key_reason` is None; the only current key is K-ACT | `singleCurrentKeyHolds` |
| `KACT_RECORD_EQUALS_PUBLICATION` | exactly one record, equal to `expected_kact_record(publication)` | `kActRecordEqualsPublication` |
| `KACT_FINGERPRINT_RECOMPUTED` | the record's key hashes to the accepted fingerprint | — |
| `KWIT_NOT_IN_REGISTRY` | K-WIT keyId and key absent | `kWitNotInRegistry` |
| `KWIT_KACT_KROOT_DISTINCT` | `pr1_bootstrap.witness_distinctness_reason` is None; K-ROOT ≠ K-ACT, K-WIT | — |
| `NOT_A_BURNED_IDENTITY` | the canonical 20: K-ROOT, K-ACT, K-WIT keys and the registry digest | — |
| `NOT_A_KNOWN_REAL_REGISTRY_BURN` | the digest is not in a supplied real-burn register | — |
| `OWNER_TOOL_RECONSTRUCTION_EQUAL` | the owner tool rebuilds identical signing bytes from the manifest values | — |

PREPARE runs the same structural checks on the unsigned candidate (with a
placeholder signature that is parsed, never verified) and adds
`EXPECTED_DIGEST_FROZEN_BEFORE_SIGNING`.

## 11. Export allowlists (S25 → laptop)

**Success** (`~/lilith-mb3-export.tar`), exactly:

```text
lilith-mb3-registry-public/authority-registry.v1.digest
lilith-mb3-registry-public/authority-registry.v1.json
lilith-mb3/evidence.sha256
lilith-mb3/evidence/prepare.txt
lilith-mb3/evidence/sign-outcome.json
lilith-mb3/evidence/verify-s25.txt
lilith-mb3/inputs/kact-publication.json
lilith-mb3/inputs/kwit-publication.json
lilith-mb3/inputs/root-anchor.json
lilith-mb3/inputs/witness-anchor.json
lilith-mb3/mb3-inputs.json
lilith-mb3/registry-signing-bytes.bin
lilith-mb3/sign/attempt.json
lilith-mb3/sign/registry-v1.exit
lilith-mb3/sign/registry-v1.stderr
lilith-mb3/unsigned-registry.json
```

**Failure** (`~/lilith-mb3-failure-export.tar`): required `mb3-inputs.json`,
`evidence.sha256`, `evidence/prepare.txt`, `evidence/sign-outcome.json`,
`sign/attempt.json`; optionally the inputs, the unsigned candidate and
signing bytes, `sign/registry-v1.{exit,stderr,stdout}`,
`evidence/verify-s25.txt`, and `burn/real-registry-burn.json`. It never holds
the success-format public copy.

**Never exported** (refused by name and by construction; the export never
walks a directory): `k-root.der`; `~/lilith-kroot-dev-synthetic/`; anything
holding `k-root`, `.der`, `.pem`, `.cred`, `secret` or `passphrase`; any K-WIT
private material; the bundle; unrelated Termux files. Copy **only** the export
tar and the transcript.

## 12. Evidence and records

- **S25 (authoritative for M-B3 custody):** `~/lilith-mb3-registry-public/`
  and the sealed `~/lilith-mb3/`. Never deleted by the script.
- **Laptop:** the owner-controlled external M-B3 evidence set: the export,
  both transcripts, the phone-side export hash, the DEV re-proof output, the
  K-ACT publication capture, the laptop verifier output. Public only; secret
  scan 0 hits required.
- **Registry digest off-host** (`registryDigestRecordedOffHost`): written
  down by the owner from the phone screen and present in both copies.

## 13. Failure, consumption and burn handling

Every STOP after SIGN starts consumes the go. Nothing is retried, deleted or
re-signed. Outcome classes (`classify_signer_exit` + verification):

| Outcome | When | Burn |
| --- | --- | --- |
| `A_NO_SIGNATURE` | STOP before the invocation, or the signer exits 2 with one `REFUSED` line and empty stdout (every exception in the owner tool's `try` — key load, wrong passphrase, input checks, the signature itself — exits there; the stdout write is outside that `try`) | none |
| `B_SIGNED_PENDING_OWNER_ACCEPTANCE` | exit 0 with output that passes §10 | none; technical `REGISTRY_SIGNED` |
| `C_SIGNED_INVALID_BURN` | exit 0 but §10 fails; or later the owner rejects it | known burn, `digestSource SIGNED_OUTPUT` |
| `D_SIGNATURE_UNCERTAIN_BURN_FROZEN` | any other result after the invocation (signal, traceback, partial or lost output, Ctrl-C at the prompt) | known burn of the **pre-sign frozen** digest |
| `E_UNKNOWN_REAL_REGISTRY_BURN` | a signed candidate existed and neither its output nor the manifest digest can be recovered | `UNKNOWN_REAL_REGISTRY_BURN` tombstone, `registryDigest: "UNKNOWN"` |

D is deliberately conservative: when it is uncertain whether a signature
escaped, the frozen digest is burned. Burning a never-signed digest costs only
the candidate.

**Records** (`mb3_registry_ceremony`): `LILITH_REAL_REGISTRY_V1_BURN` (digest,
digest source, case, control SHA, manifest SHA-256, time,
`PERMANENTLY_BURNED`, `neverInstall`, `neverResign`) and
`UNKNOWN_REAL_REGISTRY_BURN` (failure window, provenance, never a digest).
`append_burn` and `register_extends` enforce append-only history. **No real
burn exists, and the canonical burned set is unchanged (20).** A real burn is
recorded in the external evidence, and the canonical set is updated by a
separately reviewed change **before** any replacement candidate.

## 14. Owner acceptance (separate; TEMPLATE ONLY)

After technical `REGISTRY_SIGNED` and an independent laptop PASS:

> I accept M-B3 / `SIGN_REGISTRY_V1` as completed for the current DEV_SYNTHETIC
> bootstrap. I accept the K-ROOT-signed Registry V1 with registry digest
> `<REGISTRY_DIGEST>` as the M-B3 artifact. The S25 copy is authoritative.
> Only these exact bytes are eligible for a later M-B4/M-B5. This acceptance
> does not authorize M-B4/M-B5, registry installation or effectiveness,
> genesis, record 1, First Memory, PROD activity, or any later step.
> `FRESHNESS=UNKNOWN` remains unchanged.

A rejection instead is case C: the digest is burned and never installed.

## 15. Boundaries

```text
MB3_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW
MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST
BUNDLE NOT BUILT; BUNDLE SHA-256 RECORDED OUTSIDE THE BUNDLE AFTER MERGE
PHONE-SCRIPT SHA-256 db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54
SIGNER UNCHANGED; NO RUNTIME, SEQUENCER, KEYGEN, INSTALLER OR WORKFLOW CHANGE
PREPARE NEVER ACCESSES K-ROOT; SIGN INVOKES THE SIGNER EXACTLY ONCE
NO SCRIPT FLAG, PROMPT, TOKEN OR MANIFEST IS AUTHORIZATION
M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED
M-B4/M-B5 / INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
REGISTRY EFFECTIVENESS = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT ACCESS; NOTHING SIGNED
```
