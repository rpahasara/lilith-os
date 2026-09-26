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
| polkit | `pkcheck --action-id …`, an authorization **query**, when `pkcheck` exists. **Not part of the PASS gate** (§7a): it is a tripwire only |

## 4. Denial classes

| Class | Proof |
| --- | --- |
| A. identity assumption | before L1a: `sudo -u lilith-memory-broker`, a real, existing proxy. It is a FAIL if the broker is missing or the query is inconclusive. From L1a: `sudo -u lilith-authority-dev`. Also: the effective user must be the deployer (not uid 0), in none of `root sudo adm lxd docker wheel google-sudoers systemd-journal lilith lilith-authority-dev lilith-recovery-witness lilith-memory-broker lilith-memory-ipc` |
| B. service control | sudo queries for `daemon-reload` and for `start stop restart reload try-restart reload-or-restart enable disable reenable mask unmask edit revert` on both units. The sudo route is gated. The polkit route (`manage-units`, `manage-unit-files`, `reload-daemon`) is deferred from the gate; a conclusive grant still FAILs (§7a) |
| C. key ceremony | once the CLI exists (L1c.3): sudo queries for `lilith-authority-keygen-dev actor` and bare. Before then: `DEFERRED_UNTIL_OBJECT_EXISTS`, and the effective-sudo proof covers it |
| D. release | `/opt` write denial now. From L1b: `/opt/lilith-authority-dev`, `releases/`, and every `releases/<sha>` (each must be a 40-hex root dir 0755), `current` (root symlink to `releases/<40-hex>`), and its target |
| E. CLI | `/usr/local/sbin` write denial now. From L1c.3: the CLI itself |
| F. systemd material | `/etc/systemd/system` and `/etc/tmpfiles.d` write denial now. From L1c.1: the service, socket, and tmpfiles files |
| G. credential store | `/etc` write denial now. `/etc/credstore.encrypted` is a **host prerequisite**, not a ladder object (§6a). Whenever present it must be exactly root `0700`, and read, write, and traverse are all denied. The K-ACT blob inside is `UNOBSERVABLE_BY_DESIGN` to the deployer, covered by the traversal denial |
| H. host credential key | `/var/lib/systemd` write denial now. `/var/lib/systemd/credential.secret` is a **host prerequisite** (§6a). Whenever present it must be exactly root `0400`, with read and write denied |
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

**Corrected 2026-09-26 after run 36264031829 (§12).** `L2a`
(`/var/lib/systemd/credential.secret`) and `L2b.1` (`/etc/credstore.encrypted`)
are **not** maturity signals. They are generic systemd host prerequisites
(§6a). The only LILITH-specific custody object after L1c is the K-ACT blob.
The deployer cannot observe it, so **deployer-observed maturity ends at
`L1c.3`**. Blob presence and post-L2b.2 consistency are checked only by the
root-run `install_authority_dev.py status --expect L2b.2`: blob root `0600`,
credstore root `0700`, host key root `0400`, and the complete earlier ladder.
An out-of-order blob fails there, as `UNEXPECTED_PRESENT` at any earlier
stage.

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

### 6a. Host prerequisites (never maturity)

```text
AMBIENT HOST PREREQUISITE  !=  LILITH CEREMONY ARTIFACT  !=  LILITH MATURITY EVIDENCE
```

| Path | Secure state | Denials when present |
| --- | --- | --- |
| `/var/lib/systemd/credential.secret` | regular file `root:root 0400` | `-r`, `-w` |
| `/etc/credstore.encrypted` | directory `root:root 0700` | `-r`, `-w`, `-x` |

Each is reported as one of:

- `HOST_PREREQ: <path> ABSENT`: no maturity meaning, and not a denial;
- `HOST_PREREQ: <path> PRESENT_SECURE`: no maturity meaning; the denials
  above must hold;
- `HOST_PREREQ_UNSAFE <path> …`: fail closed.

