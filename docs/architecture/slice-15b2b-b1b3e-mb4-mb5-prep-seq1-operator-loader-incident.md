# Slice 15B2b-B1b-3e — M-B4/M-B5 Preparation Sequence 1: E-21 Operator Real-Load Incident and Fix (2026-10-07)

Status:

- **`MB4_MB5_PREPARATION_SEQUENCE_1 = ENDED / STOPPED_AT_E21 / TOOL_DEFECT`.**
  The first owner-authorized M-B4/M-B5 preparation sequence (control
  `ffa9575f13e60ae8f87dfb0c7b9afc9e5d4f566d`) stopped at E-21. The reviewed
  operator's `derive` form failed while loading the real derivation module,
  **before any derivation ran**. Package §15 S-3 (an E-item not PASS) ended
  the sequence; no substitute procedure was used.
- **Nothing was derived, staged, transferred or installed.** No DEV, GCP or
  S25 contact happened in the sequence after the stop. No go was given or
  consumed. No identity is burned. K-ROOT and K-WIT private material was not
  accessed.
- **All evidence of sequence 1 is HISTORICAL / NON-REUSABLE** (continuity
  C-14, package §3): E-1, E-2, E-3, E-14 and E-19 passed inside that sequence
  but must not be replayed into a later one.
- **Owner decision (2026-10-07):** the sequence is TERMINAL / ENDED, and the
  deployment freeze it declared is RELEASED with it
  (`DEPLOYMENT_FREEZE_PREVIOUS_SEQUENCE = RELEASED`). That decision authorizes
  no deployment.
- **The fix is repository-only (§4).** It changes only how the operator loads
  the derivation module. The derivation, the representation rules, the three
  accepted representation pins and every other tool pin are unchanged.
- **Nothing is authorized by this record.** A new preparation sequence needs
  its own owner authorization after this fix is reviewed, merged and deployed.
- Append-only. Earlier records are not edited except for the operator pin in
  the package §1 table (which must equal the code) and later-state pointers.

```text
E-21 STOP            != derivation output       != staging        != M-B4 go consumed
tool defect          != burn                    != authority mutation
sequence-1 PASS items = HISTORICAL; never replayed into a later sequence
fix merged           != new sequence authorized != evidence fresh != M-B4 go
```

## 1. Identities

