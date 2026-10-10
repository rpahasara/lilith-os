# Slice 15B2b-B1b-3e — M-B10 / WRITE_HELD: INITIAL_CUSTODY HELD (Design, Tooling and Runbook)

Status:

- **REPOSITORY ONLY: DESIGN, DOCUMENTATION, A VERIFIER, A DR-5 TARGET TOOL, A DENIAL PROOF, AN OWNER-ELIGIBILITY
  TOOL, AN OPERATOR AND TESTS.** The owner authorized this design-and-tooling slice only (2026-10-10). Writing it
  contacted no live system: no DEV, no S25 and no owner key. **No M-B10 step has run. HELD is absent.**
- Packages P3-5 bootstrap step 12 (`WRITE_HELD`, M-B10) into one owner-attended sequence with **one irreversible
  boundary**: exactly one invocation of the reviewed release CLI `lilith-authority-hold-dev create-initial-held`.
- **Nothing is authorized by this record.** M-B10, every hold-store mutation, every live DEV contact, M-B11 signer
  start, Registry V1 effectiveness, authority activation, First Memory and PROD stay **NOT AUTHORIZED**. The
  continuity and freeze semantics (§10) are **proposed for owner decision**, not accepted.
- Predecessors: [Package C completion](slice-15b2b-b1b3e-pkgc-completion.md) (`PC5_PACKAGE_C_ACCEPTED`; record 1
  AUTHENTIC + CURRENT; `ACCEPTANCE_COMPLETE`) and its first post-C5 deploy `38038318626` (`EQUAL`,
  `W9_5_GENESIS_COMMITTED_EXACT`).

