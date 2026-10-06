# Slice 15B2b-B1b-3e — M-B2 / GENERATE_K_WIT Preflight (Repository-Only)

Status:

- **Current: `READY_FOR_OWNER_MB2_DECISION`**, after the
  [M-B2 PR-2 continuity owner decision](slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md)
  resolved every gap in §4. This means only that the owner can now decide
  whether to authorize one M-B2 sequence. **It authorizes nothing.**
- **Pre-decision classification (history): `NOT_READY_FOR_OWNER_MB2_DECISION`.**
  The analysis below was produced on control `cd417be` before the continuity
  decision. It was delivered as a review report and is recorded here
  unchanged in substance.
- Repository-only inspection. No GitHub, DEV, GCP, S25 or replica contact.
  No DR-5, PR-2, CHECK_ELIGIBILITY, K-WIT, K-ROOT, registry / genesis,
  record 1 or First Memory action.
- **M-B2 / `GENERATE_K_WIT` is NOT AUTHORIZED.** M-B3, registry / genesis,
  record 1, First Memory and PROD are NOT AUTHORIZED. `FRESHNESS=UNKNOWN`.

```text
ready for owner decision != M-B2 sequence authorized != M-B2 go != K-WIT generated
```

| Field | Value |
| --- | --- |
| Control `main` | `cd417be472bebfb65d70d096ebc4e3e7a20eb5ea` (merge of PR #150, the M-B1 completion record) |
| Preceding accepted state | [M-B1 / `GENERATE_K_ROOT` COMPLETED / ACCEPTED](slice-15b2b-b1b3e-mb1-kroot-completion.md); E-21 `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf` |

## 1. Question

What are the exact accepted prerequisites and execution boundary of
M-B2 / `GENERATE_K_WIT`, given that a fresh PR-2 immediately before it is
mandatory and the M-B1 Condition 3 evidence does not carry forward?

## 2. Facts established from the repository

1. **What M-B2 is.** P3-5 step 2
   ([sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3;
   `pr1b_sequencing.STEPS`): `GENERATE_K_WIT`, `K_ROOT_GENERATED →
   K_WIT_CUSTODIED`, mutation M-B2, gate `REQUIRED_UNKNOWN_BLOCK`, point of
   no return `CUSTODY`. Required evidence: `pr2RevalidatedImmediatelyBefore`,
   `kWitPublicationCaptured`, `kWitFingerprintRecordedOffHost`,
   `secretScansClean`, `currentKActUnchanged`, `kWitDistinctFromKActAndKRoot`.
2. **Where it runs.** On `lilith-dev-01`, as root:
   `lilith-authority-keygen-dev witness` (closed form, no arguments;
   `lilith_authority_keygen_dev.py`). It refuses a non-root user, a
   non-isolated interpreter and any other hostname. It is not run on the S25
   or on the laptop. The keygen docstring: run by the owner, as root, inside a
   separately authorized ceremony step.
3. **What it writes.** One Ed25519 key, keyId
   `test-only.witness.dev-synthetic.b1b3d.1`, encrypted
   `systemd-creds encrypt --with-key=host --name=recovery-witness-signing-key`,
   written `O_EXCL` as one `root:root 0600` blob at
   `/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred`
   (RR-36). It prints only `LILITH_WITNESS_KEY_PUBLICATION`. It is one-time:
   a non-empty `credentials/` directory is `WITNESS_CREDENTIAL_ALREADY_PRESENT`.
   Its preflight requires the K-ACT credstore to hold exactly CURRENT and
   proves CURRENT unchanged before and after the write.
4. **K-ROOT is not consumed.** No K-ROOT private operation occurs in M-B2.
   The first K-ROOT signature is M-B3 (registry v1). Only the public E-21
   fingerprint is a comparison input. The K-ROOT passphrase is not needed;
   it may be entered only on the S25 (B-5 decision §7).
5. **Owner register gate.** `REQUIRED_UNKNOWN_BLOCK` requires the owner
   register to be `KNOWN_EMPTY` (`owner_register_state`): fresh reads of
   Replica A and an owner-run read of Replica B.
6. **PR-2 scope** is P3-5 §13: snapshots and instant snapshots, machine and
   custom images, resource policies and schedules, Backup and DR, the disk
   list / attachment / replication, Admin Activity since the last accepted
   window, and the owner freshness storage topology. Any change is
   `PR2_REVALIDATION_REQUIRED`, which means `PR1B_NOT_ELIGIBLE`.
7. **DR-5.** Deployments after `11c08cf` need a fresh DR-5 comparison
   before a later step relies on them (completion record §6).
8. **Every PR-1B phase re-proves CURRENT** (live-install preflight §24, §28).
   The owner-retained K-ACT L2b.2 publication is on the host
   ([PR-1A read-only preflight](slice-15b2b-b1b3e-pr1a-readonly-preflight.md)
   D-7) and is the §24 "publication relation" input.
9. **Crash windows.** C-3 (K-WIT generated, publication not captured):
   `MANUAL_RECOVERY_REQUIRED`, burn and record, regenerate before M-B4 only.
   C-4 (K-WIT custodied): `KNOWN_CUSTODY_DEBT`, continue forward. After
   M-B2, `reset()` is `REBOOTSTRAP_FORBIDDEN`.
10. **Authorization.** B-5 Outcome A authorizes M-B1 … M-B15 in order, "each
    under its own reviewed procedure" (decision packet §4). The owner's M-B1
    acceptance requires a separate explicit K-WIT authorization.
    `CHECK_ELIGIBILITY` is not re-run (the sequencer is forward-only; the
    carry-forward decision B bound M-B1 only).

## 3. Pre-decision finding

The accepted
[Condition 3 validity model](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md)
is scoped "for the Condition 3 / eligibility window only", and the
[substrate-drift policy](substrate-drift-and-evidence-revalidation-policy-v0.1.md)
§11 leaves other windows open. "Fresh PR-2 immediately before
`GENERATE_K_WIT`" therefore had no accepted meaning. No reviewed M-B2
procedure or go template existed.

## 4. Pre-decision gaps

| Gap | Description | Resolution ([continuity decision](slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md) §3) |
| --- | --- | --- |
| M2-A | Fresh PR-2 expiry and invalidation semantics | **RESOLVED** |
| M2-B | Deployment freeze for the M-B2 sequence | **RESOLVED** |
| M2-C | One-attempt and refusal semantics of the M-B2 go | **RESOLVED** |
| M2-D | Location of the off-host K-WIT fingerprint record | **RESOLVED** |
| M2-E | Recording a known burned real K-WIT | **RESOLVED** |
| M2-F | Recording a real K-WIT candidate whose identity was never captured | **RESOLVED** |

Pre-decision recommendation: `NOT_READY_FOR_OWNER_MB2_DECISION` until one
owner decision defined the M-B2 PR-2 validity and continuity model
(M2-A … M2-F). The reviewed M-B2 procedure and go template follow from it.
That decision has now been made.

## 5. Current classification

```text
PRE-DECISION: NOT_READY_FOR_OWNER_MB2_DECISION
CURRENT: READY_FOR_OWNER_MB2_DECISION
M2-A … M2-F RESOLVED BY MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT
NO RUNTIME, SEQUENCER, KEYGEN, INSTALLER, WORKFLOW OR INFRASTRUCTURE CHANGE REQUIRED
M-B2 / GENERATE_K_WIT = NOT AUTHORIZED
M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED
REGISTRY / GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED
```

> **Later current state (2026-10-06, pointer only; the classification above
> is preserved as written).** The owner authorized one M-B2 sequence and,
> after its fresh PR-2 PASS and final gates, a separate one-attempt go. The
> single keygen invocation succeeded and the owner accepted
> **M-B2 / `GENERATE_K_WIT` COMPLETED / ACCEPTED**
> ([completion record](slice-15b2b-b1b3e-mb2-kwit-completion.md); K-WIT
> `publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf`;
> `K_WIT_CUSTODIED`). M-B3, registry / genesis, record 1, First Memory and
> PROD remain NOT AUTHORIZED, and FRESHNESS is UNKNOWN.
