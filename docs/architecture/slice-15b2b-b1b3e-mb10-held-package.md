# Slice 15B2b-B1b-3e — M-B10 / WRITE_HELD: INITIAL_CUSTODY HELD (Design, Tooling and Runbook)

Status:

- **REPOSITORY ONLY: DESIGN, DOCUMENTATION, VERIFIERS, A DR-5 TARGET TOOL, A DENIAL PROOF, AN OWNER-ELIGIBILITY
  TOOL, A READ-ONLY S25 STAGE, A BOUNDED SCRATCH RECOVERY, AN OPERATOR AND TESTS.** The owner authorized this
  design-and-tooling slice only (2026-10-10). Writing it contacted no live system: no DEV, no S25 and no owner key.
  **No M-B10 step has run. HELD is absent.**
- Packages P3-5 bootstrap step 12 (`WRITE_HELD`, M-B10) into one owner-attended sequence with **exactly one
  irreversible HELD write boundary**: one invocation of the reviewed release CLI
  `lilith-authority-hold-dev create-initial-held`.
- **Owner decisions OD-M10-1 … OD-M10-8 were accepted on 2026-10-10** (verbatim in §10.1) and are bound by the
  tooling and the templates. They decide semantics only: they authorize no live step.
- **Nothing is authorized by this record.** M-B10, every hold-store mutation, every live DEV contact, every S25
  write, M-B11 signer start, Registry V1 effectiveness, authority activation, First Memory and PROD stay
  **NOT AUTHORIZED**.
- Predecessors: [Package C completion](slice-15b2b-b1b3e-pkgc-completion.md) (`PC5_PACKAGE_C_ACCEPTED`; record 1
  AUTHENTIC + CURRENT; `ACCEPTANCE_COMPLETE`) and its first post-C5 deploy `38038318626` (`EQUAL`,
  `W9_5_GENESIS_COMMITTED_EXACT`).

```text
HELD = restrictive custody state only;  HELD != issuance authority != signer start (M-B11) != activation
non-empty hold store != HELD exact;  W10_1_HELD_EXACT technical PASS != owner acceptance;  UNKNOWN != success
DR-5 EQUAL != HELD evidence (the deployer cannot observe the hold store);  proposal != authority
```

## 1. Canonical sources and the accepted starting state