```text
HELD = restrictive custody state only;  HELD != issuance authority != signer start (M-B11) != activation
non-empty hold store != HELD exact;  W10_1 technical PASS != owner acceptance;  UNKNOWN != success
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

Accepted state this slice starts from (control `28597c1d84f33d6781e68bf9b2d2850cb6e56d4c`, deploy `38038318626`):
witness phase `W9_5_GENESIS_COMMITTED_EXACT`; committed genesis
`ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`; witness `8af12bd6…` / `1580` / 0; boot
`cb0d71da…`; record 1 `77752db1…` AUTHENTIC + CURRENT; envelope 1 `95da36cd…` `ACCEPTANCE_COMPLETE`; hold store
empty; `REGISTRY_EFFECTIVE = NO`, `AUTHORITY_ACTIVE = NO`, `authorityGranted = false`, signer inactive.

## 2. What M-B10 writes, and its crash windows

`lilith-authority-hold-dev create-initial-held` (root) reads the host inputs and the witness store, requires the
witness `CONSISTENT` with the pinned genesis, takes an exclusive `flock` on the store, requires it **empty**, and
publishes one record: a scratch `.<name>.tmp` in the parent (`O_EXCL`, fsync), `rename` into `holds/`, fsync of
`holds/` and of the parent. It prints `{"record":{…}}` on success, or `REFUSED <reason>` (exit 2).

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
presence or absence: the host classification decides.**

## 3. Post-HELD witness classification (`mb10_held_verifier.py`)

Root, read-only, streamed as one hash-gated bundle **after** the unchanged W5, M-B6, W8 and W9 verifiers. It never
reinterprets the W9 verifier. It reports:

- `w9PhaseDirect`: the UNCHANGED W9 judgement (a HELD is `W9_LATER_STATE` there, by design);
- `w9PhaseHoldJudgedSeparately`: the SAME W9 code with only its hold-store listing handed to this verifier. The
  substitution is a bounded seam: exactly that one path, consulted exactly once, or the result is `UNCLASSIFIED`;
- `holdClass`: its own read-only judgement (`lstat`, `O_NOFOLLOW` reads, no lock, directory identity unchanged
  during the read) against the ONE expected record (§2), bytes, name, owner, mode and link count;
- `releaseObserver`: the release's complete root observer (`HoldStoreV1.observe`, shared lock) as a cross-check.

| Phase | Exactly when | Route |
| --- | --- | --- |
| `W10_0_PRE_HELD_EXACT` | witness side `W9_5`, committed = candidate; store exactly empty; unchanged W9 = `W9_5`; release observer sees `[]` | proceed only by gate + go |
| `W10_1_HELD_EXACT` | witness side `W9_5`; exactly the one expected HELD, byte-exact; unchanged W9 = `W9_LATER_STATE`; release observer sees exactly that name | SAFE_ADOPT (POST10, D3); forward only |
| `W10_1S_HELD_EXACT_WITNESS_STOPPED` | as W10_1 with the witness stopped (`W9_5S`) | SAFE_RESTART (separately authorized), fresh POST10 |
| `W10_P_SCRATCH_RESIDUE_NOT_HELD` | the parent holds only `holds` and the writer's exact scratch; the store is empty | STOP: HELD not written; a separately reviewed bounded scratch removal is needed |
| `W10_HOLD_RECORD_MALFORMED` | an entry that is not the canonical record (bytes, metadata, symlink, unparseable) | **HALT** pending adjudication |
| `W10_HELD_MISBOUND` | a valid INITIAL_CUSTODY HELD bound to another witness digest | **HALT** (RR-40: never re-bound) |
| `W10_HOLD_SET_UNEXPECTED` | more than one record, RELEASED, or another ceremony kind | **HALT** |
| `W10_FOREIGN_OR_UNSAFE` | store / parent absent or unsafe; any other parent entry; scratch together with a record | **HALT** |
| `W10_WITNESS_NOT_EXACT` | the witness side is not `W9_5` / `W9_5S`, or committed ≠ candidate | STOP_REVALIDATE |
| `W10_SIGNER_OR_LATER_STATE` | the signer, or a later witness state | STOP |
| `UNCLASSIFIED_STOP` | unreadable, changed during observation, judgements disagree, seam not exact | STOP; UNKNOWN is never success |

Invalid hold content dominates every other observation (a HALT is reported even if the witness also drifted). A
non-empty hold store is never success by itself. Every report carries `heldGrantsAuthority: false`,
`issuanceAuthority: NONE`, `registryEffective: false`, `authorityActive: false`, `authorityGranted: false`.

**Consequence (by design):** once HELD exists, every Package B / Package C form that requires `W9_5` (mb9 `host
POST9B`, mb9 `health`, mb9 `chain-export`, pkgc `acquire`) fails closed. Post-HELD reads use `mb10_operator.py host
POST`. The installer's `status --expect P1B-10` (unchanged) checks shape only (one valid name); byte exactness is
the W10 verifier's.

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

**4.3 Targets.** New, phase-specific names; their texts equal the W9 sources; the W9 targets and the W9 phase map
are untouched; historical W9_5 evidence stays historical:

| W10 phase | Target | Result set | DR-5 block | Pre-deploy |
| --- | --- | --- | --- | --- |
| `W10_1_HELD_EXACT` | `WITNESS_RUNNING_HELD` | 192 `593c90e1…ff65` | 153 `ace51f27…fd5a` | 29 `f5087042…4cae` |
| `W10_1S_HELD_EXACT_WITNESS_STOPPED` | `WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD` | 190 `7f70aa3b…0989` | 151 `3d7cd041…50af` | 29 `f5087042…4cae` |

Every other phase, including every W9 phase, is `NO_BASELINE_STOP`. The targets are derived, **not accepted**; no
global evidence epoch is introduced. Because the deployer cannot see the hold store, a DR-5 `EQUAL` after M-B10 is
preservation evidence only, never evidence that HELD exists; that proof is the root W10 verifier.

## 5. Owner-side eligibility (`mb10_owner_eligibility.py`)

The host cannot see owner-record custody, so eligibility is proven on the owner laptop (WSL), immediately before
the gate, from the accepted Package C state and one fresh, receipt-bound chain export of the M-B10 sequence:

| Fact | Required |
| --- | --- |
| Package C | sequence `e6b7a333…`; `C5_ACCEPTANCE.json` `16afa08a…`; no `STOP.json`; binding `bd1c35e7…` |
| Replica A / store A | exactly record 1 `77752db1…` / exactly envelope 1 `95da36cd…`; custody ids exact; no pending file |
| proven B views | `replica-b-1` `2534bda8…`, `store-b-1` `5cb0bc77…` (the C3 / C4B owner transcriptions); envelope bytes identical on A and B |
| freshness / acceptance | AUTHENTIC + CURRENT / `ACCEPTANCE_COMPLETE` (the canonical classifiers through the pinned pkgc operator) |
| fresh chain | `chain/1.json` = `witness.json` = `252c3220…` and byte-identical to the bound genesis-only chain |

Every fact is observed separately; any exception is recorded as UNKNOWN. The result is `MB10_OWNER_ELIGIBLE` only
when every fact is observed and exact; anything else is `MB10_OWNER_REVALIDATE` with reasons. The record names the
export receipt it was taken against. The empty hold store is a HOST fact, proven by the W10 verifier in the gate.

A read-only local dry run against the real owner state (2026-10-10; the post-C5 preservation chain export; a dummy
receipt; output in a scratch directory only; no owner file changed) returned `MB10_OWNER_ELIGIBLE`. It is a tooling
check, not gate evidence.

## 6. Failure / recovery classification

`mb10_held_verifier.classify_sequence` (pure) combines the host phase, the hold class and the operator's records
(marker, transcript class, POST10, acceptance, DR-5). The transcript never proves presence or absence.

| Situation | Sequence phase | Disposition |
| --- | --- | --- |
| no marker, `W10_0` | `S10_0_NOT_ATTEMPTED` | CONTINUE (gate, then the separate go) |
| marker written, writer not invoked; or writer REFUSED (before write or ambiguous); host `W10_0` | `S10_R_CONSUMED_NOT_WRITTEN` | **ENDS**; read-back done; a **linked successor** may follow |
| marker; store empty; host drifted (witness / signer) | `S10_R_HOST_DRIFT_NOT_WRITTEN` | **ENDS**; reviewed revalidation to `W10_0` first, then a linked successor |
| HELD exact, reply exact | `S10_HELD_POST_PENDING` | CONTINUE: read-only POST10 |
| HELD exact by read-back, reply lost / not exact / refused after the rename | `S10_HELD_UNACKNOWLEDGED` | CONTINUE: POST10, then D3 with the explicit adoption sentence; never a retry |
| HELD exact, POST10 failed | `S10_HELD_POST_NOT_VERIFIED` | STOP adjudication; a fresh read-only POST10 may be re-run; HELD stays |
| POST10 verified | `S10_POST_VERIFIED_ACCEPTANCE_PENDING` / `…_ADOPTION_PENDING` | CONTINUE: owner D3 |
| accepted; first post-freeze deploy `EQUAL` / not `EQUAL` | `S10_ACCEPTED` / `S10_ACCEPTED_DR5_DRIFT` | CONTINUE / STOP revalidation (HELD stays) |
| HELD exact, witness stopped | `S10_HELD_WITNESS_STOPPED` | STOP; separately authorized restart, fresh POST10 |
| HELD exact, host drifted | `S10_HELD_WITH_HOST_DRIFT` | STOP adjudication; no POST until `W10_1` again |
| pending / temp artifact (scratch), store empty | `S10_SCRATCH_RESIDUE_NOT_WRITTEN` | STOP adjudication: bounded scratch removal (separate reviewed design), then a linked successor |
| malformed, misbound, unexpected or foreign hold content (with or without a marker) | `S10_HALT_HOLD_STORE_INVALID` | **HALT permanently** pending adjudication; no tool acts (RR-40) |
| hold content this sequence did not attempt (no marker, or no recorded invocation) | `S10_UNEXPLAINED_HOLD_STATE` | **HALT permanently** pending adjudication |
| a claimed success the host does not show; any unknown input | `S10_UNCLASSIFIED_STOP` | READ_BACK: a fresh read-only classification |
| duplicate / retry | — | the `O_EXCL` marker refuses a second `mb10` (`ATTEMPT_ALREADY_CONSUMED`); the writer itself refuses `HOLD_STORE_NOT_EMPTY` (defence in depth) |

## 7. Denial proofs after HELD

- **P1B-10** (`mb10_hold_denial_proof.py`, new, separately pinned): preconditions exact (parent `0700` holds only
  `holds`; store `0700` holds only the expected name; record `root:root 0600`, one link; witness active; signer
  inactive; `GRANT_ABSENT`), else no probe runs. 8 rows × 5 principals (application, deployer, broker, signer,
  witness) = **40 `DENIED`**, no `ALLOWED_BY_DESIGN`, 0 `ALLOWED`.
- **P1B-9b** (witness) and **P1B-5** (custody) proofs are unchanged and still valid after HELD (neither requires an
  empty hold store); POST10 runs all three.

## 8. Operator (`mb10_operator.py`) and state machine

The operator subclasses the pinned Package B operator (transport, direct-plink verifier bundles, `O_EXCL` marker, go
check) unchanged. Forms: `pins`, `render`, `open`, `export`, `host PRE|POST`, `gate`, `mb10`, `post`, `classify`,
`accept`, `stop`, `dr5`. `render` prints each owner text with every value inserted from the files (copy-paste
ready; no placeholder is ever left to the owner).

```text
open (D1, read-only; freeze per §10)
  → export (fresh chain export + RECEIPT) → [WSL] mb10_owner_eligibility evaluate (receipt-bound)
  → host PRE (all codes 0; W10_0; W9_5) → gate (fresh, never-consumed host read + eligibility + freeze facts)
  → render D2 → owner D2 (exact; PONR acknowledgement; binds the gate SHA)
  → mb10: fresh W10_0 read (same incarnation as the gate) → O_EXCL marker `mb10`
          → ONE `sudo -n /usr/local/sbin/lilith-authority-hold-dev create-initial-held`
          → transcript class → independent W10 read-back → sequence phase (§6)
  → post (POST10: host POST, P1B-10 / P1B-9b / P1B-5, health CONSISTENT, hold `observe`, HELD bytes, chain unchanged)
  → render D3 → owner D3 (ends the freeze; authorizes nothing)
  → first deploy after the freeze → `dr5 W10_1_HELD_EXACT <log>` must be EQUAL
