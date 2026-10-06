# Slice 15B2b-B1b-3e — PR-1B Eligibility Review

Status:

- **READ-ONLY REVIEW / CLASSIFICATION ONLY**. No DEV mutation by this review;
  the only mutation in the window was the routine deploy triggered by the
  owner's merge of `28daf7b` (§2)
- Classification: **`PR1B_NOT_ELIGIBLE`**, with five exact blockers (§8)
- **PR-1B EXECUTION NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**

```text
eligibility review != eligibility != authorization != execution
technical preconditions met != PR1B_ELIGIBLE
```

## 1. Question and gate

> Are all reviewed preconditions satisfied to authorize the real PR-1B
> authority bootstrap?

The reviewed gate is
`services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py`
`evaluate_eligibility`
([P3-5 §1](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md)).

- It returns `PR1B_ELIGIBLE` only when every precondition is literally
  `True`.
- One of those preconditions is `pr1bAuthorized`. So in the reviewed
  design, `PR1B_ELIGIBLE` is reached only together with the owner's
  explicit authorization, at `CHECK_ELIGIBILITY` (P1B-0) inside the PR-1B
  ceremony.
- This review can therefore conclude at most that **every other
  precondition is met**. It is not there yet (§8).

**Control SHA:** `28daf7b42fd76e98a847c510504345e911fed92c` (merge of PR #108,
the PR-2 revalidation record). It differs from `c0adb70` in docs only.

## 2. Reviewed evidence

**Live read-only checks** (2026-09-29, about `10:23Z`–`10:30Z`, tools from
`CONTROL_SHA`):

| Check | Result |
| --- | --- |
| merge-triggered DR-5 | run `36554630110` (`28daf7b`, `DEPLOY_REQUIRED`, `10:17:21Z`–`10:22:58Z`): `SUDO_EFFECTIVE_PROOF=PASS`, `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`. No real `FAIL`, no `ALLOWED(unexpected)`. The `DENIED` set, including the six OR-6 `/run` denials, is identical to run `36552218231` |
| broker `preservation` (verifier `bd7aa35a…`) | `PASS`, `failures=[]`: boot `eea461c3-60f0-4b10-8ee9-556dcef19711`, incarnation `84798e5b74494e1ea362ce90f1cf04ad`, PID 2586, start ticks 69918, `NRestarts=0`, candidate `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2`, controller loaded / inactive / never started |
| `status --expect P1A-9 aee323e…` | PASS |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| authority / witness units | all five `inactive`, `static`, no InvocationID |
| host observer | `c4a654033dac…`, equal to the [PR-2 revalidation](slice-15b2b-b1b3e-pr2-revalidation.md) observation |
| custody | `prepared/`, `retired/`, `holds/`, and witness `credentials/` are empty. K-WIT (both names), `/var/lib/lilith-authority-dev` (ledger), `/var/lib/lilith-recovery-witness` (witness state), `hold`, `INSTALLED`, and both runtime credential directories are absent. `P1A-9` enforces empty `registry/`, `trust/`, and `owner/`. RecoveryEpoch is absent |

**Offline checks.**

- `services/owner-memory-control/tests`: 634 tests OK.
- The coded step order was printed from `STEPS` (§5).
- `owner_acceptance.real_acceptance_block("DEV_SYNTHETIC")` returns
  `P3_3_STORAGE_INCOMPLETE`.

**Owner replicas.** Not contacted. The state is taken from the
[P3-3 acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md): A real
and empty, B real and empty, 0 accepted records, record 1 absent,
`FRESHNESS_UNKNOWN`.

## 3. Preconditions A–R

