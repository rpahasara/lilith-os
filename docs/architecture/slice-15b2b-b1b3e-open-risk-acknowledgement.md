# Slice 15B2b-B1b-3e — Owner Acknowledgement of Open DEV_SYNTHETIC Risks (PR-1B blocker B-2)

Status:

- **ACKNOWLEDGED** by explicit owner statement (2026-09-29), for **DEV_SYNTHETIC only**
- Closes PR-1B blocker **B-2** (`openRisksAcknowledged`) of the
  [PR-1B eligibility review](slice-15b2b-b1b3e-pr1b-eligibility-review.md)
- `LIVE_MUTATION = NONE`; no DEV contact; no owner-replica contact
- **PR-1B remains `PR1B_NOT_ELIGIBLE`**: B-3, B-4, B-5 open

```text
acknowledgement != mitigation != closure != rollback resistance
acknowledgement != freshness CURRENT != PR-1B authorization
DEV_SYNTHETIC acknowledgement != PROD acknowledgement
```

## 1. Owner statement (verbatim)

> I explicitly acknowledge, for LILITH DEV_SYNTHETIC only, the following open risks as ACCEPTABLE_PRECONDITION_DEBT for entering PR-1B: OR-1 (whole-disk / whole-host rollback can present a self-consistent old authority world), OR-2 / DR-3 (root-equivalent principals and host-local copies remain possible), the cross-environment PROD-deployer osAdminLogin root-equivalent reach, OR-3 (cloud principals retain capability to create future snapshots, images, or clones), OR-4 (DEV consumes no independent external freshness; owner-side freshness is the intended detector only after record 1 exists), OR-7 (/tmp and /var/tmp remain on the boot disk; current reviewed use is transient and not key custody), and OR-8 (future snapshot or image activity can stale PR-2).
> OR-9 is a visibility-scope limitation only and is not an accepted risk. OR-5 and OR-6 are closed and are not part of this acknowledgement.
> This acknowledgement is not mitigation, is not rollback resistance, does not make owner freshness CURRENT, and does not authorize PR-1B execution. It does not apply to PROD. Fresh PR-2 revalidation remains mandatory wherever it is already required, including immediately before CHECK_ELIGIBILITY and GENERATE_K_WIT. Owner freshness does not protect against simultaneous rollback or compromise of both owner replicas.
> This acknowledgement becomes void if any stated staleness condition occurs, and it satisfies PR-1B precondition openRisksAcknowledged only.

## 2. Acknowledged items

Every item stays **OPEN**. Sources:

- [PR-2 inventory](slice-15b2b-b1b3e-pr2-snapshot-inventory.md);
- [PR-2 revalidation](slice-15b2b-b1b3e-pr2-revalidation.md);
- [B1c acceptance](slice-15b2b-b1c-acceptance-record.md);
- the PR-3 records;
- the [PR-1B eligibility review](slice-15b2b-b1b3e-pr1b-eligibility-review.md) §4.

