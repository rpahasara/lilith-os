# Slice 15B2b-B1b-3e — E-19 Controlled Release Transition: Implementation

Status:

- **REPOSITORY-ONLY ENGINEERING SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `0b72e4449083871d53ac103890fd2fbf263d4a0a` (the PR #192 merge, deploy `38402859495`).
- **Owner decisions ACCEPTED (2026-10-13), as recommended in the readiness review:** E19-D1 … E19-D5 and OD-M11-13
  ([E-19 release maintenance](slice-15b2b-b1b3e-e19-release-maintenance.md) §10). They accept direction and scope.
  They authorize no live step: every U-phase step below needs its own verbatim owner go.
- **DEV at the start of this slice:** release `aee323e`, `WRB_2_EFFECTIVE_EXACT` (the witness restart boundary is
  installed and loaded), witness `8af12bd64d024d0eba56bbcedbc534a6` / 1580 / 0 restarts, HELD `c713ea1d…`, signer
  inactive, Registry and authority inactive.
- **NEW is not built.** `e19_p1b10_upgrade.NEW_RELEASE` and `NEW_MANIFEST_SHA256` stay `None`. Every DEV form of
  the new operator refuses (`NEW_RELEASE_NOT_ESTABLISHED`) until a later merged owner pin, after the reproducible
  build and attestation (E19-D4: the candidate identity is established before U0).

```text
source implemented != NEW built != NEW attested != NEW pinned != U0 accepted != any go
one go = one marker = one remote invocation;  no retry, no rollback, no repair
```

## 1. The four blockers and what changed

### A. Installer stages: `e19_release_stages.py` (new)

The installer `services/authority-dev/ceremony/install_authority_dev.py` is **not edited**. It is pinned
(`fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487`) by the completed M-B6, M-B9 and M-B10 operators.
Those operators stream it from their control checkout for `status --expect`, and about ten pin tests hold it
byte-identical. Completed ceremonies stay byte-identical, as `mb6_operator` did for E-19 (record §3.1).

The E-19 stages are therefore an **adjunct module**, run on DEV in ONE mb6 BOOT bundle `[installer, contract,
stages]` under the system interpreter. It reuses the installer's code unchanged:

- `verify_archive`, `release_tree_failures`, `_write_new`, `_normalize_tree`, `_fsync_directory`;
- the installer `status --expect P1B-10`.

The installer's own `UPGRADE_EXISTING_DEV_SYNTHETIC` mode still refuses a custody host.

| Form | Pre-state (exact, else refused) | Effect | Post-state |
| --- | --- | --- | --- |
| `e19-status <OLD> <NEW>` | — | read-only | one of the states below, or `E19_INCONSISTENT` |
| `e19-stage <OLD> <NEW> <manifest-sha256> <archive> <stamp>` | `E19_OLD_ONLY` | `releases/<NEW>` beside OLD (staging `mkdir`, `O_EXCL` files, venv, import check as the signer account, rename) | `E19_NEW_STAGED` |
| `e19-select <OLD> <NEW>` | `E19_NEW_STAGED` **and** the witness service and both sockets STOPPED | `current -> releases/<NEW>` (symlink + rename) | `E19_NEW_SELECTED` |
| `e19-retire-old <OLD> <NEW> <invocation>` | `E19_NEW_SELECTED` **and** that replacement (never the ending id) running, 0 restarts, cwd `releases/<NEW>` | remove `releases/<OLD>` | `E19_OLD_RETIRED` |

Each state is judged from these facts:

- the release set and the selector;
- staging and selector residue;
- both trees (`release_tree_failures`);
- the payload delta: exactly `lilith_owner_memory/pr1_acceptance.py` `e0928854…` → `0d2e6cca…` (contract
  `PAYLOAD_DELTA`), checked against the archive before anything is written;
- the installer `status --expect P1B-10` of the **selected** release. Its only admissible failure while two
  releases are installed is `RELEASE_SET`. At U0 and U5 it must PASS outright.

Nothing here reloads, starts or stops a unit, loads a credential, or touches custody, HELD, the ledger or the
witness state.

### B. Controlled witness stop and start: `e19_operator.py` (new)

`stop` runs `sudo -n /usr/bin/systemctl stop lilith-recovery-witness.service lilith-recovery-witness-owner.socket
lilith-recovery-witness-signer.socket`. That is one transaction: the service and both sockets.

`start` runs `sudo -n /usr/bin/systemctl start lilith-recovery-witness.service`, the service only. Its `Requires=`
pulls in both sockets, and WRB_2 refuses a manual socket start. Both strings are the contract's `STOP_COMMAND` and
`START_COMMAND`, prefixed by `sudo -n`.

Every mutating form (`stage`, `stop`, `select`, `start`, `retire`) does the following, in order:

1. Checks the owner's go, rendered by `render`. The go binds:
   - the control commit and the operator SHA-256;
   - OLD, NEW and the NEW manifest;
   - the U0 statement digest;
   - the latest observation of the required phase.
2. Takes one fresh read-only observation, which must be exactly the pre-phase and maintenance-ready (boundary
   effective, fragments exact). For `retire` the running identity must also be the **accepted** replacement.
3. Writes the `O_EXCL` marker, which consumes the go.
4. Makes ONE remote invocation, never retried.
5. Takes one read-only post observation.

`E19_<STEP>_REACHED_<phase>` needs exit 0 **and** the expected post-phase. Anything else is `E19_<STEP>_STOP`.

Incarnation counting is the merged contract's: one start go is one counted K-WIT load. A failed start is
`US_REPLACEMENT_START_FAILED`, and an extra load is `US_KWIT_LOADS_NOT_EXACTLY_ONE`. Retirement is refused without
VERIFIED POST9A-R, the owner's verbatim replacement statement, and its re-verified local record.

### C. Two-release-aware host reads (`e19_operator.host`)

The M-B10 host POST cannot judge U1–U5, for two reasons:

- `status --expect P1B-10 aee323e` fails `RELEASE_SET` as soon as NEW is staged;
- `readiness_ok` pins `current -> releases/aee323e` and the 38 aee323e module hashes, so it fails as soon as NEW is
  selected.

`host <U0|U1|U4|U5>` runs the same Package B reads (`mb10_operator._package_b_commands`) plus W9 and W10, with
these changes:

- **readiness** is judged against the **selected release of the phase**. OLD uses the accepted M-B6 pins. NEW uses
  exactly `PAYLOAD_DELTA` moved (`new_release_module_pins`). The fixed CLIs are byte-identical in both.
- **installer state** comes from `e19-status`, and must equal the phase's state.
- **W9** (`W9_LATER_STATE`) and **W10** (`W10_1_HELD_EXACT`) are unchanged and release-agnostic.

U2 and U3 have no host read: the witness is stopped and nothing may contact a socket, so the observer is the
evidence. The M-B10 tools, their pins, their DR-5 targets and the routine preservation path are unchanged. POST9A-R
stays the separate replacement-acceptance boundary, and package READY stays U5-only.

### D. Live-compatible observer (`e19_maintenance_observer.py`)

Under the BOOT loader `__file__` is `<mb6-bundle:NAME>` and no tool file exists on DEV. The merged observer
failed there in three ways:

- `_check_contract` read `E.__file__`;
- `_broker` loaded `scripts/verify_broker_dev_current_incarnation.py` from a path derived from `__file__`;
- `observe` read its inputs from a host file.

The fixes:

- **Contract pin.** Bundled, the contract pin is judged from the pin map the loader itself enforced in argv[1]
  before executing anything (exit 96 on any mismatch). On a workstation it is still the file hash.
- **Broker.** The broker reader is the bundled module, whose pin must be the accepted post-reboot re-pin
  `b90ed6ef…`. On a workstation it is the hash-checked repository file.
- **Inputs.** `observe-inline <b64url> <sha256>` takes the inputs as canonical JSON bound to their SHA-256, with no
  host file and no stdin (the bundle uses stdin). The bundle echoes `inputsSha256`, and the operator rejects any
  observation whose echo differs.
- **Path hygiene.** Bundled, the observer no longer puts the remote cwd on `sys.path`.

Pinning, journal-cursor retention, distinct new-invocation counting and fail-closed `null` are unchanged.

## 2. Owner sequence (each step its own owner act; none authorized here)

1. Merge this PR, then routine preservation (DR-5 W10_1 EQUAL and a host POST; `aee323e` is unchanged).
2. Build NEW at that protected-main commit with the PR-1A process: two independent builds, then `inspect` ×2 and
   `attest` (`attest_authority_dev_build.py`).
3. A PR pinning `NEW_RELEASE` / `NEW_MANIFEST_SHA256` and the derived E-19 DR-5 targets (`derive_release_swap`).
   This is the record update the contract names. Then preservation again.
4. `observe` (U0 candidate), then `render U0`, then the owner's verbatim statement, then `accept-u0`. The freeze
   starts here: no deploy until U5.
5. The owner transfers the attested archive and its builder stamp to `/home/<OS Login user>/lilith-e19-transfer/`
   (gcloud scp, the M-A1 precedent).
6. E19-GO-STAGE, then `stage` (U1).
7. E19-GO-STOP, then `stop` (U2).
8. E19-GO-SELECT, then `select` (U3).
9. E19-GO-START, then `start` (U4).
10. `post9a-r` (VERIFIED), then `render REPLACEMENT`, then the owner's verbatim statement, then
    `accept-replacement`.
11. E19-GO-RETIRE, then `retire` (U5).
12. `host U5`, then the completion record PR that pins the replacement. Its merge is the first post-transition
    deploy, whose DR-5 must be EQUAL to the derived E-19 targets. Then the owner's completion acceptance.

## 3. Pins

| Tool | SHA-256 |
| --- | --- |
| `services/owner-memory-control/tools/e19_release_stages.py` (new) | `77279d4546db1da85dac489ccbcbf477adc9a3f1a9fcea274fc487ff0ab0396d` |
| `services/owner-memory-control/tools/e19_maintenance_observer.py` (was `6c9e97e3…`) | `1689b6ba916210009df67053c0c7a9a7e02d21821882d78eaa853b5c0e585a1c` |
| `services/owner-memory-control/tools/e19_p1b10_upgrade.py` (unchanged) | `152022eeff26993f383ce0ba94c0ea552c7dda01ff3b87bc249be295106f34cb` |
| `services/authority-dev/ceremony/install_authority_dev.py` (unchanged) | `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `services/owner-memory-control/tools/mb10_operator.py` (unchanged, reused) | `74e1611fd067b67841029b6d2ae0189e2b2d417bc88122811bde11f3bea5042b` |

`e19_operator.py` pins every tool it ships or imports (`TOOL_PINS`) and refuses unless it is itself at the control
commit. Its own SHA-256 is bound in each owner go.

## 4. Tests

`services/owner-memory-control/tests/test_b1b3e_e19_transition.py`:

- the installer stages on a synthetic DEV root:
  - the full stage, select and retire sequence with custody bytes unchanged and no unit command;
  - refusals: unpinned manifest, any payload delta other than `pr1_acceptance`, staging residue, re-run, select
    while running or with a lone socket, retire for the ending id, another id, a restart or a replacement on OLD;
  - inconsistent layouts;
- the **real** mb6 BOOT loader, isolated, from an empty working directory:
  - the observer bundle (contract pin, bundled broker, inline inputs, forged digest refused, a substituted contract
    or broker refused, `observe-inline` checks inputs before the DEV root check);
  - the stage bundle with the unchanged installer;
- the operator against a fake DEV whose observations are the **real** observer over the synthetic host:
  - U0 → U5 with exactly one invocation per go;
  - out-of-order and reused go refused;
  - a changed host fails the fresh gate before the marker;
  - a failed start or an extra load is a STOP, never retried;
  - retirement needs POST9A-R and the owner acceptance;
  - a reworded statement, a non-echoed input digest or a missing NEW pin is refused;
  - an unretained journal cursor is UNKNOWN;
- two-release readiness (each release by its own pins; mixed, wrong or foreign releases fail) and the host reads
  per phase;
- pins and source guards.

Totals: owner-memory-control 1776 OK (16 skipped; 32 new, also green as a non-root user), authority-dev 241 OK,
recovery-witness 44 OK, `validate_repository.py` OK.

## 5. Open items (not defects of this slice)

- The NEW build, attestation and pin (steps 2–3), and the E-19 DR-5 targets.
- The archive transfer is an owner act; the operator reads only the two fixed host paths.
- The pre-existing `mb11_restart_boundary` / `mb11_restart_boundary_install` and verifier modules still insert
  `Path(__file__).resolve().parent` into `sys.path` at import. Under the loader that is the remote cwd (the operator
  user's home, under `sudo`). It changes nothing here: every bundle module is already registered, and that user
  already holds sudo. A hygiene fix would re-pin those modules, so it is left for a separate decision.

## 6. State

```text
E19 TRANSITION = SOURCE IMPLEMENTED (stages, stop/start, two-release reads, live observer); NOTHING RUN
INSTALLER = BYTE-UNCHANGED (fe10d9a3…); CONTRACT = UNCHANGED (152022ee…); NEW_RELEASE = NOT BUILT / NOT PINNED
DEV = aee323e, WRB_2_EFFECTIVE_EXACT, witness 8af12bd6… / 1580 / 0, HELD c713ea1d…, signer inactive
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  authorityGranted = false
```
