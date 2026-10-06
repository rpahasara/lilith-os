# Slice 15B2b-B1b-3e — PR-1B Eligibility Sequence 3: `CHECK_ELIGIBILITY` Result (2026-10-05)

Status:

- **`PR1B_ELIGIBLE = TRUE`.** The canonical evaluator
  `evaluate_eligibility` was invoked **exactly once**, inside one continuous
  owner-authorized DEV_SYNTHETIC eligibility sequence, and returned
  `status = PR1B_ELIGIBLE`, `reasons = []`, `eligible = True`.
- **Condition 3 was current at the evaluator call and is no longer
  current.** The final Condition 3 window expired when the sequence ended.
  That expiry is REVALIDATE, not FAIL. It does not retroactively change the
  completed evaluation.
- **M-B1 carry-forward (current): `B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1`**,
  by the later
  [owner decision](slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md).
  This result is **not reusable** to begin a later M-B1. The pre-decision
  analysis in §9 classified the question as `C. AMBIGUOUS`; it stays below
  as history.
- **M-B1, K-ROOT, K-WIT, registry / genesis mutation and First Memory are
  NOT AUTHORIZED.** Owner freshness is `FRESHNESS=UNKNOWN`.
- Operational record. Raw evidence is operator-held outside the repository.
  No repository file was changed during the live sequence.

```text
PR1B_ELIGIBLE = TRUE (completed evaluation)  !=  CONDITION_3_CURRENT now
eligible != M-B1 go != K-ROOT exists != freshness CURRENT != First Memory
policy evaluation != authorization
```

## 1. Identities