| Source | Governs |
| --- | --- |
| [P3-5 bootstrap sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §6 – §7 | step 12 `WRITE_HELD` → `INITIAL_CUSTODY_HELD`; "hold store empty before; HELD bound to genesis digest"; PONR **HOLD**; `REQUIRED_CURRENT` + `ACCEPTANCE_COMPLETE`; RR-40 (never deleted, recreated or re-bound); C-16b, C-17 |
| [PR-1 live install preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md) M-B10 row | root writes INITIAL_CUSTODY HELD; forward only; STOP if the store is not empty before |
| code (release `aee323e`, unchanged): `lilith_authority_root/hold_store.py`, `cli.py`, `successor_custody.py` | the ONLY writer (`HoldStoreV1.create_initial_held`), its complete root observer, the record contract |
| [Package B](slice-15b2b-b1b3e-mb9-witness-genesis-package.md), `mb9_witness_verifier.py` (`e4aca11d…`, unchanged) | the W9 phases; `W9_LATER_STATE` for any non-empty hold store |
| `mb9_dr5_target.py` (`d176864a…`, unchanged), `scripts/deployer_authority_boundary_proof.sh` (`9b569f9b…`, unchanged) | the accepted running-witness DR-5 target; what the routine deployer can observe |
| [Package C](slice-15b2b-b1b3e-pkgc-record1-envelope-package.md), `pkgc_operator.py` (`c5e5a5cc…`), `pkgc_s25_phone.sh`, the S25 bundle `77eeb7d5…` (all unchanged) | the owner-custody classifiers, the S25 procedure and evidence class |

Accepted state this slice starts from (control `28597c1d84f33d6781e68bf9b2d2850cb6e56d4c`, deploy `38038318626`):
witness phase `W9_5_GENESIS_COMMITTED_EXACT`; committed genesis
`ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`; witness `8af12bd6…` / `1580` / 0; boot
`cb0d71da…`; record 1 `77752db1…` AUTHENTIC + CURRENT; envelope 1 `95da36cd…` `ACCEPTANCE_COMPLETE`; hold store
empty; `REGISTRY_EFFECTIVE = NO`, `AUTHORITY_ACTIVE = NO`, `authorityGranted = false`, signer inactive.

## 2. What M-B10 writes, and its crash windows

`lilith-authority-hold-dev create-initial-held` (root) reads the host inputs and the witness store, requires the
witness `CONSISTENT` with the pinned genesis, takes an exclusive `flock` on the store, requires it **empty**, and
publishes one record: a scratch `.<name>.tmp` in the parent (`O_EXCL`, 0600, fsync), `rename` into `holds/`, fsync
of `holds/` and of the parent. It prints `{"record":{…}}` on success, or `REFUSED <reason>` (exit 2).

The record is fully determined by fixed context (no operator text, time or random value):

| Field | Value |
| --- | --- |
| ceremonyId | `dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1` |
| transitionKind / state / reason | `INITIAL_CUSTODY` / `HELD` / `INITIAL_CUSTODY_BOOTSTRAP` |
| expectedPredecessorKeyId / expectedSuccessorKeyId | null / `test-only.dev-synthetic.actor.b1b3d.1` |
| observedWitnessDigest | the committed genesis `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4` |
| store name | `1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json` (= SHA-256 of the ceremony id) |
| bytes (RFC 8785) | 421 bytes, SHA-256 `c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d` |
| metadata | regular file, `root:root 0600`, one link; store and parent `root:root 0700` |

Crash windows: before the scratch exists (nothing written); after the scratch, before the rename (scratch residue,
store empty; every later writer refuses `HOLD_PARENT_UNEXPECTED_ENTRY`); after the rename (HELD present; the reply
may still be lost, or an `OSError` from a later fsync may print `REFUSED OSError`). **The transcript never proves
presence or absence: the independent hold-store read-back decides (OD-M10-4).**

## 3. Post-HELD witness classification (`mb10_held_verifier.py`)

Root, read-only, streamed as one hash-gated bundle **after** the unchanged W5, M-B6, W8 and W9 verifiers. It never
reinterprets the W9 verifier. It reports:

- `w9PhaseDirect`: the UNCHANGED W9 judgement (a HELD is `W9_LATER_STATE` there, by design);
- `w9PhaseHoldJudgedSeparately`: the SAME W9 code with only its hold-store listing handed to this verifier. The
  substitution is a bounded seam: exactly that one path, consulted exactly once, or the result is
  `UNCLASSIFIED_STOP`;
- `holdClass`: its own read-only judgement (`lstat`, `O_NOFOLLOW` reads, no lock, directory identity unchanged
  during the read) of the WHOLE hold-store set against the ONE expected record (§2): bytes, digest, genesis binding,
  name, owner, mode and link count;
- `releaseObserver`: the release's complete root observer (`HoldStoreV1.observe`, shared lock) as a cross-check.

Owner-accepted architecture (OD-M10-7): `W10_0_PRE_HELD_EXACT` = the exact `W9_5_GENESIS_COMMITTED_EXACT` state
plus an empty hold store; `W10_1_HELD_EXACT` = exactly the expected INITIAL_CUSTODY HELD bytes plus the otherwise
exact accepted pre-signer state. The stopped-witness state has ONE canonical name:
`W10_1S_HELD_EXACT_WITNESS_STOPPED`.

| Phase (canonical name) | Exactly when | Route |
| --- | --- | --- |
| `W10_0_PRE_HELD_EXACT` | witness side `W9_5_GENESIS_COMMITTED_EXACT`, committed = candidate; store exactly empty; unchanged W9 agrees; release observer sees `[]`; signer inactive | proceed only by the gate and a separate go |
| `W10_1_HELD_EXACT` | witness side `W9_5_GENESIS_COMMITTED_EXACT`; exactly the one expected HELD, byte-exact; unchanged W9 = `W9_LATER_STATE`; release observer sees exactly that name; signer inactive | SAFE_ADOPT (POST10, D3); forward only |
| `W10_1S_HELD_EXACT_WITNESS_STOPPED` | as `W10_1_HELD_EXACT` with the witness stopped (`W9_5S_GENESIS_COMMITTED_STOPPED`) | SAFE_RESTART (separately authorized), then a fresh POST10 |
| `W10_P_SCRATCH_RESIDUE_NOT_HELD` | the parent holds only `holds` and the writer's exact scratch; the store is empty | STOP (OD-M10-6); only MB10_SCRATCH_RECOVERY under its own authorization |
| `W10_HOLD_RECORD_MALFORMED` | an entry that is not the canonical record (bytes, metadata, symlink, unparseable) | **HALT** pending adjudication |
| `W10_HELD_MISBOUND` | a valid INITIAL_CUSTODY HELD bound to another witness digest | **HALT** (RR-40: never re-bound) |
| `W10_HOLD_SET_UNEXPECTED` | more than one record, RELEASED, or another ceremony kind | **HALT** |
| `W10_FOREIGN_OR_UNSAFE` | store or parent absent or unsafe; any other parent entry; scratch together with a record | **HALT** |
| `W10_WITNESS_NOT_EXACT` | the witness side is not `W9_5_GENESIS_COMMITTED_EXACT` / `W9_5S_GENESIS_COMMITTED_STOPPED`, or committed ≠ candidate | STOP_REVALIDATE |
| `W10_SIGNER_OR_LATER_STATE` | the signer, or a later witness state | STOP |
| `UNCLASSIFIED_STOP` | unreadable, changed during observation, judgements disagree, seam not exact | STOP; UNKNOWN is never success |

Invalid hold content dominates every other observation (a HALT is reported even if the witness also drifted). A
non-empty hold store is never success by itself. Every report carries `heldGrantsAuthority: false`,
`issuanceAuthority: NONE`, `registryEffective: false`, `authorityActive: false`, `authorityGranted: false`.

**Consequence (by design):** once HELD exists, every Package B / Package C form that requires
`W9_5_GENESIS_COMMITTED_EXACT` (mb9 `host POST9B`, mb9 `health`, mb9 `chain-export`, pkgc `acquire`) fails closed.
Post-HELD reads use `mb10_operator.py host POST`.

**P1B-10 (OD-M10-8).** The installer's unchanged `status --expect P1B-10` checks shape only (one valid record name).
It stays an install-stage and denial-phase check; it is never evidence of HELD correctness. M-B10 success requires
the W10 verifier's independent exact bytes, digest, genesis binding and hold-store set, and the operator's own byte
fetch, before D3.

## 4. Post-HELD DR-5 target (`mb10_dr5_target.py`)

**4.1 Method.** The rule stays `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`. The tool runs the pinned W9 derivation
(`mb9_dr5_target.derive`, unchanged) over the accepted post-M-B6 texts, then applies the **proven** M-B10 delta.

**4.2 The delta is empty, and it is proven, not assumed.** From the pinned script text the tool checks that the hold
store appears only as one `AB_PR1_UNOBSERVABLE` leaf beneath the root-only parent (the deployer prints
`UNOBSERVABLE_BY_DESIGN: /var/lib/lilith-authority-custody/holds (beneath root-only …)` before and after M-B10); that
the parent's ladder row is `P1A-9|/var/lib/lilith-authority-custody|directory|700|-r -x` (kind, owner and mode only;
never a time or size); and that no other list of the script (parents, root files, ladders, prerequisites, later
state, CLIs) names a path at or beneath the store or a parent dot-file. M-B10 writes beneath that parent only. A
changed script (pin), or any of those conditions failing, is a refusal.

