# Slice 15B2b-B1b-3e — Fresh A1–A7 Crash/Replay Rehearsal Accepted (TEST-only, 2026-10-20)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records the fresh A1–A7 crash/replay design and technical rehearsal
  (TEST-only, synthetic, DEV_SYNTHETIC), the step after FULL_READINESS in
  [bootstrap sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §14. The code merged as PR #233
  (`6fbceff70801a0f2f990e6e7301dd28d86cf7a16`), its tree identical to the owner-accepted integration commit
  `ca9060a1cfe5699dcfd758fe6f7e3bfcd3bdb257`. The owner accepted it verbatim (§5). The merge deployed to DEV, and the
  post-deploy DR-5 is `EQUAL` (§6).
- `FRESH A1–A7 = COMPLETED / OWNER-ACCEPTED` (2026-10-20), within the TEST-only scope of §7. This is a fresh design. It
  is **not** a retry of the legacy Stage III A2 controller, which stays deferred and must not be retried.
- **Earlier records are unchanged.** The A1–A7 points in the
  [custody-isolation design](slice-15b2b-b1b3-custody-isolation-design.md) ("Relationship to Stage III A2") and the
  S1–S6 table in the [B1b-3b adapter record](slice-15b2b-b1b3b-broker-signing-l04-v2-adapter.md) ("Stage III
  implications") are historical design inputs. Neither is rewritten.
- **Grants no authority.** Authority stays **DARK**, issuance stays **UNWIRED** (RR-39), `authorityGranted` stays
  false, Registry V1 is **NOT EFFECTIVE**, First Memory is **NONE**, and no PROD authorization exists. RR-39 and
  `DurableAuthorityLedgerV1` are unchanged. `first_memory_gate` can now return at most `FIRST_MEMORY_REVIEW_ELIGIBLE`.
  It never returns an authorization.
- **Merging this record may itself trigger a DEV deployment.** That deployment needs its own post-merge DR-5
  verification (`EQUAL` 194 / 155 / 29, no rebaseline). It is **PENDING** and is not covered by §6.

```text
A1-A7 TEST rehearsal accepted != production L04 migration != durable broker custody != First Memory eligibility review
DR-5 EQUAL = deployment-boundary evidence only;  REVIEW_ELIGIBLE != authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| base | `72b40501108397ccfeed9fffdc887411cccdb813` (merge of PR #232, M-B15 record) |
| reviewed commit | `84973baebbe5c3da2b35703ef97ef53b3d266989` (base `627ad67`) |
| integration commits | `43087e7` (clean cherry-pick of `84973ba`) → `ca9060a1cfe5699dcfd758fe6f7e3bfcd3bdb257` (callback correction, §3) |
| merge | PR #233, `6fbceff70801a0f2f990e6e7301dd28d86cf7a16`; tree = `ca9060a` |
| changed files | 6, all under `services/`: `core-api/lilith_memory/canonical_store.py`, `core-api/tests/test_canonical_runtime.py`, `owner-memory-control/lilith_authority_signer/synthetic_evidence_ledger.py`, `owner-memory-control/lilith_owner_memory/l04_v2_adapter.py`, `owner-memory-control/tests/synthetic_b1b3b.py`, `owner-memory-control/tests/test_fresh_a1_a7_restart.py` |

## 2. Design

Owner decision "Link in L04 txn": the admission ↔ authority link is written inside the L04 commit transaction, and the
authority-side evidence reservation and confirmation are durable in the TEST components.

- **Link inside the L04 commit.** `CanonicalMemoryStoreV2.apply(in_transaction=...)` runs a callback on the same
  connection after every L04 write and before the commit. `L04AdmissionLinkStoreV1` writes the link and its archived
  chain (including the verified challenge record) there. A committed admission always has its link; an uncommitted one
  never does. The table is created by the TEST harness, outside the L04 runtime schema objects.
- **Durable evidence use (TEST).** `SyntheticEvidenceUseLedgerV1` takes an optional injected write-ahead journal: it is
  rebuilt from the journal and writes each transition before applying it. The signer package stays free of I/O. The
  journal is an authority-side file, never inside the L04 database.
- **A7 reconciliation.** `L04V2AdmissionAdapter.reconcile` re-verifies the archived owner proof and signed evidence,
  then confirms a still-RESERVED use against exactly the committed admission and link. It never re-applies, reserves or
  reissues, and any mismatch fails closed.

## 3. Correction made during verification

The callback first ran under the full L04 authorizer, so a caller could write any memory table inside a committed
admission, contrary to `apply`'s "no caller-controlled authority inputs". In `ca9060a`, the only write permitted while
the callback runs is an INSERT into `memory_admission_authority_link`, which is not in `_MEMORY_TABLES`. A core-api test
requires SQLite `not authorized` for each other write and a full rollback; against the unfixed store it fails all 7
checks. A test for reconciliation after a recovery-epoch advance was also added
([B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md) §15).

## 4. Rehearsal results

Each crash point is followed by a simulated restart (§7): every authority and adapter component is rebuilt over the
persisted files.

| Point | Result |
| --- | --- |
| A1 prepared, never answered | consume refused `CHALLENGE_UNKNOWN`; nothing written |
| A2 consumed, no evidence | issue refused; the owner proof is burned |
| A5 signed, response lost | never reissued (fail closed; the owner re-authorizes) |
| A3/A4 reserved, nothing applied | replay refused `EVIDENCE_ALREADY_CONSUMED / EVIDENCE_ALREADY_RESERVED`; stays RESERVED |
| A6 before the L04 commit (`after_revision`, `before_commit`, failed link write) | no admission and no link; stays RESERVED; replay refused |
| A7 committed and linked, confirmation lost | not accepted until `reconcile`, then `ACCEPTED_MEMORY`; idempotent; never re-applies |
| A7 fully confirmed | `ACCEPTED_MEMORY` after restart |
| A7 after a recovery-epoch advance | `reconcile` refused `AUTHORITY_EVIDENCE_REJECTED / REGISTRY_EPOCH_MISMATCH`; stays RESERVED |
| any point, repeated replay | never a second memory commit |

| Suite at `ca9060a` | Result |
| --- | --- |
| fresh A1–A7 rehearsal | 15 / 15 OK |
| B1b-3b signing and hardening | 70 / 70 OK |
| core-api | 71 / 71 OK, 0 skipped |
| full owner-memory-control, Linux, `git archive` (CI-equivalent) | 2,024 run, OK, 16 skipped (environment-gated: 8 need a non-root uid, 1 needs `LILITH_MB3_EXPORT`, 7 need git history) |
| full owner-memory-control, Linux, with git history | 3 failures, the same 3 as on unmodified main (below) |
| repository validator; `git diff --check` | passed; clean |

The three history-dependent failures pre-date this work and are not in its diff: M-B1 / M-B3 package-pin tests
(`test_b1b3e_mb1_finalization`, `test_b1b3e_mb3_final_package_pins`, `test_b1b3e_mb3_replacement_final_package_pins`)
assert that `pr1_acceptance.py` is unchanged since their control commits, and it changed later (the E-19 defect fix).

## 5. Owner acceptance

**Historical proposed text (not the binding acceptance).** This is the statement proposed for owner review, quoted
byte-exact from `ACCEPT-PROPOSED-DRAFT.txt` (SHA-256 `6f9f443e218a9ad6ea3ddc75a5e593a6ff97e1bd77f35df6f59676c388ed617e`),
including its original DRAFT header. The owner's decision below accepts within "the TEST-only synthetic scope
documented in the proposed acceptance statement"; that decision, not this text, is the acceptance.

> DRAFT FOR OWNER REVIEW - NOT AN ACCEPTANCE.
> I accept the fresh A1-A7 crash/replay design and rehearsal (TEST-only, synthetic) for DEV_SYNTHETIC at integration commit ca9060a1cfe5699dcfd758fe6f7e3bfcd3bdb257 (main 72b40501108397ccfeed9fffdc887411cccdb813 plus reviewed commit 84973baebbe5c3da2b35703ef97ef53b3d266989 and the in_transaction authorizer correction).
> A1, A2 and A5 fail closed; A3/A4 reserved evidence is single-use across restart; the A6 pre-commit boundary leaves neither admission nor link; A7 recovers ACCEPTED_MEMORY after a durable commit and restart only through reconciliation, which never re-applies and refuses after a recovery-epoch advance; no crash point or replay produces a second memory commit.
> Restart is simulated in-process from persisted files, with TEST link and evidence-journal stand-ins; there is no broker re-delivery and no durable owner acknowledgement.
> This acceptance authorizes nothing further: not a merge or deploy, authority activation, issuance, Registry V1 effectiveness, First Memory or PROD.

**Binding owner acceptance (verbatim, 2026-10-20, `OWNER-MESSAGE.txt`, SHA-256
`5266ab84d7ba3336d9c440091c94e719f3f56712300bfdff9a85b6a6d1871a81`):**

> I accept the fresh A1–A7 crash/replay design and technical rehearsal for DEV_SYNTHETIC, strictly within the TEST-only synthetic scope documented in the proposed acceptance statement for integration commit `ca9060a1cfe5699dcfd758fe6f7e3bfcd3bdb257`.
>
> This acceptance covers the reported A1–A7 verification evidence, including the 15 passing rehearsal tests, the 2,024 passing Linux regression tests with 16 skips, the documented pre-existing history-dependent failures, and the explicitly stated limitations.
>
> I acknowledge that this does not establish production L04 migration, durable broker challenge handling, real OS power-loss recovery or whole-host rollback protection.
>
> Record this acceptance verbatim against the verified evidence and preserve the original acceptance statement and evidence hashes.
>
> This decision does not authorize a GitHub push or merge, DEV deployment, authority activation, issuance, Registry V1 effectiveness, First Memory or PROD. Any such action requires separate authorization.

The exact regression figure is 2,024 tests run, all OK, 16 of them skipped (§4); the acceptance record states it.
This acceptance did not itself authorize the later push, PR, merge or deployment. Each step after it:

| Step (2026-10-20) | Authorization and record |
| --- | --- |
| push of `review/a1-a7-integration` at `ca9060a` | separate owner authorization (branch only, no PR, because of the Actions budget); pushed without force; no Actions run was triggered |
| PR #233 opened (13:53:04Z) and merged (14:22:17Z) | both by the owner account `rpahasara` (GitHub record). The authorizations were given outside this record's evidence and are not reproduced here |
| DEV run `39438974835` attempt 2 | a re-run of only the protected DEV job, as reported by the owner; the legacy run was not rerun |
| legacy `deploy.yml` disabled (15:01:55Z) | separate owner authorization; `gh workflow disable`; GitHub API state `disabled_manually` (§6) |

| Item | Value |
| --- | --- |
| acceptance record | `A17_ACCEPTANCE.json` `283b3c41f527b912f7b152d9093103317b3641b9a80322e9a1ac5f77ca998a62` (`verbatim` true, `authorityGranted` false, `issuanceWired` false) |
| acceptance seal | `SHA256SUMS` `8bdcbb51842e4044d5ec172e48bf1ca6ab5ab67c0532db23a3f4ecb84440403c` (statement, owner message, record, references) |
| review packet seal | `4f47bd2c19db886e821ef690e60572bd3cf62b8bc0475bd6244dd87e5564cf0f` (summary, proposed statement, 12 test transcripts) |

## 6. DEV deployment and DR-5

| Item | Value |
| --- | --- |
| deploy run | `39438974835` "Deploy LILITH Core API to DEV", attempt 2 success (14:37:51Z – 14:41:24Z); attempt 1 was cancelled at the read-only custody-reach proof, before any deploy step; `MODE=DEPLOY_REQUIRED`, `BASE_SHA` `72b4050` |
| target | `lilith-dev-01` RUNNING; release `…/releases/6fbceff70801a0f2f990e6e7301dd28d86cf7a16`; `candidateSha` `6fbceff…`; bundle `12565857024c4c49ff18d3fd4981379034a43f4d3f9dc9f41b4d59074017c3d5`; deployed `canonical_store.py` `da151b43…` = the merged blob |
| health and boundary | health `ok`, `database` true, `NRestarts` 0; `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` (PR1 `P1A-9`); `FEDERATION_BOUNDARY=PASS` (PROD compute, IAP and SA denied) |
| run log | attempt-2 log 430,326 B, SHA-256 `4422e29d6c406091b2bb906e68bf7731a03a0f94ee5277a30e64f052a281abf0` |
| E-08 artifact | `authority-boundary.txt` `7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c` = the pinned transcript |
| **DR-5** | `e22_dr5_target compare` against the unchanged E-22 target (workdir seal-11 `6e3570be…` verified): **`EQUAL`** 194 / 155 / 29 (`a0ebd54d…` / `7fe21378…` / `f5087042…`); `unequal []`, `allowed 0`, `fail 0`, no old-release lines; output `c9ba3e9898e6c1c4669fdcd17fc6ab9836feddfc60c0c990611bec93c468ad0d`, byte-identical to the accepted comparison; reproduced independently from a fresh log and fresh tools; no rebaseline |

The deploy's standard synthetic durability probe wrote and removed its own synthetic DEV fact (`CLEANUP_COMPLETE`).
That is not First Memory. DR-5 cannot read the hold store, so `EQUAL` is deployment-boundary evidence only.

**Legacy production workflow (incident).** The same merge also triggered the legacy `.github/workflows/deploy.yml`
(run `39438607377`, push to `main` on the `services/core-api/**` path).

- **Cancelled before deployment.** It authenticated as the legacy deployer and was cancelled during "Upload deployment
  candidate". Its deployment step ("Deploy with production validation, health check, and rollback") and its final
  verification step were skipped, so the remote install-and-restart script never ran. It was not rerun.
- **Possible temporary leftovers, unverified.** A partial `/tmp/lilith-app-6fbceff….py` on the legacy VM, and the
  runner's ephemeral SSH key in instance or project metadata or OS Login. Neither was checked (no PROD contact).
- **Disabled manually.** Owner-authorized on 2026-10-20 (15:01:55Z); GitHub API state `disabled_manually`. This is a
  repository setting and can be re-enabled.
- **Durable fix outstanding.** The `push` trigger is unchanged in the repository. It must be removed, or the workflow
  retired, before any future core-api merge.

## 7. Limitations and nonclaims

- **TEST components only.** The durable link table is a harness stand-in for a reviewed L04 migration. The
  evidence-use journal is a TEST file with one live ledger per journal. Production custody (B1b-3c / B1b-3d) is not
  built.
- **In-process restart.** Restart is simulated in one OS process from persisted files. There is no OS-kill,
  power-loss or fsync testing.
- **Not provided; these fail closed and the owner re-authorizes:** a durable broker challenge ledger and an atomic
  consume + sign + record transaction; re-delivery of issued evidence (A5); durable acknowledgement to the owner (only
  the authority-side confirmation is rehearsed).
- RESERVED evidence after A3/A4/A6 is never reusable, and there is no cleanup path.
- Whole-host rollback stays undetected ([B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md) §16). Cross-epoch
  reconciliation is refused, not implemented.
- No DEV mutation beyond the routine deploy, and no S25 or PROD contact. No authority activation, issuance wiring,
  Registry V1 effectiveness or First Memory.

## 8. Off-host evidence

The evidence folders are identified by name. They live in the owner's private evidence root, outside Git.

| Evidence folder | Contents | Seal |
| --- | --- | --- |
| `lilith-a17-review-ca9060a` | technical summary, proposed statement, 12 test transcripts | `SHA256SUMS` `4f47bd2c…cf0f` |
| `lilith-a17-accept-ca9060a` | proposed-statement copy, owner message, `A17_ACCEPTANCE.json`, references | `SHA256SUMS` `8bdcbb51…403c` |
| `lilith-a17-postdeploy-6fbceff` | control clone `ctl/` (not sealed), attempt-2 log, E-08 artifact, DR-5 comparison; independent re-verification | `SHA256SUMS` `295e9522294d2b0c5a7d383b1aee9fd488532db3790a3c0e5113be63e7611048`; `SHA256SUMS.seal-2-reverify` `afe30f1d764e3e9baa02a51133e8e2d92b1f24336eb307ff21aea9e4d35d5b46` |

## 9. State

```text
M-B15 = COMPLETED / OWNER-ACCEPTED 2026-10-20 (FULL_READINESS READY)
FRESH A1-A7 = COMPLETED / OWNER-ACCEPTED 2026-10-20 (TEST-only; merge 6fbceff; DR-5 EQUAL 194 / 155 / 29)
CUSTODY = RELEASED;  AUTHORITY = DARK;  ISSUANCE = UNWIRED (RR-39);  REGISTRY V1 = NOT EFFECTIVE
FIRST MEMORY = NONE (at most REVIEW_ELIGIBLE; no authorization);  PROD = NOT AUTHORIZED
legacy deploy.yml = disabled_manually; push trigger still in the repository; durable fix OUTSTANDING; PROD leftovers UNVERIFIED
this record's merge may deploy to DEV: its own post-merge DR-5 = PENDING (must be EQUAL 194 / 155 / 29; no rebaseline)
```
