# Slice 15B2b-B1b-3e — M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY`: Repository Remediation (G-1 … G-7)

Status:

- **REPOSITORY REMEDIATION. SOURCE AND DESIGN ONLY (2026-10-06/07).**
  - Done under the owner's repository-only authorization of control
    `69dc8373ef64bbff9fd1e334a144203cff53a78f`.
  - It follows the read-only M-B4/M-B5 preflight, which returned
    `READY_FOR_OWNER_MB4_MB5_DESIGN_DECISION` (execution not ready, G-1 … G-7).
  - It implements the [owner design decision](slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md).
- **Closed in source:**
  - G-1 / G-2: governed derivation tooling; three representation pins,
    derived three times and byte-identical;
  - G-3: tests for the installer stages;
  - G-4: a read-only pre-ledger content verifier;
  - G-6: crash-window classification and a bounded remove-before-M-B6
    tool;
  - G-7: the documentation erratum.
- **Prepared only:** G-5. The continuity model is **PROPOSED, not accepted**
  (§8). A separate explicit owner decision is required.
- **Unchanged:** the installer, the runtime, the sequencer, the release
  file set, the workflows, and every accepted record's original text.
- Nothing installed. No DEV, S25 or GCP contact; no K-ROOT or K-WIT private
  material accessed; nothing staged, committed or pushed by this work.
- M-B4, M-B5, `INSTALL_TRUST_AND_REGISTRY`, genesis, record 1, First Memory
  and PROD remain **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.

```text
source remediation != execution readiness != owner go
derivation != installation;  content verifier PASS != owner acceptance
TRUST_INSTALLED candidate != registry effective != authority active
removal tool exists != removal authorized;  removal != reset
continuity PROPOSED != continuity ACCEPTED
```

## 1. Files