| Item | Value |
| --- | --- |
| sequence | Sequence 3, `2026-10-05T20:09:38Z`–`20:15:28Z` (all times UTC) |
| control `main` (`CONTROL_SHA`) | `92ab03927a03dadef66b43101b583926c4e2760f` (merge of PR #146; unchanged through the sequence) |
| B-5 grant | [owner grant for the current DEV_SYNTHETIC packet](slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md). Its "2026-10-06" is the owner's local date; it merged on `main` (`92ab039`) at about `2026-10-05T19:28Z`, before this sequence |
| evaluator | `services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py` `evaluate_eligibility` |
| raw evidence | operator-held external bundle (109 files), **not canonical repository content**. `SHA256SUMS` SHA-256 **`6a94d85387ef51aca8d7b432bfaf2d38385744e12b6e21949f3c28965b80137c`**. Evaluator output SHA-256 `16594278fb21b42aeca7fc43ea5a6d272941f30c2fd89544127f80367d571b7c`; preflight output SHA-256 `c9d182d7054bdbffddda21ead005c53521ae5e67416414ff6390bb49ac81a142`. Location not published |
| secret scan | 0 hits |

**Earlier attempts (provenance only).** Sequence 1 (`19:35:35Z`–`19:53:53Z`)
was stopped by the owner during host collection. In Sequence 2
(`19:54:05Z`–`20:02:57Z`), Condition 3 passed, but the evaluator process
failed at Python import twice (`lilith_memory`, then `rfc8785`, in Windows
Python) **before `evaluate_eligibility` was entered**. Neither produced an
eligibility result. Their Condition 3 windows expired and were not reused.

## 2. Owner authorization (verbatim)

> I authorize a new DEV_SYNTHETIC eligibility sequence. Before opening
> Condition 3, perform an import-only evaluator preflight in the existing WSL
> Ubuntu-24.04 environment using existing/vendored dependencies, without
> installing or modifying anything and without calling evaluate_eligibility.
>
> If that preflight passes, reconfirm no intervening DEV deployment, collect a
> fresh final Condition 3 from the beginning, invoke the canonical
> CHECK_ELIGIBILITY evaluator exactly once, and stop immediately after
> reporting the result.
>
> This does not authorize package installation, M-B1, KROOT, KWIT,
> registry/genesis mutation, or First Memory.

## 3. Evaluator preflight (import only)

Run before Condition 3 opened, in WSL with the distribution named
explicitly (`-d Ubuntu-24.04`; reported OS Ubuntu 24.04.5 LTS, Python
3.12.3). The Windows default WSL distribution (`docker-desktop`) was not
used and not changed.

- **Source:** an existing in-WSL extract of the repository, verified first
  to be byte-equal to `92ab039` for all 42 `.py` files of the import closure
  (`lilith_owner_memory`, `lilith_memory`), with no extra or missing files.
- **Dependencies:** the existing pinned dependency directory, including the
  `rfc8785` 0.1.4 wheel (the version pinned in
  `services/core-api/requirements.txt`).
- Python ran with `-B`, `PYTHONDONTWRITEBYTECODE=1` and a nonexistent
  bytecode prefix: no bytecode was read or written. Nothing was installed.

```text
WSL_DISTRO = Ubuntu-24.04
LILITH_MEMORY_IMPORT = PASS
RFC8785_IMPORT = PASS
PR1B_SEQUENCING_IMPORT = PASS
EVALUATE_ELIGIBILITY_SYMBOL_PRESENT = YES
EVALUATE_ELIGIBILITY_CALLABLE = YES
EVALUATE_ELIGIBILITY_CALL_COUNT = 0
EVALUATOR_PREFLIGHT = PASS
```

The repository working tree was clean after the preflight.

## 4. DR-5 and B-5 grant usability

- Read-only GitHub inspection. The latest successful DEV deployment is run
  `37356261343` (`47f2655`, `2026-10-05T18:28:54Z`). It equals the accepted
  run `36552218231` on the full result set (186 lines, `f1869234…`), the
  DR-5 block (147, `a1d98773…`) and the pre-deploy block (29, `f5087042…`):
  `P1A-9`, `L1c.3`, `GRANT_ABSENT`, no `ALLOWED`.
- The `92ab039` deploy run `37365210560` was **SKIPPED** (all jobs skipped).
  Its validation run `37363577780` failed because hosted runners did not
  acquire two jobs. No DEV contact followed. Nothing was queued or in
  progress before Condition 3 or before the evaluator call.
- **`DR5_CURRENTNESS = CURRENT`.**
- **`B5_GRANT_USABLE = YES`.** No B-5 packet §9 stop condition fired. No
  G-1 … G-9 was observed. No replica or custody event was known.

## 5. Final Condition 3 (fresh, `20:10:01Z`–`20:15:09Z`)

The accepted read-only procedure of the
[fresh read-only rebaseline](slice-15b2b-b1b3e-dev-synthetic-fresh-readonly-rebaseline.md)
(itself the [Condition 3 PASS](slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md)
procedure), with only the output location, `CONTROL_SHA` and the audit
start (`2026-10-05T16:20:54Z`) changed. Tool blobs at `92ab039` equal the
accepted ones.

| Item | Observed | vs accepted |
| --- | --- | --- |
| cloud / rollback domain | 23 artifacts byte-identical (instance, one boot disk, no snapshot / image / resource policy / bucket, `backupdr` off, IAM incl. all service-account policies); whole-life compute Admin Activity identical: **no compute call ever** | equal |
| Admin Activity since `16:20:54Z` | all `iam.serviceAccounts.actAs`: deployer entries for the two known deploys; owner OS Login sessions of the rebaseline and Sequences 1–2 | explained |
| host identity / boot | `lilith-dev-01`, boot **`eea461c3-60f0-4b10-8ee9-556dcef19711`**, `REBOOT_REQUIRED=absent` | same boot |
| broker preservation | **`BROKER_PRESERVATION=PASS`, `failures=[]`**, output byte-identical; incarnation **`c4b9cb38d7a041dc91db0d8ada7e8d04`**, candidate **`a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d`** | equal |
| observer | `stableSha256` `c54f21ba09bdc3b3fb0434ec35875fb280d2042716d4e0111b124d8faf386f33`; every section equal | equal |
| P1A-9 | `status --expect P1A-9` PASS, byte-identical | equal |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` | equal |
| units, systemd, storage probe | equal except volatile fields only (`MemoryAvailable`; probe `meta`, `timers`, `end`) | equivalent |
| packages | the 12 broker-mapped packages at unchanged versions; **none pending**; lists, upgradable set, holds (none) and activity (idle) equal; `dpkg -V needrestart` clean | equal |
| needrestart | probe output and configuration byte-identical | equal |
| unattended-install horizon | next `apt-daily-upgrade` `2026-10-06T06:48:30Z` | outside the sequence |
| Replica A | records `0`; manifest `fbdd045c…978b`; inodes `59905 / 59906 / 59907`; mtime `1790643451` | byte-identical |

```text
CONDITION_3_FRESH_PR2 = PASS
CONDITION_3_CURRENT = ESTABLISHED (at the evaluator call)
G-1 … G-9: none observed
material drift: none
```

No expiry trigger (a)-(h) of the
[validity-window decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md)
occurred between collection and the evaluator call (about 12 seconds; no
new run; no reboot or broker replacement observed).

## 6. Eligibility inputs (from the code at `92ab039`)

`PRECONDITIONS` lists exactly 12 inputs. Each was `True`:

| Input | Evidence | Currentness / ADR-0015 basis |
| --- | --- | --- |
| `p33Complete` | [P3-3 storage acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md) | accepted state; replicas continuous (Replica A this window; Replica B owner-observed at 17:45Z per the [packet](slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md)); no G-6 |
| `twoRealReplicasExist` | P3-3 acceptance; [Replica B canonical path](slice-15b2b-b1b3e-pr3-p33b-replica-b-ceremony.md) | same |
| `replicasCapabilityAdmitted` | P3-3 acceptance | same |
| `replicaIndependenceEstablished` | P3-3 acceptance | same |
| `replicasAgentUnreachableCopy` | P3-3 acceptance; packet custody G-9 (owner-observed) | no agent contact with the phone since; no §9 custody event |
| `ownerRegisterKnownEmpty` | Replica A 0 records (this window); Replica B 0 records (packet, 17:45Z) | Replica B offline; no ceremony step since |
| `pr3ToolingAccepted` | [PR-3 tooling acceptance](slice-15b2b-b1b3e-pr3-tooling-acceptance.md) (B-1) | tool sources unchanged at `92ab039`; no G-4 |
| `pr1aBaselineValid` | P1A-9 PASS this window | same boot |
| `pr2InventoryRevalidated` | §5 (this window) | fresh, immediately before |
| `noUnreviewedTopologyChange` | §5 cloud inventory and audit; DR-5 CURRENT | fresh, immediately before |
| `openRisksAcknowledged` | packet owner risk review (OR-1 … OR-9) | OR-8 terms met by this window |
| `pr1bAuthorized` | B-5 grant | owner assertion; grant usable (§4); input only, not persisted |

## 7. The evaluator call

- **Environment:** the same WSL `Ubuntu-24.04` environment and import roots
  as the preflight, unchanged in between. Inline Python on stdin; no wrapper
  script, no sequencer transition, nothing persisted.
- **Call count: exactly 1**, at `2026-10-05T20:15:21Z`.

```text
ENTERING evaluate_eligibility (call 1 of 1)
RESULT status = PR1B_ELIGIBLE | reasons = [] | eligible = True
EVALUATE_ELIGIBILITY_CALL_COUNT = 1; no sequencer advance; nothing persisted
rc=0
```

**`PR1B_ELIGIBLE = TRUE`.**

## 8. After the sequence

- The sequence ended at `20:15:28Z`, by owner design (stop after the
  result). Under trigger (h) the Condition 3 window **expired**:
  `CONDITION_3_CURRENT = NOT_ESTABLISHED` now. This is **REVALIDATE, not
  FAIL**, and it does not reverse the completed evaluation.
- `PR1B_ELIGIBLE = TRUE` remains the recorded result of that evaluation.
  Whether it can be **consumed** by a later M-B1 is §9.

## 9. M-B1 carry-forward determination (pre-decision analysis)

> **Resolved by a later owner decision.** The owner chose
> `B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1`
> ([owner decision](slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md)).
> The analysis below is kept as the pre-decision history that led to it;
> its `C` classification is no longer current.

**Question.** Can this completed `PR1B_ELIGIBLE = TRUE` result serve as the
PR-1B eligibility prerequisite for a later, separately owner-authorized
M-B1 ceremony, after the Condition 3 window that supported it has expired?

**Pre-decision classification: `C. AMBIGUOUS — OWNER/ARCHITECTURE DECISION REQUIRED`.**

No accepted record defines the lifetime or consumption of a completed
eligibility result. The controlling semantics point both ways.

**Read as allowing the result to stand (no contemporaneity rule):**

1. The M-B1 operator-flow preconditions
   ([ceremony package](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md) §3;
   [final pins](slice-15b2b-b1b3e-mb1-final-package-pins.md) §4; B-5 packet
   §5) are: the package merged; the DEV deploy boundary reviewed; "a fresh
   PR-2 revalidation PASS immediately before **eligibility**";
   "`CHECK_ELIGIBILITY` returns `PR1B_ELIGIBLE`"; and the owner's separate
   M-B1 go. None says the eligibility check must be contemporaneous with
   M-B1.
2. The [validity-window decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md)
   binds Condition 3 to use "immediately before `CHECK_ELIGIBILITY`" inside
   one continuous **eligibility** sequence. It does not say Condition 3 must
   remain current through M-B1.
3. The only accepted rule that carried Condition 3 through M-B1 (the
   2026-10-02 PASS: "valid … only if the eligibility-to-M-B1 window ends
   before the next unattended run") is recorded as **historical, not a
   rule** ([policy](substrate-drift-and-evidence-revalidation-policy-v0.1.md)
   §7; ADR-0015 Context).
4. The next mandatory PR-2 revalidation is immediately before
   `GENERATE_K_WIT` (M-B2) ([P3-5](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md)
   §13; replacement OR-8 acknowledgement). M-B1 runs off-host, on the S25.

**Read as requiring a fresh evaluation before M-B1:**

1. The accepted sequencer crash matrix (`pr1b_sequencing.CRASH_MATRIX`;
   P3-5 §9) classifies exactly this window, "C-1 eligibility checked /
   K-ROOT absent", as `SAFE_RETRY` with the action **"re-check eligibility;
   nothing written"**.
2. `BootstrapSequencerV1` "tracks one PR-1B bootstrap", forward only. The
   `PR1B_ELIGIBLE` state that `GENERATE_K_ROOT` advances from exists only in
   that in-memory instance; nothing persists it (P3-5 §1–§2, step table).
3. P3-5 §13: any PR-2 change "yields `PR2_REVALIDATION_REQUIRED`, and
   therefore `PR1B_NOT_ELIGIBLE`, until a new inventory is accepted". The
   policy §2 lists **eligibility** among the evidence that G-4, G-5 and G-6
   make NOT REUSABLE / REVALIDATE. Eligibility is therefore treated as
   revocable by later drift, but no procedure exists for showing a past
   result is still current.
4. B-5 packet §9: any stop condition before M-B1 voids the grant, and with
   it the `pr1bAuthorized` input the result relied on.

**What the accepted records do settle:**

- The expired Condition 3 window does **not** retroactively invalidate the
  completed evaluation.
- The result is **not** permanently reusable. Any B-5 §9 stop before M-B1
  voids the grant. Any G-4 / G-5 / G-6 makes eligibility NOT REUSABLE /
  REVALIDATE. Any detected PR-2 change yields `PR1B_NOT_ELIGIBLE`.
- Whether a fresh `CHECK_ELIGIBILITY` is **required** before M-B1 is not
  established either way. This record adds no rule.

## 10. Gates that remain before any M-B1

Separate, and none authorized here:

| Gate | State |
| --- | --- |
| PR-1B eligibility prerequisite | this record's completed result is **not reusable** for M-B1 (owner decision B). A future M-B1 sequence must re-establish current evidence, run a fresh final Condition 3 and `CHECK_ELIGIBILITY` exactly once, and continue to M-B1 only inside that same continuous sequence |
| owner M-B1 go statement | **NOT GIVEN**. It must be explicit and separate, naming the pinned script `09cbc9be…` and bundle `7f07e158…` ([final pins](slice-15b2b-b1b3e-mb1-final-package-pins.md)); burned identities = the canonical 20 |
| M-B1 G0 / G1 / T1 phone gates | run on the S25 only (ceremony package §5): Termux private storage, no SSH / `sshd`, local TTY, no existing K-ROOT or failed candidate, Replica B the accepted empty replica (`c068e533…`, not nested), bundle verified, owner types `GENERATE` |
| B-5 grant | must still be non-void at M-B1 (packet §9) |
| Condition 1 (package) | must still hold: bundle from merged `main`, pins unchanged (G-7) |
| K-ROOT generation (M-B1) | **NOT AUTHORIZED** |
| fresh PR-2 immediately before `GENERATE_K_WIT` (M-B2) | **mandatory** (P3-5 §13; OR-8); this sequence's window does not satisfy it |
| K-WIT generation (M-B2) | **NOT AUTHORIZED** |
| registry / genesis (M-B3 … M-B9b) | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED** |

## 11. Validation

- `test_b1b3e_pr1b_eligibility_sequence3.py` pins the preflight, the single
  call, the inputs, the result, the Condition 3 expiry semantics, the
  carry-forward classification and the non-claims.
- `test_b1b3e_mb1_eligibility_carry_forward_owner_decision.py` pins the
  owner decision B.
- `scripts/validate_repository.py` passes, and `git diff --check` is clean.

## 12. State

```text
EVALUATOR_PREFLIGHT = PASS (WSL Ubuntu-24.04; EVALUATE_ELIGIBILITY_CALL_COUNT = 0)
DR5_CURRENTNESS = CURRENT (37356261343 / 47f2655; 92ab039 deploy SKIPPED)
B5_GRANT_USABLE = YES
CONDITION_3_FRESH_PR2 = PASS (2026-10-05T20:10:01Z-20:15:09Z)
EVALUATOR CALL COUNT = 1
ALL 12 INPUTS TRUE
EVALUATOR RESULT = PR1B_ELIGIBLE; REASONS = []
PR1B_ELIGIBLE = TRUE
CONDITION_3_CURRENT = NOT_ESTABLISHED AFTER SEQUENCE END (EXPIRED; REVALIDATE, NOT FAIL)
COMPLETED_HISTORICAL_RESULT = PR1B_ELIGIBLE
REUSABLE_FOR_LATER_M_B1 = NO
M-B1 CARRY-FORWARD (PRE-DECISION) = C. AMBIGUOUS — OWNER/ARCHITECTURE DECISION REQUIRED
M-B1 CARRY-FORWARD (CURRENT, OWNER DECISION) = B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1
FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY
M-B1 = NOT AUTHORIZED
KROOT = NOT AUTHORIZED
KWIT = NOT AUTHORIZED
REGISTRY / GENESIS MUTATION = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO PACKAGE INSTALLATION
NO DEV, CLOUD, IAM, REPLICA OR RUNTIME MUTATION
NO REPOSITORY CHANGE DURING THE LIVE SEQUENCE
```