| # | Precondition | Result | Basis |
| --- | --- | --- | --- |
| A | PR-1A accepted and current | **MET** | [PR-1A acceptance](slice-15b2b-b1b3e-pr1a-acceptance.md); live `P1A-9` |
| B | P1A-9 still valid | **MET** | status PASS on the accepted post-reboot baseline |
| C | DR-5 / L1c.3 current | **MET** | run `36554630110` |
| D | broker preservation current | **MET** | live PASS against the [re-pinned](slice-15b2b-b1b3e-broker-preservation-repin.md) baseline |
| E | activation still dark | **MET** | `GRANT_ABSENT` |
| F | PR-2 current / revalidated | **MET for this window** | [PR-2 revalidation](slice-15b2b-b1b3e-pr2-revalidation.md); the observer is unchanged since. P3-5 §13 requires it **again**, immediately before `CHECK_ELIGIBILITY` and before `GENERATE_K_WIT` |
| G | P3-3 complete | **MET** | `P3_3_COMPLETE` |
| H | both owner replicas exist and are empty | **MET** (by record; not re-contacted) | P3-3 acceptance §1–§2, §6 |
| I | record 1 absent | **MET** | same |
| J | owner freshness `FRESHNESS_UNKNOWN` | **MET** | same |
| K–P | no K-WIT, registry, ledger, witness state, holds, or RecoveryEpoch | **MET** | §2 live checks |
| Q | authority / witness units inert | **MET** | §2 |
| R | the P3-5 PR-1B sequence is unchanged and applicable | **MET, with the P3-6 envelope steps** (§5) | coded `STEPS` |

Reviewed-gate facts (`evaluate_eligibility`):

| Precondition | Value |
| --- | --- |
| `p33Complete`, `twoRealReplicasExist`, `replicasCapabilityAdmitted`, `replicaIndependenceEstablished` | `True` (P3-3 acceptance §7) |
| `replicasAgentUnreachableCopy` | `True`, as NOT OBSERVED for Replica B (§6) |
| `ownerRegisterKnownEmpty` | `True` by record. It is evaluated live at `CHECK_ELIGIBILITY` |
| `pr1aBaselineValid`, `pr2InventoryRevalidated`, `noUnreviewedTopologyChange` | `True` |
| `pr3ToolingAccepted` | **not `True`**: no owner acceptance record exists (§8 B-1) |
| `openRisksAcknowledged` | **not `True`**: no owner acknowledgement exists (§8 B-2) |
| `pr1bAuthorized` | **not `True`** (§8 B-5) |

Result:

```text
PR1B_NOT_ELIGIBLE (PR3_TOOLING_NOT_ACCEPTED, OPEN_RISKS_NOT_ACKNOWLEDGED, PR1B_NOT_AUTHORIZED)
```

## 4. Open risks

No open risk is silently accepted here. Each classification below is a
**proposal**. `ACCEPTABLE_PRECONDITION_DEBT` becomes effective only through
the owner's explicit acknowledgement (B-2).

| ID | Risk | Proposed decision | Reason |
| --- | --- | --- | --- |
| OR-1 | whole-disk / whole-host rollback presents a self-consistent old authority world | **ACCEPTABLE_PRECONDITION_DEBT** (DEV_SYNTHETIC only) | Before record 1, a rollback only returns DEV to an earlier, equally synthetic state. After record 1, owner freshness is the designed detector: a rolled-back witness head is `STALE` / `AHEAD` against both replicas, and every gated operation requires `CURRENT` (PR3-D11). Resistance itself stays NOT ESTABLISHED |
| OR-2 | root-equivalent principals and host-local copies (DR-3) | **ACCEPTABLE_PRECONDITION_DEBT** (DEV_SYNTHETIC only) | A root-equivalent principal could copy K-ACT or K-WIT blobs together with the host key. The keys are synthetic. This must not carry over to any real authority |
| OR-3 | cloud principals able to snapshot, image, or clone | **ACCEPTABLE_PRECONDITION_DEBT**, bounded | IAM is unchanged and no artifact exists. It is procedurally controlled by the P3-5 §13 PR-2 revalidation immediately before P1B-0 and M-B2 |
| OR-4 | no external freshness consumed by DEV | **ACCEPTABLE_PRECONDITION_DEBT**, by design | Freshness is judged owner-side (PR-3). DEV consuming none is the accepted architecture, not a gap PR-1B must close first. It becomes meaningful only after record 1 |
| OR-7 | disk-backed `PrivateTmp` / `/tmp` | **ACCEPTABLE_PRECONDITION_DEBT** | Credentials load into `/run/credentials` (tmpfs). The only reviewed `/tmp` use is the root forensic ledger read (`ledger._on_copy`): a transient `0600` copy of the ledger in a private temp directory, removed afterwards. That is authority state, not key material; any retained copy falls under OR-2 |
| OR-8 | future snapshot activity can stale PR-2 | **ACCEPTABLE_PRECONDITION_DEBT**, procedurally controlled | The P3-5 §13 revalidation-immediately-before rule |
| OR-9 | visibility scope | **not a risk decision**: visibility-scope limitation only | Unrelated visible projects are not LILITH components |
| OR-5 | pending reboot | **CLOSED** | [reboot evidence](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline-acceptance.md) |
| OR-6 | tmpfiles runtime directories | **CLOSED** | same |