| Item | Value |
| --- | --- |
| control commit of sequence 1 | `ffa9575f13e60ae8f87dfb0c7b9afc9e5d4f566d` (PR #161) |
| DEV deploy at control | `37573254876` (success) |
| failing tool | `services/owner-memory-control/tools/mb4_mb5_operator.py`, SHA-256 `2d9835edb18361df231c58d914c8859240438c7ed7dd39de547bee4756acfbbf` (**superseded; must not be used**) |
| module it loads | `services/owner-memory-control/tools/mb4_mb5_installable_inputs.py`, SHA-256 `dbe94a2d3a38fa838d4fd7eeb9016274c85c684221ddb770e8e993cc15b18d61` (unchanged) |
| failing form | `mb4_mb5_operator.py derive <repo> <export.tar> <workdir>`, owner laptop WSL, Python 3.12.3, pinned wheels |
| input | the accepted M-B3 export (operator copy), SHA-256 `c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8`, unchanged before and after |
| failure time | `2026-10-07T05:04:48Z` |
| fixed operator (pre-merge) | SHA-256 `e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a` |

## 2. What happened in sequence 1

| Item | Result (historical) |
| --- | --- |
| E-1 repository control | PASS: `origin/main` = clean checkout = `ffa9575`; `MB4_MB5_TOOL_PINS_EXACT`; operator, owner-freshness and DR-5 pins exact |
| E-2 / E-3 deploy relationship and freeze | PASS: latest DEV deploy `37573254876` at control, nonmaterial by content; nothing queued or running; freeze declared `2026-10-07T05:03:14Z` |
| E-14 DR-5 | PASS: the ten deploys `37445851939` … `37573254876` each equal the accepted run `36552218231` on all three digests (`f1869234…`, `a1d98773…`, `f5087042…`); 158 `DENIED`, no `ALLOWED`, `P1A-9`, `L1c.3`, `GRANT_ABSENT` |
| E-19 Registry V1 custody | PASS: export `c4ea3d66…`; `verify_mb3_registry.py` with the M-B3 go pins `MB3_LAPTOP_VERIFIED` (digest `fa662721…14fc`); transport `3f0a59c0…6156` inside |
| **E-21 derivation** | **NOT PASS**: the operator stopped with `AttributeError: 'NoneType' object has no attribute '__dict__'` inside `dataclasses`, while executing the derivation module. `derive_rc=1`; no `derived/` directory was created; the export was unchanged |
| E-4 … E-13, E-15 … E-18, E-20 | not run (sequence ended at the stop) |
| E-22 | not authorized, not run |

All of these results are **historical** and may not be replayed.

## 3. Root cause

`Operator.derive` loaded the pinned derivation module with
`importlib.util.spec_from_file_location` + `module_from_spec` +
`spec.loader.exec_module`, **without first registering the module in
`sys.modules`**.

The derivation module uses `from __future__ import annotations`, so every
annotation is a string. When `@dataclass(frozen=True)` processes
`SourcePinsV1`, the string annotation `L.AcceptedIdentitiesV1` is checked for
`ClassVar` / `KW_ONLY` by `dataclasses._is_type`. That function reads
`sys.modules[cls.__module__].__dict__`. The module was not registered, so the
lookup returned `None` and the load failed. A diagnostic load (module load
only, no derivation) confirmed it: the unregistered load fails, and the same
load succeeds once the module is registered.

**Why the tests did not catch it.** The operator's only `derive` test injected
a fake derivation object, so the real load path never ran. The derivation's
own tests import the module normally (registered by the import system), so
they could not see the defect either.

## 4. Fix (repository-only)

**Operator** (`mb4_mb5_operator.py`):

- a new `load_derivation(repo)`, used by `derive`. It follows the
  `verify_mb3_registry._load` pattern:
  1. re-checks the derivation file against its pin (`TOOL_PIN_MISMATCH`, before
     any byte is executed);
  2. builds a **fresh** module under the fixed name
     `mb4_mb5_installable_inputs_operator`;
  3. registers it in `sys.modules` **before** `exec_module`, replacing (never
     reusing) any earlier entry under that name;
  4. on any exception during execution, removes the half-executed module from
     `sys.modules` and STOPs with `DERIVATION_LOAD_FAILED`.
- `derive` loads the module **before** anything is written, so a load failure
  leaves no output.
- `derive` now passes the accepted source pins (`ACCEPTED_SOURCES`) and the
  operator's representation pins (`DERIVED`) explicitly to `read_export`,
  `derive_from_members` and `check_pins`. These are the same values the
  defaults held, so the production result is unchanged; the explicit form lets
  a test substitute synthetic pins on the real, freshly loaded module.

Everything else is unchanged: the source pin checks for the derivation and
`mb3_registry_ceremony.py`, the export pin check, the double derivation and
comparison, the pin check, the `O_EXCL` writes into a new directory, the
independent re-hash, `SHA256SUMS`, and the export-unchanged check.

**Tests** (`test_b1b3e_mb4_mb5_operator.py`, new `RealDerivationLoadTests`).
They load the **real** module through the operator and run the **real**
derivation on a synthetic TEST world (the M-B3 package test keys and a
synthetic export tar). The only substitution is the source / export / derived
pins, set on the freshly loaded module. The accepted export is never read.

| Requirement | Test |
| --- | --- |
| the escaped defect is real | the old unregistered pattern raises `AttributeError` on the real module |
| A, B, C: real module, registered during `exec_module`, dataclasses initialize | a spy around the real loader records `sys.modules[name] is module` before and after execution; `SourcePinsV1` and `DerivationV1` are dataclasses of the loaded module; its pins equal the operator's |
| D, 7: the real derive path runs | `mb4_mb5_operator.py derive` through the CLI on the synthetic export: `MB4_MB5_DERIVED_PINNED`, the written bytes equal an independent derivation, `SHA256SUMS`, registry = transport minus exactly one LF |
| D: real derivation logic | a tampered synthetic K-WIT publication is refused by the real module's `DerivationRefusal`, and nothing is written |
| E: repeated invocation | a planted stale module is replaced; two loads give two distinct modules; two full derives in one process are byte-equal |
| F, G: load failure fails closed, no output | a real execution failure (the module's own import of `mb3_registry_ceremony` blocked) gives `STOP DERIVATION_LOAD_FAILED`, no module left in `sys.modules`, CLI exit 1 with empty stdout, an empty work directory and an unchanged export |
| pin check before execution | unpinned derivation bytes are never executed (`TOOL_PIN_MISMATCH`) |

Against the old operator (`2d9835ed…`), the real `derive` on the synthetic
export reproduces the E-21 `AttributeError`. Against the fixed operator it
reaches the real derivation logic.

## 5. Pin cascade

| Pin | Before | After |
| --- | --- | --- |
| `mb4_mb5_operator.py` | `2d9835edb18361df231c58d914c8859240438c7ed7dd39de547bee4756acfbbf` | `e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a` |
| every other package §1 tool pin | unchanged | unchanged |
| R-3 release module pins (14) | unchanged | unchanged |
| `registry-root.json` | `bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687` | unchanged |
| `witness-anchor.json` | `be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a` | unchanged |
| `authority-registry.v1.json` | `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` | unchanged |

The operator pin appears in the package §1 table only, and it is updated
there. The package tests compute the operator hash from the file, so they
bind the new value. No go template or go-file check names the operator pin.

## 6. DR-5 and B-5 boundary

- DR-5 is not extended, and no new DR-5 baseline is created.
- Sequence 1's DR-5 PASS is historical. This change will produce a new DEV
  deploy when merged. The next preparation sequence must freshly compare every
  DEV deploy since the last accepted comparison, **including that new
  deploy**, under package §14.1.
- Nothing here claims current B-5 usability.

## 7. Remaining blockers before a new preparation-sequence decision

1. Review and merge of this fix. The package §1 operator pin must equal the
   merged bytes (`e380ab18…`).
2. The resulting DEV deployment completes through the normal flow (not
   authorized here).
3. A new owner authorization for a preparation sequence on the new control
   commit (package §12.1).
4. In that sequence, everything from package §4 is collected fresh: E-1 …
   E-21 (including DR-5 over all deploys since `37435321602` plus the new
   one, Replica A, the owner's S25 Replica B read and E-21 confirmation).
   E-22 still needs its own transfer authorization.

## 8. State

```text
MB4_MB5_PREPARATION_SEQUENCE_1 = ENDED / STOPPED_AT_E21 / TOOL_DEFECT (HISTORICAL; NON-REUSABLE)
DEPLOYMENT_FREEZE_PREVIOUS_SEQUENCE = RELEASED (OWNER DECISION; AUTHORIZES NO DEPLOYMENT)
OPERATOR_REAL_LOAD_FIX = SOURCE AND TESTS READY FOR REVIEW (PRE-MERGE OPERATOR e380ab18…)
SUPERSEDED OPERATOR PIN = 2d9835ed… (MUST NOT BE USED)
MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO (ACCEPTED; UNCHANGED)
REPRESENTATION PINS UNCHANGED: 46b0bfc5… / bc5f00a7… / be360da2…
NO DERIVATION OUTPUT; NO STAGING; NO GO CONSUMED; NO BURN
PREPARATION SEQUENCE = NOT AUTHORIZED
TRANSFER = NOT AUTHORIZED
M-B4 = NOT AUTHORIZED
M-B5 = NOT AUTHORIZED
INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
TRUST_INSTALLED = NO
REGISTRY_INSTALLED = NO
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
THIS RECORD CONTACTED NO LIVE SYSTEM; NO K-ROOT OR K-WIT PRIVATE MATERIAL ACCESSED
```