**4.3 Targets (OD-M10-7).** New, semantically distinct, phase-specific targets; their texts equal the W9 sources; the
W9 targets and the W9 phase map are untouched; accepted `W9_5_GENESIS_COMMITTED_EXACT` evidence stays historical and
unchanged:

| W10 phase | Target | Result set | DR-5 block | Pre-deploy |
| --- | --- | --- | --- | --- |
| `W10_1_HELD_EXACT` | `WITNESS_RUNNING_HELD` | 192 `593c90e1…ff65` | 153 `ace51f27…fd5a` | 29 `f5087042…4cae` |
| `W10_1S_HELD_EXACT_WITNESS_STOPPED` | `WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD` | 190 `7f70aa3b…0989` | 151 `3d7cd041…50af` | 29 `f5087042…4cae` |

Every other phase, including every W9 phase, is `NO_BASELINE_STOP`: a W9 phase never satisfies the W10 target
lookup. The targets are derived, **not accepted**; no global evidence epoch is introduced. DR-5 `EQUAL` is never
evidence that HELD exists; only the root W10 verifier proves HELD.

## 5. Owner-side eligibility

### 5.1 The laptop evidence (`mb10_owner_eligibility.py`)

The host cannot see owner-record custody, so eligibility is proven on the owner laptop (WSL), from the M-B10 work
directory of ONE sequence, immediately before its gate:

| Fact | Required |
| --- | --- |
| Package C | sequence `e6b7a333…`; `C5_ACCEPTANCE.json` `16afa08a…`; no `STOP.json`; binding `bd1c35e7…` |
| Replica A / store A | exactly record 1 `77752db1…` / exactly envelope 1 `95da36cd…`; custody ids exact; no pending file |
| freshness / acceptance | AUTHENTIC + CURRENT / `ACCEPTANCE_COMPLETE` (the canonical classifiers through the pinned pkgc operator) |
| fresh chain | the sequence's own export (its RECEIPT names the sequence): `chain/1.json` = `witness.json` = `252c3220…`, byte-identical to the bound genesis-only chain |
| fresh S25 observation | the sequence's own `mb10_s25_pre` transcription, recorded after D1, EXACT against the expectation computed here (§5.2) |

Every fact is observed separately; any exception is recorded as UNKNOWN. The result is `MB10_OWNER_ELIGIBLE` only
when every fact is observed and exact; anything else is `MB10_OWNER_REVALIDATE` with reasons. The record names the
export and the S25 record it was taken against. The empty hold store is a HOST fact, proven by the W10 verifier in
the gate.

### 5.2 The fresh read-only S25 observation (OD-M10-5; `mb10_s25_phone.sh`)

Historical C3 / C4B views alone are not sufficient. After D1 and before the final gate, the owner runs, by hand in
Termux, the read-only stage `mb10_s25_pre` (it writes only its own new evidence directory; no Replica B, store B or
P-B write). It reuses the accepted S25 bundle `77eeb7d5…` and the proven A views, and prints a result block plus its
SHA-256:

| Line | Expected |
| --- | --- |
| `MB10_SEQUENCE` | this sequence's id (the stage refuses a second run for the same sequence) |
| `CHAIN_*` | `AUTHENTIC`, 1 entry, genesis `ac892dc2…` |
| `A_VIEW_TREE_SHA256` / `A_STORE_VIEW_TREE_SHA256` | equal to the live laptop Replica A / store A trees |
| `REPLICA_B_*` | manifest `c068e533…`; listing `REPLICA.json records`; 1 record; head = record 1; the one file `000001-77752db1….json`, byte-identical to Replica A's |
| `STORE_B*` | `ACCEPTANCE_STORE_VERIFIED`; manifest `df7737bd…`; listing `ACCEPTANCE.json envelopes`; 1 envelope; the one file `000001-95da36cd….json`, byte-identical to store A's |
| `PENDING` | `0` (no pending artifact in Replica B or store B) |
| `FRESHNESS` / `ACCEPTANCE` | `AUTHENTIC:CURRENT` / `ACCEPTANCE_COMPLETE` |

The operator records the owner's transcription (`s25-record`, `OWNER_SCREEN_TRANSCRIPTION`, bound to the sequence
id and time-stamped after D1); the eligibility tool compares it (exact, ordered lines and the block hash); the gate
binds the record SHA-256 and the D2 go names the transcription SHA-256. `render S25` prints the phone commands with
every value inserted (sequence id, bundle SHA-256, script SHA-256). No S25 write is authorized.

## 6. Failure / recovery classification

### 6.1 The post-marker table (OD-M10-4)

`mb10_held_verifier.classify_sequence` (pure) combines the host phase, the hold class and the operator's records
(marker, transcript class, POST10, acceptance, DR-5). The transcript never proves presence or absence: the
independent hold-store read-back decides. There is NO automatic retry. Canonical language describing an empty-store
retry (P3-5 C-16b) means "semantically recoverable", never a retry inside a sequence whose marker is consumed.

| Situation | Sequence phase | Disposition |
| --- | --- | --- |
| no marker, `W10_0_PRE_HELD_EXACT` | `S10_0_NOT_ATTEMPTED` | CONTINUE (gate, then the separate go) |
| marker written, writer not invoked; or writer REFUSED (before write or ambiguous); host `W10_0_PRE_HELD_EXACT` | `S10_R_CONSUMED_NOT_WRITTEN` | **ENDS**; the freeze stays in force; a linked successor with a fresh gate and a fresh go may follow |
| marker; store empty; host drifted (witness or signer) | `S10_R_HOST_DRIFT_NOT_WRITTEN` | **ENDS**; the freeze stays in force; the accepted revalidation / re-pin path to `W10_0_PRE_HELD_EXACT` first |
| HELD exact, reply exact | `S10_HELD_POST_PENDING` | CONTINUE: read-only POST10 |
| HELD exact by read-back, reply lost / not exact / refused after the rename | `S10_HELD_UNACKNOWLEDGED` | CONTINUE only through POST10, then D3 with the explicit adoption sentence |
| HELD exact, POST10 failed | `S10_HELD_POST_NOT_VERIFIED` | STOP adjudication; a fresh read-only POST10 may be re-run; HELD stays |
| POST10 verified, reply exact | `S10_POST_VERIFIED_ACCEPTANCE_PENDING` | CONTINUE: owner D3 |
| POST10 verified, adoption needed | `S10_POST_VERIFIED_ADOPTION_PENDING` | CONTINUE: owner D3 with the adoption sentence |
| accepted; first post-freeze deploy `EQUAL` | `S10_ACCEPTED` | done (nothing authorized) |
| accepted; first post-freeze deploy not `EQUAL` | `S10_ACCEPTED_DR5_DRIFT` | STOP revalidation; HELD stays |
| HELD exact, witness stopped | `S10_HELD_WITNESS_STOPPED` | STOP; separately authorized restart, fresh POST10 |
| HELD exact, host drifted | `S10_HELD_WITH_HOST_DRIFT` | STOP adjudication; no POST until `W10_1_HELD_EXACT` again |
| scratch / temp residue, store empty | `S10_SCRATCH_RESIDUE_NOT_WRITTEN` | **STOP**; never automatic removal; MB10_SCRATCH_RECOVERY (§6.2) only under its own authorization; the freeze stays in force |
| malformed, misbound, unexpected or foreign hold content (with or without a marker) | `S10_HALT_HOLD_STORE_INVALID` | **HALT permanently** pending adjudication; no tool acts (RR-40) |
| hold content this sequence did not attempt (no marker, or no recorded invocation) | `S10_UNEXPLAINED_HOLD_STATE` | **HALT permanently** pending adjudication |
| a claimed success the host does not show; any unknown input | `S10_UNCLASSIFIED_STOP` | READ_BACK: a fresh read-only classification |
| duplicate / retry attempt | — | **REFUSE**: the `O_EXCL` marker refuses a second `mb10` (`ATTEMPT_ALREADY_CONSUMED`); the writer itself refuses `HOLD_STORE_NOT_EMPTY` (defence in depth) |

`classify` records each classification (`classifications/NN-CLASSIFY/CLASSIFICATION.json`) with the freeze state; a
linked successor and a freeze release are judged against the latest recorded classification.

### 6.2 MB10_SCRATCH_RECOVERY (OD-M10-6; `mb10_scratch_recovery.py`)