**Also carried:**

- **DR-3.** `ubuntu` is root-equivalent through `sudo`/`lxd`. Proposed as
  ACCEPTABLE_PRECONDITION_DEBT, DEV_SYNTHETIC only, as throughout PR-1A.
- **Cross-environment PROD deployer `osAdminLogin`.** Proposed as
  ACCEPTABLE_PRECONDITION_DEBT, DEV_SYNTHETIC only.

**No open risk is proposed as `BLOCKING_PR1B` by itself.** All of them
remain `OPEN_RISKS_NOT_ACKNOWLEDGED` until the owner acknowledges them (B-2).

## 5. PR-1B sequence

The coded order (`STEPS`) is:

```text
CHECK_ELIGIBILITY (P1B-0)
M-B1  GENERATE_K_ROOT (off-host)
M-B2  GENERATE_K_WIT                 [PR-2 revalidated immediately before]
M-B3  SIGN_REGISTRY_V1 (off-host)
M-B4+M-B5 INSTALL_TRUST_AND_REGISTRY
M-B6  PROVISION_LEDGER (exactly one GENESIS row, sequence 1)
M-B7  PREPARE_GENESIS_CANDIDATE
M-B8  PIN_GENESIS (owner pin, two off-host copies + on-host copy)
M-B9a START_WITNESS
M-B9b COMMIT_WITNESS_GENESIS
      APPEND_RECORD_1_REPLICA_A     -> FRESHNESS_UNKNOWN (intended)
      APPEND_RECORD_1_REPLICA_B     -> AUTHENTIC + CURRENT
      APPEND_ENVELOPE_1_COPY_A      (P3-6)
      APPEND_ENVELOPE_1_COPY_B      (P3-6) -> ACCEPTANCE_COMPLETE
M-B10 WRITE_HELD (INITIAL_CUSTODY HELD)
M-B11 START_SIGNER
M-B12 EVALUATE_ELIGIBILITY
M-B13 OWNER_ACCEPTANCE
M-B14 WRITE_RELEASED
M-B15 EVALUATE_FULL_READINESS
```

This matches the order under review, with one addition: the two P3-6
acceptance-envelope steps come after record 1 and before `WRITE_HELD`, and
`WRITE_HELD` requires `OWNER_ACCEPTANCE_EVIDENCED`.

**Confirmed:**

- **Record 1 MUST NOT occur before the witness genesis commit.**
  `APPEND_RECORD_1_REPLICA_A` has source state `WITNESS_GENESIS_COMMITTED`,
  and the machine is linear (`BY_SOURCE`).
- **First Memory MUST NOT occur before FULL_READINESS** plus fresh A1–A7 and
  owner acceptance of those proofs. `first_memory_gate` requires
  `FULL_READINESS`, freshness `CURRENT`, `a1_a7_accepted`, and
  `owner_accepted_proofs`, and the most it ever returns is
  `FIRST_MEMORY_REVIEW_ELIGIBLE`, never an authorization.

## 6. Owner replica policy (D6 / P3-3)

- **Replica A** (laptop, WSL2 ext4) is reachable by local agent and root
  tooling. It is **not** the agent-unreachable copy.
