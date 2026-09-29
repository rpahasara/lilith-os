# Slice 15B2b-B1b-3e PR-3 P3-3: Real Owner Storage Acceptance

**Status: `P3_3_COMPLETE`. TWO INDEPENDENT OWNER REPLICA STORAGE DOMAINS
ESTABLISHED.**

- Both real replicas are **empty**; the accepted freshness record count is
  **0**.
- There is no record 1 and no acceptance envelope. Real freshness remains
  **`FRESHNESS_UNKNOWN`**.
- There was no DEV contact, no cloud contact, and no PR-1B activity. This
  review was read-only, plus documentation.

```text
P3-3 completion != freshness CURRENT
P3-3 completion != owner acceptance
P3-3 completion != PR-1B completion (or eligibility)
```

| Field | Value |
| --- | --- |
| Closes | the P3-3 storage foundation ([PR-3 record §25](slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md)); the Replica B ceremony ([P3-3B](slice-15b2b-b1b3e-pr3-p33b-replica-b-ceremony.md)); the backend admission ([P3-3A](slice-15b2b-b1b3e-pr3-android-replica-publication.md)) |
| Replica A recheck | 2026-09-29 `04:10:40Z`, read-only, laptop, tool from merged `main` `44a53f2` |
| Replica B evidence | owner-supplied after the P3-3B ceremony (the phone was not contacted by this review) |

## 1. Replica A: laptop (read-only recheck)

| Check | Result |
| --- | --- |
| exists | yes |
| `verify-replica` (strict) | `REPLICA_VERIFIED` |
| replica ID | `owner-primary-dev-synthetic-01` (exact) |
| environment / profile | `dev` / `DEV_SYNTHETIC` (exact, from the manifest) |
| records / head | `0` / `null` |
| entries | exactly `REPLICA.json` and `records/`; the parent holds only the replica |
| `records/` | empty |
| manifest | `REPLICA.json` SHA-256 `fbdd045c390506f8174192dbea6a6444e6f3e819c9a24e90c61155ec9238978b`, unchanged since P3-3 |
| permissions | parent `0700`, replica `0700`, `REPLICA.json` `0600`, `records/` `0700`; the same inodes as at P3-3, so the replica is unchanged |
| filesystem | ext4 (WSL2 distribution virtual disk, internal NVMe) |
| Git / auto-sync | no `.git` in any ancestor; `location-check`: not a Git working tree, not a known auto-sync root |
| Windows bridge | WSL automount disabled; interop disabled |
| mutation | **none** |

**Storage class:** the owner workstation, a WSL2 ext4 virtual disk on the
internal SSD.

**Capability (P3-3):** `P3_STORAGE_CAPABLE`, with strict directory fsync.
Its admitted backend is `RENAME_NOREPLACE_V1` under P3-3A (hard link also
passes there).

## 2. Replica B: S25 Ultra (owner-supplied evidence)

| Item | Owner-reported result |
| --- | --- |
| initialization | real `init-real-replica` via the P3-3B bundle (merged `main` `44a53f2`) → Replica B created empty |
| strict verify | PASS |
| replica ID | `owner-offline-dev-synthetic-01` |
| environment / profile | `dev` / `DEV_SYNTHETIC` |
| records / head | `0`; null head (0 records) |
| manifest | `REPLICA.json` SHA-256 `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4`, equal to the P3-3B expected manifest |
| entries | strict verify PASS, which refuses anything but `REPLICA.json` plus an empty-or-valid `records/` |
| capability | `directory_fsync=PASS`, `hardlink=UNAVAILABLE`, `rename_noreplace=PASS`; admitted backend **`RENAME_NOREPLACE_V1`** |
| location | Termux app-private storage only; not visible in ordinary shared storage |
| transport | the tar was removed from Download |
| permissions | **not restated** in the supplied summary. The ceremony's `evidence/stat.txt` (expected `700 / 700 / 600 / 700`) is to be retained with the private evidence (PV-2). Not needed for the rollback-independence question |

**Storage class:** a separate physical Android device, in app-private
storage (f2fs/ext4 under the Android app sandbox).

## 3. Distinct devices and rollback independence

**Distinct-device proof:**

- two different replica IDs (`owner-primary-…` vs `owner-offline-…`);
- two different manifest digests (`fbdd045c…` vs `c068e533…`);
- two physically separate machines: a laptop internal SSD and a phone's
  internal flash;
- Replica B was created by a ceremony run on the phone while Replica A
  stayed untouched on the laptop.

> **Can one ordinary rollback operation restore both Replica A and Replica B together?**

**NO.** Replica A lives in the laptop's WSL virtual disk, and Replica B in
the S25's app-private storage. No shared automatic backup or sync path has
been observed:

- the laptop's WSL disk is outside OneDrive, and File History is not
  configured;
- the phone's Google "Other device data" backup is OFF and Samsung
  automatic backup is OFF;
- Smart Switch was not used;
- no cable or network sync is configured.

