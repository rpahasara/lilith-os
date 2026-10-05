# Substrate Drift and Evidence Revalidation Policy v0.1

Status:

- **Accepted** (owner acceptance, 2026-10-05). This is the companion
  operational policy to
  [ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md)
  (Accepted, 2026-10-05). It is the controlling operational governance record
  for:
  - global invalidators G-1 … G-9;
  - evidence dependency classes;
  - materiality and revalidation rules;
  - the portability matrix;
  - restart, reboot, package and kernel handling;
  - Condition 3 currentness;
  - B-5 ordering;
  - `CHECK_ELIGIBILITY` current-evidence governance;
  - REVALIDATE semantics.

  Together with ADR-0015 it resolves the substrate-drift policy that the D-4
  owner records left OPEN (ledger D-4, AUTH-02, §13.1n).
- **Governance acceptance only.** It authorizes no live action and none of the
  §10 follow-ups. The §11 owner decisions stay open.
- **Documentation only.** No live system was contacted, and nothing was
  observed, mutated or re-pinned.
- **Operational posture is unchanged:**
  - B-5 WITHHELD;
  - `FRESHNESS=UNKNOWN`;
  - Condition 3 historical closure only, not satisfied today;
  - M-B1 NOT AUTHORIZED;
  - First Memory NOT AUTHORIZED.

```text
policy accepted != evidence current != Condition 3 satisfied != B-5 granted != eligible != M-B1 authorized
```

The tables below are **operational policy**, not architecture law. They apply
ADR-0015 SD-1 … SD-14 to the evidence classes recorded in this repository.
Owner-accepted policy changes may revise them within those principles.

## 1. Definitions

| Term | Meaning here |
| --- | --- |
| **Time validity** | Whether evidence is inside its accepted chronological validity window. Each gate defines its own window. This policy sets no universal duration. |
| **Substrate equivalence** | Whether the substrate dimensions relevant to the evidence are materially equivalent to its evidence-bound baseline. |
| **Evidence currentness** | Whether the evidence may support a present gate or decision. It requires time validity, substrate equivalence and no fired stop or revalidation rule. Not current = **REVALIDATE**. |
| **Control state** | PASS, FAIL or UNKNOWN of the underlying control itself. |
| **Material drift** | A change in a dimension that can affect the property the evidence proves, or any accepted global invalidator (ADR-0015 SD-3). |
| **Relevant dependency set** | The substrate dimensions the evidence's property depends on (§3). |
| **Re-establishment** | The accepted procedure that makes a class of evidence current again: recollect, compare, owner-accept where required, re-pin where required. |
| **Owner `FRESHNESS`** | Unchanged: the `owner_freshness` witness / owner-register classification. Not time validity, substrate equivalence or currentness. |

```text
UNKNOWN drift relevance -> evidence not reusable (REVALIDATE)
REVALIDATE != FAIL
not currently proven != proven false
```

## 2. Global invalidators (Layer 1)

Each entry is already a broad stop or gate in the repository. When one is
detected, every evidence item in the "Affects" column becomes **NOT REUSABLE /
REVALIDATE** until re-established. That does not by itself show a control
failed.