- **Replica B** (S25, Termux private storage) is the independent copy. Its
  routine agent write path was NOT OBSERVED while it stays disconnected:
  no ADB, no SSH, no automation, one manual transport.

**Decision.** This posture satisfies the D6 / P3-3 policy for **entering**
PR-1B. PR-3 §25.5 requires, before record 1, that at least one of these
holds: Replica B, offline, is the agent-unreachable copy; or access to A is
otherwise separated. The first holds, as NOT OBSERVED. Replica A's custody
separation is therefore **not a blocker**.

It holds only under these conditions, and this review does not claim them
beyond that:

1. **B remains disconnected** except for owner-attended transport. Any
   ADB, SSH, backup, or sync path to B voids `replicasAgentUnreachableCopy`.
2. **The owner confirms record 1 on B from B's own re-derivation.** The
   tool on the phone re-derives the candidate from the transported chain
   and pin. The owner confirms the digest shown on the phone, never a
   digest displayed only on the agent-reachable laptop (§7, assumption 1).
3. **A alone can never establish `CURRENT`** (`minimum_replicas=2`,
   identity rule). An agent able to write A can only cause divergence,
   which is `REPLICAS_DIVERGENT` → `FRESHNESS_UNKNOWN`, fail closed. That
   is an availability risk, not a forgery path, as long as condition 2
   holds.
4. Known single-device limitations stay open: laptop VSS / restore points
   (A only), Termux `allowBackup` / Google app-data categories (B only),
   and a simultaneous compromise of both devices.

## 7. Critical hidden-assumption review

> **What assumption could make this design appear correct while it is
> wrong?**

**Answer.** It is the assumption that **"owner-side" means
agent-independent.**

These owner-side steps all run on the same workstation where agent tooling
runs as the user and as WSL root:

- K-ROOT generation (M-B1, `root-keygen`);
- registry signing (M-B3);
- the RR-38 reproduction;
- the genesis-candidate digest;
- the pin;
- the record-1 proposal;
- Replica A.

If that workstation or its agent is wrong or compromised, the "owner" and
the "host operator" become one principal. Only Replica B and the owner's
own eyes on B stay outside it. Every check here, including this review,
would still pass, because each verifies that artifacts are well formed and
ordered, not who controlled their creation. The design is correct only if
the owner's confirmations are made from independent evidence (§6 condition
2) and K-ROOT custody is decided (B-4).

**Other traps reviewed.**

| Trap | Why it is false here | Guard |
| --- | --- | --- |
| service separation = persistence separation | Signer, witness, ledger, custody, host key, and K-ACT are separate services and accounts, but all live on `sda1` of one disk (PR-2) | PR-2 matrix; OR-1 open |
| crypto separation = rollback separation | K-ACT, K-WIT, and K-ROOT are distinct keys, yet a disk restore rolls back every host-side one together, with valid signatures | PR-2 §9; owner freshness after record 1 |
| signature validity = freshness | a K-ROOT or K-WIT signature authenticates an old registry or chain equally well; it does not order | freshness register; `CURRENT` required for gated operations |
| empty replicas = CURRENT freshness | two empty replicas are `KNOWN_EMPTY` / `FRESHNESS_UNKNOWN`, never `CURRENT` | `minimum_replicas=2`; `FRESHNESS_UNKNOWN` fails closed |
| broker preservation = authority | preservation proves one broker process and its artifacts are unchanged. `authorityCustodyJudgment=NOT_PERFORMED` | output fields; P1A-9 and DR-5 are separate |
| PR-2 inventory = rollback resistance | PR-2 shows no restore artifact exists today, not that none can exist or be detected | OR-1, OR-3, OR-8 |
| signed artifact = effective authority | a signed registry is authority only at the witnessed head, after genesis, and only while `CURRENT` | `SIGNED_REGISTRY != EFFECTIVE_CURRENT_REGISTRY` (P3-5) |
| witness execution = owner acceptance | witness genesis creates a lineage; only record 1 on both replicas plus the envelope is owner acceptance, and HELD comes after it | P3-5 / P3-6 order |
| eligibility = authorization | the reviewed gate needs `pr1bAuthorized`; an eligibility review authorizes nothing | §1 |
| stale code status = current policy | `REAL_ACCEPTANCE_BLOCK_REASON` still says `P3_3_STORAGE_INCOMPLETE`, and the runbook still says "not usable for real acceptance yet", although P3-3 is complete. The block is still **effective** | B-3 |