| Item | Concrete risk | Why not blocking (DEV_SYNTHETIC) | Compensating guard | Void / stale if | Carries to PROD |
| --- | --- | --- | --- | --- | --- |
| **OR-1** | CURRENT (K-ACT), the host key, and every future K-WIT, registry, ledger, witness, hold, and RecoveryEpoch object share `sda1` on the single 20 GB boot disk. A disk restore presents an old, self-consistent, validly signed authority world, undetectable on the host | Before record 1, a rollback only returns DEV to an earlier synthetic state. After record 1, owner-side freshness is the designed detector | Every gated operation requires AUTHENTIC + `CURRENT` (PR3-D11). Detection happens only when a gated operation is attempted; operations outside the gated set are not checked | a DEV snapshot, image, clone, or restore exists or has occurred; a second disk is added; authority material moves to another persistence domain | **No** |
| **OR-2 / DR-3** | `ubuntu` is root-equivalent (`sudo`, `lxd`). A root-equivalent principal can copy the encrypted blobs and the host key with ordinary file operations. That is invisible to cloud logs, and no inventory can exclude it | The keys are DEV_SYNTHETIC; this debt was carried through the accepted PR-1A | `ubuntu` password locked and `authorized_keys` empty; DR-5 routine-deployer denials; K-WIT and K-ACT distinct; K-ROOT intended off-host (custody: B-4) | a new root-equivalent principal, key, or sudo rule; non-empty `authorized_keys`; any evidence of copying | **No** |
| **Cross-environment `osAdminLogin`** | The PROD deployer holds project-level `osAdminLogin`, so it has root (`NOPASSWD: ALL`) on DEV | Known debt accepted at B1c; it reaches only synthetic material | The B1c federation proof; routine DEV runs use their own constrained deployer | its IAM scope widens; it is used against DEV; the PROD/DEV separation changes | **No** (this is itself a PROD-side debt) |
| **OR-3** | The owner user, the default compute SA (`roles/editor`), and the compute service agent can snapshot, image, or clone the DEV disk. It is Google-managed encryption with no revocable operator key | No such artifact exists or has ever existed (full Admin Activity history) | Mandatory PR-2 revalidation immediately before `CHECK_ELIGIBILITY` and before `GENERATE_K_WIT` (P3-5 §13). Any change gives `PR2_REVALIDATION_REQUIRED` | any snapshot, image, machine image, backup, or clone appears; IAM changes; Backup and DR is enabled | **No** |
| **OR-4** | DEV consumes no independent external freshness. Before record 1 nothing tells DEV it is current | The accepted design: freshness is judged owner-side (PR-3), and is meaningful only after record 1 exists on both replicas | `FRESHNESS_UNKNOWN` fails closed; record 1 only after the witness genesis commit; two identical replicas required | the design lets DEV self-certify; a replica is lost, synced, co-backed-up, or made agent-reachable (B especially); the two-replica rule is weakened | **No** |
| **OR-7** | Anything written to `/tmp` or `/var/tmp` (including service `PrivateTmp`) lands in the rollback and snapshot domain | Credentials load into `/run/credentials` (tmpfs). The only reviewed `/tmp` use is the root forensic ledger read (`ledger._on_copy`): a transient `0600` ledger copy, removed afterwards. That is authority state, not key custody | code review; any retained copy falls under OR-2 | any key, credential, or witness material is written to disk-backed temporary storage; `/tmp` handling changes | **No** |
| **OR-8** | The PR-2 inventory is point-in-time (valid as of about `10:10Z`, 2026-09-29) | Controlled procedurally | the same mandatory revalidations as OR-3 | any cloud or topology change, or time passing before the next PR-1B step (the inventory is then void) | **No** |

**Limit recorded with OR-4.** Owner freshness does **not** protect against
simultaneous rollback or compromise of both owner replicas.

**Not acknowledged.**

- **OR-9** is a visibility-scope limitation only, not an accepted risk.
- **OR-5** and **OR-6** are **CLOSED**
  ([reboot evidence](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline-acceptance.md)).
  They are not accepted debt.

## 3. Standing obligations

- Fresh PR-2 revalidation is mandatory wherever it is already required,
  including immediately before `CHECK_ELIGIBILITY` and `GENERATE_K_WIT`.
- If any staleness condition in §2 occurs, the acknowledgement is **void**
  for the affected item. A new review and a new explicit acknowledgement
  are then required before PR-1B continues.
- The acknowledgement applies to DEV_SYNTHETIC only. PROD needs its own
  review.

## 4. PR-1B blocker state after this acknowledgement

| # | Blocker | State |
| --- | --- | --- |
| B-1 | PR-3 tooling not accepted | **CLOSED** ([tooling acceptance](slice-15b2b-b1b3e-pr3-tooling-acceptance.md)) |
| B-2 | open risks not acknowledged | **CLOSED** by §1 |
| B-3 | source-level real-acceptance block (plus the guard and runbook text) | open. Requires a separate reviewed change before M-B1 |
| B-4 | K-ROOT custody and the M-B8 pin-copy location | open |
| B-5 | PR-1B not authorized | open |

`evaluate_eligibility` would now report only `PR1B_NOT_AUTHORIZED`. B-3 and
B-4 remain review blockers outside that function. **`PR1B_NOT_ELIGIBLE`.**

## 5. Nonclaims

This acknowledgement does **not**:

- mitigate or close any risk;
- establish rollback resistance;
- make owner freshness `CURRENT`. Real freshness remains
  `FRESHNESS_UNKNOWN`;
- change `REAL_ACCEPTANCE_ENABLED` or any source;
- create K-ROOT, K-WIT, a registry, a ledger, witness state, a hold, a
  RecoveryEpoch, INITIAL_CUSTODY, record 1, or an envelope;
- apply to PROD;
- authorize PR-1B, A1–A7, or First Memory.

## Explicitly not done

```text
NO DEV CONTACT
NO DEV MUTATION
NO OWNER REPLICA CONTACT
NO REAL RECORD 1
NO ACCEPTANCE ENVELOPE
REAL_ACCEPTANCE_ENABLED UNCHANGED (False)
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