LILITH does not own the generic `/etc/credstore.encrypted` namespace. The
deployer cannot see whether it is empty (mode 0700). Emptiness before K-ACT
creation is checked root-side, by `status` and the keygen.

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

### 7a. Polkit disposition: deferred from the PASS gate

`AUTHORITY_BOUNDARY_PROOF=PASS` never counts unknown polkit evidence.

Over a non-interactive SSH session, `pkcheck` normally reports a challenge
(rc 2: authorization would need interactive authentication). That is neither
a grant nor a conclusive denial. `pkcheck` may also be absent, or error
(rc 127). So a conclusive polkit **denial** cannot meaningfully be proven
before L1a. The polkit route is therefore **removed from the PRE_L1A
acceptance set and deferred**:

- **rc 0**, a conclusive grant: `FAIL`, so the proof is never PASS.
- **Any other rc**, or `pkcheck` unavailable: a `DEFERRED_NOT_IN_GATE: polkit …`
  line. It is never printed as `DENIED`, never counted as evidence, and never
  turned into success.

What the gate does prove about unit control is the **sudo** route (class B
queries, plus the effective-sudo proof), together with the deployer being
outside every privileged group, including the `sudo`/`adm` groups that
polkit treats as administrators. Proving the polkit route conclusively is
open work for a later owner-run check.

### 7b. Denial-proof invariant

```text
DENIAL PROOF != ATTEMPT THE FORBIDDEN MUTATION
```

No probe runs a command whose success would itself be a forbidden mutation.
Mutating commands are only ever **queried** (`sudo -n -l <exact command>`).

The existing inline B1c deny list had one probe that violated this:

- **Old:** `deny sudo -n /usr/bin/systemctl restart lilith-memory-broker.service`.
  If the permission were ever granted, the probe itself would have restarted
  the pinned memory broker.
- **New:** `query_denied /usr/bin/systemctl restart lilith-memory-broker.service`.
  It runs `sudo -n -l <command>` with the same classification as this proof:
  - rc 0 prints `ALLOWED(unexpected) query: …` and fails;
  - `unknown user`, `command not found`, `unable to resolve`, or
    `unknown group` prints `INCONCLUSIVE query: …` and fails;
  - otherwise it prints `DENIED(query): …`.

  A failure fails the existing step, so the deployment stops before
  *Package* and *Deploy*.

The assertion is unchanged: the routine deployer must not be able to
restart `lilith-memory-broker.service`. No other deny line runs a unit
start, stop, restart, reload, enable, disable, mask, or daemon-reload; a test
pins this. The remaining execute-style probes (`sudo -n true`,
`sudo -n bash -c true`, `sudo -n /usr/bin/python3 -c 0`, `sudo -n -u lilith true`)
run only no-op commands. The sudoers rule and the helper are unchanged.

## 8. Trusted-control / bootstrap analysis

**Trust scope.** This DR-5 proof establishes the boundary against compromise
of the **routine DEV deployer identity**. It assumes that protected-main,
owner-reviewed repository control stays trusted. It does **not** establish
integrity against an attacker who can maliciously modify the protected-main
workflow or the proof itself. That attacker could remove or weaken the gate
in the same merge. No new trusted-parent infrastructure is added for that
case.


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
- **Outcome, recorded in §12:** the first post-merge run (36264031829)
  exercised the proof live and failed closed on a false maturity inference.
  That was a real finding, not a bootstrap artefact.
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
- the polkit tripwire line (`DEFERRED_NOT_IN_GATE` expected; it is not
  evidence, and a grant would FAIL);
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

  **Residual DR-5 debt outside B1b-3d:** the existing inline B1c/broker
  deny list still counts some missing paths as `DENIED`, for example
  `/var/lib/.lilith-memory-broker-stage3-a2`. That is not changed here. Its
  execute-style broker-restart probe **is** fixed here (§7b).