The live operator never deletes or repairs residue. The separate, bounded procedure has its own pin, its own owner
recovery authorization (`render SCRATCH <plan-dir>`) and its own one-attempt marker
(`scratch-recovery-<plan digest prefix>`). `plan` (read-only) proves, and `recover <plan-digest>` re-proves before
removing:

- the canonical HELD is absent and the hold store is EMPTY (no other hold-store content at all);
- the parent holds exactly `holds` and the ONE scratch `.1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json.tmp`;
- the scratch is the reviewed writer failure form: a regular `root:root 0600` file with one link, at most 421 bytes,
  whose bytes are a prefix of the exact expected HELD bytes;
- the plan digest (scratch name, inode, size, SHA-256, completeness) equals the authorized one.

It removes exactly that one file (`unlinkat`, parent fsync) and re-observes; `MB10_SCRATCH_RECOVERED` only when the
parent holds exactly `holds` and the store is empty. It writes no HELD and is not a retry. Afterwards `classify`
gives `S10_R_CONSUMED_NOT_WRITTEN`; a linked successor needs its own D1, fresh evidence, a new gate and a new D2,
under the continuing freeze. Until it is used under authorization, scratch residue means halt for owner
adjudication.

## 7. Denial proofs after HELD

- **P1B-10** (`mb10_hold_denial_proof.py`, new, separately pinned): preconditions exact (parent `0700` holds only
  `holds`; store `0700` holds only the expected name; record `root:root 0600`, one link; witness active; signer
  inactive; `GRANT_ABSENT`), else no probe runs. 8 rows × 5 principals (application, deployer, broker, signer,
  witness) = **40 `DENIED`**, no `ALLOWED_BY_DESIGN`, 0 `ALLOWED`. It is a denial proof, not HELD evidence.
- **P1B-9b** (witness) and **P1B-5** (custody) proofs are unchanged and still valid after HELD (neither requires an
  empty hold store); POST10 runs all three.

## 8. Operator (`mb10_operator.py`) and state machine

The operator subclasses the pinned Package B operator (transport, direct-plink verifier bundles, `O_EXCL` marker, go
check) unchanged. Forms: `pins`, `render`, `open`, `export`, `s25-record`, `host PRE|POST`, `gate`, `mb10`, `post`,
`classify`, `accept`, `stop`, `release-freeze`, `scratch-plan`, `scratch-recover`, `dr5`. `render` prints each owner
text (or the S25 phone commands) with every value inserted from the files: copy-paste ready, no placeholder is ever
left to the owner.

```text
open (D1, read-only; the freeze begins, or continues unbroken from a predecessor)
  → export (fresh chain export + RECEIPT) → render S25 → owner: mb10_s25_pre (read-only) → s25-record
  → [WSL] mb10_owner_eligibility evaluate <workdir> <export> <s25> … (bound to both)
  → host PRE (all codes 0; W10_0_PRE_HELD_EXACT) → gate
       exact                → CONTINUE
       ordinary staleness   → REVALIDATE: fresh evidence, a new gate, a re-rendered D2
       material change      → SEQUENCE_ENDED (pre-marker; the freeze holds until STOP or release)
  → render D2 → owner D2 (binds the gate, names every superseded gate, the S25 and eligibility evidence; PONR)
  → mb10: an old D2 bound to a superseded gate is refused (`GO_BOUND_TO_SUPERSEDED_GATE`);
          a fresh W10_0_PRE_HELD_EXACT read (same incarnation as the gate) → O_EXCL marker `mb10`
          → ONE `sudo -n /usr/local/sbin/lilith-authority-hold-dev create-initial-held`
          → transcript class → independent W10 read-back → sequence phase (§6.1); the freeze stays in force
  → classify (recorded) → post (POST10) → render D3 → owner D3 (ends the freeze; authorizes nothing)
  → first deploy after the freeze → `dr5 W10_1_HELD_EXACT <log>` must be EQUAL
Pre-marker only: owner STOP (ends the sequence and its freeze).
Post-marker, NOT-WRITTEN outcome only: owner freeze RELEASE (ends the freeze; authorizes no retry).
```

**The gate** requires a host PRE read of this sequence, never used by an earlier gate; `MB10_HOST_PRE_PASS`; W10
`W10_0_PRE_HELD_EXACT` with hold class `EMPTY` and unchanged W9 `W9_5_GENESIS_COMMITTED_EXACT`; witness
`8af12bd6…`/`1580`/0 and boot `cb0d71da…`; broker preservation PASS; `REBOOT_REQUIRED=absent`; an
`MB10_OWNER_ELIGIBLE` record of this sequence bound to a never-consumed export and a never-consumed S25 record, both
taken after D1 and before the eligibility; the last deploy unchanged since D1 and an empty workflow queue.

