# Slice 15B2b-B1b-3e — Package B: M-B9a `START_WITNESS` + M-B9b `COMMIT_WITNESS_GENESIS` (Design, Tooling and Runbook)

Status:

- **REPOSITORY ONLY: SOURCE, TESTS AND DOCUMENTATION.** No live Package B sequence has run. Writing this slice
  contacted no live system (no DEV, no S25, no owner key custody).
- Packages M-B9a and M-B9b into one owner-attended sequence with **two separate authority boundaries** (owner
  decisions OD-B1 … OD-B13, 2026-10-08, §20). The lineage point of no return stays inside M-B9b and is never
  batched with M-B9a (§5).
- **Nothing is authorized by this record.** E-A18, the Package B sequence, M-B9a, M-B9b, witness genesis, record 1,
  the signer, authority activation, First Memory and PROD remain **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- Predecessor: [Package A completion](slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md) (`GENESIS_PINNED`,
  `OWNER_INPUTS_INSTALLED_EXACT`). E-A18 is still pending and must complete before Package B opens (§13).
- **Later current state (2026-10-08, pointer only; the text above is preserved as written).** E-A18 completed and
  was owner-recorded. Package B sequence 1 opened on control `5ce067c` and was stopped by the owner during opening
  evidence: the W9 verifier bundle did not fit a Windows command line (`WinError 206`) before any W9 DEV contact; no
  B2, no marker, no witness mutation ([sequence 1 stop and remediation R-B1](slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md)).
  R-B1 moves the verifier bundles to stdin (§8.1) and adds the owner pre-M-B9a stop (§10.8, §14).

```text
M-B9a technical PASS != WITNESS_STARTED accepted (B3) != M-B9b authorized (B4)
witness started != witness genesis committed != record 1 != Registry V1 effective != authority active
commit point = the fsync of chain/ after chain/1.json;  after it: forward only;  committed != pin -> REBOOTSTRAP_FORBIDDEN
```

## 1. Canonical sources

