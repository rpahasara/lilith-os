# Slice 15B2b-B1b-3e — Package A: M-B7 `PREPARE_GENESIS_CANDIDATE` + M-B8 `PIN_GENESIS` (Design, Tooling and Runbook)

Status:

- **PACKAGE A DESIGN / IMPLEMENTATION REVIEW (REPOSITORY ONLY), 2026-10-08.** Control:
  `e6fde13a54384c63016b3591beed18cb1a505e24`. `MB7_MB8_PACKAGE_READY_FOR_REVIEW`.
- **Owner batching direction (2026-10-08):** package M-B7 and M-B8 together, with explicit and separate authority
  and result boundaries. M-B7 is classified on its own. M-B8 never runs only because M-B7 output exists.
  Package A implies nothing about M-B9.
- **Owner decisions OD-1 … OD-5 (2026-10-08) are applied** (§19). The continuity (§9), the `MB7_MB8_UPDATED_AT`
  capture rule (§3.1), the P-A / P-B owner records (§5.1), the DR-5 rule (§7) and the M-B7 scratch-copy
  classification (§3) are owner-accepted **design rules only**.
- **Nothing here authorizes anything.** Each of these needs its own explicit owner act: ACT 1, the sequence
  authorization (§14.1); ACT 2, the GENESIS_PREPARED acceptance and P-A / P-B record authorization (§14.2); ACT 3,
  the M-B8 host-install go (§14.3); a removal (§14.4); and the Package A acceptance (§16). M-B7 and M-B8 are
  **NOT AUTHORIZED**.
- Repository and off-host only. This slice contacted no DEV, GCP or S25 system and touched no K-ROOT, K-WIT or K-ACT
  material.

```text
package reviewed != sequence authorized != M-B7 technical PASS != GENESIS_PREPARED accepted != M-B8 go
  != M-B8 POST verified != Package A accepted != M-B9a authorized
candidate != pin != committed genesis;  on-host pin copy != owner pin (P-A, P-B)
one M-B8 go = exactly one `install-owner-inputs`; no automatic retry
```

## 1. Canonical discovery: implementation map

The high-level map matches the canonical repository. No material difference was found, so the design was not
stopped.

**Sequencer** (`services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py`, `STEPS`):

| Step | Transition | Row | Freshness gate | Evidence | PONR |
| --- | --- | --- | --- | --- | --- |
| `PREPARE_GENESIS_CANDIDATE` | `LEDGER_PROVISIONED` → `GENESIS_PREPARED` | M-B7 | `NOT_APPLICABLE_PRE_GENESIS` | `hostCandidateDigestEqualsOwnerDigest` | none |
| `PIN_GENESIS` | `GENESIS_PREPARED` → `GENESIS_PINNED` | M-B8 | `REQUIRED_UNKNOWN_BLOCK` (owner register `KNOWN_EMPTY`) | `pinStoredOffHostTwoCopies`, `onHostPinCopyEqualsOffHost`, `pinEqualsCandidateDigest` | `RECORD` |
| `START_WITNESS` | `GENESIS_PINNED` → `WITNESS_STARTED` | M-B9a | `REQUIRED_UNKNOWN_BLOCK` | `witnessStoreUninitialized`, `witnessNotEnabled` | none |
| `COMMIT_WITNESS_GENESIS` | `WITNESS_STARTED` → `WITNESS_GENESIS_COMMITTED` | M-B9b | `BOOTSTRAP_SPECIAL_CASE` | `pinEqualsCandidateDigest`, `committedDigestEqualsPin`, … | `LINEAGE` |

Crash matrix: C-8 "ledger provisioned / candidate not prepared" `SAFE_RETRY` (read-only step); C-9 "candidate
prepared / pin absent" `SAFE_RETRY`; C-10 "pin stored / witness not started" `SAFE_RETRY`; C-12 "committed genesis
differs from pin" `REBOOTSTRAP_FORBIDDEN`.

**M-B7 code path (host).** `/usr/local/sbin/lilith-authority-verify-dev genesis-candidate <registryVersion>
<updatedAt>` (release wrapper `cli/lilith-authority-verify-dev`, SHA-256 `bc331636…00a4`) →
`lilith_authority_root.cli._verify` → `lilith_authority_root.genesis.candidate`:

1. `lilith_authority_host.inputs.read_host_inputs` (anchors, registries, owner copies);
2. `lilith_authority_dev.ledger.observe_copy` (a private scratch copy of the ledger; see C-1);
3. `lilith_owner_memory.pr1_bootstrap.build_genesis_candidate`, which re-verifies Registry V1 under the installed
   root anchor and refuses unless the ledger sits at exactly sequence 1 with the registry-implied head;
4. `genesis.candidate_report` → one JSON line on stdout.

The release code on this path is unchanged between `aee323e` (installed) and the control.

**M-B7 code path (owner, off-host).** `services/authority-dev/ceremony/lilith_authority_owner_dev.py reproduce
<registry> <registry-root> <witness-anchor> <updatedAt>` (PR-1S S-11, RR-38 B). The
[B-4 decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md) §2 requires it to run on the S25 too, with the
digest read on the phone screen.