**Drift before the marker (OD-M10-3).** Material substrate events — `BOOT_CHANGED`, `WITNESS_INCARNATION_CHANGED`,
`BROKER_PRESERVATION_NOT_PASS`, `REBOOT_REQUIRED_PRESENT_OR_UNKNOWN`, `DEPLOY_SINCE_OPENING`, `HOST_NOT_W10_0`,
`W9_NOT_EXACT` — END the sequence (`ENDED.json`; every later gate, export, S25 record and D2 refuses
`SEQUENCE_ENDED`); the applicable accepted revalidation / re-pin path precedes any linked successor. Every other
event is ordinary staleness: `MB10_GATE_REVALIDATE`, fresh evidence, a new gate and a re-rendered D2. **Explicit
supersession:** every D2 names the gate it binds and every superseded gate of the sequence; a D2 bound to a
superseded gate is refused, never silently reused.

**The freeze (OD-M10-2).** It begins at the successful D1 and forbids any intentional merge, deploy, reboot, witness
restart, broker restart, package or OS upgrade, signer action, Registry effectiveness or authority activation. Its
normal end is the accepted D3. A pre-marker STOP ends it explicitly. After the marker a NOT-WRITTEN outcome does NOT
end it: it stays in force through read-back and classification and into any linked successor (whose D1 must carry
the same last deploy and says `CONTINUES_UNBROKEN_FROM <origin D1 SHA-256>`), unless the owner explicitly releases
it (`release-freeze`, only after a recorded `S10_R_CONSUMED_NOT_WRITTEN`, `S10_R_HOST_DRIFT_NOT_WRITTEN` or
`S10_SCRATCH_RESIDUE_NOT_WRITTEN` classification). A pre-marker material END does not end it either; a STOP does.

**Linked successors.** A successor's D1 names its predecessor's D1 SHA-256. It is permitted only after a pre-marker
STOP or material END, or a recorded `S10_R_CONSUMED_NOT_WRITTEN` / `S10_R_HOST_DRIFT_NOT_WRITTEN`; never after any
HELD, POST10 or D3. Each sequence has its own one-attempt marker; a consumed marker is never reused, and a successor
can write only while the store is provably empty, so at most one HELD can ever exist.

**Owner acts** (templates; tool pins are static, every other value comes from the files): **D1** opening, **D2** the
one-attempt go (with `I understand that INITIAL_CUSTODY HELD is forward only: once written it is never deleted,
recreated or re-bound, and no automatic retry is authorized after the attempt marker.`), **D3** acceptance (ends
the freeze; authorizes nothing; the adoption sentence when required), **STOP** (pre-marker), **RELEASE** (post-marker
NOT-WRITTEN freeze release), **SCRATCH** (the bounded recovery). D2 names the W10 verifier `73a8fe9a…` and the
P1B-10 proof `3685472f…`.

## 9. Live boundary of this slice

Allowed and done: this record, the tools, tests on synthetic fixtures (the REAL release hold writer and the REAL
scratch recovery on a synthetic root with a committed synthetic witness genesis), local validation, the read-only
local checks of §13, and PR preparation. Not done and not authorized: any live DEV contact, `create-initial-held`,
any hold-store mutation, any S25 contact or write, witness / broker restart, deploy, merge, signer start, Registry
V1 effectiveness, activation, First Memory, PROD.

## 10. Owner decisions (accepted 2026-10-10)

### 10.1 Verbatim

Owner decision text SHA-256 (exactly the text below: LF line ends, one terminal LF):
`b76d9cf2e28c1f82af4b7b3c4302f7a90ce85774959d1e1aea4cc7d9ef33a641`.