- **Polkit** unit control is deferred, not proven (§7a).

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
   - the polkit tripwire line (expected `DEFERRED_NOT_IN_GATE`, not evidence);
   - in the preceding step, `DENIED(query): /usr/bin/systemctl restart lilith-memory-broker.service`.

   Check the preceding step shows `SUDO_EFFECTIVE_PROOF=PASS`. Check the
   run completed *Deploy* and *Health*.
3. If the last line is anything else: STOP. Do not rerun. Investigate from
   the transcript. L1a stays blocked.
4. On PASS, record the run URL and transcript as the pre-L1a denial evidence
   in an owner record. That satisfies the L2 L1a PRE together with L0.
5. After each later LILITH ladder step (L1a through L1c.3), the next
   routine deployment must pass at that step's maturity before the next step
   is authorized.
   - L2a and L2b.1 are **host-prerequisite** transitions. Their owner
     ceremony POST (`status --expect L2a|L2b.1`) is authoritative. A later
     routine deployment observes them as `HOST_PREREQ … PRESENT_SECURE`, but
     it reports no new maturity label, and none is forced.
   - L2b.2 is checked root-side only (§6).

## 12. Negative result: run 36264031829 (`DR5_MATURITY_FALSE_POSITIVE`)

Register entry
[N-44](../research/negative-results-register.md#register).
[Run 36264031829](https://github.com/rpahasara/lilith-os/actions/runs/36264031829)
was on main `e534f96`, the merge of this record's first version.

- **What ran.** It was the first post-merge DR-5 proof, run live as the real
  routine deployer.
- **Evidence that held.** Real deployer evidence was collected:
  - every parent write denial;
  - `sudo -u lilith-memory-broker`;
  - 27 unit-control sudo queries;
  - polkit `pkcheck_rc=2` for all three actions, `DEFERRED_NOT_IN_GATE`.
- **The failure.** The proof inferred `maturity=L2b.1` from the ambient
  `/etc/credstore.encrypted`. It then correctly failed:
  - `LADDER_OBJECT_MISSING` for the account and every L1b–L1c object and
    the host key;
  - `SUDO_QUERY_INCONCLUSIVE` for the absent keygen.

  Last line: `AUTHORITY_BOUNDARY_PROOF=FAIL maturity=L2b.1`.
- **Nothing proceeded.** The workflow failed closed before *Package* and
  *Deploy*. No custody mutation occurred. No authority account, key, or
  blob existed.
- **Owner read-only observation afterwards:**
  - `/etc/credstore.encrypted` directory `root:root 0700`, empty;
  - `/var/lib/systemd/credential.secret` absent;
  - blob absent;
  - account absent.

  The actual maturity was `PRE_L1A`.
- **Classification:** `DR5_MATURITY_FALSE_POSITIVE`. It is a genuine negative
  result. It is **not** successful pre-L1a evidence and is not reinterpreted
  as such. The run is not rerun.
- **Correction** (§6, §6a): maturity comes only from LILITH-specific objects.
  Host prerequisites are reported separately and never advance it. The
  accepted maturity labels are `PRE_L1A|L1a|L1b.1|L1b.2|L1c.1|L1c.3`.
- **Expected next live result** for the recorded DEV state:
  - `HOST_PREREQ: /var/lib/systemd/credential.secret ABSENT`;
  - `HOST_PREREQ: /etc/credstore.encrypted PRESENT_SECURE`, with `DENIED`
    for `-r`, `-w`, and `-x`;
  - last line `AUTHORITY_BOUNDARY_PROOF=PASS maturity=PRE_L1A`.

## Explicitly not done

- No DEV session, account, release, unit, credstore, host key, key, or blob.
- No `systemd-creds`; nothing started or enabled.
- No sudoers, helper, library, verifier, IAM, WIF, PROD, or Stage III change.
- No broker → signer IPC, witness, ledger, or Privacy custody.
- DR-3 and DR-5 are not closed. Custody is not claimed.