**M-B8 code path.** `install_authority_dev.py install-owner-inputs <RELEASE_SHA> <genesis-pin> <register>`
(stage P1B-8, `stage_install_owner_inputs`). It requires `status --expect P1B-6` PASS. It checks both documents
(`_canonical_document`: ASCII, no floats, `environment = dev`, exact sorted-keys bytes) and their key sets. It then
installs `genesis-pin.json` and then `authorization-register.json` with `_install_once`. Each install is `_write_new`
(`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, `0644`, write, fsync, chown `0:0`, chmod `0644`) followed by an fsync of
`/etc/lilith-authority-dev/owner`. It returns `status --expect P1B-8`. There is no P1B-7 installer stage: M-B7 has
no host stage.

**Consumers of the two copies (all later than Package A).**

- `inputs.read_host_inputs`: the reasons `GENESIS_PIN_COPY_MISSING` / `_INVALID` and `AUTHORIZATION_REGISTER_COPY_MISSING` / `_INVALID`.
- Witness `BOOTSTRAP` (`writer.bootstrap`): `candidate_pin_reason` before signing, `genesis_pin_reason` after commit.
- `genesis.bootstrap` (`lilith-recovery-witness-owner-dev bootstrap`).
- Witness readiness `GENESIS_PIN`.
- `verify_authorization_history`: every chain head must be in `headRegistries`.

**Existing material reviewed.**

- Preflight §12, §22, §27 (M-B7 / M-B8 rows), §28, §29, §30.
- Sequencing record §4.5, §5.
- B-4 decision §2–§4.
- M-B6 remediation §14 / §15.
- The M-B4/M-B5 install-stage tests (owner-input partial file).
- The M-B6 tests (an owner copy is later state).
- `test_pr1s_root_tooling` (pin before commit through the witness).
- No unit, socket or tmpfiles file is touched by M-B7 or M-B8.

**Tools (Package A).** Each is pinned by its exact bytes. `mb7_mb8_operator.py pins <repo>` checks every pin and
re-checks each tool before it is streamed.

| Tool (repository path) | Where it runs | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb7_mb8_operator.py` | owner laptop (bound into each owner text) | `9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd` |
| `services/owner-memory-control/tools/mb7_genesis_candidate.py` | owner workstation, WSL (pinned wheels) | `d50fcb36afab51a79c7918a7a43c86f97338241f62144c780d8b342c68b3c8b2` |
| `services/owner-memory-control/tools/mb8_owner_input_verifier.py` | DEV, root, release interpreter (bundle with the W5 and M-B6 verifiers) | `b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341` |
| `services/owner-memory-control/tools/mb8_owner_input_removal.py` | DEV, root, `/usr/bin/python3 -I -B -` (streamed; §6.3 only) | `d9a6e0d5dcfb07558ca7533e8144b7f2b7c29b1b4db28400571aede55b99f7f5` |
| `services/owner-memory-control/tools/mb8_owner_input_denial_proof.py` | DEV, root, streamed (P1B-8) | `5d63137a2c6e43f12f663febdd4e22fd7b2b519a6c0cfa544dad12f0bc958517` |
| `services/owner-memory-control/tools/mb6_operator.py` | owner laptop (transport / marker helpers, reused unchanged) | `4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5` |
| `services/authority-dev/ceremony/lilith_authority_owner_dev.py` | owner workstation and S25 (`reproduce`, unchanged) | `49b82760dae20201172548d8d4802a3dc5436c58a1339982fc274b1a69b21c99` |
| `services/authority-dev/ceremony/install_authority_dev.py` | DEV, root (streamed; `status`, `install-owner-inputs`) | `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py` | DEV, root, release interpreter | `78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361` |
| `services/owner-memory-control/tools/mb6_ledger_verifier.py` | DEV, root, release interpreter (bundle) | `6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5` |
| `services/authority-dev/ceremony/observe_authority_dev_host.py` | DEV, root (streamed) | `a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf` |
| `scripts/verify_broker_dev_current_incarnation.py` | DEV, root (streamed; `preservation`) | `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba` |
| `scripts/authority_custody_denial_proof.py` | DEV, root (streamed; P1B-5, unchanged) | `f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455` |
| `services/owner-memory-control/tools/mb6_ledger_denial_proof.py` | DEV, root (streamed; P1B-6, unchanged) | `470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0` |
| `services/owner-memory-control/tools/mb6_dr5_target.py` | owner laptop (stdlib; §7) | `9978e3a791a829d6beace81ca0e4c6db9b1c154fbc56091f6312385d02632656` |
| `scripts/deployer_authority_boundary_proof.sh` (DR-5; the deploy workflow runs it) | DEV, routine deployer | `9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43` (unchanged) |

Release readiness (the `host` form) pins the same 38 release modules as M-B6 (`mb6_operator.RELEASE_MODULES` and
`PROVISION_MODULES`; the `genesis-candidate` path loads the same `lilith_authority_root.cli` closure), the ledger CLI
`fda779cd…c45b`, and the verify CLI `bc331636eedbbae22a53667aa230ba0672fb1e22b8a5bd4975ac9f8557a400a4`.

## 2. Contradictions and gaps (reported, not silently resolved)

| # | Finding | Package A handling | Owner decision needed? |
| --- | --- | --- | --- |
| C-1 | Preflight §27 says M-B7 is "none on host (read-only construction)". In code, `genesis-candidate` calls `observe_copy`. That creates a private `0700` scratch directory `lilith-ledger-observe.*` in the root process's temp directory (`/tmp`), copies the ledger (and any WAL) there, opens the copy with SQLite, and deletes it on exit. No LILITH authority path is written and the live ledger is opened only `O_RDONLY`. A killed process could leave a residue (a copy of the public ledger) | `MB7_TEMP_LEDGER_COPY = EPHEMERAL_SCRATCH_IO_ONLY`: M-B7 is persistent-state read-only with bounded ephemeral scratch I/O (§3). A leftover scratch copy fails the M-B7 gate. The operator checks for a residue after M-B7 and in every `host` read. The W8 verifier recomputes the same candidate in memory, as an independent cross-check | **OD-5 ACCEPTED** |
| C-2 | The preflight M-B8 row names only the pin. The installer installs both copies (erratum D-4 already records this) | M-B8 = both copies, pin first | no |
| C-3 | Preflight §27 allows "remove the copy (before M-B9b)". The sequencer marks `PIN_GENESIS` `PONR_RECORD`, and §29 says "owner genesis pin (M-B8): never silently replaced" | Not a conflict once the two objects are separated. The **on-host copy** is a protocol copy (B-4: "not an owner copy") and is removable. The **owner pin P-A / P-B** is the record PONR. The bounded removal (§6.3) is narrower: **before M-B9a only**, and never a new pin | no (records the reading) |
| C-4 | `BootstrapSequencerV1.reset()` refuses re-bootstrap after any PONR, including `PIN_GENESIS` (`RECORD`) | A removal re-installs the **same** pin; it is not a re-bootstrap. A different candidate after P-A / P-B exist is an owner re-bootstrap decision: STOP | no |
| C-5 | B-4: "No reviewed pin writer exists". P-A / P-B handling is procedural | `mb7_genesis_candidate.py record-p-a` is the reviewed create-only P-A writer; `check-copy` verifies each record file separately. P-B stays procedural (create-only copy, `sha256sum` on the phone screen). No phone writer is added | no |
| C-6 | **No record decides the off-host custody of the owner's `OwnerAuthorizationRegisterV1`.** Preflight §22 makes it PR-3 foundation; B-4 places only the pin copies | the register is kept, byte-identical, beside the pin in the P-A and P-B owner records (§5.1) | **OD-3 ACCEPTED** |
| C-7 | M-B8's `REQUIRED_UNKNOWN_BLOCK` (`KNOWN_EMPTY`) is a sequencer / procedure gate. Installer code does not check it (as at M-B6) | evidence E-A10 before the M-B8 go | no |
| C-8 | §13.1ai's going-forward rule compares deploys with `mb6_dr5_target.py compare LEDGER_COMMITTED_EXACT`, and that phase is selected from the M-B6 verifier. After M-B8 the M-B6 verifier reports `OUT_OF_SCOPE_LATER_STATE` (owner copies present), so that selection would give `NO_BASELINE_STOP` | the operator `dr5` form selects the **same accepted target** from an independently verified W8 phase (§7) | **OD-4 ACCEPTED** |
| C-9 | No record bounds `updatedAt`. Genesis accepts any well-formed instant. Every later witness successor refuses `WITNESS_TIME_REGRESSION` while its clock is earlier than `updatedAt` | `MB7_MB8_UPDATED_AT` capture rule (§3.1): owner-supplied once; the owner tool refuses a value before Registry V1 `issuedAt` (`2026-10-06T15:16:21Z`), after the owner's clock, or different from a recorded P-A pin | **OD-2 ACCEPTED** (the value: at the live sequence) |
| C-10 | `reproduce` reports `registryVerified` but does not require it, and does not pin its inputs | the Package A tool wraps `reproduce` unchanged. It adds input pins, requires a verified registry, the owner-accepted ledger head and K-WIT, and an independent restatement of the digest | no |
| C-11 | The pinned M-B6 operator's `O_EXCL` marker writes use a text-mode descriptor on Windows, which turns LF into CRLF. These are marker files only and harmless | the new tools add `O_BINARY`. The emitted install bytes are LF-only (tested) | no (M-B6 tool unchanged) |
| C-12 | `_write_new` fsyncs the data, then runs chown / chmod. The parent fsync follows. A crash in between can leave a file whose bytes are complete but whose mode is still the create mode (umask-dependent) | classified `PARTIAL` (W8-1 / W8-3), never `EXACT` | no |

## 3. M-B7 exact semantics

| # | Question | Answer (canonical) |
| --- | --- | --- |
| 1 | entry points | host: `sudo -n /usr/local/sbin/lilith-authority-verify-dev genesis-candidate 1 <updatedAt>`, exactly once per M-B7 run (operator `mb7`). Owner: `mb7_genesis_candidate.py emit`, which wraps `reproduce`. S25: `lilith_authority_owner_dev.py reproduce` (B-4) |
| 2 | read-only against DEV? | **persistent-state read-only with bounded ephemeral scratch I/O** (OD-5). No persistent LILITH path changes and the live ledger is opened only `O_RDONLY`; the scratch copy of C-1 is the only write |
| 3 | local / off-host artifacts | owner: `<workdir>/genesis/` (`genesis-pin.json`, `authorization-register.json`, `pin-record.json`, `expected-host-stdout.txt`, `candidate.json`, `SHA256SUMS`) and evidence directories. DEV: none persistent |
| 4 | writes anywhere? | DEV: bounded ephemeral scratch only (C-1). Laptop: the work directory. S25: none (the result is read on screen). P-A / P-B are written only after ACT 2, never by M-B7 |
| 5 | inputs | the owner-held accepted installables: Registry V1 `46b0bfc5…8b1e`, root anchor `bc5f00a7…f687`, witness anchor `be360da2…ab5a`. `MB7_MB8_UPDATED_AT` (§3.1). The owner-accepted ledger position (1, `19bf9091…1630`). On host: the same installed files and the provisioned ledger |
| 6 | output | one line: `{"authorityGranted":false,"candidateDigest":…,"genesis":false,"pin":{…},"unsignedGenesis":{…}}` followed by LF (sorted keys, no whitespace, ASCII). The owner tool predicts these bytes exactly (`expected-host-stdout.txt`) |
| 7 | canonicalization | `candidateDigest = SHA-256("LILITH_RECOVERY_WITNESS_V2\0" ‖ JCS(unsigned))` over the 14 signed fields (`witness_v2_signing_bytes`). `signature` is excluded, so K-WIT signing the exact body keeps the digest. The pin and register are stored as JCS bytes with no trailing LF (the installer form) |
| 8 | owner-computed / pinned | the candidate digest; the genesis-pin bytes and SHA-256; the register bytes and SHA-256; the expected host stdout SHA-256; `updatedAt`. All are pinned by being named in §14.2 / §14.3 and stored in P-A / P-B |
| 9 | ledger | binds `ledgerSequence = 1` and `ledgerHead = 19bf9091…1630`. Any other ledger position refuses (`GENESIS_LEDGER_NOT_INITIAL`, `GENESIS_LEDGER_HEAD_MISMATCH`) |
| 10 | Registry V1 | binds `registryVersion 1`, `registryDigest fa662721…14fc`, epoch `(1, 11f18488…)` and policy. The registry must verify under the installed root at its own epoch, with a single current key |
| 11 | K-ROOT / K-WIT / K-ACT | K-ROOT: public anchor only. K-WIT: key ID only (the fixed profile ID; the anchor must name it). K-ACT: only through the ledger `GENESIS` op's `signingKeyIds` and the registry. No private key |
| 12 | private keys touched? | **no.** K-ACT is not needed, so the "STOP if K-ACT is required" clause does not trigger |
| 13 | classification before | `LEDGER_PROVISIONED` (owner-accepted), host W8-0 |
| 14 | classification after success | technical `MB7_TECHNICAL_PASS`. `GENESIS_PREPARED` only after the owner's §14.2 statement. The host is still W8-0 |
| 15 | retry / idempotency | deterministic and read-only: `SAFE_RETRY` into a NEW evidence directory. The same `updatedAt` gives the same digest. A new `updatedAt` gives a different candidate and needs new owner texts |
| 16 | failure | stdout ≠ expected, CLI refusal, W8 not W8-0, or a residue: `MB7_NOT_PASS` and STOP for owner review. No candidate is accepted |
| 17 | recovery | none needed for persistent state. A leftover scratch copy fails the gate and is a STOP for owner adjudication; no tool deletes it |
| 18 | owner acceptance | ACT 2 (§14.2): binds the digest, `MB7_MB8_UPDATED_AT`, the host stdout SHA-256, the S25 equality and the three record SHA-256 values; recorded by `accept-b7` |

**OD-5 conditions** (`MB7_TEMP_LEDGER_COPY = EPHEMERAL_SCRATCH_IO_ONLY`). The scratch copy is acceptable only while all
of these hold, and they hold in the canonical code (`lilith_authority_dev.ledger._on_copy`):

- a private `0700` temporary directory (`tempfile.TemporaryDirectory`, then `chmod 0700`);
- created only for candidate verification (`genesis.candidate` → `observe_copy`);
- its source is the existing ledger, read `O_RDONLY | O_NOFOLLOW`;
- no persistent LILITH path is modified, the ledger is not mutated, and no canonical state is replaced;
- the directory is removed on normal exit, and the context manager attempts the removal on every error path;
- a successful technical M-B7 requires that no `lilith-ledger-observe.*` entry remains in `/tmp` (§13).

A process killed without cleanup can leave a copy. The M-B7 gate then does not pass: STOP for owner adjudication.

### 3.1 `MB7_MB8_UPDATED_AT` (OD-2)

- No value is hard-coded in the repository. The owner captures exactly one fresh UTC timestamp at the opening of
  the live sequence, before M-B7, and supplies it in ACT 1 as `MB7_MB8_UPDATED_AT`.
- Format: the canonical `YYYY-MM-DDTHH:MM:SSZ` (whole seconds; `rotation_contracts._instant`, the CLI
  `_INSTANT`).
- It must not be later than the owner's clock at derivation (the owner tool refuses `UPDATED_AT_IN_THE_FUTURE`), so
  it is never future-dated relative to the fresh sequence evidence. It must not be earlier than Registry V1
  `issuedAt`.
- Once captured it is immutable for this bootstrap lineage. The owner `emit`, the host M-B7 command, the S25
  `reproduce`, ACT 1 / 2 / 3, the P-A / P-B `pin-record.json`, and later M-B9b `bootstrap` all use the same value.
- No tool chooses or replaces it. Once the P-A record exists, `emit` refuses any other value
  (`UPDATED_AT_ALREADY_PINNED`) or any other candidate (`CANDIDATE_ALREADY_PINNED`), and `record-p-a` refuses any
  different record (`OWNER_RECORD_CONFLICT`).

## 4. The genesis candidate (exact fields)

The unsigned V2 genesis (`rotation_contracts.plan_witness_v2_genesis` plus `witnessKeyId`) and its classes:

| Field | Value | Class |
| --- | --- | --- |
| `protocol` | `LILITH_RECOVERY_WITNESS` | DERIVED (constant) |
| `schemaVersion` | `2` | DERIVED (constant) |
| `environment` | `dev` | OWNER-PINNED (profile) |
| `witnessVersion` | `1` | DERIVED (genesis) |
| `previousWitnessDigest` | `null` | DERIVED (genesis) |
| `currentRecoveryEpoch` | `{"counter":1,"random":"11f184889f333dece054f3b91a301632"}` | DERIVED from Registry V1 (owner-accepted M-B3) |
| `registryVersion` | `1` | DERIVED from Registry V1 |
| `registryDigest` | `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc` | DERIVED; owner-accepted identity |
| `policyVersion` | `policy.dev-synthetic.v1` | DERIVED from Registry V1 |
| `ledgerSequence` | `1` | DERIVED (`initial_position`); RUNTIME-OBSERVED on host, must equal |
| `ledgerHead` | `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630` | DERIVED; owner-accepted (M-B6); RUNTIME-OBSERVED on host, must equal |
| `consumedAuthorizationId` | `null` | DERIVED (genesis consumes none) |
| `updatedAt` | `MB7_MB8_UPDATED_AT`, owner-captured once (OD-2, §3.1) | OWNER-PINNED; time metadata, not authority, but part of the digest |
| `witnessKeyId` | `test-only.witness.dev-synthetic.b1b3d.1` | DERIVED (fixed profile); the anchor must name it |
| `signature` | absent | NOT PRESENT (created only at M-B9b by K-WIT) |

**Items that are NOT PRESENT in the candidate:**

- signer / actor identity (K-ACT binds only through `ledgerHead` and `registryDigest`);
- bootstrap phase;
- any nonce;
- the authorization-register state;
- a separate "expected statement" (the candidate is the unsigned statement itself).

**Time and randomness.** The only time value is `updatedAt` (`MB7_MB8_UPDATED_AT`), captured by the owner. The only random value is the
registry epoch random, fixed at M-B3. Given the same `updatedAt`, the candidate is reproducible bit for bit on the
laptop, the S25 and DEV.

**Owner inputs installed at M-B8** (the bytes the owner tool emits):

```text
genesis-pin.json             = JCS({"pinType":"LILITH_RECOVERY_WITNESS_V2_GENESIS_PIN","schemaVersion":1,
                                    "environment":"dev","genesisWitnessDigest":<candidate>})
authorization-register.json  = JCS({"registerType":"LILITH_OWNER_AUTHORIZATION_REGISTER","schemaVersion":1,
                                    "environment":"dev","authorizations":[],
                                    "headRegistries":[{"registryVersion":1,"registryDigest":"fa662721…14fc"}]})
```

The register content is the canonical one: preflight §22, and M-B6 remediation §14 (`authorizations: []`,
`headRegistries: [(1, fa662721…)]`).

**Owner record only (P-A, P-B; never installed on DEV):**

```text
pin-record.json              = JCS({"recordType":"LILITH_MB7_MB8_OWNER_PIN_RECORD","schemaVersion":1,"environment":"dev",
                                    "updatedAt":<MB7_MB8_UPDATED_AT>,"candidateDigest":<candidate>,"ledgerSequence":1,
                                    "ledgerHead":"19bf9091…1630","registryDigest":"fa662721…14fc",
                                    "genesisPinSha256":<pin>,"authorizationRegisterSha256":<register>})
```

It binds `MB7_MB8_UPDATED_AT` to the pinned candidate (the pin schema itself has no time field). It is an owner
bootstrap record, not authority.

## 5. M-B8 exact semantics

**Entry point.** `install_authority_dev.py install-owner-inputs aee323e94412accbe321bc84eae78c5b8cf95afc
/home/ravindupahasara2_gmail_com/lilith-mb8-stage/genesis-pin.json
/home/ravindupahasara2_gmail_com/lilith-mb8-stage/authorization-register.json`. It is streamed hash-gated under
`/usr/bin/python3 -I -B`, exactly once (operator `mb8`).

| Path | Source / custody | Owner:group, mode | Write | Replace policy | Expected | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| P-A `/root/lilith-genesis-pin-dev-synthetic/{genesis-pin,authorization-register,pin-record}.json` (laptop WSL) | owner-emitted bytes | owner (WSL root), dir `0700`, files `0600` | `record-p-a`, after ACT 2: each file `O_EXCL`, fsync dir | never replaced (record PONR); a different record is `OWNER_RECORD_CONFLICT` | three SHA-256 values | `check-copy` (each file separately) |
| P-B `$HOME/lilith-genesis-pin-dev-synthetic/{…same three…}` (S25 Termux private) | the same bytes, transferred | owner (Termux) | owner, after ACT 2, create-only (`set -o noclobber`; procedural) | never replaced | three SHA-256 values | `sha256sum` of each file on the phone screen |
| `/home/ravindupahasara2_gmail_com/lilith-mb8-stage/` (+ 2 files) | `scp` over IAP from the owner work directory | operator account, dir `0700` | `stage` form, before the go | created once; removed by `cleanup` | both SHA-256 | `staged_check` (`sha256sum -c --strict`) |
| `/etc/lilith-authority-dev/owner/genesis-pin.json` | the staged pin bytes | `root:root 0644`, regular, one link | `_write_new` (`O_EXCL|O_NOFOLLOW`), fsync file, chown, chmod, fsync dir; new inode, no rename | never replaced (`O_EXCL`); a re-run refuses (P1B-6 listing) | pin SHA-256 | `status P1B-8`, W8 `OWNER_INPUTS_INSTALLED_EXACT`, P1B-8 proof |
| `/etc/lilith-authority-dev/owner/authorization-register.json` | the staged register bytes | same | same, **after** the pin | same | register SHA-256 | same |
| `/etc/lilith-authority-dev/owner/` (directory) | — | unchanged `root:root 0755` | gains two entries; `mtime` / `ctime` change | — | listing = the two names | W8 verifier, observer (recorded delta) |

Nothing else changes: no unit, no witness state directory (that is P1B-9a, M-B9a), no credential, no ledger.

### 5.1 P-A / P-B owner records (OD-3)

The canonical owner layout fixes where these may live:

- B-4 §2: "a dedicated owner pin directory on the laptop, outside Replica A and outside its parent"; "a dedicated
  Termux-private pin directory on the S25, outside Replica B and outside its parent".
- Laptop: Replica A is WSL `/root/lilith-owner-freshness/owner-primary-dev-synthetic-01` (PR-2 pre-B5
  revalidation record).
- S25: Termux `$HOME` holds Replica B `lilith-owner-offline-dev-synthetic-01`, `lilith-kroot-dev-synthetic`
  (private K-ROOT only) and `lilith-kroot-dev-synthetic-public` (the public K-ROOT anchor). The Replica B gates list
  `$HOME` entries named `lilith-owner*`.

So the dedicated directory is the same sibling name on both devices, following the existing
`lilith-<purpose>-dev-synthetic` convention:

```text
P_A = /root/lilith-genesis-pin-dev-synthetic      (laptop, WSL Ubuntu-24.04; outside /root/lilith-owner-freshness)
P_B = $HOME/lilith-genesis-pin-dev-synthetic      (S25, Termux private /data/data/com.termux/files/home)
files (both) = genesis-pin.json  authorization-register.json  pin-record.json   (nothing else)
```

- Not a replica, inside no replica parent, and not named `lilith-owner*`, so no Replica A / B gate changes.
- Not a K-ROOT directory. The K-ROOT public directory is not reused: B-4 requires a **dedicated** pin directory.
- Both copies are byte-identical, separately hash-verified, owner-controlled, and write-once for this bootstrap
  state. Only a separately reviewed recovery procedure may change them.
- `authorization-register.json` here is the owner's `OwnerAuthorizationRegisterV1` copy. It is **not** the owner
  freshness register: `OWNER_REGISTER = KNOWN_EMPTY` (Replica A + Replica B, zero records) stays the M-B8 gate, and
  nothing in P-A / P-B is read by the freshness tool.

Recording happens only after ACT 2, in this order:

1. P-A: `mb7_genesis_candidate.py record-p-a <workdir>/genesis`, then `check-copy <workdir>/genesis
   /root/lilith-genesis-pin-dev-synthetic`.
2. P-B: the three files are transferred (USB / MTP via Download, as in earlier S25 steps) and copied create-only
   into `$HOME/lilith-genesis-pin-dev-synthetic` (`0700`). Each `sha256sum` is read on the phone screen and must
   equal the ACT 2 values. The transfer copy is then removed.

No live record exists yet.

**Transaction shape.** M-B8 is **two ordered write-once mutations, not one transaction**:

- partially recoverable only through the bounded removal (§6.3);
- **not idempotent**: after any write, `status P1B-6` fails, so a re-run refuses `PRECONDITION_FAILED` and changes
  nothing (tested);
- **non-retryable after the marker**: the go is consumed;
- a new attempt needs a new go and a fresh re-proof.

## 6. Partial-state and recovery model

### 6.1 W8 host phases (`mb8_owner_input_verifier.py`)

The verifier judges every phase against **owner-computed** values passed as arguments (ledger head, candidate
digest, `updatedAt`). It applies four judgments:

- trust anchors and Registry V1: the accepted W5 verifier, unchanged;
- the ledger: the accepted M-B6 byte reader, unchanged;
- the candidate: recomputed **in memory** from the installed state, with nothing written;
- each copy, classified as `ABSENT`, `EXACT`, `PARTIAL`, `FOREIGN` or `UNSAFE`.

`PARTIAL` means a prefix of the expected bytes, `root`-owned, with a mode no wider than `0644`: exactly what an
interrupted `_write_new` can leave.

| Phase | Host state | Classifier label | Routing |
| --- | --- | --- | --- |
| `W8_0_NO_OWNER_INPUTS` | neither copy; host-input reasons are exactly the two W5 gaps; the in-memory candidate equals the owner's | (also the only valid state during and after M-B7) | `SAFE_RETRY` (nothing consumed) |
| `W8_1_PIN_PARTIAL` | pin `PARTIAL` (empty, truncated, or complete bytes before chmod); register absent | interrupted first write / fsync | `SAFE_REMOVE_AND_RETRY` |
| `W8_2_PIN_ONLY_EXACT` | pin exact; register absent | interrupted between the two writes | `SAFE_REMOVE_AND_RETRY` |
| `W8_3_PIN_EXACT_REGISTER_PARTIAL` | pin exact; register `PARTIAL` | interrupted second write / fsync | `SAFE_REMOVE_AND_RETRY` |
| `OWNER_INPUTS_INSTALLED_EXACT` | both exact; no host-input reason; `candidate_pin_reason` is None; register exactly `(1, fa662721…)`; the in-memory candidate equals the owner's | both installed; validation by POST | `SAFE_ADOPT` (POST; owner acceptance) |
| `W8_FOREIGN_OR_UNSAFE_STOP` | any copy with other content, a wider mode, a symlink, a hard link, or a non-root owner | not producible by the installer | `STOP_OWNER_ADJUDICATION` |
| `OUT_OF_SCOPE_LATER_STATE` | witness state, a running signer / witness credential or socket, or a hold record | M-B9a or later | `STOP_OWNER_ADJUDICATION` |
| `UNCLASSIFIED_STOP` | trust / ledger / candidate not exact; an unexpected entry; a register without an exact pin (`NOT_REACHABLE_BY_DESIGN`: the pin is written first); both copies partial | inconsistent | `STOP_OWNER_ADJUDICATION` |

Not reachable by design: an **interrupted atomic rename** (the installer never renames: `O_EXCL` create in place),
and a **register without a pin**.

### 6.2 Sequence phases (host phase + the operator's marker, transcript and POST record)

| Sequence phase | Meaning | Route |
| --- | --- | --- |
| `W8_0_NO_OWNER_INPUTS` (no marker) | M-B8 not attempted | `SAFE_RETRY` |
| `S8_R_ATTEMPT_CONSUMED_NO_MUTATION` | marker; refused before the first write (or transport unknown) and the host is W8-0 | `SAFE_RETRY`: go consumed; a new go and a fresh re-proof |
| W8-1 / W8-2 / W8-3 (marker; transcript not `INSTALL_PASS`) | partial | `SAFE_REMOVE_AND_RETRY` |
| `S8_4_INSTALLED_TRANSCRIPT_INCOMPLETE` | host exact, transcript lost (SSH, timeout, status FAIL) | `SAFE_ADOPT` after a read-only POST and an explicit owner adoption decision |
| `S8_5_INSTALLED_POST_PENDING` | host exact, `INSTALL_PASS` | run POST |
| `S8_6_POST_VERIFIED_ACCEPTANCE_PENDING` | POST verified | owner acceptance (§16) |
| foreign / later / unclassified | — | `STOP_OWNER_ADJUDICATION` |

`INSTALL_REFUSED` is always raised before the first write. It never accompanies both copies being present:
`UNCLASSIFIED`. No route is automatic.

### 6.3 Bounded removal (`mb8_owner_input_removal.py`)

- `plan` (read-only) refuses unless all of these hold:
  - the ledger exists;
  - no witness state, running credential, socket or hold record exists (**before M-B9a**);
  - the owner directory is `root:root 0755` and lists only the two names;
  - each present copy is a regular root-owned file with one link, at most 64 KiB.
- `plan` prints the file facts and a plan digest.
- `remove <planDigest>` re-plans and refuses `PLAN_CHANGED` on any difference. It unlinks the register copy, then the
  pin copy (reverse install order), fsyncs the directory, and stops.
- It judges no content, and never touches P-A, P-B, the directory or any other path.
- The operator allows it only for W8-1 / W8-2 / W8-3, and only with the §14.4 authorization.
- Afterwards: `status P1B-6` PASS and W8-0 (tested: interrupted M-B8 → removal → a new install succeeds).

**IRREVERSIBLE in Package A:** nothing on DEV. The owner pin record (P-A / P-B) is never silently replaced (§8).

## 7. DR-5, broker preservation and observer impact

**M-B7:** creates no object. **DR-5 unchanged.**

**M-B8:** creates two leaves under `/etc/lilith-authority-dev/owner`. The DR-5 script
(`scripts/deployer_authority_boundary_proof.sh`, unchanged):

- stats that directory only as `%F|%u|%g|%a` (P1A-9 ladder row; kind, owner, group and mode do not change);
- never lists it;
- names neither leaf in `AB_PR1_LADDER`, `AB_PR1_UNOBSERVABLE` or `AB_LATER`.

The activation verifier reads only `/etc/lilith-os-dev/activation`. **The DR-5 output is therefore deterministically
unchanged:**

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | 188 | `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 3 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | 149 | `d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801` | 133 `DENIED`, 0 `ALLOWED`, 3 `DEFERRED`, 6 `UNOBSERVABLE` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

```text
POST_MB8_DR5_TARGET = NOT DERIVED (NO DR-5-OBSERVABLE DELTA)
DR-5 substitutions for M-B8 = none;  new DENIED / ALLOWED / FAIL / DEFERRED / UNOBSERVABLE lines = none
comparison target after M-B8 = the accepted post-M-B6 baseline (3640ca01…), phase-bound
```

**Phase-bound use** (operator `dr5 <repo> <verified-host-phase> <deploy-log>`, the same pinned extractor):

- `W8_0_NO_OWNER_INPUTS` or `OWNER_INPUTS_INSTALLED_EXACT`, independently verified by the W8 verifier: the accepted
  post-M-B6 target;
- anything else: `NO_BASELINE_STOP` (the freeze forbids a deploy there).

**OD-4 (ACCEPTED).**

- Successful exact M-B8 does not establish a new DR-5 baseline. The owner-accepted post-M-B6 baseline stays
  authoritative, but only while the W8 verifier classifies the host as `W8_0_NO_OWNER_INPUTS` or
  `OWNER_INPUTS_INSTALLED_EXACT`.
- Any partial, foreign, unsafe, inconsistent or later state must not use the baseline as evidence of normality. It
  is STOP / owner adjudication, unless the reviewed recovery route (§6.3) explicitly applies.
- No automatic rebaseline. No derived post-M-B8 target is required.
- `EQUAL` is not acceptance. The first post-freeze deploy after M-B8 must compare `EQUAL`, and the owner records that
  the baseline is preserved.

**Broker preservation** (`CUSTODY_PATHS`): the owner directory is `{present, uid, gid, mode}`. The leaves are not
listed. **Unchanged.**

**Observer:** it inventories `/etc` entries carrying LILITH markers with `mtime` / `ctime`. After M-B8 the two new
files and the owner directory's `mtime` / `ctime` are **expected deltas**. The owner compares them; nothing else may
differ.

**Accepted M-B6 tools after M-B8:**

- the M-B6 verifier reports `OUT_OF_SCOPE_LATER_STATE` (its scope ends at the first owner copy);
- the W5 verifier still reports `OUT_OF_SCOPE_POST_LEDGER` with all evidence true;
- P1B-5 and P1B-6 still PASS (neither lists the owner directory).

The separate P1B-8 proof adds 10 `DENIED` (write, by application, deployer, broker, signer and witness, on each
copy). The copies are public and readable by design.

## 8. Points of no return

| Event | Nature |
| --- | --- |
| M-B7 (candidate calculation) | **M-B7 = NOT LINEAGE-COMMITTING.** Persistent-state read-only (bounded scratch I/O only); candidate ≠ genesis |
| GENESIS_PREPARED (ACT 2, semantic acceptance) | not a witness-lineage commit; no persistent DEV change |
| accepted pin recorded in P-A and P-B (after ACT 2) | **OWNER PIN (P-A, P-B) = RECORD POINT OF NO RETURN** for the owner bootstrap record. Never silently replaced. A different pin is an owner re-bootstrap decision, possible only before M-B9b (preflight §29, sequencing §5) |
| on-host copies installed (ACT 3, M-B8 host part) | filesystem mutation, reversible **before M-B9a only** through the separately reviewed and separately authorized removal (§6.3); not lineage |
| witness genesis preparation / commitment | preparation = M-B7 + M-B8. Commitment = M-B9b |
| M-B9b | **M-B9b = LINEAGE POINT OF NO RETURN** (commit point: the fsync of `chain/`; RR-35, RR-40) |

M-B8 is preparatory and lineage-reversible. It is not lineage-significant, so the combined design is not stopped.

## 9. Continuity model (OWNER-ACCEPTED 2026-10-08, OD-1)

`MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE`

Accepted as continuity semantics only; it authorizes no act. Three owner acts, none implied by another:

| Act | Authorizes | Never authorizes |
| --- | --- | --- |
| ACT 1 (§14.1) | opening the Package A sequence and the deployment freeze; the read-only M-B7; binds `MB7_MB8_UPDATED_AT` | GENESIS_PREPARED; any P-A / P-B record; M-B8 |
| ACT 2 (§14.2), after the exact M-B7 technical PASS | the `GENESIS_PREPARED` acceptance; recording exactly that candidate and its pin, register and pin record into P-A and P-B | the M-B8 host install |
| ACT 3 (§14.3), after P-A / P-B exactness and fresh `KNOWN_EMPTY` | exactly one M-B8 host install | M-B9a or anything later |

| # | Rule |
| --- | --- |
| PA-1 | One live sequence, owner-attended throughout, one fresh evidence set (§12), one deployment freeze (§10) |
| PA-2 | No wall-clock TTL. Any relevant uncertainty or material drift ⇒ REVALIDATE (re-collect the affected evidence) or STOP |
| PA-3 | **ACT 1** (§14.1) opens the sequence and authorizes the read-only M-B7 only |
| PA-4 | M-B7 technical PASS (§13) is necessary for M-B8 and never sufficient |
| PA-5 | **ACT 2** (§14.2) is a separate act: GENESIS_PREPARED and the P-A / P-B record authorization. Recorded locally (`accept-b7`); no new repository PR |
| PA-6 | After ACT 2 and before ACT 3, the owner records P-A and P-B (§5.1). P-A = P-B = the emitted bytes, each file separately hash-verified |
| PA-7 | `OWNER_REGISTER = KNOWN_EMPTY` is freshly established from Replica A and Replica B before the M-B8 go |
| PA-8 | The closing gate (§12, E-A13) passes immediately before the M-B8 go |
| PA-9 | **ACT 3**, the M-B8 host-install go (§14.3): one attempt; the `O_EXCL` marker precedes the one invocation |
| PA-10 | A refusal before the marker consumes nothing |
| PA-11 | After the marker, any STOP consumes the go. There is no automatic retry. A partial state enters only the W8 classifier and the §14.4 removal, and a new attempt needs a new go and a fresh re-proof |
| PA-12 | The sequence may end after ACT 2 without M-B8. A later M-B8 then needs a new sequence, a fresh re-proof and a re-run M-B7 with the same recorded `MB7_MB8_UPDATED_AT` (same digest) |
| PA-13 | POST verified ≠ acceptance. Package A acceptance ≠ M-B9a authorization |

Considered and rejected:

- one go for both stages (M-B8 would follow M-B7 output automatically);
- two sequences (duplicate evidence with no added safety: M-B7 leaves no persistent state).

## 10. Deployment freeze

A freeze is required: the DR-5 phase rule needs no deploy while the host is partial, and continuity needs no
substrate change between M-B7 and M-B8.

| Item | Rule |
| --- | --- |
| start | the sequence authorization, before E-A1 |
| scope | no DEV deploy (`deploy-dev` workflow), no merge to `main` that triggers one, no manual DEV change, no package upgrade, no reboot, no broker / signer / witness unit action |
| invalidating events | any deploy, a boot-id change, broker preservation not PASS, a release / module / CLI hash change, a ledger change, an unexpected owner-directory entry, an IAM / topology / snapshot change in the cloud captures |
| end after M-B7 only | the owner ends the sequence after GENESIS_PREPARED (or declines it); the host is W8-0 |
| end after M-B8 | POST verified (S8-6) and the owner's Package A acceptance, or sequence termination with the host W8-0 or exact |
| partial M-B8 | the freeze holds until the host is W8-0 (after the authorized removal) or exact and accepted, or the owner explicitly releases it after adjudication |
| after the freeze | the first deploy compares `EQUAL` under §7 (owner records it; OD-4) |

## 11. Registry and authority effect of a successful M-B8

| Item | After M-B8 | Why (canonical) |
| --- | --- | --- |
| `REGISTRY_EFFECTIVE` | **NO** | "registry storage != accepted registry head (the witness decides the head)". No witness chain exists until M-B9b |
| `AUTHORITY_ACTIVE` | **NO** | no signer running; readiness has no genesis, hold or record |
| `authorityGranted` | **false** | every tool output |
| `GRANT_ABSENT` | **remains** | `/etc/lilith-os-dev/activation` untouched |
| witness | **inactive** | no unit start; `/var/lib/lilith-recovery-witness` absent (P1B-9a creates it) |
| signer | **inactive** | no unit start; K-ACT never loaded |
| Record 1 | **absent** | needs a committed genesis (M-B9b) |
| First Memory | **absent / NOT AUTHORIZED** | §18 |
| host-input reasons | **none** (both W5 gaps closed) | `read_host_inputs` |
| `FRESHNESS` | **UNKNOWN** | register `KNOWN_EMPTY`; record 1 absent |

## 12. Fresh evidence (one Package A sequence)

Every DEV read uses the operator's closed forms. K-ACT and K-WIT are evidenced as ciphertext SHA-256 and `stat`
only, and are never decrypted.

| ID | Evidence | Form | Stage |
| --- | --- | --- | --- |
| E-A0 | `MB7_MB8_UPDATED_AT`: one fresh owner UTC timestamp, captured before M-B7 and bound in ACT 1 (§3.1) | owner | opening |
| E-A1 | clean control = merged `main` containing this record; every tool pin | `pins` | opening |
| E-A2 | latest DEV deploy and every deploy since `e6fde13`: DR-5 `EQUAL` to the accepted post-M-B6 baseline | `dr5 <repo> W8_0_NO_OWNER_INPUTS <log>` (phase from E-A5) | opening |
| E-A3 | deploy queue empty (no run in progress or queued) | `gh run list` | opening; repeated in E-A13 |
| E-A4 | cloud: instance, disks, snapshots, images, IAM, Admin Activity since the M-B6 sequence | `cloud` | opening |
| E-A5 | host PRE: identity / boot; K-ACT and K-WIT ciphertext custody; release readiness (38 modules + 2 CLIs); `status P1B-6`; broker preservation; observer; W5 `OUT_OF_SCOPE_POST_LEDGER`; M-B6 `LEDGER_COMMITTED_EXACT` (sequence 1, head `19bf…1630`); W8-0 (both copies absent; authority inactive; `GRANT_ABSENT`; signer / witness inactive; no later state); no scratch residue | `host PRE` | opening (pre-M-B7) |
| E-A6 | P1B-5 and P1B-6 denial proofs PASS | `denial`, `ledger-denial` | opening |
| E-A7 | owner installables hash to the accepted pins; the candidate derived twice; the emitted directory | `genesis` | pre-M-B7 |
| E-A8 | S25 `reproduce` digest (same `MB7_MB8_UPDATED_AT`) = the emitted candidate (B-4) | phone screen | before ACT 2 |
| E-A9 | M-B7: W8-0 before; one `genesis-candidate`; stdout byte-equal; W8-0 after (in-memory candidate equal); no residue | `mb7` | M-B7 |
| E-A10 | `OWNER_REGISTER = KNOWN_EMPTY` from Replica A and Replica B | owner freshness tool | pre-M-B8 |
| E-A11 | after ACT 2: P-A `record-p-a` then `check-copy` `OWNER_COPY_EQUAL` (three files); P-B three SHA-256 on the phone screen | `mb7_genesis_candidate.py`; phone | pre-ACT 3 |
| E-A12 | stage directory with exactly the two files, re-hashed on DEV | `stage` | pre-M-B8 |
| E-A13 | closing gate: `pins`; deploy queue empty; `host PRE` re-run (a NEW evidence directory) PASS and equal to E-A5 except time | `pins`, `host PRE` | immediately before the M-B8 go |
| E-A14 | the one `install-owner-inputs` transcript and its class | `mb8` | M-B8 |
| E-A15 | POST: `host POST` (`status P1B-8`; W8 `OWNER_INPUTS_INSTALLED_EXACT` with all three evidence items; M-B6 `OUT_OF_SCOPE_LATER_STATE`; W5 unchanged; preservation; observer deltas only §7) + P1B-8 proof | `post` | post-M-B8 |
| E-A16 | P1B-5 and P1B-6 still PASS | `denial`, `ledger-denial` | post-M-B8 |
| E-A17 | stage removed | `cleanup` | closing |
| E-A18 | first post-freeze deploy `EQUAL` | `dr5 <repo> OWNER_INPUTS_INSTALLED_EXACT <log>` | after the freeze (OD-4) |

Carried through the sequence without repetition:

- E-A4 (re-run only on an invalidating event);
- E-A6;
- E-A7 / E-A8 (the candidate does not change);
- E-A10 is taken once, before the go.

## 13. M-B7 technical gate

`MB7_TECHNICAL_PASS` (written once, `O_EXCL`, by `mb7`) requires all of the following:

- ACT 1 (§14.1) contains every line with this control, operator, candidate digest and `MB7_MB8_UPDATED_AT`;
- W8 before and after = `W8_0_NO_OWNER_INPUTS`, with `hostCandidateDigestEqualsOwnerDigest` (the in-memory recomputation);
- the CLI exits 0 with empty stderr, and **stdout is byte-equal to `expected-host-stdout.txt`**. That binds the
  candidate bytes, the digest, every decoded field (§4), the ledger head, the registry identity, the epoch and
  policy, and the pin document;
- no `lilith-ledger-observe.*` entry left in `/tmp` (OD-5: a leftover scratch copy fails the gate and is a STOP);
  no owner copy (W8-0 ⇒ no M-B8 state);
- E-A5 PASS in this sequence.

Then the owner gives ACT 2 (§14.2, with E-A8). `accept-b7` records it, P-A and P-B are recorded (§5.1), and M-B8
becomes **eligible** in the same sequence, without a new repository PR. Eligible is not authorized: the host install
still needs ACT 3 (§14.3), after fresh `KNOWN_EMPTY` and the closing gate.

## 14. Owner texts (DRAFT TEMPLATES; NOT ISSUED)

Placeholders are bound by the operator, which refuses any text that misses a line or a value. `<operator>` is the
SHA-256 of `mb7_mb8_operator.py` at the control (the operator checks it equals itself). `<updatedAt>` is
`MB7_MB8_UPDATED_AT`.

### 14.1 ACT 1: sequence authorization (read-only M-B7 only)

> I authorize the Package A (M-B7 + M-B8) live sequence now, for this current DEV_SYNTHETIC sequence only.
> Continuity: MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE.
> The deploy freeze holds from the start of this sequence through the Package A close.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/mb7_mb8_operator.py SHA-256 <operator>.
> Owner candidate tool: services/owner-memory-control/tools/mb7_genesis_candidate.py SHA-256 d50fcb36afab51a79c7918a7a43c86f97338241f62144c780d8b342c68b3c8b2.
> W8 verifier: services/owner-memory-control/tools/mb8_owner_input_verifier.py SHA-256 b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341.
> M-B7 command: /usr/local/sbin/lilith-authority-verify-dev genesis-candidate 1 <updatedAt>, read-only, exactly one invocation per M-B7 run.
> MB7_MB8_UPDATED_AT: <updatedAt>, captured once by the owner at the opening of this sequence; immutable for this bootstrap lineage.
> Owner candidate digest: <candidate>.
> This authorizes the read-only M-B7 only. It does not accept GENESIS_PREPARED and does not authorize M-B8, M-B9a, M-B9b, witness genesis, record 1, First Memory or PROD.

### 14.2 ACT 2: GENESIS_PREPARED and the P-A / P-B records (after MB7_TECHNICAL_PASS and E-A8)

> I accept GENESIS_PREPARED for exactly this candidate in this Package A sequence.
> Candidate digest: <candidate>. MB7_MB8_UPDATED_AT: <updatedAt>.
> M-B7 host stdout SHA-256: <stdout> equals the owner-computed expected stdout.
> The S25 reproduce result equals this candidate digest.
> I authorize recording exactly this candidate, create-only, in P-A /root/lilith-genesis-pin-dev-synthetic (laptop WSL) and P-B $HOME/lilith-genesis-pin-dev-synthetic (S25 Termux): genesis-pin.json SHA-256 <pin>, authorization-register.json SHA-256 <register>, pin-record.json SHA-256 <record>.
> This act does not authorize the M-B8 host install; that needs its own go.

### 14.3 ACT 3: the M-B8 host-install go (one attempt; after E-A10, E-A11, E-A13)

> I authorize M-B8 / PIN_GENESIS on-host install now for exactly one attempt within this current Package A sequence.
> Continuity: MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/mb7_mb8_operator.py SHA-256 <operator>.
> Installer: services/authority-dev/ceremony/install_authority_dev.py SHA-256 fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487.
> W8 verifier: services/owner-memory-control/tools/mb8_owner_input_verifier.py SHA-256 b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341.
> Removal: services/owner-memory-control/tools/mb8_owner_input_removal.py SHA-256 d9a6e0d5dcfb07558ca7533e8144b7f2b7c29b1b4db28400571aede55b99f7f5.
> Owner-input denial proof: services/owner-memory-control/tools/mb8_owner_input_denial_proof.py SHA-256 5d63137a2c6e43f12f663febdd4e22fd7b2b519a6c0cfa544dad12f0bc958517.
> Release: aee323e94412accbe321bc84eae78c5b8cf95afc.
> Command: install-owner-inputs aee323e94412accbe321bc84eae78c5b8cf95afc /home/ravindupahasara2_gmail_com/lilith-mb8-stage/genesis-pin.json /home/ravindupahasara2_gmail_com/lilith-mb8-stage/authorization-register.json, exactly one invocation.
> Pre-state: W8_0_NO_OWNER_INPUTS.
> Candidate digest: <candidate>.
> Genesis-pin copy SHA-256: <pin>. Authorization-register copy SHA-256: <register>.
> MB7_MB8_UPDATED_AT: <updatedAt>. Pin-record SHA-256: <record>.
> The owner records P-A /root/lilith-genesis-pin-dev-synthetic (laptop) and P-B $HOME/lilith-genesis-pin-dev-synthetic (S25) each hold exactly these three files, byte-identical and separately hash-verified.
> GENESIS_PREPARED was owner-accepted in this sequence.
> OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B.
> This go does not accept GENESIS_PINNED, and does not authorize M-B9a, M-B9b, witness genesis, record 1, First Memory or PROD.
> Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the attempt marker consumes this go and ends the sequence. There is no automatic retry.
> A partial state enters only the reviewed W8 classifier and the separately authorized removal or adoption path.

### 14.4 Bounded removal (W8-1, W8-2 or W8-3 only; separately authorized)

> I authorize the bounded M-B8 owner-input removal for exactly one invocation.
> Plan digest: <plan>.
> Classified W8 phase: <phase>.
> I acknowledge: this removal is not a retry of M-B8 and is not a new pin; the owner pin copies P-A and P-B and the candidate are unchanged; a new M-B8 attempt needs a new owner go and a fresh re-proof.

## 15. M-B8 POST requirements

`post` writes `POST_VERIFIED` (S8-6) only if all of the following hold:

- sequence phase S8-5 (marker, `INSTALL_PASS`, host exact);
- every host read exits 0, readiness is exact, and there is no scratch residue;
- `status --expect P1B-8 aee323e…` PASS;
- W8 `OWNER_INPUTS_INSTALLED_EXACT` with all three evidence items true:
  - `hostCandidateDigestEqualsOwnerDigest`;
  - `onHostPinCopyEqualsOffHost` (on-host bytes = the emitted bytes; P-A and P-B equal by E-A11);
  - `pinEqualsCandidateDigest`;
- no host-input reason;
- `registryEffective = false`, `authorityGranted = false`;
- M-B6 verifier `OUT_OF_SCOPE_LATER_STATE`; W5 `OUT_OF_SCOPE_POST_LEDGER`; broker preservation PASS;
- the observer shows only the §7 deltas;
- the P1B-8 proof PASS (18 lines, `denied=10 allowed=0`).

Then: HARD STOP for owner review. `pinStoredOffHostTwoCopies` is the owner's own statement (E-A11) and is never
host-observable.

## 16. Package A owner acceptance (DRAFT TEMPLATE; NOT ISSUED)

> I accept Package A for this sequence: M-B7 / PREPARE_GENESIS_CANDIDATE and M-B8 / PIN_GENESIS are COMPLETED.
> Candidate digest: <candidate>. MB7_MB8_UPDATED_AT: <updatedAt>. Genesis-pin copy SHA-256: <pin>.
> Authorization-register copy SHA-256: <register>. Pin-record SHA-256: <record>. POST_VERIFIED evidence:
> <post-evidence-sha256>.
>
> ```text
> M-B7 = OWNER-ACCEPTED
> M-B8 = OWNER-ACCEPTED
> GENESIS_PREPARED = YES
> GENESIS_PINNED = YES
> OWNER P-A PIN = RECORDED
> OWNER P-B PIN = RECORDED
> OFF-HOST AUTHORIZATION REGISTER P-A = RECORDED / EXACT
> OFF-HOST AUTHORIZATION REGISTER P-B = RECORDED / EXACT
> HOST OWNER INPUTS = OWNER_INPUTS_INSTALLED_EXACT
> LEDGER = SEQUENCE 1 / HEAD 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
> REGISTRY_EFFECTIVE = NO
> AUTHORITY_ACTIVE = NO
> authorityGranted = false
> GRANT_ABSENT = TRUE
> WITNESS = INACTIVE; SIGNER = INACTIVE
> M-B9a = NOT AUTHORIZED
> M-B9b = NOT AUTHORIZED
> WITNESS_GENESIS = NOT COMMITTED
> RECORD 1 = ABSENT
> FIRST MEMORY = NOT AUTHORIZED
> PROD = NOT AUTHORIZED
> FRESHNESS = UNKNOWN
> ```
>
> This acceptance authorizes nothing further. The deployment freeze ends now; the first post-freeze deploy must
> compare EQUAL to the accepted post-M-B6 DR-5 baseline (separate owner record).

These are the target semantics for the future ceremony only; none is accepted now. Every line was checked against
the code (§11): `GRANT_ABSENT` is preserved because nothing in Package A touches `/etc/lilith-os-dev/activation`. If
the sequence ends after ACT 2 only, the record instead states `M-B7 = OWNER-ACCEPTED`, `GENESIS_PREPARED = YES`, the
P-A / P-B records as recorded, and `M-B8 = NOT AUTHORIZED`, with both W5 gaps remaining.

## 17. Package B hand-off (not implemented; nothing authorized)

Package B = M-B9a `START_WITNESS` + M-B9b `COMMIT_WITNESS_GENESIS`. It receives exactly:

- state `GENESIS_PINNED`; host W8 `OWNER_INPUTS_INSTALLED_EXACT`;
- ledger sequence 1, head `19bf9091…1630`; Registry V1 installed, not effective;
- witness and signer inactive; `/var/lib/lilith-recovery-witness` absent; hold store empty; `GRANT_ABSENT`;
- the owner-accepted candidate digest and **the same `MB7_MB8_UPDATED_AT`** (from the P-A / P-B `pin-record.json`). M-B9b's
  `lilith-recovery-witness-owner-dev bootstrap 1 <updatedAt>` must use this value, or `genesis.bootstrap` refuses
  `GENESIS_PIN_NOT_CANDIDATE`;
- P-A = P-B (three record files) and on-host pin copy = the pinned digest;
- the accepted post-M-B6 DR-5 baseline (preserved).

Package B owns:

- the installer `witness-state` stage (P1B-9a), which requires `status P1B-8`;
- the witness `daemon-reload` / start;
- the `UNINITIALIZED` proof;
- the single `BOOTSTRAP`;
- the C-11 / C-12 crash windows (C-12 = `REBOOTSTRAP_FORBIDDEN`).

Package B changes DR-5. While they exist, `AB_LATER` turns each of `/var/lib/lilith-recovery-witness`,
`/run/lilith-recovery-witness` and `/run/credentials/lilith-recovery-witness.service` from one `DEFERRED` line into
`DENIED` lines. Package B must derive that phase-bound delta itself, before its own mutation.

## 18. First Memory hard boundary

First Memory must never be:

- inferred by tooling;
- auto-generated;
- selected by Claude;
- selected by a model;
- written merely because readiness gates pass.

No model or tool may choose, draft, infer or write First Memory. When bootstrap eventually reaches
`FIRST_MEMORY_READY`, execution MUST STOP. The owner and the architecture reviewer
discuss its semantic content before any separate authorization exists. Nothing in Package A reads, writes, proposes
or prepares a memory record.

## 19. Owner decisions applied, and remaining blockers

**Owner decisions (2026-10-08), applied in this slice:**

| # | Decision | Where |
| --- | --- | --- |
| OD-1 | `MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE` ACCEPTED, with three separate owner acts | §9, §14 |
| OD-2 | `MB7_MB8_UPDATED_AT` capture rule ACCEPTED; no value in the repository | §3.1 |
| OD-3 | off-host authorization-register copies ACCEPTED in both owner records, P-A and P-B, beside the pin | §5.1 |
| OD-4 | no new DR-5 baseline after exact M-B8; the post-M-B6 baseline only for `W8_0` / `OWNER_INPUTS_INSTALLED_EXACT` | §7 |
| OD-5 | `MB7_TEMP_LEDGER_COPY = EPHEMERAL_SCRATCH_IO_ONLY` ACCEPTED, with the gate conditions | §3, §13 |

The owner also accepted the point-of-no-return semantics (§8), the W8 recovery model (§6), and the Package A
success hand-off as target semantics (§16, §17). No recovery and no act is authorized by these decisions.

**Remaining blockers before any live Package A sequence:**

| # | Class | Blocker |
| --- | --- | --- |
| B-1 | review | review and merge of this slice; canonicalization of the merged control |
| B-2 | evidence | `MB7_MB8_UPDATED_AT` captured (E-A0) and the fresh evidence E-A1 … E-A13 in one owner-authorized sequence |
| B-3 | governance | ACT 1; later and separately ACT 2 and ACT 3 |

## 20. State

```text
PACKAGE_A (M-B7 + M-B8) = REPOSITORY ONLY (SOURCE + TESTS + DOCS); NOT MERGED; NOT RUN
CONTROL = e6fde13a54384c63016b3591beed18cb1a505e24
MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE (OWNER-ACCEPTED 2026-10-08, OD-1)
MB7_MB8_UPDATED_AT = NOT CAPTURED (OD-2 rule accepted; captured at the opening of the live sequence)
P_A = /root/lilith-genesis-pin-dev-synthetic (OD-3; laptop WSL; NO RECORD YET)
P_B = $HOME/lilith-genesis-pin-dev-synthetic (OD-3; S25 Termux; NO RECORD YET)
POST_MB8_DR5_RULE = POST-M-B6 BASELINE ONLY FOR W8_0 / OWNER_INPUTS_INSTALLED_EXACT; ELSE STOP (OWNER-ACCEPTED, OD-4)
MB7_TEMP_LEDGER_COPY = EPHEMERAL_SCRATCH_IO_ONLY (OWNER-ACCEPTED 2026-10-08, OD-5)
M-B6 = FULLY CLOSED; LEDGER_PROVISIONED = OWNER-ACCEPTED
LEDGER_SEQUENCE = 1
LEDGER_HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
POST_MB6_ACCEPTED_DR5_BASELINE = 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494 (PRESERVED)
POST_MB8_DR5_TARGET = NOT DERIVED (NO DR-5-OBSERVABLE DELTA)
AUTHORIZATION_REGISTER_COPY_MISSING = TRUE
GENESIS_PIN_COPY_MISSING = TRUE
GRANT_ABSENT = TRUE
authorityGranted = false
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
M-B7 = NOT AUTHORIZED
M-B8 = NOT AUTHORIZED
M-B9a = NOT AUTHORIZED
M-B9b = NOT AUTHORIZED
WITNESS_GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
AUTHORITY_ACTIVATION = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO RUNTIME OR RELEASE-PAYLOAD FILE CHANGED
```
