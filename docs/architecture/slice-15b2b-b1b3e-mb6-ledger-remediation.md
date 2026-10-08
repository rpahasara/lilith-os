# Slice 15B2b-B1b-3e — M-B6 `PROVISION_LEDGER`: Repository Remediation and Design (2026-10-07)

Status:

- **REPOSITORY-ONLY REMEDIATION / DESIGN SLICE.** It was written under the owner's design decision and
  repository-only authorization of control `aca41f43c1a5540fcdd182fe770fbcdb0a04e6a8` (the merge of PR #163). It
  closes the M-B6 preflight gaps in source, tests and documentation.
- **Nothing here is authorized for live use:**
  - M-B6 and M-B7 and later are **NOT AUTHORIZED**.
  - Genesis, record 1, First Memory and PROD are **NOT AUTHORIZED**.
  - `FRESHNESS=UNKNOWN`.
- **Owner governance decisions recorded (2026-10-07).** The owner's decisions R-1, R-2A, R-2B, R-3 and R-6 and
  the runtime-timeout and owner-head instructions were given on control `aca41f4` with a repository-only
  finalization authorization. They are recorded in [Owner decisions](#owner-decisions-2026-10-07) and in §6, §8, §9,
  §12 and §13. None of them authorizes M-B6.
- **The pin-derived ledger head in §5 is a cross-check value only.** It is
  `CROSS_CHECK_ONLY / NOT_OWNER_COMPUTED / NOT_ACCEPTED`. The real owner-held Registry V1 derive happens only after
  this slice is merged and canonicalized.
- **No live system was contacted.** No DEV, GCP, S25, owner custody, K-ROOT, K-WIT or K-ACT. No runtime or
  release-payload file changed.

```text
ledger provisioned != authority state accepted;  ledger existence != authority
ledger GENESIS op != witness genesis candidate != OwnerGenesisPinV1 != committed witness genesis
owner-computed expected head != owner-accepted pin != host-observed head != authority
recovery != reset != retry;  plan digest != authorization
LEDGER_COMMITTED_EXACT != owner acceptance of LEDGER_PROVISIONED != M-B7 authorization
```

## Owner decisions (2026-10-07)

Owner decisions on the M-B6 remediation slice, recorded verbatim in substance. Each is scoped to M-B6 and is not
broadened to later M-steps.

| # | Decision | Accepted value | Where |
| --- | --- | --- | --- |
| R-1 | M-B6 continuity model | `MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO` | §8 |
| R-2A | post-M-B6 DR-5 model | `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` (owner-accepted phase-bound governance rule; no global DR-5 rebaseline) | §12.2 |
| R-2B | B-5 §9 after M-B1 | `B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED` (governance clarification / erratum) | §12.3 |
| R-3 | P1B-6 denial proof | a separate M-B6 denial-proof tool with its own pin; the P1B-5 tool and the M-B4/M-B5 package pins unchanged | §13 |
| R-6 | W6-4 policy | `W6_4_CLEAN_COMMITTED = REVIEWED_ADOPTION_PATH_ALLOWED` (bounded); `W6_4_DATA_ONLY_IN_WAL = STOP / OWNER_ADJUDICATION_REQUIRED` | §6 |
| — | runtime `TimeoutExpired` change | `DEFERRED`: no installed-release payload change in this slice | §9 |
| — | owner-computed head | the real owner derive is **not** performed; `19bf9091…1630` stays `CROSS_CHECK_ONLY / NOT_OWNER_COMPUTED / NOT_ACCEPTED`; no S25 or owner-custody contact | §5 |

```text
owner decision recorded != M-B6 authorized
MB6_CONTINUITY accepted != M-B6 go;  phase-bound DR-5 rule accepted != post-M-B6 baseline accepted
P1B-6 proof implemented != P1B-6 PASS;  M-B6 acceptance != M-B7 authorization
```

## 1. What M-B6 is (proven in the preflight; unchanged)

| Item | Value |
| --- | --- |
| Sequencer step | `PROVISION_LEDGER`, `TRUST_INSTALLED → LEDGER_PROVISIONED`, mutation `M-B6`, gate `REQUIRED_UNKNOWN_BLOCK`, no point of no return (`pr1b_sequencing.STEPS`) |
| Required evidence | `ledgerSequenceIsOne`, `ledgerHeadEqualsOwnerComputed`, `ledgerSchemaFingerprintVerified` |
| Host command | `/usr/local/sbin/lilith-authority-ledger-dev provision 1`: a root half (`prepare_state_directory`), then the signer half through `runuser … provision-as-signer 1` |
| Writes | `/var/lib/lilith-authority-dev` (`lilith-authority-dev`, `0700`) and `authority_ledger.db` (`0600`) with exactly one ledger-journal `GENESIS` row at sequence 1 |
| Does not | create a witness genesis or candidate; install the authorization-register or genesis-pin copy; make Registry V1 effective; activate authority; start the signer or the witness |
| Code that runs | the installed release `aee323e`. `lilith_authority_root/{cli,ledger_tool}.py`, `lilith_authority_dev/ledger.py` and `authority_ledger_journal.py` are byte-identical at control. **This slice changes none of them** |

## 2. Files

| File | Change | Role |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb6_ledger_verifier.py` | new (DEV, root, release interpreter) | §3, §4: read-only POST verifier and W6 classifier. SHA-256 `6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5` |
| `services/owner-memory-control/tools/mb6_ledger_recovery.py` | new (DEV, root, release interpreter) | §6: bounded pre-M-B9b recovery. SHA-256 `8c2db24970a1e97f19e98574d712459ccfbe185ea669755235dc0b24ba71c612` |
| `services/owner-memory-control/tools/mb6_expected_ledger_head.py` | new (owner workstation) | §5: off-host expected ledger position. SHA-256 `5ecaaaaeba57c8a1afe0d76d0fa0ecaa4ef6bff35d291dc84e0fe7a205a019c8` |
| `services/owner-memory-control/tools/mb6_ledger_denial_proof.py` | new (DEV, root, system interpreter) | §13: the separate P1B-6 ledger denial proof (decision R-3). SHA-256 `470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0` |
| `services/owner-memory-control/tools/mb6_operator.py` | new (owner laptop) | §7: the M-B6 operator. It pins the four tools above and the unchanged installer, W5 verifier, observer, broker verifier and P1B-5 denial proof |
| `services/owner-memory-control/tests/test_b1b3e_mb6_ledger_remediation.py` | new | §10: 34 tests |
| `services/owner-memory-control/tests/test_b1b3e_mb6_ledger_denial_proof.py` | new | §13: the P1B-6 proof, its exact transcript, refusals, and the unchanged P1B-5 / M-B4/M-B5 pins |
| `services/owner-memory-control/tests/test_b1b3e_mb6_remediation_record.py` | new | this record, the errata, the owner decisions and the governance boundaries |
| `services/authority-dev/tests/test_pr1s_root_tooling.py` | one test changed | T-1: the dead `if False` branch is replaced by the real signer half (§10) |
| the [PR-1 live install preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md), the [PR-1B bootstrap sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) | erratum blocks appended; original text preserved | §11: D-1 … D-5 |
| the [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md) §9, the [current B-5 grant](slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md) §7, the [M-B4/M-B5 ceremony package](slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md) §3 | governance-clarification blocks appended; original text preserved | §12.3: decision R-2B |
| [acceptance ledger](current-architecture-acceptance-ledger-v0.1.md) §13.1ae, §13.1af, the AUTH-02 cell, the [README](README.md) | two sections, one sentence, one row | the current-state reconciliation and the owner decisions |

Unchanged (pinned):

- `install_authority_dev.py` (`fe10d9a3…`);
- `mb4_mb5_trust_install_verifier.py` (`78f57c01…`), imported unchanged as the trust and registry judge;
- `authority_custody_denial_proof.py` (`f4e39c81…`, the P1B-5 proof; decision R-3 keeps it unchanged);
- the M-B4/M-B5 operator (`e380ab18…`) and every pin in its `TOOL_PINS`, including the remove-before-M-B6 tool
  (`db0629a6…`);
- `deployer_authority_boundary_proof.sh` (DR-5);
- every `services/authority-dev` runtime, release-payload and file-set file.

## 3. M-B6 POST verifier (`mb6_ledger_verifier.py`)

**How it runs:**

- On DEV, as root, under the installed release interpreter.
- The operator streams it as an in-memory bundle together with the unchanged W5 verifier (§7).
- Forms are `observe <head>` and `expect <PHASE> <head>`. `<head>` is the owner-computed expected head (§5) and is
  never a host value. There is no path argument.

**It is read-only by construction.** The ledger is never opened as a database:

- the database file and its WAL are read as bytes, through bounded `O_NOFOLLOW` descriptors;
- the **committed** state is rebuilt in memory by the SQLite WAL recovery rule;
- that image is examined through an in-memory `sqlite3` connection (`deserialize`).

It creates no temporary copy, no `-shm`, no checkpoint and no lock. A test asserts that the source contains no
write, chmod, unlink, mkdir, subprocess or fsync, and that a verification leaves the host tree bit-identical.

**The WAL recovery rule it applies:**

- The header is valid only with:
  - the magic;
  - version 3007000;
  - a power-of-two page size in [512, 65536];
  - a matching header checksum.
- Frames count while their salts match, the page number is non-zero and the cumulative checksum holds.
- Only frames up to the last commit frame are applied.
- A differential test confirms the rebuilt rows equal SQLite's own recovery of an on-disk copy.

**The successful state (`LEDGER_COMMITTED_EXACT`) requires every one of these:**

| Check | Meaning |
| --- | --- |
| `trustRegistryExact` | `mb4_mb5_trust_install_verifier.evaluate`: `anchorsEqualOwnerCopies`, `witnessAnchorNamesKWit`, `registryVerifiesOnHost` all true |
| `hostInputReasonsExactlyW5Gaps` | the runtime reader reports exactly `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING` (§15) |
| `genesisOpEqualsRegistryV1` | `authority_ledger_journal.genesis_op(installed registry v1)` = the op implied by the accepted pins (E0 `(1, 11f18488…)`, `policy.dev-synthetic.v1`, `registryVersion` 1, `signingKeyIds` = [K-ACT keyId]) |
| `ownerHeadIsHeadOfRegistryV1` | the owner's `<head>` = `next_head(0^32, op)` by the release journal and by an independent restatement |
| `stateDirectoryExact` / `ledgerFileExact` | signer `uid:gid`, `0700` / `0600`, real directory and regular file, never a symlink |
| `laterStateAbsent` | no witness state, credentials runtime directory, owner/witness socket, owner-input copy or HELD record |
| the content checks | the following items, all from the committed image |

The content checks:

- `integrity_check` is `ok`;
- the header is in WAL mode;
- the schema fingerprint is the pinned `65127a68…9cb7`, which equals `ledger.SCHEMA_FINGERPRINT`;
- the meta row is `(1, 1, dev, DEV_SYNTHETIC)`;
- there is **exactly one** journal row: sequence 1, op `GENESIS`, payload = JCS(op);
- `prev_head` is `0^64`, and the head chain is valid;
- **head = owner head**;
- `ledger_epoch` is exact;
- there is exactly one epoch row, and it is exact;
- the challenge, evidence and use tables hold no rows.

Only in that state are the three sequencer evidence items `true`. The report also states:

- `registryEffective=false`, `authorityActive=false`, `authorityGranted=false`;
- `witnessGenesisPresent=false`;
- `ownerRegisterCopyPresent=false`, `genesisPinCopyPresent=false`.

## 4. The W6 classifier

**Host phases** come from the verifier alone.

| Host phase | Exact condition |
| --- | --- |
| `W6_0_NO_MB6_MUTATION` | state directory absent; trust exact; W5 gaps exact; no later state |
| `W6_1_STATE_DIRECTORY_INEXACT` | a real, empty directory, owned `root:root` with no group/other bits: `mkdir` done, `chown`/`chmod` not |
| `W6_2_STATE_DIRECTORY_EXACT_EMPTY` | exact signer-owned `0700`, empty: the root half finished, the signer half created nothing |
| `W6_3_LEDGER_INCOMPLETE` | exact directory; entries ⊆ {db, `-wal`, `-shm`}, all signer-owned with no group/other bits; the **committed** image is empty or has no schema (the one M-B6 transaction never committed) |
| `LEDGER_COMMITTED_EXACT` | every §3 check true; `ledgerClean` = the database is the only entry |
| `OUT_OF_SCOPE_LATER_STATE` | any M-B8-or-later state present |
| `UNCLASSIFIED_STOP` | anything else, for example: a `-journal`; an extra entry; a symlink; an inexact directory with entries; a committed but inexact ledger; a wrong head; a torn WAL header over a non-empty database; trust not exact |

**Sequence phases** combine the host phase with the operator's own records: the attempt marker, the transcript
class (§7) and the POST record.

| Sequence phase | Rule (`classify_sequence`, pure) |
| --- | --- |
| `W6-0` | host `W6_0` (go consumed or not; a refusal before mutation consumes the go) |
| `W6-1`, `W6-2`, `W6-3` | the same host phase, after a consumed attempt whose transcript is not `CLI_SUCCESS_EXACT` |
| `W6_4_COMMITTED_CLI_INCOMPLETE` | host committed, and the transcript is not an exact success (traceback, timeout, ssh loss, output not exact) **or** the ledger is not clean |
| `W6_5_CLI_SUCCEEDED_POST_PENDING` | host committed and clean, transcript `CLI_SUCCESS_EXACT`, no POST record |
| `W6_6_POST_VERIFIED_ACCEPTANCE_PENDING` | as W6-5, plus the operator's `POST_VERIFIED` record |
| `UNCLASSIFIED_STOP` | any inconsistency, for example: M-B6 state with no attempt; a success transcript without a committed ledger; a refusal that left a committed ledger |

An exact success transcript is exit 0, empty stderr, and exactly two JSON lines:

1. the signer half's line;
2. the root half's line, carrying `stateDirectory` = `CREATED` from W6-0, or `ADOPTED_NO_MUTATION` from W6-2.

## 5. The owner-computed expected ledger position (`mb6_expected_ledger_head.py`)

**The mechanism** runs off-host, from the owner's own files. No DEV input decides the value.

- **`derive <authority-registry.v1.json> <registry-root.json>`:**
  1. Both files must hash to the accepted installable pins (`46b0bfc5…`, `bc5f00a7…`) and parse as exact JCS.
  2. The registry must verify under the root anchor at its own epoch, with:
     - digest `fa662721…`;
     - root key E-21 and the accepted root keyId;
     - E0 and policy;
     - the single key = K-ACT.
  3. The tool then computes `genesis_op` and `initial_position` with the **merged-main**
     `authority_ledger_journal`.
- **Every head is computed twice:** once by the journal, and once by an independent restatement of the head
  function and of JCS for this value class. The two must be equal.
- **The `derive` result must also equal the head derived from the accepted pins.**
- **It pins nothing and accepts nothing.** The operator's `expected` form runs `derive` twice and writes the
  result once to a new `<workdir>/expected`.

The architecture defines **no separate GENESIS-op digest**. `genesisOpJcsSha256` is reported for
reproducibility only.

**The concrete value, synthetic/test conditions.**

- The test world's `derive` head equals:
  - `J.initial_position(registry)`;
  - the head the real `ledger_tool` provisions;
  - the head the verifier observes.
- **Pin-derived cross-check for the real accepted Registry V1.** This comes from the accepted public
  identities alone (`mb6_expected_ledger_head.py pins`). It is **not owner-computed and not accepted**:

| Item | Value |
| --- | --- |
| ledger sequence | `1` |
| GENESIS op (JCS) | `{"environment":"dev","op":"GENESIS","policyVersion":"policy.dev-synthetic.v1","recoveryEpoch":{"counter":1,"random":"11f184889f333dece054f3b91a301632"},"registryVersion":1,"signingKeyIds":["test-only.dev-synthetic.actor.b1b3d.1"]}` |
| `genesisOpJcsSha256` (informational) | `8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60` |
| pin-derived ledger head | `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630` |

**The owner value is not yet produced.** The owner's `derive` over the owner-held Registry V1 installable
(`46b0bfc5…`) and root anchor (`bc5f00a7…`) remains a preparation step. It needs the owner's files, which this
repository-only pass did not touch. It must reproduce the head above, or the tool refuses
(`PIN_CROSS_CHECK_DISAGREES`). Pinning it is a separate owner decision.

**Owner instruction (2026-10-07).** The real owner-held Registry V1 derive is **not** performed in this slice:
no S25 or owner-custody contact. `19bf9091…1630` is not pinned merely because the repository cross-check produced
it; it stays `CROSS_CHECK_ONLY / NOT_OWNER_COMPUTED / NOT_ACCEPTED`. The owner derive happens only after this slice
is merged and canonicalized.

## 6. Recovery (`mb6_ledger_recovery.py`)

**Governance basis:**

- Removal is allowed before M-B9b: preflight §29 and F-5, sequencing C-7.
- The owner decided that "partial = permanent STOP" is **not** the design target.

**What the tool is:**

- It is the one reviewed way to act on an interrupted M-B6.
- It is **not** a reset and **not** a retry: it never runs `provision` and never writes a ledger byte.

**How it runs:**

- `plan <head>` is read-only. It prints the plan and its `planDigest`, which binds:
  - the classified phase;
  - the action;
  - each target's inode, device, size, times and SHA-256;
  - the state directory's identity;
  - the full verifier observation.
- `recover <head> <planDigest>` re-derives the plan. It refuses `PLAN_CHANGED` unless the plan is identical, then
  acts once and re-classifies.

| Window | Action | Result | Rationale |
| --- | --- | --- | --- |
| W6-1 | `REMOVE_EMPTY_STATE_DIRECTORY`: `rmdir`, fsync `/var/lib` | `W6_0` | back to pre-M-B6. Completing the `chown` instead would finish M-B6's own work, which is a silent retry |
| W6-3 | `REMOVE_UNCOMMITTED_LEDGER_FILES`: unlink the present `-wal`, `-shm`, then the database; fsync the directory | `W6_2` | nothing was committed; the exact directory stays, and a **new** go may re-run `provision 1`, which adopts it (`ADOPTED_NO_MUTATION`) |
| W6-4, clean | `ADOPT_COMMITTED_LEDGER`: fsync the ledger file and the state directory; **no byte is written** | `LEDGER_COMMITTED_EXACT` | the ledger is deterministic, exact and owner-head-equal; durability cannot be observed afterwards, so it is made certain. **A valid committed ledger is never deleted** |
| W6-4, data still in the WAL | none: `OWNER_ADJUDICATION_REQUIRED` | — | adoption would need a checkpoint, which is a signer-uid SQLite write not reviewed as a recovery primitive; leaving the WAL makes the state differ from the reviewed success state; deleting a valid ledger is not wanted. **STOP / OWNER ADJUDICATION REQUIRED** |
| W6-0, W6-2 | none: `NOTHING_TO_RECOVER` | — | W6-2 is re-entered only by a new go |
| any other phase | refused | — | uncertain = STOP |

**Bounds:**

- root on `lilith-dev-01` only;
- refused while any M-B8-or-later state exists, so after M-B9b it can never run;
- only the state directory and the three ledger artifact names;
- no trust, registry, owner-freshness, witness, hold or credential change;
- no unit action;
- no burn or point of no return reopened.

**Any use needs a separate explicit owner authorization naming the plan digest** (the operator's `recovery`
template, §7).

### 6.1 W6-4 policy (owner decision R-6, ACCEPTED 2026-10-07)

```text
W6_4_CLEAN_COMMITTED = REVIEWED_ADOPTION_PATH_ALLOWED
W6_4_DATA_ONLY_IN_WAL = STOP / OWNER_ADJUDICATION_REQUIRED
```

**Clean committed W6-4.** The reviewed adoption path (`ADOPT_COMMITTED_LEDGER`) is allowed **only** where the
reviewed classifier proves every one of:

- `LEDGER_COMMITTED_EXACT`;
- sequence = 1;
- the schema fingerprint is exact;
- the exact GENESIS op;
- the exact owner-computed head;
- no later bootstrap state;
- the ledger is clean (the database is the only entry);
- the required durability / adoption checks pass (fsync of the ledger file and the state directory; no byte
  written).

The valid committed ledger must not be deleted merely because the original CLI response was lost. Adoption still
needs the separate plan-digest authorization above.

**W6-4 with data only in the WAL.** The policy is **STOP / OWNER_ADJUDICATION_REQUIRED**. The tool does not, and
no procedure may:

- checkpoint it;
- delete it;
- adopt it;
- rerun `provision`;
- mutate it;
- infer successful durability.

No recovery mutation is authorized for that state until a separately reviewed procedure exists and the owner
explicitly authorizes it. The recovery tool's plan for it is `OWNER_ADJUDICATION_REQUIRED` with
`mutating = false`, and `recover` refuses it.

**Point of no return.** M-B6 still has none (`ponr=None`; preflight §29, "no, until M-B9b"). With this tool, the
reviewed pre-M-B9b removal path exists for W6-1 and W6-3. The adoption path exists for a clean W6-4.

## 7. The M-B6 operator (`mb6_operator.py`)

**Forms:**

| Form | Kind |
| --- | --- |
| `pins` | local |
| `expected` | local |
| `cloud` | read-only |
| `host … PRE\|POST` | read-only |
| `denial` (existing phase `P1B-5`, unchanged tool) | read-only |
| `ledger-denial` (separate tool, phase `P1B-6`, §13) | read-only |
| `mb6` | mutation, one attempt |
| `post` | read-only |
| `classify` | read-only |
| `recovery-plan` | read-only |
| `recovery` | mutation, separate authorization |

**What `host` reads:**

- identity and custody;
- release readiness: the 18 release modules the bundle loads, at their `aee323e` hashes, plus the
  `sqlite3.deserialize` capability;
- installer `status --expect P1B-5` (PRE) or `P1B-6` (POST);
- broker preservation and the observer;
- the W5 verifier: `expect W5_INSTALLED_CONTENT_VERIFIED` (PRE) or `expect OUT_OF_SCOPE_POST_LEDGER` (POST);
- the M-B6 verifier: `expect W6_0_NO_MB6_MUTATION` (PRE) or `expect LEDGER_COMMITTED_EXACT` (POST).

**Bundles.** The verifier and recovery bundles are a gzip'd JSON of module sources, piped to a fixed in-memory
loader:

- the loader refuses (exit 96) unless every module's SHA-256 equals its pin;
- it registers each module before executing it;
- it writes no file;
- a test runs it for real.

**One attempt: `mb6 <repo> <workdir> <go-file>`.** In order:

1. `pins`: a clean checkout at the control commit, with every tool exact.
2. The owner-computed head from `<workdir>/expected`.
3. The go file must carry every binding line (§8) with the control commit, the head and the pre-state
   (`W6_0…` or `W6_2…`).
4. The marker must not exist, and the classifier tool must load.
5. A **read-only** pre-state check: the verifier `expect <pre-state> <head>`.
6. The `O_EXCL` marker `attempts/mb6.json` (`invocationsPermitted: 1`).
7. **Exactly one** `ssh` running `sudo -n /usr/local/sbin/lilith-authority-ledger-dev provision 1`, behind the
   hostname guard.
8. The transcript is saved and classified.

Every refusal in steps 1–5 happens before the marker, so it consumes nothing.

**After the marker, the attempt is consumed whatever happens:**

- exit 0, `REFUSED`, a traceback, ssh loss and a local timeout all count;
- a timeout is recorded as `TRANSPORT_FAILED`;
- there is no retry and no second invocation path;
- the source holds exactly one `self.ssh(PROVISION)`.

**After the attempt:**

- `post` writes `<workdir>/post` and computes the sequence phase. Only on W6-5 with every code 0, readiness exact,
  the three evidence items true and `registryEffective` / `authorityGranted` false does it write `POST_VERIFIED`
  (W6-6).
- It **never continues to M-B7**. Owner acceptance of `LEDGER_PROVISIONED` is separate.
- The owner-acceptance evidence after W6-6 includes `denial` (P1B-5) PASS and `ledger-denial` (P1B-6) PASS
  (§13).

> **Note (2026-10-07, M-B6 ceremony package; the text above is unchanged).** The
> [ceremony package](slice-15b2b-b1b3e-mb6-ceremony-package.md) extends the operator. The readiness probe also
> imports `lilith_authority_root.cli` and pins all 38 release modules of the `provision` path plus the installed
> CLI wrapper (§2.2 there); the merged probe covered only the 18 verifier-bundle modules. The go lines also bind
> the operator, verifier, recovery and P1B-6 proof SHA-256, and `mb6` refuses `OPERATOR_NOT_AT_CONTROL` unless
> the running operator equals its bytes at `HEAD`. The verifier, recovery, expected-head and P1B-6 tools are
> unchanged.
- A partial outcome goes to `classify`, then `recovery-plan`, then (separately authorized) `recovery`.

## 8. M-B6 continuity (owner decision R-1, ACCEPTED 2026-10-07)

```text
MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO
```

The owner accepted this model for M-B6 only. It is not broadened to later M-steps. Accepted semantics:

| # | Accepted semantics |
| --- | --- |
| MC-1 | One owner-attended, evidence-bounded preparation/execution sequence. |
| MC-2 | One fresh evidence set. |
| MC-3 | One deploy freeze from the start of the live preparation sequence through technical POST and owner acceptance or sequence termination. |
| MC-4 | The owner-computed expected ledger head must be derived and pinned before the M-B6 go. |
| MC-5 | KNOWN_EMPTY must be freshly established from accepted Replica A and Replica B evidence before eligibility/go. |
| MC-6 | Exactly one explicit M-B6 owner go. |
| MC-7 | Exactly one physical `/usr/local/sbin/lilith-authority-ledger-dev provision 1` invocation. |
| MC-8 | A REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other post-marker STOP consumes the go. |
| MC-9 | Failures before the attempt marker is created consume nothing. |
| MC-10 | There is no automatic retry. |
| MC-11 | Partial outcomes are classified using the reviewed W6 classifier and may enter only an explicitly reviewed recovery/adoption path. |
| MC-12 | Technical M-B6 success and owner acceptance of `LEDGER_PROVISIONED` are separate. |
| MC-13 | M-B6 acceptance does NOT authorize M-B7. |
| MC-14 | No wall-clock TTL. |
| MC-15 | Relevant drift or uncertainty means REVALIDATE / current sequence not reusable. |

**Not inherited from M-B4/M-B5.** M-B6 is one physical operation with one go, not two stages with two gos.
Nothing in M-B4/M-B5 Sequence-2 evidence is replayed.

**How the operator binds it (§7).**

| Semantics | Mechanism |
| --- | --- |
| MC-4 | `mb6` refuses without `<workdir>/expected`, and the go must name that head |
| MC-6, MC-7 | the `O_EXCL` marker `attempts/mb6.json` with `invocationsPermitted: 1`; the source holds exactly one `self.ssh(PROVISION)` |
| MC-8 | every outcome after the marker returns `attempt: CONSUMED` (`MB6_STOP` unless `CLI_SUCCESS_EXACT`) |
| MC-9 | every refusal in steps 1–5 (§7) is raised before the marker exists |
| MC-10 | a second `mb6` in the same work directory refuses `ATTEMPT_ALREADY_CONSUMED:mb6` and invokes nothing |
| MC-11 | `post` / `classify` → `recovery-plan` → separately authorized `recovery` (§4, §6) |
| MC-12, MC-13 | `POST_VERIFIED` records `ownerAccepted: false`; `post` says "M-B7 is not authorized" |

**Go template.** The binding lines are `mb6_operator.MB6_GO_LINES`. They include:

- the `MB6_CONTINUITY` value;
- the deploy-freeze line (MC-3);
- "Command: /usr/local/sbin/lilith-authority-ledger-dev provision 1, exactly one invocation";
- the pre-state;
- the owner head;
- Registry V1 digest `fa662721…`;
- the KNOWN_EMPTY statement;
- the W5-gap statement;
- the M-B7 boundary;
- the post-marker consumption and no-automatic-retry line.

## 9. Timeout hardening (F)

**The finding.** In the installed CLI, `subprocess.run(..., timeout=120)` in the root half raises
`subprocess.TimeoutExpired`. `cli.main` does not catch it: it catches `OSError`, and `TimeoutExpired` is a
`SubprocessError`. The result is an uncontrolled traceback and exit 1, after the signer child is killed. A
characterization test proves this. The host can then be in any of W6-2 … W6-4.

**The runtime fix is NOT applied.** `lilith_authority_root/cli.py` is release payload: it is in `ROOT_MODULES`
and covered by the runtime manifest. Changing it would:

- make merged source diverge from the installed `aee323e`, which M-B6 actually runs;
- invalidate the "code identical to the installed release" fact the preflight relied on;
- take effect only after a new release install, which is a PR-1A-class operation.

That is not a narrow, behaviour-preserving change at this point.

**The hardening is applied at the operator instead.**

- Any exit other than an exact success, or `REFUSED` with exit 2, is `CLI_FAILED_UNCLASSIFIED`. That includes
  exit 1 with a traceback.
- ssh 255 and a local timeout are `TRANSPORT_FAILED`.
- The host is then classified by the verifier, never by the CLI's output.

A runtime `TimeoutExpired → REFUSED` change is recorded as optional future hardening for a later release.

**Owner decision (2026-10-07): DEFERRED.** The installed release payload is not modified in this slice. The
reviewed M-B6 operator continues to treat any result other than an exact success or a clean `REFUSED` as a
failure, and classifies the actual host state with the independent verifier. A runtime timeout fix may be
considered in a future release and needs its own release and redeployment review.

## 10. Tests (T-1 … T-3 closed)

| Owner item | Test (`test_b1b3e_mb6_ledger_remediation.py` unless noted) |
| --- | --- |
| 1 root half success | `test_root_half_and_signer_half_success` |
| 2 signer half success | `test_signer_half_alone_success_and_refusals`; T-1: `test_pr1s_root_tooling.test_ledger_provisioning_is_two_halves_and_one_time` now calls the real `provision_as_signer` (the dead `if False` is gone) |
| 3, 4 CLI `provision` / `observe` | `test_cli_provision_and_observe`: the real `cli.main`, the exact `runuser` argv, `FIXED_ENV`, timeout 120, the exact two-line stdout |
| 5 positive `status --expect P1B-6` | `test_positive_status_expect_p1b6` |
| 6, 7 sequence 1, head, fingerprint | `test_committed_clean_ledger_is_the_post_state`, `test_verifier_is_read_only_by_construction` |
| 8, 9 adoption / unsafe directory | `test_exact_empty_directory_is_adopted_and_unsafe_directory_refused` |
| 10–15 W6-1 … W6-6 | `test_w6_1_and_w6_2_directory_windows`, `test_w6_3_uncommitted_windows`, `test_w6_4_committed_in_the_wal_is_exact_and_matches_sqlite`, `test_committed_clean_ledger_is_the_post_state`, `test_post_then_classify_w6_5_to_w6_6`, `test_post_after_an_incomplete_cli_is_w6_4` |
| 16, 17 existing DB / sidecars / `-journal` | `test_signer_half_alone_success_and_refusals`, `test_sidecar_or_journal_before_provisioning_is_refused`, `test_owner_head_mismatch_and_unexpected_artifacts` |
| 18 owner-head mismatch | `test_owner_head_mismatch_and_unexpected_artifacts` |
| 19, 20 registry mismatch, wrong `signingKeyIds` | `test_wrong_signing_key_ids_and_wrong_registry`, `ExpectedHeadTests.test_refusals` |
| 21 one-attempt operator | `test_one_attempt_exactly_one_provision`, `test_failures_consume_the_go_and_never_retry`, `test_refusals_before_the_marker` |
| 22 tool pin mismatch | `test_refusals_before_the_marker`, `test_bundle_loader_is_hash_gated_and_runs_in_memory`, `test_tool_pins_are_the_tree` |
| 23 no later-state mutation | `test_root_half_and_signer_half_success` (only the directory and the database appear), the recovery tests (nothing outside the state directory changes) |
| 24 no witness / service activation | `test_positive_status_expect_p1b6` (units inactive; no `systemctl start`), `test_ledger_tool_never_activates_a_unit`, `test_later_state_is_out_of_scope` |

**Recovery** is covered by the W6-1, W6-3 and clean-W6-4 tests, the WAL W6-4 adjudication test, plan binding, and
refusals outside the pre-M-B9b bound.

**Uid coverage.** The signer half refuses euid 0 by design, so 7 tests need a non-root uid. The positive P1B-6
contract needs `0 < uid < 1000` (the system-account contract) or root. GitHub CI runs as uid 1001, so it skips
that one test with an explicit reason. Local runs used uid 777 (all run) and root (the non-root tests skip).

## 11. Errata D-1 … D-5

Each erratum is appended to the original record as a dated block; the original text is unchanged.

| # | Where | Correction |
| --- | --- | --- |
| D-1 | sequencing §4.4 | provisioning has several durability windows (the `mkdir`/`chown`/`chmod` steps, an `O_EXCL` empty file, then one transaction). Storage without a GENESIS row **can** exist: W6-1, W6-2, W6-3 |
| D-2 | preflight §27 (M-B6 row) | the rollback boundary is **before M-B9b** (§29, F-5, C-7), not "before M-B9" |
| D-3 | preflight §14 | the code adopts an exact, empty, signer-owned `0700` state directory unchanged (`ADOPTED_NO_MUTATION`); it refuses only an unsafe directory or any existing ledger artifact |
| D-4 | preflight §27 (M-B8 row) | M-B8 (`install-owner-inputs`, P1B-8) installs **both** the genesis-pin copy and the authorization-register copy |
| D-5 | preflight §2 | naming hazard: ledger `GENESIS` op (M-B6, a journal row) ≠ witness genesis candidate (M-B7) ≠ `OwnerGenesisPinV1` (M-B8) ≠ committed witness genesis (M-B9b) |

## 12. Post-M-B6 DR-5 expected delta (phase-bound rule ACCEPTED; derived baseline NOT YET PRODUCED)

**DR-5 is not changed, extended or rebaselined here.** The DR-5 script is unchanged, and no global DR-5
rebaseline happens.

### 12.1 Exactly what M-B6 changes in DR-5 output

This is derived from `scripts/deployer_authority_boundary_proof.sh`. Only two code paths read the new paths:

- the `AB_PR1_UNOBSERVABLE` leaf loop;
- `ab_check_later_state` (`AB_LATER`, first entry).

| Before M-B6 (accepted baseline) | After M-B6 (any of W6-1 … W6-6) |
| --- | --- |
| `DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev/authority_ledger.db (/var/lib/lilith-authority-dev absent)` | `UNOBSERVABLE_BY_DESIGN: /var/lib/lilith-authority-dev/authority_ledger.db (beneath root-only /var/lib/lilith-authority-dev; checked only by root tooling)` |
| `DEFERRED_UNTIL_OBJECT_EXISTS: /var/lib/lilith-authority-dev (later step)` | `DENIED: test -w /var/lib/lilith-authority-dev`, `DENIED: test -r /var/lib/lilith-authority-dev`, `DENIED: test -x /var/lib/lilith-authority-dev` (in that order) |

**Counts derived from source.** These must be confirmed against the owner-held accepted log text.

| | Before | After |
| --- | --- | --- |
| DR-5 block lines | 147 | 149 |
| `DENIED` | 130 | 133 |
| `DEFERRED_UNTIL_OBJECT_EXISTS` | 5 | 3 |
| `UNOBSERVABLE_BY_DESIGN` | 5 | 6 |

If no other deploy-time proof prints these paths, the full result set goes from 186 lines / 158 `DENIED` to
188 / 161. The repository shows that only DR-5 probes them.

**Unchanged:**

- `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`;
- `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`;
- `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.

The same delta appears for W6-1 … W6-3: DR-5 cannot tell those phases apart.

### 12.2 Accepted rule: `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` (owner decision R-2A, 2026-10-07)

```text
POST_MB6_DR5_RULE = PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA  (owner-accepted phase-bound governance rule)
```

The owner accepted this governance model. The rules:

| # | Accepted rule |
| --- | --- |
| DR6-1 | Preserve the accepted pre-M-B6 DR-5 baseline unchanged as historical evidence (run `36552218231`: result set `f1869234…`, DR-5 block `a1d98773…`, pre-deploy block `f5087042…`). |
| DR6-2 | M-B6 is known by design to change only the specifically derived DR-5 lines associated with `/var/lib/lilith-authority-dev` and the ledger leaf (§12.1). |
| DR6-3 | Derive the expected post-M-B6 DR-5 text offline from the accepted pre-M-B6 text and the reviewed DR-5 source. |
| DR6-4 | Do NOT treat arbitrary differences as expected. |
| DR6-5 | The phase-specific comparison target is selected only after the host phase is independently verified (the M-B6 verifier). |
| DR6-6 | W6-1, W6-2 or W6-3 do not establish an accepted post-M-B6 DR-5 baseline. |
| DR6-7 | A deploy while the host is in an unresolved partial M-B6 phase is a STOP. |
| DR6-8 | Only a verified successful M-B6 state may use the post-M-B6 expected baseline. |
| DR6-9 | Any `ALLOWED` result remains an unexpected failure. |
| DR6-10 | Any change to `GRANT_ABSENT` remains an unexpected failure. |
| DR6-11 | Any difference outside the explicitly derived M-B6 delta remains drift. |
| DR6-12 | Acceptance of the derived post-M-B6 baseline is separate from the technical M-B6 invocation. |

**Baseline selection** by the independently verified host phase:

| Verified host phase | DR-5 comparison target |
| --- | --- |
| `W6_0_NO_MB6_MUTATION` | the preserved pre-M-B6 baseline |
| `LEDGER_COMMITTED_EXACT` | the derived post-M-B6 expected text (§12.1 substitutions only) |
| W6-1, W6-2, W6-3, `UNCLASSIFIED_STOP`, anything else | none: a deploy there is a STOP (DR6-6, DR6-7), and the M-B6 freeze (MC-3) forbids it |

**Derivation.** The post-M-B6 expected text is the accepted pre-M-B6 text with exactly the §12.1 substitutions
and nothing else. It is derived from the owner-held accepted log, never from a post-M-B6 run. A post-M-B6 deploy
must equal it byte-for-byte. Unchanged by design: `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`,
`AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`, `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.

**What is accepted and what is not.** The **rule** is accepted. The derived post-M-B6 **baseline** is not: it
has not been produced, and its acceptance is a separate owner act after a verified successful M-B6 (DR6-12).

**Open before the rule can be used (not before this slice's PR):**

- producing the derived text from the owner-held accepted log, and confirming the §12.1 counts against it;
- whether `verify_broker_dev_current_incarnation.py`'s reported (never judged) `CUSTODY_PATHS` lines enter the
  deploy full result set;
- the reboot comparator's expected `PR1_OBJECT_CHANGED:/var/lib/lilith-authority-dev`.

### 12.3 B-5 §9 after M-B1 (owner decision R-2B, 2026-10-07): governance clarification

```text
B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED
```

**The conflict this resolves.** The [decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md) §9 is
titled "Stop conditions that invalidate an authorization **before M-B1**". The merged
[M-B4/M-B5 ceremony package](slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md), a post-M-B1 step, imported it as a
live terminator (T-11, E-15; §13 and §14.1: a different DR-5 result set after a deployment "is a B-5 §9 stop and
**voids** the grant"). Because M-B6 changes the DR-5 result set by design (§12.1), carrying that forward would
permanently block M-B6 or void B-5 on the first post-M-B6 deploy.

**Owner clarification (accepted).**

1. The B-5 §9 voiding clause was scoped to the pre-M-B1 decision context.
2. Once M-B1 was successfully exercised and accepted (§13.1u of the acceptance ledger), that clause no longer
   acts as a standing global invalidator for later bootstrap phases.
3. It remains historical evidence explaining the conditions under which B-5 was originally granted.
4. Later bootstrap phases use their own accepted phase-specific evidence, continuity and DR-5 rules. For M-B6
   these are `MB6_CONTINUITY` (§8) and `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` (§12.2).
5. This does **not** retroactively alter M-B1, M-B2, M-B3, M-B4 or M-B5, and does not replay historical PASS
   evidence as current evidence. Where the M-B4/M-B5 package applied T-11 / E-15 within its own sequences, that
   application stands as history.

**How it is recorded.** As a dated governance-clarification block appended to the decision packet §9, the
current grant §7 and the M-B4/M-B5 ceremony package §3. The prior text is not rewritten.

## 13. Denial proof at P1B-6 (owner decision R-3: separate tool, IMPLEMENTED)

**Decision.** The pinned P1B-5 proof `scripts/authority_custody_denial_proof.py` (`f4e39c81…`) is **not**
modified, so there is no pin cascade through the accepted M-B4/M-B5 ceremony package and the reviewed
remove-before-M-B6 path stays reachable. A separate tool carries the M-B6 phase:

| Item | Value |
| --- | --- |
| File | `services/owner-memory-control/tools/mb6_ledger_denial_proof.py` |
| SHA-256 | `470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0` (pinned in `mb6_operator.TOOL_PINS`) |
| Phase | `P1B-6` only (closed); no path, principal or command argument |
| Runs | DEV, root, `/usr/bin/python3 -I -B -` streamed hash-gated by the operator's `ledger-denial` form, after a verified `LEDGER_COMMITTED_EXACT` |
| Writes | nothing; it reads `lstat`, the directory listing, two unit `ActiveState`s and the activation verifier |

**Preconditions, checked by root before any probe.** Any failure prints `FAIL: …` and ends
`MB6_LEDGER_DENIAL_PROOF=FAIL phase=P1B-6 reason=PRECONDITION probes=0` with no probe run:

1. the signer account exists and is not uid/gid 0;
2. `/var/lib/lilith-authority-dev` is a real directory (not a symlink), signer `uid:gid`, `0700`, holding exactly
   `authority_ledger.db` (a `-wal`, `-shm`, `-journal` or any other entry is refused);
3. `authority_ledger.db` is a regular file, signer `uid:gid`, `0600`, one link;
4. `lilith-authority-dev.service` and `lilith-recovery-witness.service` are `inactive` (no signer or witness
   activation implied);
5. `lilith-activation-verify` exits 1 with exactly one line beginning
   `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` (`GRANT_ABSENT` preserved).

**The fixed rows.** Each row is `runuser -u <principal> -- /usr/bin/test <op> <path>` for the principals
`lilith`, `sa_112096412008414111981`, `lilith-memory-broker`, `lilith-recovery-witness`. The signer owns the
state by design and is never probed.

| # | Op | Path | Meaning | Principals | Expected |
| --- | --- | --- | --- | --- | --- |
| L-1 | `-r` | `/var/lib/lilith-authority-dev` | unauthorized read (listing) | 4 | 4 `DENIED` |
| L-2 | `-x` | `/var/lib/lilith-authority-dev` | unauthorized traversal | 4 | 4 `DENIED` |
| L-3 | `-w` | `/var/lib/lilith-authority-dev` | unauthorized write | 4 | 4 `DENIED` |
| L-4 | `-r` | `/var/lib/lilith-authority-dev/authority_ledger.db` | unauthorized ledger read | 4 | 4 `DENIED` |
| L-5 | `-w` | `/var/lib/lilith-authority-dev/authority_ledger.db` | unauthorized ledger write | 4 | 4 `DENIED` |

Exit 1 is `DENIED`; exit 0 is `FAIL: ALLOWED(unexpected)`, never acceptable; any other exit is
`FAIL: PROBE_INCONCLUSIVE`.

**Expected PASS transcript: 28 lines.**

| Lines | Content |
| --- | --- |
| 2 | `STATE:` the directory and the ledger, exact |
| 2 | `UNIT: … ActiveState=inactive` |
| 1 | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| 20 | `DENIED:` (5 rows × 4 principals) |
| 1 | `SCOPE: denial only; ledger provisioned != Registry V1 effective != authority active; signer and witness not started` |
| 1 | `MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0` |

Counts: `DENIED` 20, `ALLOWED` 0, `FAIL` 0, probes 20. The output carries no time, pid, inode or size, so it is
deterministic; the operator records the transcript SHA-256 for ceremony-package pinning.

> **Erratum (2026-10-07, M-B6 completion; owner determination `P1B6_LINE_COUNT_DISCREPANCY = DOCUMENTATION_ERRATUM_ONLY`; the text above is unchanged).**
> The P1B-6 PASS transcript has **27** lines, not 28: 2 state + 2 unit + 1 `GRANT_ABSENT` + 20 `DENIED` probes + 1 scope + 1 PASS.
> The live M-B6 transcript (`f8722cb7…2e2b`) is byte-equal to the 27-line PASS transcript bound by the merged tests. This is a documentation count error only.
> It does not alter P1B-6 PASS, M-B6 technical success, W6-6, the owner acceptance, the ledger sequence, head, op or schema, the denial semantics, the deployment-freeze history, or any previous evidence result.
> See the [M-B6 completion record](slice-15b2b-b1b3e-mb6-provision-ledger-completion.md) §7.

**What it does not imply.** It does not imply that Registry V1 is effective, that authority is active, or that a
signer or witness started. `GRANT_ABSENT` is required, not changed. The signer mount-namespace probes stay at
P1B-12 in the existing tool.

**Use in M-B6.** Before the go, the operator runs the unchanged P1B-5 proof (`denial`). After a verified
W6-6, the owner-acceptance evidence for `LEDGER_PROVISIONED` includes both `denial` (P1B-5) PASS and
`ledger-denial` (P1B-6) PASS. The DR-5 deploy-time baseline is unaffected (§12).

## 14. KNOWN_EMPTY (K)

`KNOWN_EMPTY` refers to the **owner freshness register**: the P3-2 owner register, exactly two admitted replicas,
identical, with zero records (`pr1b_sequencing.owner_register_state`).

```text
KNOWN_EMPTY (owner freshness register) != OwnerAuthorizationRegisterV1 (authorization-register copy) != OwnerGenesisPinV1
```

- It is **not** `OwnerAuthorizationRegisterV1`. That register holds `authorizations: []` and
  `headRegistries: [(1, fa662721…)]`, and its host copy is M-B8's.
- The M-B6 code does not read or enforce it. `PROVISION_LEDGER`'s `REQUIRED_UNKNOWN_BLOCK` gate is a sequencer
  and procedure gate.
- A future M-B6 ceremony must freshly establish it, before the go, through the accepted Replica A + Replica B
  procedure (MC-4).
- No semantic ownership moves into host code.

## 15. The W5 gaps stay M-B8 work (L)

After a successful M-B6:

- `hostInputReasons` must be **exactly** `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING`. The
  verifier requires it (`hostInputReasonsExactlyW5Gaps`), and the success test asserts it.
- `ownerRegisterCopyPresent` and `genesisPinCopyPresent` are `false`.
- M-B6 success **must not** clear them. Any copy present makes the host `OUT_OF_SCOPE_LATER_STATE`.
- They are installed only by M-B8 (`install-owner-inputs`, which requires `status P1B-6`).

## 16. Remaining blockers

**Before the M-B6 remediation PR (this slice):** none in the repository. Owner review, staging, commit, push
and PR are the owner's decision.

**Before an M-B6 execution decision (after this slice is merged):**

| # | Class | Blocker |
| --- | --- | --- |
| B-1 | review | review and merge of this slice; canonicalization of the merged control |
| B-2 | evidence / preparation | the owner's off-host `derive` over the owner-held Registry V1 installable and root anchor at the merged control, then an owner pin of the expected head (§5, MC-4). `19bf9091…1630` is not that value |
| B-3 | evidence | the derived post-M-B6 DR-5 text from the owner-held accepted log, and the open items of §12.2 |
| B-4 | package | an M-B6 ceremony package binding the merged tool hashes (verifier, recovery, expected-head, P1B-6 proof, operator) |
| B-5 | evidence | the full fresh evidence set under MC-1 … MC-5, including DR-5 for every deploy since `37590712214` and after the merge, and KNOWN_EMPTY from Replica A and Replica B |
| B-6 | governance | the explicit M-B6 owner go (MC-6); none is given or implied here |
| B-7 | deferred | the runtime `TimeoutExpired` handling, only in a future release with its own review (§9) |

**Closed by the owner decisions of 2026-10-07:** R-1 (continuity), R-2 (DR-5 rule, B-5 §9), R-3 (P1B-6), R-6
(W6-4 policy). A procedure for W6-4 with data only in the WAL does not exist; that state is STOP / owner
adjudication (§6.1).

## 17. State

```text
M-B6 REMEDIATION / DESIGN = REPOSITORY ONLY (SOURCE + TESTS + DOCS); NOT MERGED
TRUST_INSTALLED = YES
REGISTRY_INSTALLED = YES
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO (OWNER-ACCEPTED 2026-10-07, R-1; M-B6 ONLY)
POST_MB6_DR5_RULE = PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA (OWNER-ACCEPTED 2026-10-07, R-2A); DR-5 UNCHANGED; NO GLOBAL REBASELINE
PRE_MB6_DR5_BASELINE = PRESERVED (HISTORICAL EVIDENCE)
POST_MB6_DR5_BASELINE = NOT DERIVED; NOT ACCEPTED
B5_SECTION_9_POST_MB1_STATUS = HISTORICAL_AFTER_MB1_EXERCISED (OWNER-ACCEPTED 2026-10-07, R-2B; CLARIFICATION, PRIOR TEXT PRESERVED)
P1B-6 DENIAL PROOF = SEPARATE TOOL IMPLEMENTED (R-3); P1B-5 TOOL AND M-B4/M-B5 PINS UNCHANGED; NOT RUN
W6_4_CLEAN_COMMITTED = REVIEWED_ADOPTION_PATH_ALLOWED (R-6; BOUNDED)
W6_4_DATA_ONLY_IN_WAL = STOP / OWNER_ADJUDICATION_REQUIRED (R-6)
RUNTIME TIMEOUT FIX = DEFERRED; NO RELEASE-PAYLOAD CHANGE
PIN-DERIVED LEDGER HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630 (CROSS-CHECK ONLY; NOT OWNER-COMPUTED; NOT ACCEPTED)
OWNER-COMPUTED LEDGER HEAD = NOT DERIVED; NOT PINNED; NOT ACCEPTED
AUTHORIZATION_REGISTER_COPY_MISSING + GENESIS_PIN_COPY_MISSING = PRESERVED (M-B8 WORK)
M-B6 = NOT AUTHORIZED
M-B7 = NOT AUTHORIZED
M-B8 = NOT AUTHORIZED
M-B9a / M-B9b = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO RUNTIME OR RELEASE-PAYLOAD FILE CHANGED
```
