# Slice 15B2b-B1b-3e — M-B12 Completion Record and M-B13 Preparation

Status:

- **REPOSITORY RECORD.** `LIVE_MUTATION = NONE`, `CUSTODY = HELD`, `AUTHORITY = DARK`. Base: main
  `31e5a2825ec26ce53830cb7e4b2825d92653b664` (PR #224).
- **M-B12 = COMPLETED** (owner-accepted verification milestone, §1).
- **M-B13 = PREPARED, NOT ACCEPTED.** This record does not accept M-B13.
- **M-B14** (the forward-only HELD → RELEASED operation, `release-initial`) is **not prepared, run or authorized
  here.**

```text
M-B12 READY (verification) != M-B13 owner acceptance != M-B14 RELEASED != authority
```

## 1. M-B12: completed verification milestone

**Owner decision (verbatim, 2026-10-19):**

> The reported M-B12 READY result is accepted as the completed M-B12 verification milestone, bound to package digest:
> eab79d56e58f0d7ce88217c43acdba1d31dec30743d79245dca6a893b49a1a86

| Item | Value |
| --- | --- |
| package digest (`HOLD_RELEASE_ELIGIBILITY`) | `eab79d56e58f0d7ce88217c43acdba1d31dec30743d79245dca6a893b49a1a86` |
| status / reasons | `READY` / `[]`. 23 checks PASS; `E22_SECRET_HYGIENE` = `OWNER_RISK_ADJUDICATED` (OD-M12-10, `9528f733…`) |
| flags | `authorityGranted`, `activationGranted`, `issuanceWired` = false; scope `PR1_INITIAL_CUSTODY`, environment `dev` |
| evaluation | one read-only `e22_operator package` (control `31e5a28`, deploy `39203335226`), signer `efbc0784…` / 128648 bound before and after HEALTH |
| envelope | `3128a0a857cae8a0121c2febf97f2e6e0e9a3f0e92f9fa6bec843dba13c875fb` (`mb12_readiness_inputs`, `expectedNotReady` empty) |
| DR-5 | EQUAL (194 / 155 / 29) on deploys `39197801754`, `39200840403` and `39203335226` |
| evidence | `C:\Users\edufo\lilith-mb12-digest-31e5a28\` (`SHA256SUMS` `2f48c3c3…`); inputs `lilith-mb12-package-d4655f1`, `lilith-e22-mb12-b1f30c2`; transition `lilith-e22-v0-04a0cdd` |

**Why E-22 was upgraded.** The E-19 release judge could only return PASS or FAIL for SECRET_HYGIENE. The journal
scan FAILs on 12 historical markers from the 2026-09-27 L2b period, so the package could never be READY. OD-M12-10
accepted a narrow owner-risk adjudication for that exact failure set, and the `d3df4cfc…` judge carries it. Installing
that judge required the one-member release transition E-22, V0 … V7:

- the replacement witness `8cbfbed2…` / 127192 and signer `efbc0784…` / 128648 were owner-accepted;
- the K-ACT load count is 2;
- the OD-M12-11 windows were recorded;
- the post-V7 reads show exactly the 12 historical markers and no new one.

The adjudication is never a clean scan.

## 2. M-B13 preparation

M-B13 is the owner acceptance of the exact package digest (preflight §27 row M-B13; sequencing step 15). It needs the
off-host reproduction (RR-38 B) and the E-25 … E-28 owner-side bindings. OD-M11-13 (accepted 2026-10-13) binds those
to the PR-1 package digest at M-B13, with no release-verifier extension.

### 2.1 RR-38 B: owner off-host reproduction

Run off-host in WSL, with no DEV contact. The tool is `mb12_pr3_material.offhost_reproduction` at `31e5a28`, over:

- the DEV package (`package/remote.out` of the M-B12 evidence);
- the PR-3 material that `package_input` re-derives from the owner-retained inputs and the re-confirmation
  `c01db2f5…`.

| Check | Result |
| --- | --- |
| mismatches (genesis pin, registry head, K-WIT, K-ACT publication, release, manifest, bound register, dark flags) | none: **REPRODUCED** |
| independently recomputed package digest (`pr1_acceptance.package_digest`) | `eab79d56…`, equal to the reported one |
| E-18 | PASS |

Evidence: `C:\Users\edufo\lilith-mb13-prep-31e5a28\rr38b\` (`rr38b-result.json`).

### 2.2 E-25 … E-28 (owner-side bindings)

| # | Required evidence | Binding | State |
| --- | --- | --- | --- |
| E-25 | owner freshness at package time: `AUTHENTIC` + `CURRENT`, register head digest, latest accepted record version | needs a **current** classification: Replica A (WSL), a current read-only Replica B observation (S25), and a current witness chain export | **PENDING (owner S25 act)** |
| E-26 | record 1 bytes and digest; `compare-replicas` verified | record 1 `77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6`, version 1, on Replicas A and B (`REPLICAS_IDENTICAL`), Package C C2 / C3 | bound (Package C completion, owner-accepted C5) |
| E-27 | P3-3 storage and independence | `P3_3_COMPLETE`. Replica A `REPLICA.json` `fbdd045c390506f8174192dbea6a6444e6f3e819c9a24e90c61155ec9238978b` (WSL); Replica B `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4` (S25, `$HOME/lilith-owner-offline-dev-synthetic-01`). Two independent devices (record `slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md`) | bound (accepted) |
| E-28 | record-1 acceptance envelope digest and `ACCEPTANCE_COMPLETE` | envelope 1 `95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c` on copies A and B, `ACCEPTANCE_COMPLETE` (Package C C4A / C4B) | bound (owner-accepted C5) |

E-25 is the only open binding. Package C's C5 gate classified freshness from a proven Replica B peer view on
2026-10-10. A package-time classification needs a fresh one, which needs the owner's read-only S25 step.

### 2.3 Draft M-B13 owner acceptance text (NOT issued, NOT accepted)

Issued only after E-25 is bound. It is shown here so the owner can review it:

> I accept M-B13 for DEV_SYNTHETIC: the PR-1 package with digest
> eab79d56e58f0d7ce88217c43acdba1d31dec30743d79245dca6a893b49a1a86 (HOLD_RELEASE_ELIGIBILITY READY), reproduced
> off-host (RR-38 B), with E-25 … E-28 bound as recorded. This is acceptance only: it does not release custody, run
> release-initial, activate authority, make Registry V1 effective, or authorize First Memory or PROD.

**Validity.** M-B14 refuses unless a current re-run of the package gives exactly this digest (RR-38). The package
binds live host evidence: the signer and witness incarnations, CURRENT, the hold, the release and the ledger. Any
restart, redeploy that changes them, or credential event before M-B14 invalidates the digest and needs a new M-B12 run.

## 3. State

```text
M-B12 = COMPLETED (owner-accepted 2026-10-19, digest eab79d56…a1a86)
RR-38 B = REPRODUCED;  E-26 / E-27 / E-28 = BOUND (accepted records);  E-25 = PENDING (owner S25 read)
M-B13 = PREPARED, NOT ACCEPTED;  M-B14 = NOT AUTHORIZED;  CUSTODY = HELD;  AUTHORITY = DARK;  FIRST MEMORY = NONE
```