```text
OD-M10-1 — CONTINUITY

ACCEPT:

MB10_CONTINUITY =
OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_HOLD_BOUNDARY

M-B10 contains exactly one irreversible HELD write boundary.


OD-M10-2 — FREEZE

The M-B10 freeze begins at successful D1.

While active, no intentional:
- merge;
- deploy;
- reboot;
- witness restart;
- broker restart;
- package/OS upgrade;
- signer action;
- Registry effectiveness;
- authority activation

is permitted.

The normal successful end of the freeze is accepted D3.

A pre-marker STOP may explicitly end the freeze.

After the one-attempt marker exists, the freeze does NOT automatically end
merely because the sequence is classified as not-written.

For a post-marker not-written outcome, keep the freeze continuously in force
through read-back/classification and into any linked successor unless I
explicitly authorize release of the freeze.


OD-M10-3 — PRE-MARKER DRIFT

Before the one-attempt marker:

- ordinary evidence staleness without substrate change may be revalidated with
  fresh evidence, a new gate and a re-rendered D2;
- any material substrate identity change, including boot/witness/broker
  incarnation change, ends the sequence and requires the applicable accepted
  revalidation/re-pin path before a linked successor.

An old D2 bound to an invalidated gate is unusable and must be explicitly
superseded, never silently reused.


OD-M10-4 — POST-MARKER RECOVERY

After the one-attempt marker:

NO AUTOMATIC RETRY.

Independent hold-store read-back decides the state.

- exact HELD present -> continue to POST10;
- exact HELD present but writer response lost/non-exact -> adopt only through
  the reviewed POST10 + D3 adoption path;
- store proven empty and writer never successfully wrote -> sequence ends;
  a linked successor with a fresh gate and fresh owner go may later proceed;
- scratch/temp residue -> STOP;
- malformed/misbound/foreign/unexpected content -> HALT pending adjudication;
- duplicate/retry attempt -> REFUSE.

Interpret any canonical language describing an empty-store retry as
semantically recoverable, not permission to retry inside a sequence whose
one-attempt marker has already been consumed.


OD-M10-5 — FRESH OWNER-CUSTODY EVIDENCE

For live M-B10, historical/proven C3/C4B views alone are NOT sufficient to
satisfy the "CURRENT per step" requirement.

After D1 and before the final M-B10 gate/D2, require a fresh read-only S25
observation proving:

- Replica B contains exactly Record 1;
- Replica B head is the accepted Record 1 digest;
- acceptance store B contains exactly Envelope 1;
- copy B matches the accepted envelope digest;
- no pending artifacts exist;
- freshness remains AUTHENTIC + CURRENT;
- acceptance remains ACCEPTANCE_COMPLETE.

Bind that fresh S25 evidence into owner eligibility / the M-B10 gate.

No S25 write is authorized by this requirement.


OD-M10-6 — SCRATCH RESIDUE

The live M-B10 operator must NOT automatically delete or repair scratch/temp
residue.

Scratch residue is STOP, not success and not retryable.

Before live M-B10 is authorized, define and test a separate bounded
MB10_SCRATCH_RECOVERY procedure.

That procedure may remove only an exactly recognized writer scratch artifact
after proving:

- canonical HELD is absent;
- no other hold-store content exists;
- the residue matches the reviewed writer failure form;
- an explicit owner recovery authorization exists.

Until that recovery path exists, scratch residue means halt for owner
adjudication.


OD-M10-7 — POST-HELD CLASSIFICATION / DR-5

Accept the architecture where:

W10_0_PRE_HELD_EXACT
= exact W9_5 state plus empty hold store.

W10_1_HELD_EXACT
= exact expected INITIAL_CUSTODY HELD bytes plus otherwise exact accepted
pre-signer state.

Define a single exact canonical name for the stopped-witness W10_1S state;
do not leave a wildcard/placeholder phase name in canonical documentation.

The W10 DR-5 target may have byte-identical hashes to W9_5 if the derivation
tool proves the hold store is unobservable to DR-5.

However:

- W9_5 and W10_1 remain semantically distinct phase targets;
- a W9 phase must never satisfy the W10 target lookup;
- DR-5 EQUAL is never evidence that HELD exists;
- only the root W10 verifier proves HELD;
- accepted W9_5 evidence remains historical and unchanged.


OD-M10-8 — P1B-10 / EXACT HELD VERIFICATION

P1B-10's filename-level check is not sufficient evidence of HELD correctness.

It may remain a denial/install-stage proof, but M-B10 success requires the
new W10 verifier to independently verify the exact expected HELD bytes,
digest, genesis binding and hold-store set before D3.

HELD remains restrictive custody state only.

HELD grants no issuance authority.
HELD does not make Registry V1 effective.
HELD does not activate authority.
M-B11 signer remains a completely separate later milestone.
```

### 10.2 Where each decision is bound

| Decision | Bound by |
| --- | --- |
| OD-M10-1 | `CONTINUITY` in every D1 / D2 template; exactly one `create-initial-held` path in the operator (tested) |
| OD-M10-2 | `freeze_state`; the D1 freeze line; `stop` (pre-marker only); `release-freeze` (post-marker NOT-WRITTEN only); a successor's continuous freeze and same-deploy check |
| OD-M10-3 | the gate's material / ordinary split and `ENDED.json`; D2 supersession; `GO_BOUND_TO_SUPERSEDED_GATE` |
| OD-M10-4 | `classify_sequence` and §6.1; adoption only through POST10 + D3; the marker and the writer refuse duplicates |
| OD-M10-5 | `mb10_s25_phone.sh`, `s25-record`, the eligibility S25 comparison, the gate's S25 binding, the D2 S25 line |
| OD-M10-6 | the operator never removes residue; `mb10_scratch_recovery.py` plus `scratch-plan` / `scratch-recover` under the SCRATCH authorization |
| OD-M10-7 | the canonical phase names (§3); W10-only DR-5 lookup; `NO_BASELINE_STOP` for every W9 phase |
| OD-M10-8 | POST10's W10 byte / digest / binding / set checks before D3; P1B-10 kept as a denial proof only |

## 11. Architecture invariants (preserved)

```text
proposal != authority;  request != permission;  approval evidence != execution;  execution != verification
deployment != activation;  model capability != LILITH authority;  model willingness != permission
model output != accepted state;  HELD = restrictive custody state only;  HELD grants no authority
HELD does not make Registry V1 effective;  HELD does not activate authority;  M-B11 is a separate later milestone
```

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 12. Tooling and pins

