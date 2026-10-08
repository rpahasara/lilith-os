# Slice 15B2b-B1b-3e — Post-M-B6 DR-5 Baseline: Owner Acceptance and Preservation (2026-10-08)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records the later transition of the post-M-B6 DR-5 target, from
  derived to owner-accepted, and the first preservation of that accepted baseline:

  ```text
  DERIVED / NOT ACCEPTED  ->  first post-freeze deploy EQUAL  ->  owner acceptance  ->  later deploy preservation EQUAL
  ```

- **The earlier record is unchanged.** The [M-B6 completion record](slice-15b2b-b1b3e-mb6-provision-ledger-completion.md)
  states `POST_MB6_DR5_TARGET_ACCEPTED = NO`. That was correct when it was written and accepted, and it is not
  rewritten. This record supersedes it on this one point only, from 2026-10-08.
- `POST_MB6_DR5_TARGET_ACCEPTED = YES`. `POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES`.
- **Documentation and governance only.** This record authorizes no live bootstrap stage. M-B7, M-B8, M-B9a, M-B9b,
  witness genesis, record 1, First Memory, authority activation and PROD stay **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- **No live mutation.** Every evidence read for this record was read-only. No DEV, ledger or deployment change was
  made.

The rule is `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`, owner decision R-2A, in the
[M-B6 remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §12.2. Under DR6-12 the derived baseline is
accepted separately, after the first post-freeze deploy compares `EQUAL`. This record is that separate acceptance.

## 1. Phase-bound baselines (both kept)

| Phase | Status | Full result set | DR-5 block | Pre-deploy block |
| --- | --- | --- | --- | --- |
| pre-M-B6 (`W6_0_NO_MB6_MUTATION`) | `PRE_MB6_DR5_BASELINE = PRESERVED AS HISTORICAL ACCEPTED EVIDENCE` (run `36552218231`) | `f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b` (186 lines, 158 `DENIED`) | `a1d98773bcd07c39b2a17f0628f75db858a3e1e6bcd19e7bcd8918c0e79f1390` (147 lines) | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` (29 lines) |
| post-M-B6 (`LEDGER_COMMITTED_EXACT`) | `POST_MB6_DR5_BASELINE = OWNER-ACCEPTED` | `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494` (188 lines, 161 `DENIED`) | `d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801` (149 lines) | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` (29 lines) |

**The two phases are not collapsed.** The pre-M-B6 baseline stays historical accepted evidence. It is the comparison
target only for a host verified at `W6_0_NO_MB6_MUTATION`.

## 2. The first post-freeze, baseline-establishing deploy

| Item | Value |
| --- | --- |
| `FIRST_POST_FREEZE_DEV_DEPLOY` | `37726177957`: the first DEV deployment after the M-B6 freeze ended (2026-10-07T19:08:52Z) |
| control | `e1b5a2cf22be9214ccb9cdd429ce1a08b11a9124` |
| source validation | `37726011359` (`push`), success |
| deploy result / window | success, 2026-10-08T04:10:10Z–04:13:36Z |
| mode | `DEPLOY_REQUIRED` |
| previous DEV deploy | `37666101351` (`5752bc8`, 2026-10-07T18:20Z), before the freeze ended; none in between |

**Fresh DR-5** (from that run's own log, not reused):

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | 188 | `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 3 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | 149 | `d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801` | 133 `DENIED`, 0 `ALLOWED` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

`PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` and
`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` were all present.

**Comparison.** The canonical `mb6_dr5_target.py` (SHA-256 `9978e3a7…2656`) ran `compare LEDGER_COMMITTED_EXACT
<log>`. The result was **`EQUAL`**, with `unequal = []`, `allowed = 0` and `fail = 0`. A read-only host check at the
same time confirmed `LEDGER_COMMITTED_EXACT` and a ledger unchanged since M-B6 POST.

## 3. Owner acceptance (verbatim)

> I accept the post-M-B6 DR-5 baseline for DEV_SYNTHETIC based on first post-freeze DEV deployment 37726177957 at
> control e1b5a2cf22be9214ccb9cdd429ce1a08b11a9124. The fresh DR-5 result set is 188 lines with SHA-256
> 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494, 161 DENIED, 0 ALLOWED and 0 FAIL; the DR-5 block
> is 149 lines with SHA-256 d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801 and 133 DENIED, 0
> ALLOWED; the pre-deploy block is 29 lines with SHA-256
> f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae and is unchanged. The canonical mb6_dr5_target.py
> comparison for LEDGER_COMMITTED_EXACT returned EQUAL with no unequal fields, allowed=0 and fail=0. The ledger
> remains sequence 1 with head 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630 and is unchanged
> from M-B6 POST. REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. GRANT_ABSENT remains true.
> AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain. No M-B7-or-later state exists. Therefore
> POST_MB6_DR5_TARGET_ACCEPTED = YES. This acceptance does not authorize M-B7, M-B8, M-B9a, M-B9b, witness genesis,
> Record 1, First Memory, authority activation or PROD.

```text
POST_MB6_DR5_TARGET_ACCEPTED = YES
```

## 4. The first preservation: the PR #166 deploy

| Item | Value |
| --- | --- |
| PR #166 merge commit | `dea8a94967cafb2565d61c2339b57f4324cafa01`, merged 2026-10-08T04:26:12Z |
| main validation | `37727472154` (`push`), success |
| DEV deploy | `37727603638`, success, 2026-10-08T04:27:54Z–04:31:20Z |
| mode / base | `DEPLOY_REQUIRED`; base `e1b5a2cf22be9214ccb9cdd429ce1a08b11a9124` |
| later or pending | none at the check |

**Fresh DR-5 reproduced the accepted baseline exactly:**

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | 188 | `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL` |
| DR-5 block | 149 | `d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801` | 133 `DENIED`, 0 `ALLOWED` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

```text
POST_MB6_DR5_COMPARISON = EQUAL
POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES
```

## 5. Ledger and authority preservation

The read-only host check (`mb6_operator.py host … POST`) after the preservation deploy showed:

- **Ledger:** `LEDGER_COMMITTED_EXACT`, sequence 1, head
  `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630`, failures `[]`.
- **Unchanged since M-B6 POST:** the committed-image hash (`fae62c87…`), the file metadata and the state-directory
  metadata are identical. The database is still the only ledger-state entry.
- **Registry and authority:** `REGISTRY_EFFECTIVE = NO`; `AUTHORITY_ACTIVE = NO` (`authorityGranted = false`);
  `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.
- **W5 gaps:** `AUTHORIZATION_REGISTER_COPY_MISSING` and `GENESIS_PIN_COPY_MISSING` remain.
- **No later state:** signer and witness remain inactive. No M-B7-or-later state exists. There is no witness genesis,
  no record 1 and no First Memory.
- **Other checks:** `status --expect P1B-6` PASS; broker preservation PASS. Custody is byte-identical to M-B6 POST.

## 6. Procedural note: observer client exit anomaly

**The first host check did not pass.** It returned **`MB6_HOST_POST_NOT_PASS`**, solely because the observer
sub-read process exited **`0xC0000005`** (code 3221225477).

**What the evidence showed:**

- That is a crash of the local Windows gcloud client.
- The observer output itself was complete (`PR1A_HOST_OBSERVATION=COMPLETE`), and stderr was empty.
- The observer digest was `f432b724…`, equal to the accepted M-B6 POST observer digest. Only the normal clock fields
  differed.
- All 7 other sub-reads returned 0 with exact facts.
- No DEV mutation, ledger change or authority change occurred.

**The re-run passed.** One immediate, identical, read-only re-run returned **`MB6_HOST_POST_PASS`** with all 8 codes
0. Its custody, readiness, status, W5 and verifier output was byte-identical to the first read. The broker and
observer facts equalled the accepted POST state except the clock fields.

```text
OBSERVER_CLIENT_EXIT_ANOMALY = PROCEDURAL_CLIENT_FAILURE_ONLY
AUTHORITY_DRIFT = NO
SUBSTRATE_DRIFT = NO
LEDGER_DRIFT = NO
```

The first process exit is kept on record. The first invocation did **not** succeed; only the re-run passed.

## 7. Rule going forward

For every later applicable DEV deployment while the ledger remains in the `LEDGER_COMMITTED_EXACT` phase:

1. First establish the verifier phase: a read-only M-B6 verifier read must confirm `LEDGER_COMMITTED_EXACT`.
2. Then require `mb6_dr5_target.py compare LEDGER_COMMITTED_EXACT <fresh-log>` = **`EQUAL`** against the accepted
   post-M-B6 baseline (§1).

Anything else is **drift requiring owner adjudication**. There is **no automatic rebaseline**.

## 8. Boundaries

| Fact | State |
| --- | --- |
| M-B6 | COMPLETED / OWNER-ACCEPTED |
| `LEDGER_PROVISIONED` | OWNER-ACCEPTED (sequence 1, head `19bf9091…1630`) |
| `REGISTRY_EFFECTIVE` | **NO** |
| `AUTHORITY_ACTIVE` | **NO** |
| `GRANT_ABSENT` | TRUE |
| `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING` | TRUE (both remain) |
| M-B7 | **NOT AUTHORIZED** |
| M-B8 | **NOT AUTHORIZED** |
| M-B9a / M-B9b | **NOT AUTHORIZED** |
| witness genesis | **NOT AUTHORIZED** |
| record 1 | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED** |
| authority activation | **NOT AUTHORIZED** |
| PROD | **NOT AUTHORIZED** |

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 9. State

```text
POST_MB6_DR5_TARGET_ACCEPTED = YES (2026-10-08; earlier record's NO preserved as history)
POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES (deploy 37727603638, EQUAL)
PRE_MB6_DR5_BASELINE = PRESERVED AS HISTORICAL ACCEPTED EVIDENCE
POST_MB6_DR5_BASELINE = OWNER-ACCEPTED (3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494)
OBSERVER_CLIENT_EXIT_ANOMALY = PROCEDURAL_CLIENT_FAILURE_ONLY
AUTHORITY_DRIFT = NO
SUBSTRATE_DRIFT = NO
LEDGER_DRIFT = NO
M-B6 = COMPLETED / OWNER-ACCEPTED
LEDGER_PROVISIONED = OWNER-ACCEPTED
LEDGER SEQUENCE = 1
LEDGER HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
GRANT_ABSENT = TRUE
AUTHORIZATION_REGISTER_COPY_MISSING = TRUE
GENESIS_PIN_COPY_MISSING = TRUE
M-B7 = NOT AUTHORIZED
M-B8 = NOT AUTHORIZED
M-B9a = NOT AUTHORIZED
M-B9b = NOT AUTHORIZED
WITNESS GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```