| File | Kind | Purpose |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb4_mb5_installable_inputs.py` | new, control tooling (offline, owner laptop) | G-1/G-2: governed derivation of the three installable representations from the accepted M-B3 export; `derive`, `check`, `check-files` |
| `services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py` | new, control tooling (DEV, read-only, root, release interpreter) | G-4: content evidence `anchorsEqualOwnerCopies`, `witnessAnchorNamesKWit`, `registryVerifiesOnHost`; crash-window phase |
| `services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py` | new, control tooling (DEV, root, stdlib only) | G-6: bounded removal of the three public install files, before M-B6 only; `plan`, `remove <planDigest>` |
| `services/owner-memory-control/tests/test_b1b3e_mb4_mb5_installable_inputs.py` | new tests | derivation rules, fail-closed cases, pins; real-export pin proof when `LILITH_MB3_EXPORT` is set |
| `services/owner-memory-control/tests/test_b1b3e_mb4_mb5_install_stages.py` | new tests | G-3 installer P1B-4/P1B-5; G-4 verifier; G-6 crash windows and removal |
| `services/owner-memory-control/tests/test_b1b3e_mb4_mb5_remediation_records.py` | new tests | semantic pins of these records and the authority boundary |
| [owner decision](slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md) | new record | the three derivation rules |
| this record | new record | remediation, verifier semantics, crash model, PROPOSED continuity |
| [PR-1 live-install preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md) §27 | erratum (G-7) | the M-B5 row no longer says "`current` pointer"; the erratum is noted below the table |
| `README.md` index, acceptance ledger §13.1aa / AUTH-02, [M-B3 completion](slice-15b2b-b1b3e-mb3-registry-sign-completion.md) pointer | status text | discoverability; original text preserved |

The tools sit in `services/owner-memory-control/tools/` next to the M-B3
tooling, not in `services/authority-dev/`. That tree has an exact release
file-set contract (`release_file_set.py`), and the installer is pinned at
`fe10d9a3…5487`. Both stay unchanged.

## 2. Gap status

| Gap | Preflight finding | Status | Where |
| --- | --- | --- | --- |
| G-1 | Registry V1 transport = JCS + LF; installer/runtime need exact JCS | **CLOSED IN SOURCE** (owner rule + derivation + pin) | owner decision §2; §3 |
| G-2 | root and witness anchors: no installable form, no pin | **CLOSED IN SOURCE** | owner decision §3–§4; §3 |
| G-3 | zero tests for `stage_install_anchors` / `stage_install_registry` / P1B-4 / P1B-5 | **CLOSED** | §4 |
| G-4 | no producer of the three content evidence items | **CLOSED IN SOURCE** (not yet run live; needs its own authorization) | §5 |
| G-5 | no continuity decision, ceremony package, transport/cleanup, go templates | **PREPARED, OPEN**: model PROPOSED (§8); owner decision, package pins and runbook still needed | §8, §9 |
| G-6 | crash windows unclassified; no reviewed removal | **CLOSED IN SOURCE** (classification + bounded tool; running it needs separate authorization) | §6 |
| G-7 | preflight §27 "`current` pointer" error | **CLOSED** (erratum) | §7 |

## 3. Derivations (G-1, G-2)

### 3.1 Sources and pins

The only input is the accepted M-B3 public export:
`lilith-mb3-export.tar`, SHA-256 `c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8`,
phone = laptop. The tool reads exactly five members from it, without
extracting it, and pins each one:

| Member | SHA-256 (accepted) |
| --- | --- |
| `lilith-mb3-registry-public/authority-registry.v1.json` (signed transport) | `3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156` |
| `lilith-mb3/mb3-inputs.json` (frozen manifest) | `9ce94816a28cac159b768f998d072c829b4a7fdd36d1dba3b88c2e57572aa319` |
| `lilith-mb3/inputs/root-anchor.json` (E-21 wrapper) | `300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f` |
| `lilith-mb3/inputs/kact-publication.json` | `d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032` |
| `lilith-mb3/inputs/kwit-publication.json` | `9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472` |

The export's `witness-anchor.json` (`5e2bb7c9…1959`, JCS + LF) is **not** a
source. It is used only as a consistency cross-check against the M-B3
manifest's `witnessAnchorSha256`.

### 3.2 Schemas used

| Document | Schema (reviewed, unchanged) | Fields |
| --- | --- | --- |
| E-21 wrapper | `mb3_registry_ceremony.verify_root_anchor_bytes` (the `root-keygen` output) | exactly `{registryRoot, publicKeySha256}`, JCS + LF |
| root anchor | `authority_contracts.TrustedRegistryRootV1` / `TRUSTED_ROOT_FIELDS`; installer `ANCHOR_SHAPE` | `{schemaVersion: 1, rootKeyId, environment: "dev", algorithm: "Ed25519", publicKey}` |
| K-WIT publication | `pr1_bootstrap.parse_publication_document` / `WitnessKeyPublicationV1` via `mb3_registry_ceremony.verify_kwit_publication_bytes` | `LILITH_WITNESS_KEY_PUBLICATION`, `DEV_SYNTHETIC` |
| witness anchor | `pr1_bootstrap.witness_anchor_document` → `recovery_contracts.TrustedWitnessAnchorV1` / `ANCHOR_FIELDS`; installer `ANCHOR_SHAPE` | `{schemaVersion: 1, witnessKeyId, environment: "dev", algorithm: "Ed25519", publicKey}` |
| Registry V1 | `authority_contracts.REGISTRY_FIELDS` / `REGISTRY_SIGNED_FIELDS`; `rotation_contracts.registry_digest`; `authority_verifier.verify_authority_registry`; installer `REGISTRY_SHAPE` | unchanged signed document |

### 3.3 Checks (fail closed; any failure = `STOP <code>`, exit 1)

**Every representation:**
- strict parse: ASCII only, no duplicate keys, no floats, no NaN/Infinity;
- `rfc8785.dumps(value)` must equal the installer's form
  `json.dumps(sort_keys, separators, ensure_ascii)`;
- `witness_readiness.parse_document_bytes` (the runtime) must accept the
  bytes;
- `environment == "dev"`;
- no trailing newline.

**Registry V1:**
- all five member pins;
- the accepted M-B3 verification `verify_signed_registry` over the
  unchanged transport. This covers the E-21 signature, the frozen manifest
  digest and unsigned fields, K-ACT as the single current key, and K-WIT
  absent;
- the transport ends in LF, contains exactly one LF and no CR, and the byte
  before the LF is `}`;
- R = transport minus that byte, and JCS(parse(R)) == R;
- `registry_digest(R) == fa662721…14fc`;
- the signed fields equal the manifest's frozen `unsignedRegistrySha256`;
- `verify_authority_registry` under E-21 passes again over R;
- parse(transport) == parse(R), so no semantic change.

**Root anchor:**
- the wrapper pin, then `verify_root_anchor_bytes`. That proves the
  wrapper's exact field set and canonical form, that the `publicKeySha256`
  check value equals the recomputed key hash equals E-21, the accepted
  keyId, `dev` and `test-only.`;
- extract only `registryRoot`. Its field set must equal
  `TRUSTED_ROOT_FIELDS`, with `schemaVersion` 1 and `algorithm` `Ed25519`;
- the derived anchor's key hash must equal E-21, the wrapper value and the
  wrapper key.

**Witness anchor:**
- the publication pin, then `verify_kwit_publication_bytes`. That checks
  the SHA, the fingerprint recomputed from the key, the keyId, the blob
  and `dev`;
- build `witness_anchor_document`, then `TrustedWitnessAnchorV1` with the
  accepted keyId and the fingerprint `5d778701…0bdf`;
- after derivation: SHA-256(anchor + LF) must equal the M-B3 manifest's
  `witnessAnchorSha256`;
- K-ROOT, K-WIT and K-ACT keys are pairwise distinct.

### 3.4 Derived representation pins

| Installable file (install target) | Representation SHA-256 | Bytes |
| --- | --- | --- |
| `registry-root.json` (`/etc/lilith-authority-dev/trust/registry-root.json`) | `bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687` | 179 |
| `witness-anchor.json` (`/etc/lilith-authority-dev/trust/witness-anchor.json`) | `be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a` | 176 |
| `authority-registry.v1.json` (`/etc/lilith-authority-dev/registry/authority-registry.v1.json`) | `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` | 955 |

These are representation pins only. They are pinned in code (`DERIVED_SHA256`,
`ACCEPTED_PINS`), and a test keeps the two copies equal.

### 3.5 Deterministic duplicate derivation (off-host, public bytes only)

All runs were in a local WSL Ubuntu 24.04 environment with the repository
tree and the export copied in fresh. The export was taken from the owner's
external attempt-2 evidence set, read-only; its hash re-verified as
`c4ea3d66…64d8`. Nothing was installed or sent anywhere.

| Run | How | Result |
| --- | --- | --- |
| A | `mb4_mb5_installable_inputs.py derive` in a fresh tree | exit 0; all 12 tokens |
| B | the same tool in a second, separately extracted tree, separate process | exit 0 |
| C | an **independent** implementation using no repository library (stdlib + `rfc8785` + `cryptography` only): it re-checks the pins, the single LF, JCS, the digest, the wrapper form and E-21, raw Ed25519 under E-21, the K-WIT fingerprint and scope, and key distinctness, then serializes on its own | `INDEPENDENT_DERIVATION_C_PASS`; signature verified under E-21; digest `fa662721…14fc` |

Comparison: for each of the three files, A = B = C. `cmp` showed them
byte-identical, with the SHA-256 values in §3.4.

Further proofs from the same runs:

- **Registry.** The installable file equals the transport file minus its
  last byte (`0x0a`), checked with `head -c -1 | cmp`. The transport file
  still hashes to `3f0a59c0…6156`, unchanged.
- **Witness anchor.** The installable file equals the M-B3-frozen
  `witness-anchor.json` minus its LF.
- **Real export.** `RealExportTests` (run with `LILITH_MB3_EXPORT` set)
  re-derives the pins. It checks:
  - E-21 recomputes from the root anchor's key;
  - K-WIT recomputes from the witness anchor's key;
  - the registry digest is unchanged;
  - the unchanged installer `_canonical_document` accepts all three bytes.

### 3.6 Using the tool (no authorization implied)

```text
mb4_mb5_installable_inputs.py check <export.tar>         # re-derive; compare to the pins -> MB4_MB5_INSTALLABLE_INPUTS_VERIFIED
mb4_mb5_installable_inputs.py derive <export.tar> <new>  # write the three files into a NEW 0700 directory (O_EXCL)
mb4_mb5_installable_inputs.py check-files <dir>          # exactly the three pinned files, nothing else
```

## 4. Installer stage coverage (G-3)

`test_b1b3e_mb4_mb5_install_stages.py` uses the existing PR-1S `FakeHost`
on a temporary root. It brings the host to `status --expect P1B-2` (the
full PR-1A ladder plus a stand-in K-WIT blob) and runs the **unchanged**
installer:

| Covered | How |
| --- | --- |
| `stage_install_anchors` / P1B-4 status | PASS with the derived anchors; installed bytes = derived bytes, regular, `0644`; P1B-4 PASS |
| `stage_install_registry` / P1B-5 status | PASS after anchors; installed bytes = derived bytes; P1B-5 PASS; P1B-4 then FAIL (stage-exact); P1B-6 / P1B-8 FAIL (nothing later exists) |
| ordering | `install-registry` before `install-anchors` → `PRECONDITION_FAILED` |
| canonical-byte rejection | anchors + LF and the signed transport file → `INPUT_DOCUMENT_NOT_CANONICAL`; the E-21 wrapper → `INPUT_DOCUMENT_MALFORMED`; `prod` → `INPUT_DOCUMENT_MALFORMED`; swapped anchors → `ANCHOR_SHAPE`; a non-registry document → `REGISTRY_SHAPE`; every refusal writes nothing (P1B-2 still PASS) |
| write-once / pre-existing file | re-running either stage → `PRECONDITION_FAILED`; a planted anchor or registry blocks `install-anchors` |
| partial writes | W1, W2 and W4 partial files block every re-run (§6) |
| wrong content passes shape | a foreign TEST key's anchors pass P1B-4, but the content verifier refuses them (§5) |

Wrong source pins and wrong key identity or fingerprint are covered at the
derivation layer (`test_b1b3e_mb4_mb5_installable_inputs.py`). That
includes: each wrong member pin; a wrong digest; LF variants (none, two,
CRLF, trailing space, inner whitespace); a changed field; a forged
signature; wrapper check-value, field-set, keyId and `prod` changes; a
non-E-21 key; and a wrong K-WIT key or keyId.

## 5. Read-only pre-ledger content verifier (G-4)

`mb4_mb5_trust_install_verifier.py` runs on DEV as root, under the
installed release interpreter. It imports only the selected release tree
(`/opt/lilith-authority-dev/current`), and is streamed like the installer:

```text
... | sudo /opt/lilith-authority-dev/current/venv/bin/python -I -B - observe
... | sudo /opt/lilith-authority-dev/current/venv/bin/python -I -B - expect <PHASE>
```

**It reads:**
- `lstat` and listings of `/etc/lilith-authority-dev/{trust,registry,owner}`;
- bounded `O_NOFOLLOW` reads of the three public files;
- the release runtime reader `lilith_authority_host.inputs.read_host_inputs`;
- `lexists` of `/var/lib/lilith-authority-dev` and
  `/var/lib/lilith-recovery-witness`.

**It never:**
- opens a credential, the credstore, the host key or the K-WIT blob;
- writes, chmods, removes, starts, reloads, signs or contacts anything.

A test proves the host tree is identical before and after a run. Running it
on DEV needs its own owner authorization.

**The three evidence items** (each `True` only from observed content):

| Evidence | `True` iff |
| --- | --- |
| `anchorsEqualOwnerCopies` | both anchor files are regular, `root:root 0644`, and their exact bytes hash to the owner-derived pins `bc5f00a7…f687` / `be360da2…ab5a`. The trust directory lists exactly these two names. The runtime reader parsed both (no `*_ANCHOR_MISSING/INVALID`, no environment mismatch), and the bytes it read hash to the same pins |
| `witnessAnchorNamesKWit` | the anchor parsed by the runtime has keyId `test-only.witness.dev-synthetic.b1b3d.1`, environment `dev`, and a public-key hash of `5d778701…0bdf`. Its key is none of the authority keys: not the installed root, not any installed registry key |
| `registryVerifiesOnHost` | the registry file is exact (`46b0bfc5…8b1e`, `root:root 0644`) and is the only entry. `anchorsEqualOwnerCopies` holds. The runtime reader returns exactly one registry. Its `registry_digest` is `fa662721…14fc`. `verify_authority_registry` passes under the **installed** root anchor, whose key hash is E-21 and keyId is the accepted root keyId, with E0 `(1, 11f18488…)` and `policy.dev-synthetic.v1`. It has `registryVersion` 1 and `dev`. Its single key is K-ACT (`dd13a1fb…01ed`, the accepted keyId), distinct from K-WIT. The remaining host-input reasons are only `GENESIS_PIN_COPY_MISSING` and `AUTHORIZATION_REGISTER_COPY_MISSING`, which M-B8 installs |

The installer `status` stays the owner of the path/mode contract.

**Phase:** `W0` … `W5` (§6), `UNEXPECTED_STATE`, or
`OUT_OF_SCOPE_POST_LEDGER`. `trustInstalledCandidate` is `True` only at
`W5_INSTALLED_CONTENT_VERIFIED`. `registryEffective` and `authorityGranted`
are always `False`. A verified result is technical evidence for the
sequencer's `INSTALL_TRUST_AND_REGISTRY` evidence. It is not owner
acceptance and it authorizes nothing.

## 6. Crash windows and bounded removal (G-6)

The installer writes each file with `O_EXCL`, then `write`, `fsync`, and a
directory `fsync`. It writes the root anchor, then the witness anchor, then
(M-B5) the registry. It is not atomic.

| Window | On-host state | Verifier phase | Class | Recovery |
| --- | --- | --- | --- | --- |
| W0 | nothing written (REGISTRY_SIGNED) | `W0_PRE_INSTALL` | SAFE_RETRY | the same stage, under the same go if it was never invoked; otherwise a new authorization |
| W1 | root anchor absent-or-partial, witness anchor absent | `W1_ROOT_ANCHOR_INCOMPLETE` | MANUAL_RECOVERY_REQUIRED | every re-run refuses (`PRECONDITION_FAILED`). Owner-authorized bounded removal, then `status --expect P1B-2` PASS, then a fresh re-proof and a new M-B4 go |
| W2 | root anchor exact, witness anchor absent-or-partial | `W2_WITNESS_ANCHOR_INCOMPLETE` | MANUAL_RECOVERY_REQUIRED | as W1 |
| W3 | both anchors exact, registry absent (P1B-4 PASS) | `W3_ANCHORS_INSTALLED_REGISTRY_ABSENT` | RECOVERABLE_INCOMPLETE | M-B5 with the same pinned bytes, after a fresh re-proof (§8), or bounded removal |
| W4 | both anchors exact, registry present but not exact (partial, or other bytes) | `W4_REGISTRY_INCOMPLETE` | MANUAL_RECOVERY_REQUIRED | bounded removal (all present files, back to W0); a new attempt needs new authorization |
| W5 | all three exact (P1B-5 PASS) | `W5_INSTALLED_CONTENT_VERIFIED` or `…_NOT_VERIFIED` | success candidate / STOP | verified: the owner reviews for acceptance. Not verified: STOP, investigate; removal only under separate authorization |
| — | a registry without both exact anchors, an extra entry, or a wrong-key anchor | `UNEXPECTED_STATE` | STOP | owner investigation; removal only if within the tool's bound |
| — | `/var/lib/lilith-authority-dev`, `/var/lib/lilith-recovery-witness` or an owner input exists | `OUT_OF_SCOPE_POST_LEDGER` | outside M-B4/M-B5 | no M-B4/M-B5 recovery applies; the removal tool refuses |

**Bounded removal** (`mb4_mb5_remove_before_mb6.py`, stdlib only,
streamed with `/usr/bin/python3 -I -B`) implements the PR-1 ledger's "remove
(nothing binds it yet)".

**`plan` (read-only) refuses unless:**
- the host is DEV and the caller is root;
- the host is pre-ledger: both `/var/lib` state paths are absent and the
  owner-input directory is empty;
- the trust and registry directories are `root 0755` and hold only the
  three known names;
- every present target is a regular, root-owned, bounded file (not a
  symlink).

It prints the exact files (SHA-256, size, mode, inode) and a `planDigest`.

**`remove <planDigest>`:**
- re-plans and refuses `PLAN_CHANGED` on any difference;
- unlinks only the present targets, in the order registry, witness
  anchor, root anchor, with a directory `fsync` after each;
- re-plans and requires none left (`PRE_INSTALL_RESTORED`).

It never removes a directory or any other path. A test proves every other
path is byte-identical.

**What removal does not do.** It is not a reset:
- the sequencer has no backward transition;
- a consumed M-B4/M-B5 go stays consumed;
- **the K-WIT burn/regenerate option, closed at M-B4, does not reopen**;
- a new attempt needs new owner authorization and a fresh re-proof.

Running the tool needs a separate explicit owner authorization.

## 7. G-7 erratum

Preflight §27, row M-B5, said "install registry v1 + `current` pointer".
No pointer exists:
- the installer installs only `authority-registry.v<N>.json`, and its
  listing check rejects any other name;
- the runtime reader (`inputs.py`) states "registry storage != accepted
  registry head (the witness decides the head)". The head is decided by the
  witness at M-B9b.

The row now reads "install registry v1 (`authority-registry.v1.json`; no
pointer — the witness decides the head at M-B9b)". An erratum note sits
below the table. The original wording is quoted there.

## 8. M-B4/M-B5 continuity: PROPOSED (not accepted)

```text
MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO   (PROPOSED)
```

**Meaning, as proposed by the owner:**

1. One fresh evidence sequence.
2. A separate explicit one-attempt **M-B4 go**.
3. M-B4 POST and content verification must pass (`W3`;
   `anchorsEqualOwnerCopies` and `witnessAnchorNamesKWit` `True`).
4. Hard stop.
5. A separate explicit one-attempt **M-B5 go**.
6. Interruption or relevant drift requires a fresh re-proof.
7. The M-B4 authorization must explicitly acknowledge that the K-WIT
   burn/regenerate option closes at M-B4 (C-3; preflight F-4).

**Status: PROPOSED ONLY. A separate explicit owner decision is required.**
Repository precedent recorded each earlier step's continuity model as its
own owner decision before execution:
- [M-B1](slice-15b2b-b1b3e-mb1-sequence-continuity-owner-decision.md);
- [M-B2](slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md);
- [M-B3](slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md).

Documenting the proposal here neither executes nor activates it.

**Matters the continuity decision must settle** (not decided here):
- fresh evidence before the sequence: control; deployment relationship and
  freeze; DR-5; boot and broker preservation; K-ACT CURRENT; K-WIT
  preserved; installer `status --expect P1B-2`; exposure, IAM and topology;
  B-5 §9 / G-1 … G-9;
- the owner register `KNOWN_EMPTY` (fresh Replica A plus an owner-run S25
  Replica B read), required by `REQUIRED_UNKNOWN_BLOCK`;
- the owner's E-21 re-confirmation (B-4 §2);
- whether a full PR-2 is required;
- transport: the three files staged via `check-files`, the streamed
  installer and verifier, staging path and cleanup;
- the terminators;
- post-step DR-5 and preservation;
- acceptance.

## 9. Remaining blockers before M-B4/M-B5 preparation

1. **This remediation must be reviewed and merged.** It is uncommitted.
2. **The continuity decision (§8)** must be recorded as a separate explicit
   owner decision.
3. **A ceremony package and runbook** must be reviewed and merged, and pins
   recorded from merged `main`. It covers:
   - streamed installer `fe10d9a3…5487`, verifier and removal-tool hashes;
   - staging and cleanup paths for the three files;
   - pre/post gates;
   - verifier `expect W0` before, `expect W3` after M-B4, and
     `expect W5_INSTALLED_CONTENT_VERIFIED` after M-B5;
   - go templates for both one-attempt gos.
4. **Release interpreter and module presence** on DEV must be observed
   read-only before relying on the verifier:
   - `/opt/lilith-authority-dev/current/venv/bin/python`;
   - `lilith_authority_host` and the pinned shared contracts of `aee323e`.
5. **ADR-0015 classification** of the two DEV deploys after the M-B3 window
   (`37506016808` at `1fb73e0`, the `sharp` dependency update;
   `37507920435` at `69dc837`).
6. **Optional, recommended:** extend DR-5 and the custody denial proof to
   the three new files (preflight gap G-9). Today they cover the
   directories only.
7. The owner-run S25 read (Replica B) and the owner E-21 re-confirmation
   are owner actions inside an authorized sequence. They are not
   repository work.

## 10. Validation

All runs were in WSL Ubuntu 24.04 (Python 3.12) with the pinned wheels
(`cryptography` 50.0.1, `rfc8785` 0.1.4, `fido2` 2.2.1), on a fresh copy of
the working tree. `LILITH_MB3_EXPORT` pointed at a copy of the accepted
public export.

| Check | Result |
| --- | --- |
| `test_b1b3e_mb4_mb5_installable_inputs` | 14/14 OK, including `RealExportTests` (the real pins re-derived) |
| `test_b1b3e_mb4_mb5_install_stages` | 10/10 OK |
| `test_b1b3e_mb4_mb5_remediation_records` | 13/13 OK (also OK on Windows, stdlib only) |
| full `services/owner-memory-control/tests` (`discover`) | **973 tests OK** (6 skipped) |
| full `services/authority-dev/tests` (`discover`) | **241 tests OK** |
| `compileall` of `lilith_owner_memory` and `tools` | OK |
| `scripts/validate_repository.py` | passed |
| existing test adjusted | `test_b1b3e_mb3_registry_sign_completion.test_pointers_ledger_and_index`: it pinned the AUTH-02 cell ending exactly at `(§13.1z)` followed by the owner cell `UNASSIGNED`. It now requires `(§13.1z)` inside the AUTH-02 row and the row still ending with the `UNASSIGNED` owner cell, so later reconciliation passes can append (§13.1aa) |
| unchanged | `git diff` shows no change under `services/authority-dev/`, `services/recovery-witness/`, `services/core-api/`, `.github/`, or to any `lilith_owner_memory` module, tool, sequencer or installer that existed before |

## 11. State

```text
REPOSITORY REMEDIATION (SOURCE / DESIGN ONLY) FOR M-B4/M-B5
G-1 CLOSED IN SOURCE; G-2 CLOSED IN SOURCE; G-3 CLOSED; G-4 CLOSED IN SOURCE; G-5 PREPARED / OPEN; G-6 CLOSED IN SOURCE; G-7 CLOSED
REGISTRY_V1_INSTALLABLE_SHA256 = 46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e
ROOT_ANCHOR_INSTALLABLE_SHA256 = bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687
WITNESS_ANCHOR_INSTALLABLE_SHA256 = be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a
DERIVED THREE TIMES (TOOL x2, INDEPENDENT x1); BYTE-IDENTICAL
REGISTRY_V1_DIGEST = fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc (UNCHANGED; E-21 SIGNATURE VERIFIES)
SIGNED_TRANSPORT_FILE_SHA256 = 3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156 (PRESERVED UNCHANGED)
MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO (PROPOSED; NOT ACCEPTED; SEPARATE OWNER DECISION REQUIRED)
INSTALLER / RUNTIME / SEQUENCER / RELEASE FILE SET / WORKFLOWS UNCHANGED
TRUST_INSTALLED = NO
REGISTRY_INSTALLED = NO
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
M-B4 = NOT AUTHORIZED
M-B5 = NOT AUTHORIZED
INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
VERIFIER RUN ON DEV = NOT AUTHORIZED
REMOVAL TOOL RUN = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT PRIVATE MATERIAL ACCESSED
```

> **Later current state (2026-10-07, pointer only; the text above is
> preserved as written).** The owner accepted the continuity model proposed
> in §8 as `MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO`
> ([continuity owner decision](slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md)),
> closing G-5 in governance. The reviewed
> [ceremony package](slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md) carries
> the runbook, pins and go templates. Nothing is installed. The preparation
> sequence, M-B4, M-B5, genesis, record 1, First Memory and PROD remain NOT
> AUTHORIZED, and FRESHNESS is UNKNOWN.