| Tool | SHA-256 |
| --- | --- |
| `services/owner-memory-control/tools/mb10_held_verifier.py` | `73a8fe9aec48fab7fb628a3427bc690876b55a4ae1ead55f1b7e00032075b8e3` |
| `services/owner-memory-control/tools/mb10_hold_denial_proof.py` | `3685472f865113357e3010003c3bb24ff47e66b528f114f5fca23d9d7a664b7b` |
| `services/owner-memory-control/tools/mb10_dr5_target.py` | `29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0` |
| `services/owner-memory-control/tools/mb10_owner_eligibility.py` | `3b2d6557ef5887e7f562db4686da456e1e51fe48d10bd50edee1ebfe731f93f9` |
| `services/owner-memory-control/tools/mb10_scratch_recovery.py` | `c5197f74e210ca32408ee96b8ac5799c5cf15c70a406c2917f23cf17d5bdcbd9` |
| `services/owner-memory-control/tools/mb10_s25_phone.sh` | `e6616a29605b2fba2d7bd16823380be25c80e5ad3c70d66a49edeb0dbd71fd4b` |
| `services/owner-memory-control/tools/mb10_operator.py` | bound by D1 / D2 as `{operator}` (HEAD bytes at the control) |

Reused unchanged and pinned by the operator: every Package B pin, `mb9_operator.py` `2312e26a…`, `pkgc_operator.py`
`c5e5a5cc…`, `scripts/deployer_authority_boundary_proof.sh` `9b569f9b…`. No existing tool, verifier, phase, target
or template changed.

## 13. Tests and local checks

`services/owner-memory-control/tests/test_b1b3e_mb10_held_package.py`: pins and reuse; the expected HELD equals the
release contract; the DR-5 delta proof (pinned script; three mutated scripts refused) and the W10-only lookup; the
transcript classes; the whole §6.1 table; the read-only hold-store observer; the verifier over a seamed W9; the
P1B-10 proof; the owner eligibility (each drift, the S25 binding, UNKNOWN, write-once); the S25 stage (read-only,
emitted lines = expectation, copy-paste phone commands); the scratch recovery (plan, digest, exact form, every
refusal); the operator (opening and freeze, ordinary vs material drift, explicit supersession, one marker before
one write, refusals before any marker, NOT-WRITTEN outcome with a continuous freeze into a linked successor and the
explicit release, adoption only through POST10 + D3, scratch STOP and the authorized recovery, POST10 and D3,
DR-5); static boundaries (exactly two mutation paths: the HELD write and the scratch removal); and the REAL release
hold writer and scratch recovery on a synthetic root: `W10_0_PRE_HELD_EXACT` → `W10_1_HELD_EXACT`, unchanged W9 =
`W9_LATER_STATE`, `status P1B-10` PASS, no second HELD, `W10_1S_HELD_EXACT_WITNESS_STOPPED` when stopped, a crash
before the rename gives `W10_P_SCRATCH_RESIDUE_NOT_HELD`, the recovery restores `W10_0_PRE_HELD_EXACT` and a
successor's one write reaches `W10_1_HELD_EXACT`, tampered or re-bound content HALTs.

Local read-only checks (no live contact; outputs only in scratch directories): the owner eligibility logic against
the real laptop owner state, and the S25 stage simulated in WSL against copies of the proven B views with the
accepted bundle.

## 14. Unresolved canonical ambiguities

1. **The installer's `P1B-10` stage checks shape only.** Settled by OD-M10-8: it is never HELD evidence.
2. **The accepted witness incarnation and boot are pinned.** Any reboot or restart before M-B10 is a material END;
   an accepted re-pin (as after M-R1) precedes any linked successor.
3. **Post-HELD routine preservation** can no longer use the mb9 `host POST9B` form (it fails closed by design); it
   uses `mb10_operator.py host POST` and the post-HELD DR-5 target.
4. **The S25 stage reuses the Package C staging.** It needs the accepted bundle and the proven A views still present
   under `$HOME/lilith-pkgc` on the S25; if they are gone, the stage STOPs and a fresh transfer is a separate
   owner-attended step.

## 15. State

```text
MB10 = DESIGN / REPOSITORY ONLY; NOT RUN
MB10_CONTINUITY = OWNER-ACCEPTED (OD-M10-1, 2026-10-10)
OWNER_DECISIONS OD-M10-1..OD-M10-8 = OWNER-ACCEPTED (2026-10-10; semantics only)
CONTROL_AT_DESIGN = 28597c1d84f33d6781e68bf9b2d2850cb6e56d4c
W9_PHASE = W9_5_GENESIS_COMMITTED_EXACT (last accepted read; deploy 38038318626)
WITNESS_GENESIS_DIGEST = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4
RECORD_1 = AUTHENTIC + CURRENT
ACCEPTANCE = ACCEPTANCE_COMPLETE
EXPECTED_HELD_NAME = 1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json
EXPECTED_HELD_SHA256 = c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d
POST_HELD_DR5_DELTA = EMPTY (proven from the pinned script); TARGETS DERIVED, NOT ACCEPTED
MB10_SCRATCH_RECOVERY = DEFINED AND TESTED; NOT AUTHORIZED
FRESH_S25_OBSERVATION = REQUIRED PER SEQUENCE; NOT RUN
HELD = ABSENT
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
SIGNER = INACTIVE
M-B10 = NOT AUTHORIZED
M-B11 = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
```