Before the marker only: owner STOP (ends the sequence; releases its freeze; authorizes nothing).
```

The gate requires: a host PRE read of this sequence, `MB10_HOST_PRE_PASS`, never used by an earlier gate; W10
`W10_0` with hold class `EMPTY` and unchanged W9 = `W9_5`; witness `8af12bd6…`/`1580`/0 and boot `cb0d71da…`
(the accepted post-reboot identities); `REBOOT_REQUIRED=absent`; an `MB10_OWNER_ELIGIBLE` record bound to a
never-consumed export receipt of this sequence, taken after it; the last deploy unchanged since D1 and an empty
workflow queue. Any miss is `MB10_GATE_REVALIDATE` with events. Every gate is single-use.

Owner acts (draft templates; tool pins are static, other values come from the files): **D1** opening (read-only),
**D2** the one-attempt go (with `I understand that INITIAL_CUSTODY HELD is forward only: once written it is never
deleted, recreated or re-bound, and no automatic retry is authorized after the attempt marker.`), **D3** acceptance
(authorizes nothing; optional adoption sentence), **STOP** (pre-marker only). D2 names the W10 verifier
`35b2cb19…` and the P1B-10 proof `3685472f…`.

## 9. Live boundary of this slice

Allowed and done: this record, the five tools, tests on synthetic fixtures (the REAL release hold writer on a
synthetic root with a committed synthetic witness genesis), local validation, the read-only eligibility dry run of
§5, and PR preparation. Not done and not authorized: any live DEV contact, `create-initial-held`, any hold-store
mutation, witness / broker restart, deploy, merge, signer start, Registry V1 effectiveness, activation, First
Memory, PROD.

## 10. Owner decisions requested (proposed; none accepted)

| ID | Question | Recommended |
| --- | --- | --- |
| OD-M10-1 | Continuity for one irreversible M-B10 boundary | `MB10_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_HOLD_BOUNDARY`: one sequence, one gate per go, one go, one marker, no wall-clock TTL |
| OD-M10-2 | When the freeze begins and ends; what it forbids | begins at the successful D1; ends at D3 (or at a pre-marker STOP); forbids intentional merge, deploy (incl. merge-triggered), reboot, witness or broker restart, package upgrades and any signer action |
| OD-M10-3 | Unexpected drift | before the marker: never advances; the last gate is void; a fresh export, eligibility, host PRE and gate, and a re-rendered D2 (it binds the gate). After the marker: the host classification decides (§6); never a retry |
| OD-M10-4 | Stopped pre-write sequence and successors | a **linked successor** only after `STOP`, `S10_R` or `S10_R_DRIFT` (after revalidation to `W10_0`); it needs its own D1 naming the predecessor's D1 SHA-256, fresh evidence, a new gate and a new D2; it can never follow a sequence whose store is not empty |
| OD-M10-5 | Is a fresh S25 read needed for owner eligibility? | No (the C5-gate precedent): the proven C3 / C4B views plus a fresh, bound genesis-only chain; Option B (a new read-only phone stage) remains available |
| OD-M10-6 | Where the post-HELD DR-5 comparison sits | after D3: the first deploy after the freeze must be `EQUAL` under `W10_1` (Package B precedent); alternative: keep the freeze until that deploy is `EQUAL` |
| OD-M10-7 | Scratch residue | no removal tool in this slice; `S10_SCRATCH` needs its own reviewed bounded-removal design and authorization |
| OD-M10-8 | Adoption | D3 may adopt a byte-exact HELD whose reply was lost, only with the explicit adoption sentence |

**How the one-attempt marker interacts with successors.** The marker is per sequence: once written, that
sequence's go is consumed forever, whatever happens. A successor is a new sequence with its own marker; it is
possible only while the store is provably empty, so at most one HELD can ever be written, and a written HELD can
never be written again.

**Recommended owner decision wording (for review; not issued):**

> I accept, for M-B10 / WRITE_HELD only, `MB10_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_HOLD_BOUNDARY`: one owner-attended sequence; one gate per go; one D2 go; one attempt marker; exactly one `create-initial-held`; no wall-clock TTL.
> The M-B10 freeze begins at the successful D1 opening and ends at D3, or at a pre-marker STOP. During it no intentional merge, deploy, reboot, witness restart, broker restart, package upgrade or signer action is permitted.
> Unexpected drift never advances the sequence: before the marker it voids the last gate and requires fresh evidence, a new gate and a re-rendered D2; after the marker the reviewed host classification decides, and there is no retry.
> A linked successor sequence is permitted only after a pre-marker STOP or a classified S10_R / S10_R_DRIFT with the hold store proven empty; it needs its own D1 naming its predecessor, fresh evidence, a new gate and a new D2.
> Owner-side eligibility uses the proven Package C views and a fresh, bound genesis-only chain export. The post-HELD DR-5 comparison is made at the first deploy after D3 and must be EQUAL under W10_1_HELD_EXACT.
> This decision authorizes nothing: not M-B10, HELD, the signer, authority activation, First Memory or PROD.

## 11. Architecture invariants (preserved)

```text
proposal != authority;  request != permission;  approval evidence != execution;  execution != verification
deployment != activation;  model capability != LILITH authority;  model willingness != permission
model output != accepted state;  HELD = restrictive custody state only;  HELD grants no authority
M-B11 (signer start) is a separate later milestone
```

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 12. Tooling and pins

| Tool | SHA-256 |
| --- | --- |
| `services/owner-memory-control/tools/mb10_held_verifier.py` | `35b2cb19a2a6e4673f2425d0a13432b6af736cfc0eeaeab81a48121b1de66cf5` |
| `services/owner-memory-control/tools/mb10_hold_denial_proof.py` | `3685472f865113357e3010003c3bb24ff47e66b528f114f5fca23d9d7a664b7b` |
| `services/owner-memory-control/tools/mb10_dr5_target.py` | `29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0` |
| `services/owner-memory-control/tools/mb10_owner_eligibility.py` | `8d9edfd4110529efb047e5e45eff9e48233ee3ddfe2f8d2bbd7b2015b6c51ea7` |
| `services/owner-memory-control/tools/mb10_operator.py` | bound by D1 / D2 as `{operator}` (HEAD bytes at the control) |

Reused unchanged and pinned by the operator: every Package B pin, `mb9_operator.py` `2312e26a…`, `pkgc_operator.py`
`c5e5a5cc…`, `scripts/deployer_authority_boundary_proof.sh` `9b569f9b…`. No existing tool, verifier, phase, target
or template changed.

## 13. Tests

`services/owner-memory-control/tests/test_b1b3e_mb10_held_package.py`: pins and reuse; the expected HELD equals the
release contract; the DR-5 delta proof (pinned script; three mutated scripts refused) and phase-bound comparison;
the transcript classes; the whole §6 table; the read-only hold-store observer (empty, exact, scratch, metadata,
duplicate, symlink, misbound, released, non-canonical); the verifier over a seamed W9 (agreement, disagreement,
dominance of invalid content); the P1B-10 proof; the owner eligibility (each drift, UNKNOWN, write-once); the
operator (opening, gate events, one marker before one write, refusals before any marker, post-marker
classification, stop, linked successor, POST10 and D3, DR-5 form); static boundaries (exactly one write path, no
later-milestone form); and the REAL release hold writer on a synthetic root: `W10_0` → `W10_1`, unchanged W9 =
`W9_LATER_STATE`, `status P1B-10` PASS, no second HELD, `W10_1S` when stopped, a crash before the rename gives
`W10_P_SCRATCH_RESIDUE_NOT_HELD`, tampered or re-bound content HALTs.

## 14. Unresolved canonical ambiguities

1. **"Re-classified for this step" vs Replica B / store B on the S25.** P3-5 requires `REQUIRED_CURRENT` re-classified
   per step; the laptop can only use the proven, non-custody B views. This record treats that as sufficient (as the
   C5 gate did) but leaves it to OD-M10-5.
2. **C-16b `SAFE_RETRY` vs the one-attempt marker.** P3-5 calls writing HELD into a still-empty store a safe retry;
   this design keeps every retry a new, linked successor with its own go (never automatic).
3. **The installer's `P1B-10` stage checks shape only.** Byte exactness and binding live only in the W10 verifier.
4. **The accepted witness incarnation and boot are pinned.** Any reboot or restart before M-B10 needs an accepted
   re-pin (as after M-R1) before a gate can pass.
5. **Scratch residue has no reviewed removal path** (OD-M10-7).
6. **Post-HELD routine preservation** can no longer use the mb9 `host POST9B` form (it fails closed by design); it
   uses `mb10_operator.py host POST` and the post-HELD DR-5 target.

## 15. State

```text
MB10 = DESIGN / REPOSITORY ONLY; NOT RUN
MB10_CONTINUITY = PROPOSED (OD-M10-1); NOT ACCEPTED
OWNER_DECISIONS OD-M10-1..OD-M10-8 = PROPOSED; NOT ACCEPTED
CONTROL_AT_DESIGN = 28597c1d84f33d6781e68bf9b2d2850cb6e56d4c
W9_PHASE = W9_5_GENESIS_COMMITTED_EXACT (last accepted read; deploy 38038318626)
WITNESS_GENESIS_DIGEST = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4
RECORD_1 = AUTHENTIC + CURRENT
ACCEPTANCE = ACCEPTANCE_COMPLETE
EXPECTED_HELD_NAME = 1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json
EXPECTED_HELD_SHA256 = c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d
POST_HELD_DR5_DELTA = EMPTY (proven from the pinned script); TARGETS DERIVED, NOT ACCEPTED
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