## 8. Decision: `PR1B_NOT_ELIGIBLE`

**Exact blockers.** Each needs an owner decision or a reviewed change. None
is performed here.

| # | Blocker | Needed |
| --- | --- | --- |
| B-1 | `PR3_TOOLING_NOT_ACCEPTED`: no owner acceptance of the PR-3 source and tooling (P3-2 CLI, P3-3A publisher, P3-6 envelope, P3-5 sequencer) exists. P3-3 acceptance §7 lists it as unmet | an explicit owner acceptance record, naming the reviewed commit |
| B-2 | `OPEN_RISKS_NOT_ACKNOWLEDGED`: OR-1..OR-4, OR-7, OR-8, DR-3, and cross-environment `osAdminLogin` are proposed as ACCEPTABLE_PRECONDITION_DEBT (§4) but not acknowledged | an explicit owner acknowledgement of §4, DEV_SYNTHETIC scope |
| B-3 | **Source-level acceptance block still in place.** `owner_acceptance.REAL_ACCEPTANCE_ENABLED = False` refuses every real-profile record and envelope append. The P3-4 `RealStateGuard` still models the incomplete state, and the owner ceremony runbook is still marked "not usable for real acceptance yet". Entering PR-1B now would reach `COMMIT_WITNESS_GENESIS` (a PONR lineage point) and then be unable to append record 1 or the envelope | a separate reviewed source and documentation change lifting the block. P3-3 acceptance §7 says this change comes "immediately before a record-1 ceremony is authorized", and it must land **before M-B1**, not mid-sequence |
| B-4 | **K-ROOT custody is undecided.** `root-keygen` writes the passphrase-encrypted K-ROOT to a path on the owner workstation. No record decides where K-ROOT lives, how it is kept out of agent reach, or how its fingerprint is recorded off-host (M-B1 evidence `kRootFingerprintRecordedOffHost`). Every PR-3 / P3-5 record lists "K-ROOT custody" as a nonclaim; T-10 covers only backup | an owner K-ROOT custody decision before M-B1. The same applies to the location of the two off-host M-B8 pin copies |
| B-5 | `PR1B_NOT_AUTHORIZED` | the owner's explicit PR-1B authorization, given only after B-1..B-4, at P1B-0, with PR-2 revalidated immediately before |

**Not blockers:** preconditions A–R (§3), the Replica A posture (§6), and
every open risk once acknowledged (§4).

## 9. Nonclaims

This review does **not**:

- authorize PR-1B, A1–A7, or First Memory;
- create or authorize K-ROOT, K-WIT, a registry, a ledger, witness state, a
  hold, a RecoveryEpoch, INITIAL_CUSTODY, a real record 1, or an acceptance
  envelope;
- change any source constant or guard;
- establish rollback resistance or owner freshness. Real freshness remains
  `FRESHNESS_UNKNOWN`;
- claim anything about the owner devices beyond the P3-3 record.

## Explicitly not done

```text
NO K-ROOT
NO K-WIT
NO REGISTRY
NO LEDGER
NO WITNESS STATE
NO INITIAL_CUSTODY
NO REAL RECORD 1
NO ACCEPTANCE ENVELOPE
NO OWNER REPLICA CONTACT
NO DEV MUTATION BY THIS REVIEW
REAL FRESHNESS REMAINS UNKNOWN
PR-1B EXECUTION NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```

> **Later current state (2026-10-05, pointer only; this 2026-09-29
> classification is preserved as written and was true at its date).** The
> blockers were later closed, and the canonical evaluator returned
> `PR1B_ELIGIBLE` in
> [eligibility sequence 3](slice-15b2b-b1b3e-pr1b-eligibility-sequence3.md).
> PR-1B execution (M-B1 onward) and First Memory remain NOT AUTHORIZED.
