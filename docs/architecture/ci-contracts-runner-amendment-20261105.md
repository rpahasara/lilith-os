# CI Repository-contracts runner amendment (2026-11-05)

Status: owner-approved for preparation (2026-11-05, chat, "Option A"); takes effect only when the owner merges the
reviewing PR (#322). This record amends one value of an existing owner exception. It does not replace the original
records, which stay as they were merged.

## What it amends

The M-B11 workflow-guard owner exception of PR #183 (2026-10-12) admits exactly one M-B11 workflow step, the
synthetic restart-boundary probe, in the read-only `repository-contracts` job of `.github/workflows/ci.yml`. The
exception lives in the guard itself (`mb11_workflow_violations` in
`services/owner-memory-control/tests/test_b1b3e_mb11_signer_start.py`) and is also asserted by `CiWiringTests` in
`services/owner-memory-control/tests/test_b1b3e_mb11_restart_boundary.py`. One of its conditions is the job's runner
label, which the guard required to be exactly `ubuntu-latest`.

The M-B11 design record (`docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-design.md` §6) names the runner the
proof needs: a disposable, ephemeral GitHub-hosted Ubuntu 24.04 runner with systemd 255 as PID 1. When PR #183
landed, `ubuntu-latest` resolved to that image.

| | before | after |
| --- | --- | --- |
| `repository-contracts` runner label | `ubuntu-latest` (floating) | `ubuntu-24.04` (fixed) |
| runner class | GitHub-hosted, ephemeral | GitHub-hosted, ephemeral (unchanged) |
| image / systemd today | Ubuntu 26.04 / systemd 259 (since 2026-11-05) | Ubuntu 24.04 / systemd 255 |

## Why

On 2026-11-05 the GitHub-hosted `ubuntu-latest` label moved from the Ubuntu 24.04 image (`ubuntu24/20261025.353`, the
last passing run) to Ubuntu 26.04 (`ubuntu26/20261025.179`). systemd 259 rejects the systemd-run flags of the accepted
broker stage-2 probe, which `scripts/test_memory_broker_stage2_control.py` exercises for real:
`--pty/--pty-late/--pipe is not compatible with --remain-after-exit`. #322's diagnostics captured this output.

DEV and PROD both run Ubuntu 24.04 / systemd 255 (PROD audit run 2, 2026-11-05), so the probe is correct for the hosts
it runs on. The contracts job is pinned to that same generation. The real transient-unit lifecycle test and its
negative controls are kept unchanged. A floating image would silently change the systemd that the probe evidence is
taken against.

## What does not change

- The runner is still GitHub-hosted and ephemeral. Every non-approved label fails the guard: `ubuntu-latest`,
  `self-hosted` (bare, in a list or in a block), runner groups, expressions, other images, larger runners and a
  second `runs-on`.
- The approved step stays byte-exact (`APPROVED_STEP`). The approved job, workflow, header, triggers and read-only
  `contents: read` permissions are unchanged. There are no secrets, no `id-token`, no cloud authentication and no
  environment.
- The live-token list, the PR/DEV separation needles and the `pr-source-required-check` aggregator are unchanged.
- The DEV deployment workflow, the broker-only DEV workflow and every other job keep their runners.
- The broker stage-2 probe (`scripts/memory_broker_stage2_control.py`) is not modified.

## Deployment classification

A merge of this change alone must not deploy DEV. The workflow, the stage-2 harness test and the classifier were
already control-only. The two M-B11 test files and this record are admitted as control-only only at their exact
reviewed blob (`PINNED_CANDIDATE_BLOBS`). Any later revision of them takes full deployment, as before.

## Future work (not in this change)

Before any DEV or PROD host moves past systemd 255, port `probe_equivalent_sandbox` and its CI lifecycle test so they
are valid on systemd 259 (for example, a `--wait`/`--collect` invocation with a non-`--pipe` output path). Then
re-validate the result on the target generation. Only after that may this runner be moved to a newer image, through
another amendment of this record.

## State

```
APPROVED_RUNNER = ubuntu-24.04 (GitHub-hosted)
SUPERSEDED_RUNNER = ubuntu-latest
M-B11 EXCEPTION SCOPE = UNCHANGED EXCEPT THE RUNNER LABEL
M-B11 = NOT AUTHORIZED
DEV = NOT TOUCHED
PROD = NOT TOUCHED
SYSTEMD_259_PROBE_PORT = FUTURE WORK (NOT IN THIS CHANGE)
```

## Addendum 1 (2026-11-05): the DEV deploy gate's runner

Status: owner-approved for preparation (2026-11-05, chat). It takes effect only when the owner merges its draft PR.

**Finding.** #322 merged as main `57fc4668f78bc52b6cb0c2efd90276a233b110eb`, and Repository validation passed. The DEV
deploy gate (run `41977404976`) then classified the merge `CONTROL_ONLY_NO_DEPLOY`. Its step "Validate control-only
candidate on the ephemeral runner" failed: the `deploy` job of `.github/workflows/deploy-dev.yml` re-runs
`scripts/test_memory_broker_stage2_control.py` on `ubuntu-latest`, which is now Ubuntu 26.04.1 / systemd 259. Because
that step failed, the later steps did not run: OIDC claims, Google Cloud authentication, the DEV identity check and
the authority-boundary proofs. The statement "the DEV deployment workflow keeps its runner" in *What does not change*
above is superseded for that one job only.

**Change.** Only the `deploy` job's runner moves, from `ubuntu-latest` to `ubuntu-24.04` (GitHub-hosted, systemd 255).
The comment sits below `runs-on`, so the guarded event condition above it is byte-identical. `premerge_gate`,
`broker_candidate` and `broker_postflight` do not run the lifecycle test and keep their runners.
`scripts/test_pr_ci_dev_separation.py` freezes the job's whole header byte-exact: event guard, runner, permissions
and the fixed DEV identities. Every write permission in the workflow is pinned. Mutation cases fail, including
floating, self-hosted, group, expression, other or larger image, second `runs-on`, container, environment, wider
permissions, another identity or instance, widened triggers and a dropped event guard.
`scripts/test_memory_broker_stage2_control.py` requires every job in any workflow that runs the lifecycle harness to
be on `ubuntu-24.04`. That test would have caught this gap.

**What the gate does for a control-only change (preserved, not weakened).** In `CONTROL_ONLY_NO_DEPLOY` mode, the job
first validates the candidate on the runner. It then still records the OIDC claims and authenticates to Google Cloud
as the DEV-only deployer identity. It verifies the DEV identity and target, and runs the read-only proofs that the
routine DEV deployer has no root, broker, Stage III or authority-custody reach. That mode therefore does **not** mean
zero cloud or DEV contact. It means that no Core API bundle is built, packaged or deployed through the DEV helper, and
no health check or service restart follows. The PROD-federation negative proof runs only in `DEPLOY_REQUIRED` mode.

**Federation trust.** Per the B1c records (`slice15b2b-b1c-dev-deployer-authority.md`, `slice-15b2b-b1c-acceptance-record.md`), the
provider maps `sub`, `repository`, `ref` and `workflow_ref`. The provider condition requires this repository and
`refs/heads/main`. The DEV deployer is federated only for
`workflow_ref = rpahasara/lilith-os/.github/workflows/deploy-dev.yml@refs/heads/main`. The runner image label is not a
mapped claim, and the runner stays GitHub-hosted. No IAM, provider, binding, permission, trigger, identity or target
changes. This assessment comes from the repository's records; the live IAM policy was not read.

```
DEPLOY_GATE_RUNNER = ubuntu-24.04 (GitHub-hosted; deploy-dev.yml job deploy)
DEPLOY_GATE_SUPERSEDED_RUNNER = ubuntu-latest
DEPLOY_GATE_PERMISSIONS = UNCHANGED (contents read, id-token write, pull-requests read, statuses write)
FEDERATION_AND_IAM = UNCHANGED
CONTROL_ONLY_GATE_CLOUD_AND_DEV_READ_ONLY_CHECKS = PRESERVED
```