A rollback on either device affects only its own replica. The other
replica then reveals it as divergence, `REPLICAS_DIVERGENT` →
`FRESHNESS_UNKNOWN`, which fails closed.

**Limitations (not solved):**

1. simultaneous compromise or rollback of **both** devices;
2. the owner later copying one replica into a shared backup (for example a
   Smart Switch PC archive stored with a laptop backup);
3. future backup or sync configuration changes on either device, which
   would make this conclusion stale;
4. full device or root compromise of either device;
5. Windows restore points / VSS on the laptop (UNKNOWN; P3-3 §25.3). They
   can affect Replica A alone, never B;
6. Google app-data backup categories other than "Other device data", and
   Termux's own `allowBackup` setting (UNKNOWN). They could affect B alone,
   never A;
7. a restore of the phone from a pre-ceremony archive would remove B
   rather than roll it back. That yields `REPLICA_MISSING`, which also
   fails closed.

## 4. Agent boundary

- **Replica A** is reachable by local agent and root tooling on the office
  laptop (the WSL root that agents use). It is **not** the agent-unreachable
  copy.
- **Replica B** is intended as the agent-unreachable independent copy.
  Observed: the phone is disconnected except for the one manual MTP
  transport, Developer options are OFF (so no ADB), Termux `sshd` is not
  running, and no remote service is intentionally enabled.

**Routine agent write path to Replica B: NOT OBSERVED.** This is not a
claim that compromise is impossible. It holds only while the phone stays
disconnected, with no ADB, no SSH, and no automation access to Termux.

## 5. Backup / sync posture

| Point | Status |
| --- | --- |
| Google "Other device data" backup (phone) | OFF (observed) |
| Samsung automatic backup (phone) | OFF (observed) |
| Smart Switch used for this ceremony | NO |
| transport copy in shared Download | removed |
| known auto-sync path shared with Replica A | none observed |
| Replica A under OneDrive / auto-sync / Git | no (`location-check`; the VHDX is outside OneDrive) |
| laptop File History | not configured (P3-3) |
| laptop restore points / VSS | UNKNOWN |
| Google app-data backup beyond "Other device data"; Termux `allowBackup` | UNKNOWN |
| any existing PC-side archive of the phone | UNKNOWN (none used; any pre-ceremony archive cannot contain Replica B) |

The UNKNOWN items each concern a single device and are recorded as
limitations (§3). None of them is a shared path.

## 6. Two-replica policy

| Requirement | Result |
| --- | --- |
| two distinct replica IDs | yes |
| two distinct physical devices | yes |
| both strict-verified | yes (A: this recheck; B: owner evidence) |
| both empty | yes (0 records each) |
| record 1 in either | no |
| divergence possible now | no: both are empty. The register state is `OWNER_REGISTER_EMPTY`, which is the P3-5 `KNOWN_EMPTY` once both are read together at ceremony time |
| real freshness | **`FRESHNESS_UNKNOWN`** until the record-1 ceremony |

## 7. What P3-3 completion does and does not change

**It satisfies:**

- the P3-5 precondition `p33Complete`;
- `twoRealReplicasExist`, `replicasCapabilityAdmitted`, and
  `replicaIndependenceEstablished`;
- `replicasAgentUnreachableCopy`, as NOT OBSERVED for the phone.

The other PR-1B preconditions remain unmet:

- PR-3 tooling acceptance;
- the PR-1A baseline (reboot pending);
- PR-2 revalidation;
- open-risk acknowledgement;
- **PR-1B authorization**.

So **PR-1B remains `PR1B_NOT_ELIGIBLE`.**

The source-level block `owner_acceptance.REAL_ACCEPTANCE_ENABLED = False`
(reason `P3_3_STORAGE_INCOMPLETE`) and the P3-4 real-state guard **stay in
place**. Lifting them is a separate, reviewed source change, made
immediately before a record-1 ceremony is authorized. This documentation
record does not do it. Until then, any real-profile `append` or
`append-envelope` refuses.

## 8. Nonclaims

P3-3 completion does **not** establish any of the following:

- real freshness, or any owner record, envelope, or acceptance;
- record 1;
- K-ROOT, K-WIT, registry, ledger, witness genesis or state, hold,
  RecoveryEpoch, or INITIAL_CUSTODY;
- PR-1B eligibility or completion;
- A1–A7;
- First Memory readiness;
- protection against simultaneous compromise of both devices, or against
  future backup reconfiguration;
- whole-host rollback resistance for DEV (PR-2).

```text
P3-3 COMPLETION REVIEW ONLY   NO REAL RECORD 1   NO ACCEPTANCE ENVELOPE   REAL FRESHNESS REMAINS UNKNOWN
NO DEV CONTACT   NO CLOUD CONTACT   NO K-WIT   NO REGISTRY   NO LEDGER   NO WITNESS STATE   NO INITIAL_CUSTODY
PR-1B NOT AUTHORIZED   FIRST MEMORY NOT AUTHORIZED
```