| Source | Governs |
| --- | --- |
| [PR-3 P3-5 bootstrap sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §2–§10, §14 | the order (steps 8–9), K-WIT and registry lifecycles, PONRs, crash windows C-10 … C-13, freshness gates (step 8 `REQUIRED_UNKNOWN_BLOCK`, step 9 `BOOTSTRAP_SPECIAL_CASE`), First Memory |
| [PR-1 live install preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md) §10–§13, §27 (M-B9a / M-B9b rows), §29, §30 F-6 / F-7 / F-7a / F-13 | witness design, K-WIT custody, the genesis fields, preconditions and durability, PIN-BEFORE-COMMIT (RR-35) |
| [Package A record](slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md) §6.1, §7 (OD-4), §8, §10, §11, §17, §18 | the hand-off, the phase-bound DR-5 rule, the freeze |
| [M-B6 remediation](slice-15b2b-b1b3e-mb6-ledger-remediation.md) D-2, D-5 | the naming hazard; rollback boundary "before M-B9b" |
| [Post-M-B6 DR-5 baseline acceptance](slice-15b2b-b1b3e-mb6-post-dr5-baseline-acceptance.md) | the accepted baseline `3640ca01…` and how a baseline is established |
| [M-B2 completion](slice-15b2b-b1b3e-mb2-kwit-completion.md) | the K-WIT fingerprint (SHA-256 of the 32-byte public key) `5d778701…0bdf` |
| [B-5 decision](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md) §4–§6 | no skipping / repeating steps; no real `append` before record 1 |
| code: `install_authority_dev.py` (`witness-state`, `status` P1B-9a / P1B-9b), `lilith_authority_root/genesis.py`, `cli.py`, `recovery-witness/{server,core,writer,storage}.py` and `deploy/*`, `witness_readiness.py` | what executes |

Runtime equality: `git diff aee323e..29c2b82` shows no change to the witness, genesis, recovery-classifier or
installer code, so the installed release `aee323e` runs exactly the code reviewed here (RR-37: no upgrade needed).

## 2. M-B9a `START_WITNESS` (step 8 → `WITNESS_STARTED`)

| Question | Answer |
| --- | --- |
| state change | stage 9A-1: installer `witness-state` (P1B-9a, root) creates `/var/lib/lilith-recovery-witness` `lilith-recovery-witness:lilith-authority-dev 2750` (setgid). Stage 9A-2: start of the two witness sockets, then the service (never enabled, no `daemon-reload`). The witness's startup recovery creates `witness.lock`; while it runs, systemd creates `/run/credentials/lilith-recovery-witness.service` |
| owner of the state | root (the directory); the witness (its content); systemd (the runtime credential) |
| objects | `lilith-recovery-witness.service`, `-owner.socket` (`/run/lilith-recovery-witness/owner.sock`, root 0600), `-signer.socket` (`signer.sock`, witness:signer-group 0660); `/run/lilith-recovery-witness` (tmpfiles `0710 root lilith-authority-dev`) already exists |
| K-WIT | loaded by `LoadCredentialEncrypted=recovery-witness-signing-key:<blob>`: the first time K-WIT plaintext is in a running process (`AVAILABLE_TO_WITNESS`). Not a canonical PONR |
| reversible before / after | everything; afterwards still pre-lineage: a separately authorized restart or the bounded removal (§7.3) |
| pre-state | `W9_0_PRE_WITNESS` (= W8 `OWNER_INPUTS_INSTALLED_EXACT`), units inactive and static, `GRANT_ABSENT` |
| technical success | `status P1B-9a` PASS; W9 `W9_2_STARTED_UNINITIALIZED` (all four 9a evidence items); HEALTH `publicKeySha256 = 5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`, `witnessKeyId = test-only.witness.dev-synthetic.b1b3d.1`, `classification = UNINITIALIZED`, `inputs = []`, `genericSigning = NOT_AVAILABLE`; `NRestarts = 0` |
| acceptance | B3 (`WITNESS_STARTED`); authorizes nothing |
| not authorized by success | `BOOTSTRAP`, M-B9b, `RECORD_LEDGER_ADVANCE`, head / epoch advance, the signer, HELD, record 1, activation |

## 3. M-B9b `COMMIT_WITNESS_GENESIS` (step 9 → `WITNESS_GENESIS_COMMITTED`)

| Question | Answer |
| --- | --- |
| command | `/usr/local/sbin/lilith-recovery-witness-owner-dev bootstrap 1 2026-10-08T07:21:43Z` (root, owner socket), exactly once |
| path | `genesis.bootstrap`: re-derive the candidate from a fresh ledger copy; require pin = candidate; `BOOTSTRAP`. The witness re-checks `UNINITIALIZED`, rebuilds the candidate, re-checks the pin, signs with K-WIT, verifies, creates `chain/` and `authorizations/` (idempotent), commits, publishes the pointer, re-classifies; the tool re-reads the store and requires `CONSISTENT` with digest = pin |
| state change | `chain/`, `authorizations/` (empty), `chain/1.json` (the signed genesis), `witness.json` (the pointer) |
| pre-state | `W9_2_STARTED_UNINITIALIZED`, WITNESS_STARTED accepted for the **same** `InvocationID` / `MainPID` (OD-B7) |
| technical success | `status P1B-9b` PASS; W9 `W9_5_GENESIS_COMMITTED_EXACT` (all six 9b evidence items); committed digest = owner pin = candidate `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`; chain = genesis only; pointer = genesis bytes; `authorizations/` empty; ledger unchanged |
| acceptance | B5 (Package B); "lineage anchored, not accepted" (record 1 accepts it later) |
| not authorized by success | record 1, the acceptance envelope, a CURRENT owner freshness, Registry V1 effective, HELD, the signer, eligibility, activation, First Memory, PROD |

## 4. The witness genesis (exact)

| Object | What it is | Identity |
| --- | --- | --- |
| ledger `GENESIS` op | M-B6 journal row | head `19bf9091…1630` |
| witness genesis candidate | M-B7, unsigned `RecoveryWitnessV2` body | digest `ac892dc2…65e4` |
| `OwnerGenesisPinV1` | the pin document | `genesisWitnessDigest = ac892dc2…65e4` |
| `genesis-pin.json` | the on-host / off-host pin bytes | `35747736…a590` |
| `authorization-register.json` | `OwnerAuthorizationRegisterV1`, empty | `8d5ab875…5575` |
| committed witness genesis `chain/1.json` | M-B9b, K-WIT-signed JCS document | digest must equal the pin |
| `witness.json` | the pointer (= the head) | bytes = `chain/1.json` |
| Registry V1 material | installable and digest | `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e`, `fa662721…14fc` |
| record 1 / `OwnerFreshnessRecordV1` | P3 owner ceremony, after M-B9b | absent |

Fields (preflight §12): `protocol`, `schemaVersion` 2, `environment` `dev`, `witnessVersion` 1,
`previousWitnessDigest` null, `currentRecoveryEpoch` (E0), `registryVersion` 1, `registryDigest`, `policyVersion`,
`ledgerSequence` 1, `ledgerHead`, `consumedAuthorizationId` null, `updatedAt` `2026-10-08T07:21:43Z`,
`witnessKeyId`, `signature`. Digest: `witness_v2_digest` = SHA-256(`LILITH_RECOVERY_WITNESS_V2\0` ‖ JCS(unsigned));
the signature (Ed25519, base64url, K-WIT) is over the same signing bytes and excluded from the digest.

## 5. The lineage point of no return

1. `chain/1.json` is created `O_EXCL`;
2. its bytes are fsynced;
3. `chain/` is fsynced;
4. **THE CHAIN DIRECTORY FSYNC IS THE LINEAGE COMMIT POINT** (`writer.py` `_commit`; sequencing §4.5; preflight
   §12).

After it: `WITNESS LINEAGE = FORWARD ONLY`. The pointer publication that follows is roll-forward-recoverable (the
witness's own recovery at start). The genesis lineage itself is never deleted, recreated or retried; a repeated
`BOOTSTRAP` is refused by the witness (`STORE_NOT_UNINITIALIZED`). A committed genesis that differs from the owner
pin is terminal: `REBOOTSTRAP_FORBIDDEN` (C-12, RR-35, RR-40), a separately reviewed owner recovery / successor
design; no second witness genesis, ever. A whole-host snapshot restore after commit is not detectable on-host
(F-13).

## 6. Classifiers

### 6.1 W9 host phases (`mb9_witness_verifier.py`)

Read-only, root, release interpreter, bundled with the unchanged W5, M-B6 and W8 verifiers. It never opens or
connects to a witness or signer socket (socket activation would start the service); units come from
`systemctl show` only. Every phase first re-proves the accepted Package A end state (trust, ledger, owner copies,
in-memory candidate = pin, register exact, no host-input reason).

| Phase | Observable predicate | Route | Lineage reversible | Owner act |
| --- | --- | --- | --- | --- |
| `W9_0_PRE_WITNESS` | no witness state; witness runtime stopped | `SAFE_RETRY` | YES | B2 |
| `W9_1P_STATE_DIR_PARTIAL` | state directory empty, `root:root` or witness:signer-group, mode ⊆ 0750 (mkdir done, chown / chmod not) | `SAFE_REMOVE_AND_RETRY` | YES | removal, then a new B2 |
| `W9_1_STATE_DIR_ONLY` | exact 2750 directory, empty, runtime stopped | `SAFE_CONTINUE_OR_REMOVE` | YES | none within the same B2 after an exact 9A-1; else restart or removal |
| `W9_2_STARTED_UNINITIALIZED` | only `witness.lock`; store `UNINITIALIZED`; runtime RUNNING (three units active, service running with a PID, runtime credential and both sockets present) | `SAFE_ADOPT` | YES | B3 after POST9A |
| `W9_2S_STOPPED_UNINITIALIZED` | the witness ran (lock present) and is stopped; `UNINITIALIZED` | `SAFE_RESTART_OR_REMOVE` | YES | restart or removal |
| `W9_FAILED_START` | pre-lineage; runtime failed, partial or transitional | `STOP_OWNER_ADJUDICATION` | YES | owner adjudication |
| `W9_3_PRECOMMIT_DIRS` | `chain/` and / or `authorizations/` exist and are empty; `UNINITIALIZED` (C-11) | `STOP_OWNER_ADJUDICATION` | YES | a new B4 + fresh re-proof, or restart / removal |
| `W9_4_COMMITTED_POINTER_PENDING` | `chain/1.json` valid = pin = candidate; pointer missing / corrupt / behind, or scratch residue | `STOP_OWNER_ADJUDICATION` | NO | restart (if stopped) rolls forward |
| `W9_5_GENESIS_COMMITTED_EXACT` | `CONSISTENT`; chain = [1]; pointer = genesis; digest = pin = candidate; fields = candidate; runtime RUNNING | `SAFE_ADOPT` | NO | B5 after POST9B + offline verification |
| `W9_5S_GENESIS_COMMITTED_STOPPED` | as W9-5, runtime stopped | `SAFE_RESTART` | NO | restart, then POST9B |
| `W9_RUNTIME_ABNORMAL_AFTER_COMMIT` | committed; runtime failed / partial / transitional | `STOP_OWNER_ADJUDICATION` | NO | owner adjudication |
| `W9_TORN_GENESIS` | `chain/1.json` present but not a valid witness document | `STOP_OWNER_ADJUDICATION` | UNDETERMINED | OD-B6: no automated deletion, repair or re-bootstrap |
| `W9_GENESIS_MISMATCH` | committed genesis ≠ pin / candidate | `HALT_REBOOTSTRAP_FORBIDDEN` | NO | separately reviewed recovery / successor design |
| `W9_LATER_STATE` | chain beyond genesis, a retained authorization, a hold record, signer active / credential / socket | `STOP_OWNER_ADJUDICATION` | NO | outside Package B |
| `W9_FOREIGN_OR_UNSAFE` | unexpected entry, symlink, wrong owner / mode / link count, an enabled unit, an orphan or pointer-only store | `STOP_OWNER_ADJUDICATION` | UNDETERMINED | no tool acts on it |
| `UNCLASSIFIED_STOP` | units unreadable, base not exact, unloaded unit, any contradiction | `STOP_OWNER_ADJUDICATION` | UNDETERMINED | UNKNOWN is never absence or success |

Every host phase has an explicit route (tested), so the Package A W8 routing-field defect cannot recur here.

### 6.2 Sequence phases (host phase + markers, transcripts, POST and acceptance records)

`S9_0_NOT_STARTED`; `S9A1_R_CONSUMED_NO_MUTATION`; `S9A1_PARTIAL`; `S9A1_TRANSCRIPT_INCOMPLETE`;
`S9A1_EXACT_STAGE2_PENDING`; `S9A2_R_CONSUMED_NOT_STARTED`; `S9A2_PARTIAL`; `S9A2_TRANSCRIPT_INCOMPLETE` (reply
lost with exact host state); `S9A_POST_PENDING`; `S9A_POST_VERIFIED_ACCEPTANCE_PENDING`; `S9A_ACCEPTED`;
`S9A_ACCEPTANCE_STALE_REVALIDATE` (a new incarnation); `S9A_STOPPED_REVALIDATE`; `S9B_R_CONSUMED_NO_LINEAGE`;
`S9B_COMMITTED_POINTER_PENDING`; `S9B_COMMITTED_UNACKNOWLEDGED`; `S9B_COMMITTED_STOPPED_REVALIDATE`;
`S9B_POST_PENDING`; `S9B_POST_VERIFIED_ACCEPTANCE_PENDING`; `S9B_POST_VERIFIED_ADOPTION_PENDING`;
`S9_HALT_REBOOTSTRAP_FORBIDDEN`; and the stop phases. Rules:

- markers are consumed strictly in order (`mb9a-1`, `mb9a-2`, `mb9b`); anything else is `UNCLASSIFIED_STOP`;
- stage 9A-2 is never legitimate unless stage 9A-1 was exact;
- the transcript never proves success or absence. The `bootstrap` CLI prints only `REFUSED <reason>`: a post-commit
  witness STOP and a pre-sign refusal both print `GENESIS_WITNESS_REFUSED`. With a committed host the sequence is
  committed (`S9B_COMMITTED_UNACKNOWLEDGED`), with an `UNINITIALIZED` host it is `S9B_R_CONSUMED_NO_LINEAGE`;
- an ambiguous transport classifies the host; a missing acknowledgement never implies absence.

### 6.3 Transcript classes

- stage 9A-1: `STAGE_PASS` (exit 0, empty stderr, `P1B-9a` PASS report), `STAGE_STATUS_FAIL`, `STAGE_REFUSED`,
  `GUARD_STOPPED`, `TRANSPORT_FAILED`, `FAILED_UNCLASSIFIED`;
- stage 9A-2 / restart: `START_RETURNED_OK` (systemd accepted the jobs; the host decides), `START_FAILED`, guard,
  transport;
- M-B9b: `BOOTSTRAP_PASS` (exact compact JSON with this candidate), `BOOTSTRAP_REFUSED_BEFORE_WITNESS`,
  `BOOTSTRAP_WITNESS_REFUSED`, `BOOTSTRAP_COMMITTED_NOT_PINNED`, `BOOTSTRAP_REFUSED_OTHER`, guard, transport,
  `FAILED_UNCLASSIFIED`.

## 7. Crash, recovery, adoption, removal and restart

### 7.1 One-attempt markers

- **M-B9a (OD-B3): one B2 go, two ordered one-attempt markers.** The operator checks W9-0 (read-only), writes
  marker `mb9a-1` (`O_EXCL`), runs exactly one `witness-state`, classifies; only if the transcript is `STAGE_PASS`
  **and** the host is exactly `W9_1_STATE_DIR_ONLY` does it write marker `mb9a-2` and run exactly one start of the
  two sockets and the service. Health (owner socket) is read only after the verifier observed the witness running.
  Any failure or ambiguity after a marker consumes that stage; the second mutation never runs over an inexact first
  stage.
- **M-B9b: one B4 go, one marker `mb9b`, exactly one `bootstrap`.** Refusals before the marker consume nothing:
  sequence not opened, go text not exact (including the PONR acknowledgement), host not `W9_2`, or the running
  witness not the accepted incarnation.
- A new attempt after a consumed marker needs a new owner go, a fresh re-proof and a new operator work directory.

### 7.2 Crash windows (all reached through the real writer's fault points in the tests)

| Window | W9 phase | Route |
| --- | --- | --- |
| `witness-state` interrupted after mkdir | `W9_1P_STATE_DIR_PARTIAL` (a re-run is refused by the installer's own P1B-8 precondition) | removal, new B2 |
| 9A-2 never started / reply lost | `W9_1` / `W9_2` | restart or removal / POST9A + adoption in B3 |
| witness stopped, rebooted or restarted after B3 | `W9_2S` or a new `InvocationID` | **B3 is not replayed**: restart, fresh POST9A, new B3 (OD-B7) |
| `BEFORE_CHAIN_CREATE` | `W9_3_PRECOMMIT_DIRS` (`UNINITIALIZED`) | new B4 + fresh re-proof (same candidate; directories idempotent) |
| `AFTER_CHAIN_WRITE`, `AFTER_CHAIN_FILE_FSYNC` | `W9_4` (a host crash may instead leave `UNINITIALIZED` or a torn file) | owner adjudication; roll-forward at an authorized start |
| `AFTER_CHAIN_DIRECTORY_FSYNC` (commit point reached) | `W9_4` | forward only |
| `AFTER_POINTER_SCRATCH_WRITE` / `_FSYNC` | `W9_4` | forward only |
| `AFTER_POINTER_REPLACE` / `AFTER_POINTER_DIRECTORY_FSYNC` | `W9_5` | POST9B + adoption if unacknowledged |
| torn `chain/1.json` | `W9_TORN_GENESIS` | STOP only |
| committed ≠ pin | `W9_GENESIS_MISMATCH` | HALT |
| stale `bootstrap` process / second writer | the store `flock`; the operator checks for leftover CLI processes before any reclassification | — |

### 7.3 Bounded pre-commit removal (`mb9_witness_state_removal.py`, OD-B5)

`plan` (read-only) refuses unless: the ledger and both owner copies exist; the witness and signer units are
inactive; the runtime credentials and sockets are absent; the hold store is empty; the state directory is
`root:root` or witness:signer-group with a reachable mode; and its only entries are an empty `witness.lock` and empty
`chain/` / `authorizations/`. It refuses on any chain entry (even partial), `witness.json`, the pointer scratch,
any retained authorization, any other entry, a symlink, a hard link or any ambiguity. `remove <planDigest>`
re-plans (`PLAN_CHANGED` on any difference), removes in reverse creation order and fsyncs. It never stops anything
and never removes a committed genesis. Separate owner authorization naming the plan digest and the W9 phase.

### 7.4 Separately authorized restart

`restart-plan` (read-only) records a digest of the stopped state; allowed only from `W9_1`, `W9_2S`, `W9_3`, `W9_4`,
`W9_5S` with the runtime STOPPED. `restart` re-observes, refuses `PLAN_CHANGED`, writes a one-attempt marker and runs
exactly one start of the two sockets and the service. It never stops or restarts a running witness. A fresh POST
(9A or 9B) is required afterwards; no earlier acceptance is replayed.

## 8. Operator (`mb9_operator.py`) forms

`pins`, `cloud`, `open-sequence` (B1, local), `stop-sequence` (the pre-M-B9a stop, local; §10.8),
`host <PRE|POST9A|POST9B>`, `denial` (P1B-5), `ledger-denial` (P1B-6),
`owner-denial` (P1B-8), `witness-denial <P1B-9a|P1B-9b>`, `classify`, `mb9a`, `post9a`, `accept-9a` (B3, local),
`mb9b`, `post9b`, `chain-export`, `health`, `dr5`, `removal-plan`, `removal`, `restart-plan`, `restart`. Every form
is closed. Every mutating form binds the control commit, the tool pins, the candidate and pin, the sequence state,
the owner text (verbatim lines) and its hash in the marker, the pre-state and one-attempt semantics. It never runs
`enable`, `daemon-reload`, `stop`, `restart`, a signer start, a ledger / hold / head-advance / epoch-advance /
record / activation form or any First Memory path (tested).

### 8.1 Verifier transport (remediation R-B1)

The three verifier bundles (W5 + M-B6, W8, W9) are sent over the remote command's **stdin**. The command line
carries only the hostname guard, the SHA-256 of the payload, the per-module pins, the entry module and the
arguments; its length does not grow with the verifier sources. The payload is unchanged: the same base64 of the
gzip'd JSON `{module: source}` that the pinned M-B6 loader has always read from stdin.

- The remote shell reads the payload once (`B=$(cat)`) and exits `96` unless it hashes to the digest in the
  command; only then does it decode it for the loader.
- The unchanged M-B6 loader still exits `96` unless the module set and every module's SHA-256 equal the pins.
- The client argv, capture, 900 s timeout and hostname guard are those of the pinned `ssh`; a timeout, an SSH
  failure, a non-zero exit or unparseable output is still `VERIFIER_FAILED` / UNKNOWN, never success or absence.
- Only the read-only verifier bundles use stdin. Every mutation path (`witness-state`, the two starts, `bootstrap`,
  the bounded removal) keeps its reviewed command exactly; no form becomes reachable through the transport change.
- Every argv the operator builds stays below the Windows command-line limit (32767 characters; tested). Sequence 1
  stopped because the W9 bundle (43688 characters) was the one command above it.

The verifier sources and pins are unchanged. Only `mb9_operator.py` changed; its SHA-256 is bound into each owner
text at runtime and recorded in the [R-B1 record](slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md).

## 9. Owner offline verification (OD-B11)

`mb9_owner_genesis_verify.py verify <P-A dir> <witness-anchor.json> <chain-1.json> <witness.json>`, owner workstation,
read-only. It checks: the P-A files are exactly the bytes the accepted candidate implies; the anchor is the accepted
installable (`be360da2…`), names `test-only.witness.dev-synthetic.b1b3d.1`, and its key hashes to
`5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`; `chain/1.json` is one canonical
`RecoveryWitnessV2` whose unsigned body equals the expected genesis field by field (version 1, both nulls, epoch,
registry version / digest, policy, ledger sequence / head, `updatedAt`, key ID); the K-WIT signature verifies; the
digest equals `ac892dc2…65e4`, the pin and the pin record; `witness.json` equals `chain/1.json`. It writes nothing,
never touches a replica, and does not create record 1 or make freshness current. The S25 digest cross-check is
optional evidence, not a live prerequisite.

## 10. Owner acts (DRAFT TEMPLATES; NOT ISSUED)

No template authorizes the next act. Placeholders are bound at runtime.

### 10.1 B1: sequence opening (read-only only)

> I authorize opening the Package B (M-B9a + M-B9b) live sequence now, for this current DEV_SYNTHETIC sequence only.
> Continuity: PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES.
> The Package B deployment freeze begins now and holds through M-B9a, B3, M-B9b, POST, the owner offline verification and B5; no deploy is permitted inside this sequence.
> E-A18 was completed and owner-recorded before this act, and the deploy of this control commit preserved the accepted W8-exact DR-5 result.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/mb9_operator.py SHA-256 <operator>.
> W9 verifier: services/owner-memory-control/tools/mb9_witness_verifier.py SHA-256 e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78.
> Candidate digest: <candidate>. MB7_MB8_UPDATED_AT: <updatedAt>.
> This authorizes opening the sequence and read-only evidence only. It does not authorize M-B9a, M-B9b, witness genesis, record 1, the signer, First Memory or PROD.

### 10.2 B2: the M-B9a go (one go, two markers)

> I authorize M-B9a / START_WITNESS now for exactly one attempt within this current Package B sequence.
> Continuity: PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/mb9_operator.py SHA-256 <operator>.
> Installer: services/authority-dev/ceremony/install_authority_dev.py SHA-256 fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487.
> W9 verifier: services/owner-memory-control/tools/mb9_witness_verifier.py SHA-256 e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78.
> Witness denial proof: services/owner-memory-control/tools/mb9_witness_denial_proof.py SHA-256 2720100cf56f22db7b063641ce63c22512326b794c447901d9b2551c8ab7663a.
> Removal: services/owner-memory-control/tools/mb9_witness_state_removal.py SHA-256 4e5094ebb6f1624a6f4de1769a0c2c131a6ff9b4284c6e5a4b19e40b1c383640.
> Release: aee323e94412accbe321bc84eae78c5b8cf95afc.
> Stage 9A-1 (marker mb9a-1): install_authority_dev.py witness-state aee323e94412accbe321bc84eae78c5b8cf95afc, exactly one invocation.
> Stage 9A-2 (marker mb9a-2), only after stage 9A-1 is exact (W9_1_STATE_DIR_ONLY): systemctl start lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket, then systemctl start lilith-recovery-witness.service, exactly one invocation; no enable and no daemon-reload.
> Then the read-only witness health, only after the service is observed running.
> Pre-state: W9_0_PRE_WITNESS (OWNER_INPUTS_INSTALLED_EXACT).
> Candidate digest: <candidate>. Genesis-pin copy SHA-256: <pin>. Authorization-register copy SHA-256: <register>.
> OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B.
> The P1B-5, P1B-6 and P1B-8 denial proofs passed in this sequence before this go.
> This go does not authorize BOOTSTRAP, M-B9b, witness genesis, record 1, the signer, First Memory or PROD, and does not accept WITNESS_STARTED.
> Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after a stage marker consumes that stage. There is no automatic retry, and stage 9A-2 never runs unless stage 9A-1 is exact.
> A partial state enters only the reviewed W9 classifier and the separately authorized removal or restart path.

### 10.3 B3: WITNESS_STARTED acceptance (authorizes nothing)

> I accept WITNESS_STARTED for this Package B sequence.
> W9 phase: W9_2_STARTED_UNINITIALIZED. Witness service InvocationID: <invocation>. MainPID: <mainpid>.
> POST9A_VERIFIED evidence SHA-256: <post9a>.
> Witness health: publicKeySha256 5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf, witnessKeyId test-only.witness.dev-synthetic.b1b3d.1, classification UNINITIALIZED.
> This acceptance authorizes nothing further. It is not M-B9b authorization; M-B9b needs its own go after a fresh closing gate.

### 10.4 B4: the M-B9b lineage go (one attempt)

> I authorize M-B9b / COMMIT_WITNESS_GENESIS now for exactly one attempt within this current Package B sequence.
> Continuity: PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/mb9_operator.py SHA-256 <operator>.
> W9 verifier: services/owner-memory-control/tools/mb9_witness_verifier.py SHA-256 e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78.
> Witness denial proof: services/owner-memory-control/tools/mb9_witness_denial_proof.py SHA-256 2720100cf56f22db7b063641ce63c22512326b794c447901d9b2551c8ab7663a.
> Owner genesis verifier: services/owner-memory-control/tools/mb9_owner_genesis_verify.py SHA-256 30b66fd2be9f29e820041840a75dc87f7623eff44551c025a0141790e7c89a5a.
> Release: aee323e94412accbe321bc84eae78c5b8cf95afc.
> Command: /usr/local/sbin/lilith-recovery-witness-owner-dev bootstrap 1 <updatedAt>, exactly one invocation.
> Pre-state: W9_2_STARTED_UNINITIALIZED. WITNESS_STARTED was owner-accepted in this sequence for InvocationID <invocation>, MainPID <mainpid> (POST9A_VERIFIED SHA-256 <post9a>), and the witness has run continuously since.
> Candidate digest: <candidate>. Genesis-pin copy SHA-256: <pin>. Authorization-register copy SHA-256: <register>. Pin-record SHA-256: <record>. MB7_MB8_UPDATED_AT: <updatedAt>.
> Expected genesis: registryVersion 1, registryDigest fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc, ledgerSequence 1, ledgerHead 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630, witnessVersion 1, previousWitnessDigest null, consumedAuthorizationId null, witnessKeyId test-only.witness.dev-synthetic.b1b3d.1.
> The owner records P-A /root/lilith-genesis-pin-dev-synthetic (laptop) and P-B $HOME/lilith-genesis-pin-dev-synthetic (S25) each hold exactly the three Package A record files, byte-identical and separately hash-verified, re-verified in this sequence.
> OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence, after WITNESS_STARTED, from Replica A and Replica B.
> I understand that the witness lineage becomes irreversible at the canonical chain-directory fsync commit point and that no second witness genesis or automatic retry is authorized after that point.
> A committed genesis that differs from the owner pin is REBOOTSTRAP_FORBIDDEN: STOP, with no second genesis.
> This go does not accept WITNESS_GENESIS_COMMITTED and does not authorize record 1, the acceptance envelope, HELD, the signer, First Memory or PROD.
> Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 10.5 B5: Package B acceptance (ends the freeze; authorizes nothing)

> I accept Package B for this sequence: M-B9a / START_WITNESS and M-B9b / COMMIT_WITNESS_GENESIS are COMPLETED.
> Committed witness genesis digest: <candidate> (= the owner pin = the Package A candidate). chain/1.json SHA-256: <genesis>. POST9B_VERIFIED evidence SHA-256: <post9b>. Owner offline verification: MB9B_OWNER_GENESIS_VERIFIED.
> This acceptance authorizes nothing further. The Package B deployment freeze ends now; the first deploy after it must compare EQUAL to the derived running-witness DR-5 target (separate owner record).

If the acknowledgement of M-B9b was lost (`S9B_POST_VERIFIED_ADOPTION_PENDING`), B5 must additionally state the
owner's explicit adoption of the observed committed genesis.

### 10.6 Bounded removal (separately authorized)

> I authorize the bounded pre-commit witness-state removal for exactly one invocation.
> Plan digest: <plan>.
> Classified W9 phase: <phase>.
> I acknowledge: this removal is not a retry of M-B9a or M-B9b and removes no lineage; a new attempt needs a new owner go and a fresh re-proof.

### 10.7 Restart of a stopped witness (separately authorized)

> I authorize one start of the stopped witness (the two sockets, then the service) for exactly this plan.
> Plan digest: <plan>.
> Classified W9 phase: <phase>.
> I acknowledge: this start is not a retry of M-B9a or M-B9b; any earlier WITNESS_STARTED acceptance is stale and a fresh POST is required before anything else.

### 10.8 Owner pre-M-B9a stop (remediation R-B1)

Available only while B1 is recorded and the attempt directory holds no marker or other file: no B2 has been
consumed and no M-B9a or M-B9b invocation exists. Opening evidence may be incomplete, FAILED or UNKNOWN. The stop
ends the sequence, releases its freeze, consumes its control and authorizes nothing. Once any marker exists the
operator refuses it (`STOP_REFUSED_ATTEMPT_MARKER_PRESENT`): the W9 classifier, removal, restart and recovery
routes govern instead, and the stop is never a way around them. After the stop, `mb9a` and `mb9b` refuse
(`SEQUENCE_STOPPED`) and the sequence cannot be reopened in place. Placeholders: `<control>`, `<b1>` (the SHA-256 of
`B1_SEQUENCE_AUTHORIZATION.json`), `<operator>`.

> I stop this Package B sequence now, before M-B9a, for this current DEV_SYNTHETIC sequence only.
> Control commit: <control>. B1 record SHA-256: <b1>.
> Operator: services/owner-memory-control/tools/mb9_operator.py SHA-256 <operator>.
> No B2 was issued, no M-B9a or M-B9b attempt marker exists, and no witness mutation was made by this sequence.
> This sequence is OPENED THEN STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE; its evidence is preserved and must not be replayed into a later sequence.
> The Package B deployment freeze of this sequence is RELEASED by this stop; the release authorizes no deployment, merge or DEV change.
> The selected Package B live control <control> is CONSUMED by this sequence and is not reusable.
> This stop authorizes nothing further. A new sequence needs a new merged control, a fresh preservation deploy, a new owner control selection and a new canonical B1.

## 11. Denial proofs

- **P1B-5** (`scripts/authority_custody_denial_proof.py`, unchanged) stays applicable while the witness runs: it has
  no unit precondition, and its rows for the Package B objects are deferred to P1B-12. Run at every POST.
- **P1B-6 and P1B-8** require `lilith-recovery-witness.service` inactive. Once M-B9a starts the witness they are
  out of their valid phase (not drift, not failure); they must PASS at the opening, before B2. Unchanged.
- **P1B-9a / P1B-9b** (`mb9_witness_denial_proof.py`, new): exact preconditions (state entries, ledger, owner copies,
  runtime directory / sockets / credential with the unit-file metadata, the three witness units active, the signer
  inactive, `GRANT_ABSENT`), then `runuser … test` probes. Each row names its DENIED principals and, explicitly, its
  `ALLOWED_BY_DESIGN` principals (OD-B9: the signer reads and traverses the setgid witness state and reaches its own
  socket). A by-design row that is denied, an unexpected allow, or an inconclusive probe FAILS. It re-covers the
  P1B-6 ledger rows and the P1B-8 owner-input rows with the witness active, and denies the witness any write to the
  ledger, owner inputs, trust anchors, Registry V1 and the K-WIT blob.

| Phase | `DENIED` | `ALLOWED_BY_DESIGN` | transcript lines |
| --- | --- | --- | --- |
| P1B-9a | 91 | 5 | 107 |
| P1B-9b | 125 | 11 | 148 |

The counts are derived from the row table and pinned by tests (realistic probe outcomes), not written by hand.

## 12. DR-5 by phase (`mb9_dr5_target.py`, OD-B8)

Rule: `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`, ADR-0015 dependency-bound invalidation. The targets are derived
mechanically from the ACCEPTED post-M-B6 texts (fixture `b1b3e_mb9_post_mb6_dr5_baseline.json`, which hashes to the
accepted pins) by the two `ab_check_later_state` substitutions for `/var/lib/lilith-recovery-witness` and
`/run/credentials/lilith-recovery-witness.service` (one `DEFERRED_UNTIL_OBJECT_EXISTS … (later step)` line → three
`DENIED: test -w|-r|-x` lines each). No other line changes; nothing is rebaselined globally.

| Target | Phases | Result set | DR-5 block | Pre-deploy |
| --- | --- | --- | --- | --- |
| accepted post-M-B6 baseline | `W9_0_PRE_WITNESS` | 188 lines, `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494`: 161 `DENIED`, 3 deferred, 6 unobservable | 149, `d05aa017…7801` | 29, `f5087042…4cae` |
| witness state present, service stopped | `W9_1`, `W9_2S`, `W9_5S` | 190 lines, `7f70aa3bd0c51622b362e78a2d75edca6fe2801eccf6bc9da015de093a670989`: 164 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 2 deferred, 6 unobservable | 151, `3d7cd041d21e034849af031d1a1971a09a54efe2d5490cf7c1bfba9549d450af` | unchanged |
| witness running | `W9_2`, `W9_5` | 192 lines, `593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65`: 167 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 1 deferred, 6 unobservable | 153, `ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a` | unchanged |

**M-B9b adds no DR-5 line:** `chain/`, `chain/1.json`, `witness.json` and `authorizations/` lie beneath a directory
the script never lists. Every other phase (partial, failed, pointer-pending, torn, mismatch, later, foreign,
unclassified) is `NO_BASELINE_STOP`. The running target is the expected normal post-Package-B deploy target; the
stopped target is a classification / recovery target. **Both are PROPOSED; neither is accepted** (live evidence and
a separate owner acceptance first).

## 13. E-A18 and the Package B control (OD-B2)

E-A18 cannot be performed after M-B9a's first mutation: the accepted baseline holds only while W8 classifies
`OWNER_INPUTS_INSTALLED_EXACT` (Package A §7 OD-4); any witness state is `OUT_OF_SCOPE_LATER_STATE` for W8; the
Package A operator then refuses `NO_BASELINE_STOP`; and a Package B freeze forbids deploys inside the sequence.
Order:

1. this source PR (reviewed);
2. a separate owner merge decision;
3. the merge-triggered deploy is the first deploy after the Package A freeze: the **E-A18 candidate**; it must
   compare `EQUAL` under `OWNER_INPUTS_INSTALLED_EXACT`;
4. a separate owner E-A18 acceptance;
5. a small E-A18 record PR; its merge-triggered deploy must preserve the W8-exact result;
6. only then may that merge commit become the Package B live control;
7. B1 opens Package B (separate owner act).

## 14. Continuity and freeze

`PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES` (OD-B1): one fresh
evidence sequence; one freeze; no wall-clock TTL; material uncertainty or drift ⇒ REVALIDATE / STOP (ADR-0015);
M-B9a technical PASS never implies M-B9b authority; M-B9b needs a fresh explicit go after a fresh closing gate; the
sequence may stop after an accepted M-B9a without committing lineage.

The Package B freeze begins with B1 and holds through M-B9a, B3, M-B9b, POST, the owner offline verification and
B5; B5 ends it. Before any attempt marker exists, an owner pre-M-B9a stop (§10.8) ends the sequence and releases
its freeze instead (R-B1). No deploy, merge-triggered deploy, manual DEV change, package upgrade, reboot (a global
invalidator), unit action outside the two reviewed starts, or signer action inside the sequence.

## 15. Fresh evidence

| Stage | Evidence |
| --- | --- |
| opening (after B1) | pins; control = merged `main`; E-A18 recorded; queue empty; cloud captures (IAM, topology, snapshots); `host PRE` (identity / boot, `REBOOT_REQUIRED`, custody incl. K-WIT blob `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be`, readiness incl. the owner witness CLI `9fce2e46…`, `status P1B-8`, preservation, observer, W5, M-B6, W8 `OWNER_INPUTS_INSTALLED_EXACT`, W9 `W9_0_PRE_WITNESS`); P1B-5, P1B-6, P1B-8 PASS; `genesis-candidate 1 2026-10-08T07:21:43Z` = `ac892dc2…`; P-A, P-B, `KNOWN_EMPTY` |
| before B2 (closing gate) | pins, queue, `host PRE` into a new directory equal to the opening except time; no leftover processes |
| after M-B9a | `post9a`: `host POST9A` (`status P1B-9a`, W9 `W9_2`), P1B-9a and P1B-5 PASS, health exact, `NRestarts = 0` → `POST9A_VERIFIED` bound to `InvocationID` / `MainPID`; then B3 |
| before B4 (closing gate) | same incarnation; store `UNINITIALIZED`; fresh `KNOWN_EMPTY`; P-A / P-B; in-memory candidate = pin; boot id and queue unchanged |
| after M-B9b | `post9b`: `host POST9B` (`status P1B-9b`, W9 `W9_5`), P1B-9b and P1B-5 PASS, health `CONSISTENT`, `read` head v1, exported `chain/1.json` + `witness.json` (evidence only, OD-B10) → `POST9B_VERIFIED`; owner offline verification; B5 |

K-WIT, trust and Registry V1 facts (`5d778701…0bdf`, `be360da2…`, `bc5f00a7…`,
`46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e`, `fa662721…14fc`) are re-proven fresh, never
replayed from history.

## 16. Tool pins

| Tool | SHA-256 |
| --- | --- |
| `services/authority-dev/ceremony/install_authority_dev.py` | `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py` | `78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361` |
| `services/owner-memory-control/tools/mb6_ledger_verifier.py` | `6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5` |
| `services/authority-dev/ceremony/observe_authority_dev_host.py` | `a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf` |
| `scripts/verify_broker_dev_current_incarnation.py` | `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba` |
| `scripts/authority_custody_denial_proof.py` | `f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455` |
| `services/owner-memory-control/tools/mb6_ledger_denial_proof.py` | `470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0` |
| `services/owner-memory-control/tools/mb6_operator.py` | `4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5` |
| `services/owner-memory-control/tools/mb7_genesis_candidate.py` | `d50fcb36afab51a79c7918a7a43c86f97338241f62144c780d8b342c68b3c8b2` |
| `services/owner-memory-control/tools/mb8_owner_input_verifier.py` | `b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341` |
| `services/owner-memory-control/tools/mb8_owner_input_denial_proof.py` | `5d63137a2c6e43f12f663febdd4e22fd7b2b519a6c0cfa544dad12f0bc958517` |
| `services/owner-memory-control/tools/mb7_mb8_operator.py` | `9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd` |
| `services/owner-memory-control/tools/mb9_witness_verifier.py` | `e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78` |
| `services/owner-memory-control/tools/mb9_witness_denial_proof.py` | `2720100cf56f22db7b063641ce63c22512326b794c447901d9b2551c8ab7663a` |
| `services/owner-memory-control/tools/mb9_witness_state_removal.py` | `4e5094ebb6f1624a6f4de1769a0c2c131a6ff9b4284c6e5a4b19e40b1c383640` |
| `services/owner-memory-control/tools/mb9_dr5_target.py` | `d176864a2f15cd9a64462c1ffc0bb46364428e97d3ec64b5fd547bb380ef1675` |
| `services/owner-memory-control/tools/mb9_owner_genesis_verify.py` | `30b66fd2be9f29e820041840a75dc87f7623eff44551c025a0141790e7c89a5a` |

The operator (`services/owner-memory-control/tools/mb9_operator.py`) is not in the table: it is bound into each owner
text at runtime (`<operator>`) and checked equal to the control. Every pinned Package A tool is byte-unchanged.

## 17. B-5 qualification (OD-B12)

B-5 (the [PR-1B authorization decision](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md) and its current
grant) remains governing for applicable PR-1B continuation and sequencing: steps in order, never skipped or
repeated; no real `append` before record 1; First Memory, activation, issuance and PROD not permitted.
**However, the old B-5 §9 post-M-B1 deployment-baseline condition is HISTORICAL** (already recorded as
`B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED`, ledger §13.1af). It must not invalidate any later
accepted phase, and "confirm B-5" never resurrects it. Post-M-B6 deployment evidence is governed by
`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` (§12; Package A §7).

## 18. Open remediation item (not fixed here)

The Package A W8 routing-field defect (`MB8_ROUTING_FIELD_ANOMALY = REPORTING_DEFECT_ONLY`; no
`OWNER_INPUTS_INSTALLED_EXACT -> SAFE_ADOPT` entry) remains an **OPEN FUTURE REMEDIATION** for a later independent
slice ([Package A completion](slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md) §10). Package B does not modify the
pinned W8 verifier; its own W9 tables route every phase explicitly.

## 19. First Memory hard boundary

First Memory must never be inferred by tooling, auto-generated, selected by Claude, selected by a model, or written
merely because readiness gates pass. Package B reads, writes, proposes and prepares no memory record. When bootstrap
eventually reaches `FIRST_MEMORY_READY`, execution MUST STOP and the owner is told explicitly; the owner and the
architecture reviewer discuss its content before any separate authorization exists. Package B cannot reach that
point (sequencing §14: it follows FULL_READINESS and the A1–A7 acceptance).

## 20. Owner decisions applied (2026-10-08)

| # | Decision |
| --- | --- |
| OD-B1 | ACCEPT: `PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES` |
| OD-B2 | ACCEPT: E-A18 completes and is owner-recorded before Package B opens (§13) |
| OD-B3 | ACCEPT: M-B9a = one go, two ordered one-attempt markers |
| OD-B4 | ACCEPT: B3 separately accepts `WITNESS_STARTED`; B3 ≠ M-B9b authorization |
| OD-B5 | ACCEPT: bounded, plan-digest-bound pre-commit removal tool |
| OD-B6 | ACCEPT: torn `chain/1.json` → `STOP_OWNER_ADJUDICATION` only |
| OD-B7 | ACCEPT: the witness incarnation (`InvocationID`, `MainPID`) stays stable from POST9A to the B4 go |
| OD-B8 | ACCEPT: derived stopped and running DR-5 targets |
| OD-B9 | ACCEPT: signer read / traverse of the witness state = `ALLOWED_BY_DESIGN` |
| OD-B10 | ACCEPT: the chain export is Package B evidence only; the record-1 package decides freshness storage |
| OD-B11 | OPTIONAL: the S25 digest cross-check |
| OD-B12 | CONFIRMED WITH QUALIFICATION (§17) |
| OD-B13 | ACCEPT: the W8 routing defect is fixed later, not here (§18) |

## 21. State

```text
PACKAGE_B (M-B9a + M-B9b) = REPOSITORY ONLY (SOURCE + TESTS + DOCS); NOT MERGED; NOT RUN
PACKAGE_B_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_AUTHORITY_BOUNDARIES (OWNER-ACCEPTED 2026-10-08, OD-B1)
PACKAGE_A = COMPLETED / OWNER-ACCEPTED
HOST OWNER INPUTS = OWNER_INPUTS_INSTALLED_EXACT
E-A18 = NOT YET PERFORMED
MB9_DR5_TARGETS = DERIVED (STOPPED 7f70aa3b…, RUNNING 593c90e1…); NOT ACCEPTED
PACKAGE_B_SEQUENCE = NOT AUTHORIZED
M-B9a = NOT AUTHORIZED
M-B9b = NOT AUTHORIZED
WITNESS_GENESIS = NOT COMMITTED
RECORD 1 = ABSENT
SIGNER = INACTIVE / NOT AUTHORIZED
AUTHORITY_ACTIVATION = NOT AUTHORIZED
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
GRANT_ABSENT = TRUE
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS = UNKNOWN
```
