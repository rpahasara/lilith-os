# Slice 15B2b-B1b-3d — Routine DEV Deployer Authority-Boundary Hardening (DR-5)

Status:

- **B1b-3d ROUTINE DEPLOYER AUTHORITY-BOUNDARY HARDENING IMPLEMENTED** (source)
- **DR-5 SOURCE CONTROL IMPLEMENTED; DR-5 LIVE DENIAL NOT YET PROVEN**
- **DR-5 OPEN. DR-3 OPEN.**
- **No custody installed, no account, key, credential, or unit created.**

Base: protected main `fd5b1a7644ce37b0c5fa5175cf4c56c60857ee7a`. It includes
the merged [L1 foundation](slice-15b2b-b1b3d-l1-authority-signer-foundation.md)
(PR #76) and the merged
[L2 custody preparation](slice-15b2b-b1b3d-l2-custody-preparation.md)
(PR #77). The post-merge "Deploy LILITH Core API to DEV" run for `fd5b1a7`
succeeded.

This is the pre-live gate that L2 §10 requires **before live L1a**:

```text
COMPROMISED ROUTINE DEPLOYER  !=  AUTHORITY CUSTODY CONTROL
```

It narrows and proves the boundary only. It adds no deployer capability.

## 1. Current deployer capability model (unchanged)

Canonical sources: the [B1c acceptance](slice-15b2b-b1c-acceptance-record.md)
and the [B1c design](slice15b2b-b1c-dev-deployer-authority.md).

| Capability | Value |
| --- | --- |
| Identity | OS Login `sa_112096412008414111981`, federated only for `deploy-dev.yml` on protected main; own group only |
| sudo | exactly `(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, /usr/local/sbin/lilith-dev-deploy status` |
| Helper | buffers the bundle, drops to `lilith`, restarts only `lilith-os-api-dev.service` |
| Existing in-run proof | the effective-sudo proof (self mode), a deny list, and activation `NOT_ACCEPTED` |

The sudoers template, helper, library, verifier, and effective-sudo proof
are not changed. Tests pin this.

## 2. Exact DR-5 gap

From the design §3:

- the B1c routine deny list checked `sudo -u lilith`, but not
  `sudo -u lilith-memory-broker`;
- it did not require a probed path to exist, so a missing path counted as
  `DENIED`, which proves nothing.

For B1b-3d this means every future authority path would "pass" while
absent, and nothing would force its denial to become real once it appeared.

## 3. What is implemented

| File | Role |
| --- | --- |
| `scripts/deployer_authority_boundary_proof.sh` | the proof; streamed into `bash -s` on DEV and run as the deployer |
| `.github/workflows/deploy-dev.yml` | one new step, *Prove the routine DEV deployer has no authority-custody reach*. It runs after the existing boundary proof and before *Package* and *Deploy* |
| `scripts/test_deployer_authority_boundary_proof.py` | tests: decision logic, static safety, wiring, and a real-probe smoke run |
| `.github/workflows/ci.yml` | one step running those tests |

### Probes are read-only

| Probe | Mechanism |
| --- | --- |
| filesystem | `stat` and the shell's `test -r/-w/-x` (access(2)). No file is created, even to test |
| sudo | `sudo -n -l <command>`, a policy **query**. The probed command is never run |
| polkit | `pkcheck --action-id …`, an authorization **query**, when `pkcheck` exists. Otherwise the line is `NOT_PROVEN`; the effective-sudo proof still applies |

## 4. Denial classes

| Class | Proof |
| --- | --- |
| A. identity assumption | before L1a: `sudo -u lilith-memory-broker`, a real, existing proxy. It is a FAIL if the broker is missing or the query is inconclusive. From L1a: `sudo -u lilith-authority-dev`. Also: the effective user must be the deployer (not uid 0), in none of `root sudo adm lxd docker wheel google-sudoers systemd-journal lilith lilith-authority-dev lilith-recovery-witness lilith-memory-broker lilith-memory-ipc` |
| B. service control | sudo queries for `daemon-reload` and for `start stop restart reload try-restart reload-or-restart enable disable reenable mask unmask edit revert` on both units. polkit queries for `manage-units`, `manage-unit-files`, `reload-daemon` |
| C. key ceremony | once the CLI exists (L1c.3): sudo queries for `lilith-authority-keygen-dev actor` and bare. Before then: `DEFERRED_UNTIL_OBJECT_EXISTS`, and the effective-sudo proof covers it |
| D. release | `/opt` write denial now. From L1b: `/opt/lilith-authority-dev`, `releases/`, and every `releases/<sha>` (each must be a 40-hex root dir 0755), `current` (root symlink to `releases/<40-hex>`), and its target |
| E. CLI | `/usr/local/sbin` write denial now. From L1c.3: the CLI itself |
| F. systemd material | `/etc/systemd/system` and `/etc/tmpfiles.d` write denial now. From L1c.1: the service, socket, and tmpfiles files |
| G. credential store | `/etc` write denial now. From L2b.1: `/etc/credstore.encrypted` must be root `0700`, and read, write, and traverse are all denied. The K-ACT blob inside is `UNOBSERVABLE_BY_DESIGN` to the deployer and is covered by the parent traversal denial |
| H. host credential key | `/var/lib/systemd` write denial now. From L2a: the key must be root `0400`, with read and write denied |
| I. later authority state | `/etc/lilith-authority-dev`, `/var/lib/lilith-authority-dev`, `/run/lilith-authority-dev`, `/run/credentials/lilith-authority-dev.service`, and the witness state/run directories. Write is denied whenever present, and read too for state and run |
| integrity of the proof's own inputs | write denial on `/etc/passwd`, `/etc/group`, the effective-sudo proof library, `/usr/local/lib/lilith-dev-deploy`, and the needrestart control file and directory. Each must exist and be root-owned |

## 5. Non-vacuous pre-L1a strategy

```text
PATH_ABSENT != ACCESS_DENIED
```

Before L1a, the proof checks the existing root-owned parent directories that
govern creation of every ladder object:

- `/opt`, `/etc`, `/etc/systemd/system`, `/etc/tmpfiles.d`,
  `/usr/local/sbin`, `/var/lib/systemd`;
- plus `/etc/needrestart/conf.d` and `/usr/local/lib/lilith-dev-deploy`.

Each must exist as a `root:root` directory, and the deployer's write access
must be denied. A missing or non-root parent is a FAIL, never a denial. These
checks, plus the effective-sudo proof and the real `sudo -u
lilith-memory-broker` refusal, are the pre-L1a evidence. Every leaf that does
not exist yet prints `DEFERRED_UNTIL_OBJECT_EXISTS` and counts for nothing.

## 6. Maturity / existence rule

**No marker is introduced.** Maturity is derived from the root-owned objects
that the ceremony steps already create:

| Maturity | Derived from |
| --- | --- |
| `L1a` | a local `/etc/passwd` entry `lilith-authority-dev`. A name resolved only through OS Login or NSS does not count |
| `L1b.1` | `/opt/lilith-authority-dev`, `…/releases` |
| `L1b.2` | `…/current` |
| `L1c.1` | the service, socket, and tmpfiles files |
| `L1c.3` | `/usr/local/sbin/lilith-authority-keygen-dev` |
| `L2a` | `/var/lib/systemd/credential.secret` |
| `L2b.1` | `/etc/credstore.encrypted` |

Rules:

1. Maturity is the latest step with **any** object present.
2. Every object of that step and of **every earlier** step must exist,
   `root:root`, with its exact kind and mode (the L2 contract). The account
   must exist from L1b.1 onward.
3. Each such object is then denied to the deployer (§4).

Why the deployer cannot forge or hide maturity:

- In the same run, the proof shows it cannot write any parent those objects
  live in, or `/etc/passwd`.
- A deployer-created object would not be root-owned, and fails rule 2.
- Deleting an object would need parent write access, which is denied.
- An object appearing out of order fails rule 2. For example, a host key
  created with no ladder behind it stops routine deploys. This is
  deliberately conservative: the owner investigates.

The rule carries no "accepted" semantics. It only decides which denials must
now be non-vacuous.

L1c.2 (`daemon-reload`) is not a filesystem object and is not a maturity
signal. Service control is queried at every maturity anyway. The rule is
defined only through L2b.1. L3 and later extend §4 class I and must add their
own rows when those slices define their objects.

## 7. Fail-closed behaviour

- A missing object after maturity, a readable or writable object that should
  be denied, an allowed or inconclusive sudo-as, service-control, or keygen
  query, or an allowed polkit action: each is a `FAIL:` line. The last line
  is `AUTHORITY_BOUNDARY_PROOF=FAIL`, and the exit status is non-zero.
- The workflow step fails unless the last line is exactly
  `AUTHORITY_BOUNDARY_PROOF=PASS maturity=<known step>`. The step has no
  `always()` and no `continue-on-error`, so *Package*, *Deploy*, and *Health*
  never run after a failure.
- Sourcing with `AB_LIBRARY_ONLY=1` (tests) defines functions only and
  prints no PASS line, so it cannot satisfy the gate.
- **Pre-L1a**, the correct live state is `PASS maturity=PRE_L1A`. Normal
  deployments continue.

## 8. Trusted-control / bootstrap analysis

| Component | Generation that runs |
| --- | --- |
| `deploy-dev.yml` steps (including this proof step and the existing inline deny list) | the default branch at `workflow_run` time: the merged candidate |
| `candidate/scripts/deployer_authority_boundary_proof.sh` | the same candidate generation (streamed from the `candidate/` checkout) |
| `candidate/scripts/classify_dev_deployment.py` | candidate (unchanged here) |
| `scripts/build_core_api_bundle.py`, `memory_broker_validation.py`, `memory_broker_os_release.py` | the **trusted first parent** (root checkout at `BASE_SHA`) — unchanged here |
| `/usr/local/lib/lilith-dev-deploy/effective_sudo_proof.sh` | owner-installed on DEV (B1c) — unchanged |

The proof deliberately uses the **same generation as the workflow file** that
decides whether it runs. It is evidence, like the existing inline deny list,
and not a validator. Taking it from the trusted parent would add no real
protection, because a candidate could simply delete the step. It would also
force an expected-failure bootstrap run, because the parent lacks the file.
Trusted-parent validation of the bundle, broker, and release builders is
**unchanged**.

Consequences for the first post-merge run of this PR:

- The PR adds `scripts/deployer_authority_boundary_proof.sh` and its test,
  which are not in `CONTROL_ONLY_PATHS`, alongside `deploy-dev.yml`. The
  classifier therefore returns `DEPLOY_REQUIRED`.
- **No bootstrap generation is expected.** No trusted-parent script
  changed.
- The first post-merge routine deployment **does exercise the new proof
  live**, as the real deployer. The expected result given the recorded DEV
  state is `AUTHORITY_BOUNDARY_PROOF=PASS maturity=PRE_L1A`. A `FAIL` there
  is a real finding, not a bootstrap artefact. It stops that deployment,
  and it must be investigated, not rerun.
- A later PR that changes only `deploy-dev.yml` is `CONTROL_ONLY_NO_DEPLOY`
  and does not contact DEV. The proof then next runs at the following
  `DEPLOY_REQUIRED` deployment. This is the existing semantics.
- The deployer cannot modify the boundary definitions. They live in GitHub
  (the deployer job has `contents: read`), in the candidate checkout on the
  runner, and in root-owned DEV files whose write denial is part of the
  proof.

## 9. What source proves vs. what needs live evidence

**Source and tests prove:**

- the decision logic for every class A–I;
- absence is never denial;
- a forged, out-of-order, or missing ladder object fails;
- probes are queries only, with no writes, executions, or redirects to
  files;
- the workflow step is before *Package* and *Deploy*, is fail-closed, and
  requires the exact PASS line;
- deployer sudo, the helper, and the Core API deploy are unchanged;
- no PROD path is added.

The unmodified script also ran with real probes on a Linux host as root and
as `nobody`. It failed closed with `UNEXPECTED_EFFECTIVE_USER`, and the real
parent write denials appeared as `nobody`.

**Needs live evidence (NOT_YET_LIVE_PROVEN):**

- `PASS maturity=PRE_L1A` from a real routine DEV deployment as
  `sa_112096412008414111981`;
- the real `sudo -n -l` refusals and the real parent denials on
  `lilith-dev-01`;
- the polkit result, or its `NOT_PROVEN` line;
- after each later ladder step, a routine deployment showing that step's
  leaf denials non-vacuously.

## 10. DR-3 and DR-5

- **DR-3 stays OPEN.** `ubuntu` is root-equivalent through `sudo` and `lxd`.
  This slice proves only the routine-deployer boundary. It never claims
  host-root denial.
- **DR-5: SOURCE CONTROL IMPLEMENTED, not closed.** Closing it for B1b-3d
  requires:
  1. the first post-merge routine deployment passing this proof live
     (pre-L1a evidence);
  2. then, after each ladder step, a routine deployment passing with that
     step's leaves non-vacuous.

  **Residual DR-5 debt outside B1b-3d:**
  - The existing inline B1c/broker deny list still counts some missing
    paths as `DENIED`, for example `/var/lib/.lilith-memory-broker-stage3-a2`.
  - Its `deny sudo -n /usr/bin/systemctl restart lilith-memory-broker.service`
    probe is execute-style. If that right were ever granted, the probe itself
    would restart the pinned broker. It should become a `sudo -n -l` query in
    a separate change.

  Neither is changed here.

## 11. Post-merge live proof procedure

1. Merge. The merge commit's post-merge "Deploy LILITH Core API to DEV" run
   classifies `DEPLOY_REQUIRED` and runs automatically. No manual rerun, and
   no owner session on DEV.
2. In that run's step *Prove the routine DEV deployer has no
   authority-custody reach*, record:
   - the full output;
   - the last line, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=PRE_L1A`;
   - the `DENIED:` lines for each parent and for
     `sudo -u lilith-memory-broker`;
   - the polkit line.

   Check the preceding step shows `SUDO_EFFECTIVE_PROOF=PASS`. Check the
   run completed *Deploy* and *Health*.
3. If the last line is anything else: STOP. Do not rerun. Investigate from
   the transcript. L1a stays blocked.
4. On PASS, record the run URL and transcript as the pre-L1a denial evidence
   in an owner record. That satisfies the L2 L1a PRE together with L0.
5. After each later live ladder step, the next routine deployment must pass
   at that step's maturity (for example `maturity=L1a`, then `L1b.1`, …)
   before the next step is authorized.

## Explicitly not done

- No DEV session, account, release, unit, credstore, host key, key, or blob.
- No `systemd-creds`; nothing started or enabled.
- No sudoers, helper, library, verifier, IAM, WIF, PROD, or Stage III change.
- No broker → signer IPC, witness, ledger, or Privacy custody.
- DR-3 and DR-5 are not closed. Custody is not claimed.