| # | Global invalidator | Affects | Repository basis |
| --- | --- | --- | --- |
| G-1 | Host identity replacement or mismatch (hostname, FQDN, machine-id, instance name or ID) | All host-bound evidence | `HOST_MISMATCH` in `scripts/verify_broker_dev_current_incarnation.py`; observer host identity; B-5 packet §9 "any cloud or host topology change" |
| G-2 | Unreviewed rollback-domain or topology change: snapshot, instant snapshot, image, clone, disk attach / detach / change, resource policy, backup / Backup and DR relationship, bucket | PR-2 rollback inventory; Condition 3; everything that relies on the rollback conclusions | B-5 packet §9; [P3-5](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §13; [open-risk acknowledgement](slice-15b2b-b1b3e-open-risk-acknowledgement.md) OR-8 |
| G-3 | IAM or service-account policy change relevant to the trusted boundary | PR-2 inventory; Condition 3; B-5 grant | B-5 packet §9 ("… or IAM"); PR-2 IAM inventory |
| G-4 | Authority material, trust root, or reviewed verifier / sequencer / owner-freshness tool change, where existing stop conditions apply | Authority-state evidence (P1A-9, activation); eligibility; B-5 grant | B-5 packet §9 (real authority material before M-B1; unreviewed tool or sequencer change) |
| G-5 | Change to burned identities, `REAL_ACCEPTANCE_ENABLED`, or authority state covered by existing stop conditions | Eligibility; B-5 grant; M-B1 package checks | B-5 packet §9; [B-3](slice-15b2b-b1b3e-b3-real-acceptance.md); [burned identities](slice-15b2b-b1b3e-burned-identities-expansion.md) |
| G-6 | Replica continuity violation (either replica not empty or not byte-continuous), or a nested Replica B | Replica custody; `ownerRegisterKnownEmpty`; eligibility; B-5 grant | B-5 packet §9; [P3-3 erratum](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md) |
| G-7 | Unreviewed bundle, or a bundle not from a merged SHA, affecting the trusted boundary | M-B1 package evidence (Conditions 1 and 5); B-5 grant | B-5 packet §9; [M-B1 final pins](slice-15b2b-b1b3e-mb1-final-package-pins.md) |
| G-8 | Unexplained broker start or process replacement, where an existing ceremony treats it as STOP | Broker preservation; any window that includes it | [Reboot-rebaseline](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline.md) F-14 and F-18; [DR-1](slice15b2b-dr1-broker-restart-forensics.md) |
| G-9 | Compromise or loss of a custody device or storage: phone, Termux private storage, laptop compromise or rollback; ADB, SSH or automation access to Termux | Custody evidence; B-5 grant; M-B1 | B-5 packet §9 |

**Not global invalidators under this policy:** network-exposure change and
clock-trust failure. The repository does not establish either as a broad stop.
ADR-0009 marks network exposure REVALIDATE, and no clock-trust mechanism
exists. Adding them is a separate owner decision (§11).

A global invalidator may also void an owner grant under that grant's own
record (B-5 packet §9). This policy neither adds to nor weakens those stop
conditions.

## 3. Evidence dependency table (Layer 2)

Each evidence class is listed with its relevant dependencies, as the existing
records bind them. Drift outside these sets is Layer 3 for that class, unless
a global invalidator applies.

| Evidence class | Property it proves | Relevant dependencies | Bound by |
| --- | --- | --- | --- |
| **Broker preservation** | The running broker is the owner-accepted incarnation, on the accepted release, config, sandbox and runtime substrate | Host identity; boot ID; InvocationID, PID, start ticks, `NRestarts`; release SHA and manifest; mapped-library bytes and inodes (none deleted); unit, socket and tmpfiles files; broker config; state DB hashes; directories; accounts and IPC group; process uid/gid, NoNewPrivs and capabilities; sandbox and environment; owner socket; Stage III artifacts and controller state; deployer sudoers and helper | `ACCEPTED_CURRENT_*`, `baselineCandidate` digest, `_broker_checks` |
| **Observer stable baseline** | Host and authority facts are unchanged from an accepted observation | Host (hostname, machine-id, boot ID, kernel, OS release, swaps, reboot-required, localtime); releases; hostFiles; units; accounts; currentBlob; hostKey; listings; pr1Objects; filesystems; namespace inventory | `stableSha256`, `sectionSha256` (`observe_authority_dev_host.py`) |
| **P1A-9 status** | Exact authority installation state | Authority release and manifest; installed objects; units; boot (P3-5: "valid until a reboot") | `install_authority_dev.py status --expect P1A-9` |
| **DR-5** | The routine deployer cannot reach authority or broker resources | Deployer sudoers text and helper digest; latest deployment and its boundary result set; boot (the ceremony forbids reusing a pre-reboot DR-5) | Result-set digests vs accepted run `36552218231` ([Condition 2](slice-15b2b-b1b3e-condition2-dev-deploy-boundary.md)) |
| **Activation** | Activation is dark (`GRANT_ABSENT`) | Authority files and units | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| **PR-2 rollback inventory** | The rollback domain and its conclusions are as accepted | Cloud topology (instance, disks, snapshots, images, resource policies, backupdr, buckets); IAM; whole-life compute Admin Activity; storage probe and custody-path placement; TPM binding | [PR-2](slice-15b2b-b1b3e-pr2-snapshot-inventory.md) and revalidation records |
| **Broker-mapped package risk** | No pending upgrade can change the broker's mapped set before the gate window ends | The mapped package set; package-list timestamps; `apt-daily` and `apt-daily-upgrade` schedules; holds; package-manager state | [Condition 3 PASS](slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md) §4 |
| **Replica custody** | The owner replicas are empty and byte-continuous, at canonical paths | Replica manifests; record counts; entries; inodes; mtime; canonical paths (no nested Replica B) | Replica A `fbdd045c…`; Replica B `c068e533…` |
| **M-B1 package (Conditions 1 and 5)** | The exact reviewed bundle and script from merged `main` | Bundle and script digests; source commit; burned-identity set | [M-B1 final pins](slice-15b2b-b1b3e-mb1-final-package-pins.md) |
| **Condition 3 window** | Composite: PR-2 materially equivalent immediately before eligibility | The union of all the above that the window includes, plus its own time window | [Condition 3 PASS](slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md) |

**Dependency notes:**

- Repository control SHA and tool digests are provenance. They are
  dependencies only where accepted evidence binds them. An example is the
  reviewed tool blobs used to collect a window: a tool change makes that
  window's method unreviewed, not its subject drifted.
- Process `exe` is recorded by the broker verifier but not compared. Whether
  it becomes a check is follow-up work (§10).

## 4. Materiality by change type

| Change | Material to | Not material by itself to |
| --- | --- | --- |
| Upgrade of a broker-mapped package or library | Broker preservation; broker-mapped package risk | PR-2 inventory; replica custody; DR-5 |
| Upgrade of a package the broker does not map | Nothing in §3 by default. The observer if it changes an observed file. | Broker preservation |
| Pending unrelated updates | Nothing by default | Broker preservation (pending ≠ installed ≠ mapped) |
| Kernel package installed, no reboot | The observer only if an observed fact changes (for example `rebootRequired`) | Running-kernel evidence. Installed kernel ≠ running kernel. Existing reboot gates still apply. |
| Reboot (new boot ID, possibly new kernel) | Broker preservation; observer `host`, `units` and runtime sections; P1A-9; DR-5 | PR-2 cloud inventory; replica custody; M-B1 package |
| Same-boot broker restart | Broker preservation; observer `units` | P1A-9; DR-5 (unless the ceremony is in a no-restart mode, F-18); PR-2 inventory; replicas |
| Broker binary, release, unit or config change | Broker preservation; observer; DR-5 where the deployment touches it | Replica custody |
| Authority release, CURRENT blob or attestation change | P1A-9; observer; activation; G-4 where it applies | Broker preservation |
| Routine Core API deployment with DR-5 equal to the accepted set | A new DR-5 must be collected and compared | Broker preservation; PR-2 inventory; replicas. The precedent is "not a topology change". |
| Docs-only repository commit | Nothing | All §3 classes |
| Frontend-only change outside every dependency set | Nothing | All §3 classes |
| Cloud topology or IAM change | G-2 or G-3 (global) | — |
| Replica content or path change | G-6 (global) | — |

**Repository-supported non-material examples.** Each applies only within the
scope where it was demonstrated. None is a universal exemption.

- Docs-only commits: [PR-1A acceptance](slice-15b2b-b1b3e-pr1a-acceptance.md);
  [pre-B-5 revalidation](slice-15b2b-b1b3e-pr2-pre-b5-revalidation.md).
- Unrelated frontend changes outside the dependency sets.
- Unmapped package updates: `libheif*`, `libxpm4`, the `snapd` refresh
  ([Condition 3 STOP](slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md) §2).
- Timer schedules, cron directory mtimes and `/var/backups` apt rotation,
  accepted as volatile (pre-B-5 revalidation).
- The `/run/lilith-dev-deploy.lock` file, under its reviewed `stat` check
  (`scripts/compare_reboot_host_observations.py`).
- The `snapd` loop device and user tmpfs sessions in `lsblk` / mounts
  (Condition 3 records).
- Observer `utcNow` and `uptimeSeconds` (volatile by design).
- Kernel package installed without switching the running kernel, subject to
  existing reboot gates ([reboot-rebaseline acceptance](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline-acceptance.md)
  RB-2).

This policy does **not** require whole-host immutability.

## 5. Portability and revalidation matrix (operational)

**Status values:**

| Status | Meaning |
| --- | --- |
| PORTABLE | The change does not, by itself, affect the evidence |
| PORTABLE_IF_REBOUND | Survives only after a reviewed comparison shows the change is limited to an accepted allowed-difference set |
| AFFECTED_ONLY | Only the affected part or section must be revalidated |
| MUST_RECOLLECT | The evidence must be collected again and, where required, re-accepted |
| UNKNOWN | Drift may be undetectable. The evidence is not reusable while the condition is suspected or known. |

| Evidence | Process restart | Reboot | Package update | Config change | Binary change | Routine deploy | VM replacement | Snapshot restore | Docs-only repo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Broker preservation | MUST_RECOLLECT | MUST_RECOLLECT | AFFECTED_ONLY (mapped set → MUST_RECOLLECT; unmapped → PORTABLE) | MUST_RECOLLECT | MUST_RECOLLECT | PORTABLE (if DR-5 equal) | MUST_RECOLLECT | UNKNOWN | PORTABLE |
| Observer stable baseline | PORTABLE_IF_REBOUND (`units` only) | PORTABLE_IF_REBOUND (reboot allowed-diff set) | PORTABLE unless an observed fact changes | AFFECTED_ONLY | AFFECTED_ONLY | PORTABLE_IF_REBOUND (deploy-lock exception) | MUST_RECOLLECT | UNKNOWN | PORTABLE |
| P1A-9 | PORTABLE | MUST_RECOLLECT | PORTABLE | AFFECTED_ONLY | AFFECTED_ONLY | PORTABLE | MUST_RECOLLECT | UNKNOWN | PORTABLE |
| DR-5 | PORTABLE | MUST_RECOLLECT | PORTABLE | AFFECTED_ONLY | AFFECTED_ONLY | MUST_RECOLLECT (then compare with the accepted set) | MUST_RECOLLECT | UNKNOWN | PORTABLE |
| PR-2 rollback inventory | PORTABLE | PORTABLE | PORTABLE | PORTABLE | PORTABLE | PORTABLE | MUST_RECOLLECT | MUST_RECOLLECT if known; UNKNOWN if undetected | PORTABLE |
| Replica custody | PORTABLE | PORTABLE | PORTABLE | PORTABLE | PORTABLE | PORTABLE | PORTABLE (owner-side) | UNKNOWN | PORTABLE |
| Condition 3 window | MUST_RECOLLECT | MUST_RECOLLECT | MUST_RECOLLECT if mapped; else AFFECTED_ONLY | MUST_RECOLLECT | MUST_RECOLLECT | PORTABLE (if DR-5 equal) | MUST_RECOLLECT | MUST_RECOLLECT if known; UNKNOWN if undetected | PORTABLE |

**Two caveats apply to every cell:**

1. **Time validity is independent and may override portability.** A PORTABLE
   cell says only that the change does not invalidate the evidence. The
   evidence must still be inside its own accepted window (OR-8; P3-5 §13).
2. **Snapshot restore stays accepted debt.** Where a restore is undetected,
   evidence can look equivalent. Cells marked UNKNOWN record that limit; they
   do not mark it solved (AUTH-05).

**Note on Condition 3 under a restart.** The cell is MUST_RECOLLECT because
that was the accepted practice (STOP → recovery → re-pin → new window).
Whether a controlled restart may later need only broker preservation to be
re-established, without a full new PR-2 window, is a separate owner decision
(§11).

## 6. Re-establishment rules (existing procedures, unchanged)

| Evidence | Re-establishment |
| --- | --- |
| Broker preservation after a replacement | Read-only candidate (`rebaseline` after a reboot; same-boot restarts currently use a manual `canonical_sha256` computation), then owner acceptance in a new record, then a reviewed re-pin of `ACCEPTED_CURRENT_*`, then routine DR-5, then live `preservation` PASS. The prior incarnation joins `RETIRED_BROKER_BASELINES`. |
| P1A-9 after a reboot | `status --expect P1A-9` in the new boot |
| DR-5 | A new run after the boot or deployment, with its result sets equal to the accepted run |
| PR-2 / Condition 3 | A new read-only window with the accepted scope, compared with the last accepted baseline |
| Replica custody | A read-only check against the recorded manifest, inodes and mtime. Replica B only in a deliberate, authorized ceremony step. |

Historical records are never edited. Each re-establishment is a new record.

## 7. Condition 3 handling

- **Historical closure is not current satisfaction.** Current Condition 3
  satisfaction is **NOT ESTABLISHED**
  ([C-04 disposition](slice-15b2b-b1b3e-condition3-c04-owner-disposition.md)).
- Condition 3 is a composite window (ADR-0015 SD-11). If any required item is
  not current, Condition 3 cannot be claimed. Its other components are not
  thereby shown failed.
- A future Condition 3 window must:
  - bind to the then-current accepted or revalidated broker incarnation and
    the other §3 baselines;
  - record its time-validity origin and window (the gate's own window; the
    2026-10-02 next-unattended-upgrade limit is historical, not a rule);
  - check the broker-mapped package risk;
  - feed eligibility only while every component is current.
- No PASS is declared here.

## 8. B-5 handling

Current state: **B-5 WITHHELD**
([re-decision](slice-15b2b-b1b3e-b5-pr1b-authorization-withheld.md)).

Recognized order (ADR-0015 SD-13):

```text
substrate-drift policy accepted
  -> fresh evidence package / B-5 packet prerequisites (packet §1 inputs, M-B1 conditions)
  -> new explicit owner B-5 decision
  -> required fresh revalidation immediately before eligibility (P3-5 §13; packet §11)
  -> CHECK_ELIGIBILITY (P1B-0)
  -> separate M-B1 go statement
  -> M-B1
```

- Acceptance of this policy grants none of these steps.
- The B-5 packet §9 stop conditions remain controlling for any grant. A §9
  trigger voids the grant as that record says. This does not mean every drift
  event shows every control failed. This policy does not weaken §9.

## 9. CHECK_ELIGIBILITY governance precondition

`evaluate_eligibility` accepts plain booleans. Until structured evidence is
implemented, these rules bind whoever prepares its inputs:

1. An evidence-backed precondition may be supplied as `True` only when it is
   supported by evidence that is **current** under §1. That means inside its
   time-validity window, substrate-equivalent for its §3 dependencies, with no
   §2 invalidator or stop rule fired since collection.
2. A stale or historical PASS is never converted into a current `True`.
3. Where currentness cannot be shown, the input is not `True`. Today that
   gives `PR2_REVALIDATION_REQUIRED` or the precondition's own reason.
4. `pr1bAuthorized` is an owner assertion, not evidence. While B-5 is WITHHELD
   it may not be `True`.

The preconditions this concerns most directly are `pr2InventoryRevalidated`,
`noUnreviewedTopologyChange`, `pr1aBaselineValid`, `ownerRegisterKnownEmpty`
and the replica preconditions.

No code changes here. No eligibility evaluation is run or authorized.

## 10. Implementation and evidence-contract follow-ups (not authorized here)

| # | Follow-up |
| --- | --- |
| F-1 | Explicit dependency manifests per evidence class (ADR-0015 SD-7) |
| F-2 | Structured evidence passed into eligibility instead of plain booleans |
| F-3 | Same-boot restart-rebaseline tooling. `rebaseline` assumes a reboot, and the 2026-10-02 candidate was computed by hand ([recovery](slice-15b2b-b1b3e-broker-restart-recovery.md)). |
| F-4 | Hash-type labeling of tool digests: git blob SHA vs file SHA. The STOP and pre-B-5 records give different values for the same tools. Not normalized here. |
| F-5 | Decide whether a process `exe` mismatch becomes a broker-verifier check |
| F-6 | Represent the validity-window origin and clock source in evidence records |
| F-7 | An optional aggregate evidence-package ID, as an index only, never a trust primitive (ADR-0015 SD-14) |

## 11. Separate owner decisions (outside this policy's acceptance)

- Package holds on the broker-mapped set vs scheduling gate windows
  immediately after a re-baseline.
- Any apt timer change.
- needrestart posture.
- Exact validity-window durations per gate.
- Whether a controlled restart can avoid a full PR-2 window.
- Whether network exposure becomes a global invalidator.
- Clock-trust policy.

## 12. Unresolved items carried, not closed

- AUTH-05: whole-host rollback resistance NOT ESTABLISHED.
- Independently persisted freshness state: NONE.
- C-15, C-16, EPI-08, REC-06, REC-15 and COMP-G: unchanged.
- G1 and G2: OPEN.
- Owner `FRESHNESS`: UNKNOWN. Its semantics are unchanged.

## Explicitly not done

```text
POLICY STATUS: ACCEPTED (2026-10-05; GOVERNANCE ONLY)
SUBSTRATE-DRIFT POLICY RESOLVED BY ADR-0015 + THIS POLICY
SEPARATE OWNER DECISIONS (§11) OPEN
FOLLOW-UPS F-1 … F-7 NOT AUTHORIZED
B-5 WITHHELD
FRESHNESS=UNKNOWN
CONDITION 3 HISTORICAL CLOSURE ONLY; CURRENT SATISFACTION NOT ESTABLISHED
NO CHECK_ELIGIBILITY RUN
M-B1 NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
NO K-ROOT / K-WIT
NO LIVE SYSTEM CONTACTED (DEV_SYNTHETIC, REPLICA B, PROD)
NO PACKAGE HOLD, APT TIMER OR NEEDRESTART CHANGE
NO RESTART, REBOOT OR RE-PIN
NO CODE, SCHEMA, RUNTIME OR SERVICE CHANGE
NO HISTORICAL RECORD EDITED
```
