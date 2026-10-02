# Slice 15B2b-B1b-3e — M-B1 Condition 2: `cfa0b3e` DEV Deploy Boundary Review

Status:

- **`CONDITION_2_READY_FOR_OWNER_REVIEW`.** This record reviews the DEV
  deployment boundary results of the B-3 merge `cfa0b3e`. On owner review and
  merge it records **`CONDITION_2_DEV_DEPLOY_BOUNDARY=ACCEPTED`**.
- The criterion is the one the
  [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
  sets (§5 item 2, §11 item 2, and the §9 stop
  condition): the `cfa0b3e` DEV deployment ran, and its DR-5 result set equals
  the accepted run's. **It does.** Every later deployment also matches.
- **Evidence source:** GitHub Actions logs of the routine deployment runs,
  plus one read-only look at Replica A on the laptop. I made no DEV, PROD or
  cloud call, and no host contact. Replica B was not contacted. This is
  **not** the fresh PR-2 revalidation (Condition 3), and not eligibility
  (Condition 4).
- **Condition 1** is CLOSED
  ([finalization record](slice-15b2b-b1b3e-mb1-final-package-pins.md),
  merged at `92ab356`). **Conditions 3, 4 and 5 are OPEN. M-B1 is NOT
  AUTHORIZED.**

```text
deploy boundary reviewed != PR-2 revalidated != eligible != M-B1 authorized
```

## 1. Deployment run identity

| Item | Value |
| --- | --- |
| merge | `cfa0b3e542e821ae2d4a3bb4ba0f198ee9e6fb58` (PR #121, B-3: the real-acceptance gate) |
| CI run | `36618884689` "Repository validation" (push): success |
| **deployment run** | **`36619219267`** "Deploy LILITH Core API to DEV" (`workflow_run`), `2026-09-29T19:26:10Z`–`19:31:46Z`, **conclusion success** |
| job | "Evaluate validated protected main for DEV": success. The PR-observation and broker-candidate jobs were skipped, as on every routine run |
| mode | `MODE=DEPLOY_REQUIRED BASE_SHA=11c47dc… CANDIDATE_SHA=cfa0b3e…` |
| effective diff | docs; `owner-memory-control` source (`burned_identities.py`, `owner_acceptance.py`, `owner_freshness_tool.py`) and its tests. **No** `services/core-api`, `services/authority-dev`, `scripts` or `.github` change |
| deployed | the Core API release only. The service is `lilith-os-api-dev`, and `current=…/releases/cfa0b3e…`. Health is `ok` and the database is `true`. The service restarted (new MainPID, `NRestarts=0`) |
| payload | `services/core-api` only. No `owner-memory-control` or authority file is in the payload |

**Accepted baseline:** run `36552218231` (`c0adb70`), as accepted in the
[pre-B-5 PR-2 revalidation](slice-15b2b-b1b3e-pr2-pre-b5-revalidation.md) §2.

## 2. Boundary evidence

Each log was normalized (Actions timestamps stripped, script echo lines
excluded). Three sets were extracted:

| Set | Definition | `cfa0b3e` (`36619219267`) | Accepted (`36552218231`) |
| --- | --- | --- | --- |
| **full result set** | every output line starting with `DENIED`, `ALLOWED`, `PASS`, `OK`, `FAIL`, `HOST_PREREQ`, `DEFERRED`, `UNOBSERVABLE`, `PR1_`, `AUTHORITY_`, `ACTIVATION`, `BROKER_`, `SUDO_`, `FEDERATION`, or `UNEXPECTED`, in order | **186 lines** (158 `DENIED…`), SHA-256 `f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b` | **identical** |
| **DR-5 block** | from `DENIED: test -w /opt` to `AUTHORITY_BOUNDARY_PROOF=…` | **147 lines** (130 `DENIED`, 5 `DEFERRED_UNTIL_OBJECT_EXISTS`, 3 `DEFERRED_NOT_IN_GATE`, 5 `UNOBSERVABLE_BY_DESIGN`, 2 `HOST_PREREQ`), SHA-256 `a1d98773bcd07c39b2a17f0628f75db858a3e1e6bcd19e7bcd8918c0e79f1390` | **identical** |
| **pre-deploy deny block** | from `DENIED: sudo -n true` to `ACTIVATION=…` | **29 lines** (28 `DENIED`), SHA-256 `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | **identical** |

**Key lines (identical in both runs):**

```text
PR1_AUTHORITY_BOUNDARY maturity=P1A-9
AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3
ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=unreadable
SUDO_EFFECTIVE_PROOF=PASS user=sa_112096412008414111981 mode=self
PASS DEV_IDENTITY_MINT kind=mint-allowed http=200 token-issued
PASS LEGACY_PRIVILEGED_MINT kind=mint-denied http=403 permission-denied status=PERMISSION_DENIED reasons=IAM_PERMISSION_DENIED
PASS PROD_COMPUTE kind=prod-denied http=403 permission-denied status=- reasons=forbidden
PASS PROD_IAP kind=prod-denied http=200 granted=[]
PASS PROD_SA kind=prod-denied http=200 granted=[]
FEDERATION_BOUNDARY=PASS
```

- **There is no real `ALLOWED(unexpected)` line** and no
  `UNEXPECTED ACCEPTED-ACTIVATION STATE`. The only `ALLOWED` text is inside
  the script's own function definitions.
- The masked full-log diff against the preceding run `36617360613`
  (`11c47dc`) contains only expected per-run variation:
  - SHAs, and archive hashes that embed the candidate SHA;
  - the effective-diff list;
  - ephemeral runner credentials and SSH keys, and transfer speeds;
  - test durations, and random goal IDs from the CI tests;
  - the expected `lilith-os-api-dev` restart (new MainPID).

  The `app.py` content hash is unchanged.

**Evidence** is kept on the owner workstation, outside Git, at
`C:\Users\edufo\lilith-b1b3e-condition2\` (21 files). It holds the five full
run logs and the three extracted sets for each run. `SHA256SUMS` is
`21c1fb16dc54a6ec5e298b0c43e30ee51a83c3b287a810064f353ad5ace9b8c8`.

## 3. Later deployments (the §9 stop condition)

The B-5 packet §9 voids the grant on "a DR-5 result set other than the
accepted one after any deployment". Every DEV deployment since `cfa0b3e`
was therefore checked:

| Run | SHA | Mode | Full result set | DR-5 block |
| --- | --- | --- | --- | --- |
| `36673169614` | `c694061` (PR #122, B-5 records) | `DEPLOY_REQUIRED`, success | identical (`f1869234…`) | identical (`a1d98773…`) |
| `36985542087` | `1e2eae3` (PR #123, M-B1 source) | **skipped**: CI failed on `npm audit` (GHSA-vcvr-r3jv-pc5j); no DEV contact | — | — |
| `36989394282` | `92ab356` (PR #124, finalization) | `DEPLOY_REQUIRED`, success | identical (`f1869234…`) | identical (`a1d98773…`) |

**Observation (not a blocker).** The `92ab356` run evaluated its effective
diff against `BASE_SHA=1e2eae3`, a SHA that was never deployed. So the
`1e2eae3` changes appear in no run's effective-diff list:
- the M-B1 builder, `burned_identities.py` (19 → 20), tests, and docs;
- none of them is in the Core API payload.

The payload is built from the full candidate tree, and the mode was
`DEPLOY_REQUIRED` either way, so DEV ended on the exact `92ab356` release.
Whether the evaluator should diff against the last *deployed* SHA is a
separate question for the deploy tooling.

## 4. The "156 result lines / 154 DENIED" figure

The pre-B-5 revalidation and the B-5 packet describe the accepted set as
"156 result lines, including 154 `DENIED` lines". **I could not reproduce
that count** from the run logs under any extraction rule I tried:
- the DR-5 block: 147 lines, 130 `DENIED`;
- the pre-deploy block: 29 lines, 28 `DENIED`;
- the full result set: 186 lines, 158 `DENIED…`;
- raw `grep` counts: 161–164.

Neither record defines its rule. **This does not affect the decision.** The
criterion is equality with the accepted run, and all three sets are
byte-identical to run `36552218231`, which is the run those records
accepted. From now on, this record's rules and digests (§2) are the
reproducible definition.

## 5. Review items

| # | Item | Result | Source |
| --- | --- | --- | --- |
| 1 | exact run | `36619219267`, `cfa0b3e` | §1 |
| 2 | completed successfully | **yes**: success, health `ok` | §1 |
| 3 | authority observer | DR-5 `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`, identical. The root-run observer `stableSha256` is not part of a routine deploy; it was last `c4a65403…` (pre-B-5 revalidation) | §2 |
| 4 | P1A-9 boundary | **`PR1_AUTHORITY_BOUNDARY maturity=P1A-9`**, identical | §2 |
| 5 | broker preservation | **not re-observed by a deploy, by design**: the verifier is root-run. The deployer is DENIED write access to every broker path, and DENIED `systemctl restart lilith-memory-broker.service`; only `lilith-os-api-dev` restarted. Last observed `BROKER_PRESERVATION=PASS` (pre-B-5 revalidation, `18:56Z`, before this deploy). Condition 3 re-observes it | §2, §6 |
| 6 | activation | **`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`**, identical | §2 |
| 7 | unexpected authority material | **none observable**. The same 5 `DEFERRED_UNTIL_OBJECT_EXISTS` lines, so the authority-dev credential, the witness credential, and the witness state directory still do not exist. The same 5 `UNOBSERVABLE_BY_DESIGN` lines | §2 |
| 8 | services that must stay inactive | **none started**. The only unit restarted was `lilith-os-api-dev`. Every authority-dev unit action (start, stop, restart, reload, enable, …) is DENIED to the deployer, identically | §2 |
| 9 | filesystem ownership / permission boundary | **no relaxation observable**: all 130 DR-5 and 28 pre-deploy write/read/sudo probes are DENIED, identically. A root-level permission audit is the observer's job (Condition 3) | §2 |
| 10 | cloud / host topology, IAM | **IAM behavior identical**: federation PASS, DEV mint allowed, legacy privileged mint denied, PROD compute / IAP / SA denied. Cloud topology (disks, snapshots, images, buckets) is not observed by a deploy. Its last state is the pre-B-5 revalidation, and Condition 3 re-observes it | §2 |
| 11 | matches accepted boundary evidence | **yes**: all three sets are byte-identical to `36552218231`, and so is every later deploy | §2, §3 |
| 12 | difference from "156 lines" | the count is not reproducible; the content is identical | §4 |

## 6. Authority state

| Statement | Holds? | Basis |
| --- | --- | --- |
| authority boundary remains P1A-9 | **yes** | §2 (latest deploy `92ab356` too) |
| broker preservation remains PASS | **yes, as last observed** | not re-observable by a deploy; no deploy can reach the broker (§5 item 5); re-observed in Condition 3 |
| activation dark / `NOT_ACCEPTED` / `GRANT_ABSENT` | **yes** | §2 (all deploys) |
| no real K-ROOT | **yes** | M-B1 has not run; custody is phone-only |
| no K-WIT | **yes** | witness credential still `DEFERRED_UNTIL_OBJECT_EXISTS` |
| no registry v1 | **yes** | nothing has run past M-B1 |
| no genesis pin | **yes** | nothing has run past M-B1 |
| no real freshness record | **yes** | Replica A has 0 records (below) |
| Replica A has 0 records | **yes** | read-only, `2026-10-02`: records `0`, entries `REPLICA.json records`, the parent holds only the replica, manifest `fbdd045c390506f8174192dbea6a6444e6f3e819c9a24e90c61155ec9238978b`, inodes `59905 / 59906 / 59907`, mtime `1790643451`. **Unchanged** from the pre-B-5 revalidation |
| freshness UNKNOWN | **yes** | there is no record 1 |

Replica B was not contacted. Its last evidence is B-4 run 2: 0 records,
manifest `c068e533…07c4`.

**WHOLE-HOST / WHOLE-DISK ROLLBACK RESISTANCE: NOT ESTABLISHED** (unchanged).

## 7. Decision

**Condition 2 can be accepted.** The `cfa0b3e` DEV deployment ran
successfully. Its DR-5 result set, its pre-deploy deny set, and its full
boundary result set are each byte-identical to the accepted run
`36552218231`. So is every later deployment. There is no unexpected
`ALLOWED`, no new authority object, no non-API unit change, and no IAM
change.

Two things are left to Condition 3, the fresh PR-2 revalidation
immediately before eligibility, and are **not** claimed here:
- live root-level observation: broker preservation, installer
  `status --expect P1A-9`, observer `stableSha256`;
- cloud topology.

```text
CONDITION_2_DEV_DEPLOY_BOUNDARY=ACCEPTED   (effective when this record is reviewed and merged)
```

## 8. Validation

- `test_b1b3e_condition2_dev_deploy_boundary.py` (5) pins this record's
  runs, digests and boundary lines. It also checks that acceptance is
  effective only on merge, that the state claims no authorization, and that
  the Condition-3 items are not claimed as observed.
- The deploy-boundary tests (WSL, Python 3.12): 92 OK, 1 skipped.
  - `test_classify_dev_deployment.py`
  - `test_deployer_authority_boundary_proof.py`
  - `test_dev_deployer_boundary.py`
  - `test_activation_authority.py`
  - `test_dev_deploy_helper_linux.py`
- The owner-memory-control suite (WSL): 729 OK, 4 git-dependent skips.
- `scripts/validate_repository.py` passes, and `git diff --check` is clean.

## 9. State

```text
CONDITION_2_READY_FOR_OWNER_REVIEW
CONDITION 1 CLOSED
CONDITION 2 OPEN UNTIL OWNER REVIEW
CONDITION 3 OPEN
CONDITION 4 OPEN
CONDITION 5 OPEN
M-B1 NOT AUTHORIZED
NO M-B1 COMMAND ISSUED
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
