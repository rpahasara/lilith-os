# Slice 15B2b-B1b-3e — E-19 Release Maintenance: Judge Correction and the Proposed `UPGRADE_FROM_P1B10_DEV_SYNTHETIC` Contract

Status:

- **REPOSITORY-ONLY ENGINEERING SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `2165cd79c10652e61a11345c6bed9dfcb3dbf82a` (PR #187 merge; M-B12 PR-B1 and PR-B2 merged).
- It corrects the E-19 judge **in source** and proposes, with synthetic test support only, the maintenance contract
  that would move DEV from release `aee323e` to a corrected release. It accepts no new custody contract and
  performs no transition.
- **E19-D1 … E19-D5 are PROPOSED (§10). None is accepted.** OD-M11-13 and OD-M11-15 are evaluated (§9) and stay
  PROPOSED.
- **The installed release is unchanged.** DEV still runs `aee323e`, whose E-19 judge keeps the defect. Nothing here
  builds, attests, stages, selects or retires a release, stops or starts the witness, loads K-WIT, rebinds custody,
  changes HELD or the ledger, starts the signer, loads K-ACT or activates authority. No code in this slice can do
  any of those things.

```text
source corrected != release built != release attested != release installed != transition accepted
witness restart != preservation of InvocationID 8af12bd6…;  one start go != one K-WIT load (counted, never inferred)
two releases installed (U1..U4) => package READY refused;  classification != permission;  STOP != repair;  no rollback
```

## 1. Witness identity history (reconciled from records; DEV not contacted)

| Phase | Identity | Source | Status today |
| --- | --- | --- | --- |
| Package B sequence 3, M-B9a (B3 `WITNESS_STARTED` acceptance), 2026-10-08, control `050e7c5` | InvocationID **`5136ea7af2544450b9370fa412786c98`**, MainPID **`143946`**, NRestarts 0 | [Package B completion](slice-15b2b-b1b3e-mb9-package-b-completion.md) (B3 record `11ae03ad…`); first post-Package-B deploy record; Package C design §1 | **Historical.** Ended by the 2026-10-09 M-R1 reboot (kernel `1014`). The owner's post-reboot acceptance says so verbatim. |
| Post-reboot, the one reviewed restart (plan `bb765760…`, `W9_5S → W9_5`), started 2026-10-09T09:42:02Z on boot `cb0d71da…` | InvocationID **`8af12bd64d024d0eba56bbcedbc534a6`**, MainPID **`1580`**, NRestarts 0 | [post-reboot re-pin](slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md) §2 (acceptance `f7f95e65…`) and §5 (`pkgc_operator.ACCEPTED_PINS`) | The owner-accepted incarnation. It was observed through Package C, M-B10 (01-PRE … POST10, 03-POST) and the post-freeze host POSTs. |
| M-B10 host/09-POST (2026-10-12T10:54:58Z, owner-local evidence `lilith-mb11-p1b10r-preflight2-5f27724`, `HOST_RESULT.json` `841a247c…`) | `8af12bd6…` / `1580` / 0; `w10verifier.out` `4e59173b…` (= the M-B10 read-back) | owner evidence | **`MB10_HOST_POST_PASS`**: the last PASS observation of the running witness. |
| M-B10 host/10-POST (2026-10-12T11:05:54Z, `lilith-mb11-p1b10r-preflight3-5f27724`, `HOST_RESULT.json` `368c23b3…`) | `8af12bd6…` / `1580` / 0; `w10verifier.out` `4e59173b…` | owner evidence | **`MB10_HOST_POST_NOT_PASS`**: `preservation` and `w9verifier` returned `0xC0000005`, a local Windows client crash after delivery. It is consistent with the same incarnation, but it is not a PASS and is not counted as one. |
| After the PR #186 merge (deploy `38251273420`) and the PR #187 merge (`2165cd7`) | — | PR-B2 record §State | **Not observed.** Neither DR-5 W10_1 EQUAL nor a fresh host POST is established after either merge. |

So the repository's **expected** running witness is `8af12bd6…` / `1580` / 0. Its last **verified** observation is
09-POST. Anything after 11:05:54Z is unobserved. The B3 incarnation `5136ea7a…` / `143946` is never the running
witness. The contract lists it in `HISTORICAL_INCARNATIONS`, and if it ever appeared it would be a STOP.

## 2. The E-19 correction (`pr1_acceptance.py`)

`ACTIVATION_DARK_LINE` was the three-field prefix `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`. The B1c printer
(`scripts/dev_deployer/lilith_activation_verify.py`) always appends ` advisoryConfigEnabled=<true|false|unreadable>`,
so E-19 failed on every honest host line. The fix is this slice's change (OD-M12-5 → proposed E19-D1):

| Edit | Effect |
| --- | --- |
| `ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"` | the complete line, compared by **exact equality** (no prefix, trim, case or field-order tolerance) |
| E-19 also requires `type(line) is str` | a `str` subclass or any JSON non-string fails `ACTIVATION_NOT_DARK` |
| `_activation_evidence`: the package evidence records the line only if it is a UTF-8-encodable `str`, and `b1cUnchanged` only if it is a `bool`; otherwise `null` | a malformed value (float, list, object, lone surrogate) **failed closed by crashing** the package canonicalization (`TypeError` / `CanonicalizationError`); it now fails closed **as a FAIL** with a digestible package |

Regression coverage (`test_b1b3e_e19_release_maintenance.py`, `E19JudgeTests`). The full line with `b1cUnchanged
true` passes. Each of these FAILs `ACTIVATION_NOT_DARK`:

- the old three-field form;
- `advisoryConfigEnabled=true`, `=unreadable` or `=False`;
- `reason=GRANT_INVALID` or `GRANT_EXPIRED`;
- `ACTIVATION=ACCEPTED …`;
- leading or trailing space, CR, LF, CRLF, a second line, NUL, a double space, tab or NBSP separators, lower case,
  reordered fields, an extra field, a BOM, an empty string, a lone surrogate or a Cyrillic homoglyph;
- `None`, `0`, `1.5`, `True`, a list, an object, or a `str` subclass as the line;
- `b1cUnchanged` of `False`, `None`, `1`, `"true"` or `"True"`.

A missing observation is `ACTIVATION_UNOBSERVED`. A source anchor pins the printer's exact `print(f"…")` form. The
same line now appears identically in `pr1_acceptance`, `mb11_restart_boundary_install.ACTIVATION_DARK`,
`mb12_readiness_inputs.HOST_ACTIVATION_DARK_LINE` and this contract's preserved `activationLine`. A test asserts all
four are equal.

`pr1_acceptance.py`: `e0928854e1fcf4107458939ba9ebf1903cf7a4d0ab6808f7e89108db1444bbff` (aee323e) →
**`0d2e6ccabf916425a1dfa7dc587bfcb3d7a232eb6c52c5cd938d573199715cff`**. `e19_p1b10_upgrade.reverse_e19` undoes exactly
the pinned `E19_EDITS` and must reproduce `e0928854…`, so the diff is proven to be these edits and nothing else.

## 3. Source and release consequences

### 3.1 Re-pins made here

| File | Change |
| --- | --- |
| `services/authority-dev/release_file_set.py` `SHARED_HASHES[pr1_acceptance.py]` | `e0928854…` → `0d2e6cca…` (release file set `48918350…` → `713ac96b…`) |
| `services/authority-dev/tests/test_pr1s_runtime_wiring.py` | the constant pin follows the full line |
| `services/owner-memory-control/tools/mb12_readiness_inputs.py` (`1d7d771a…` → `3483020e…`) | `E19_DEFECTIVE_RELEASES = {aee323e}`: the builder still reports E-19 as an expected gap (and the known defect) for the installed `aee323e`, and no longer for any other release |
| PR-B1 / PR-B2 tests | the known-defect pins become the corrected-judge pins; the synthetic TEST end-to-end with all seven producers is now `READY` (TEST trust only; no DEV meaning) |
| `test_b1b3e_mb6_ceremony_package.py` | M-B6 is a completed ceremony, so `mb6_operator` keeps its historical aee323e pin `e0928854…` byte-unchanged; its tests compare that pin against `reverse_e19(source)` (the post-reboot re-pin precedent) |

### 3.2 The release payload delta is exactly one member

Against the `aee323e` commit, every runtime payload source and every CLI source is byte-identical except
`lilith_owner_memory/pr1_acceptance.py`. That was checked with `git show` over `RUNTIME_SOURCE_MAP` and
`CLI_SOURCES` (53 + 6 sources). The test runs when the commit is present in the clone. It is also proven without
history:

- the 38 aee323e module pins of `mb6_operator`, moved only by `PAYLOAD_DELTA`, equal the current payload;
- the ledger, verify and witness-owner CLIs equal their aee323e pins;
- both signer unit fragments equal `mb11_restart_boundary_install.FRAGMENTS`.

Consequences:

- **No unit, socket, tmpfiles, daemon-reload or CLI step.** The installed copies already equal the NEW members.
- Runtime digests: `authority` `4b32f169…` → `5a7c9903…`. `witness` `5137ddb0…` and `rootTooling` `28e9d6cb…` do not
  change, **but both code paths import `pr1_acceptance`**. The witness's `core.py` uses `PA.parse_hold_snapshot`, and
  the root verifier and hold store use E-19 itself. The prefix-based digests do not cover that import. "Witness
  digest unchanged" is therefore not "witness code unchanged".
- The NEW release SHA does not exist yet. By N-45 it will be a protected-main commit, built and attested like PR-1A
  (`attest_authority_dev_build.py`). `NEW_RELEASE = None` and `NEW_MANIFEST_SHA256 = None`. With them unset,
  `classify` refuses (`NEW_RELEASE_NOT_ESTABLISHED`).

### 3.3 Why the witness cannot keep running across the swap

`lilith-recovery-witness.service` has `WorkingDirectory=/opt/lilith-authority-dev/current` and
`ExecStart=/opt/lilith-authority-dev/current/venv/bin/python -B -m lilith_recovery_witness.server`.

- Its `sys.path[0]` and cwd are the resolved `releases/aee323e`. Its venv prefix is derived from the unresolved
  `current/venv/...` path.
- After `current` flips, any lazy import can load NEW bytes into the ending process. That is a **mixed** state.
- After `releases/aee323e` is retired, the process runs from a **deleted** tree.

Neither state may be an accepted endpoint. The RR-25 single-installed-release rule (installer `RELEASE_SET`, judge
E-01 `RELEASE_SET_UNEXPECTED`) forbids keeping `aee323e` indefinitely. So the swap **requires ending the accepted
witness incarnation and starting a replacement**. That restart is a new incarnation and a new K-WIT load
(`LoadCredentialEncrypted=` decrypts the same custodied blob `f8759370…` at every exec attempt). It is never a
preservation of `8af12bd6…`.

### 3.4 The existing installer upgrade mode cannot be reused

`UPGRADE_EXISTING_DEV_SYNTHETIC` (PR-1A, M-A1 … M-A6) was written for the pre-custody host:

- `_require_upgrade` refuses when the custody root exists;
- `preservation_failures` refuses when a witness credential exists;
- it has no witness, HELD, ledger or broker preservation;
- its state table requires a unit change.

This contract therefore needs its own reviewed installer stages. They are **not implemented** (E19-D2). A source
test pins those refusal lines.

## 4. The proposed contract `UPGRADE_FROM_P1B10_DEV_SYNTHETIC`

Tool: `services/owner-memory-control/tools/e19_p1b10_upgrade.py` (stdlib, pure, SHA-256
`e3e9ae4775a7be3fb78f4a87667ad20f4a4be45e116be822b832fb0b2e6bf528`). It sits outside the release tree;
`release_file_set.check_source_tree` is unchanged. It judges a recorded observation document of a closed schema.
`None` is the only spelling of "unobserved", and it is never a default. No host observer exists for it yet.

### 4.1 Entry: only from a fully established post-P1B10 state

U0 requires all of the following, and its observation becomes the **baseline**. Every later phase must present
that baseline (`BASELINE_REQUIRED`).

- the release set `[aee323e]` and `current -> releases/aee323e`;
- the accepted ending incarnation running from `releases/aee323e`, health `CONSISTENT` with K-WIT `5d778701…`, and
  no invocation since the baseline;
- the signer dark;
- boot `cb0d71da…`;
- every preserved fact exact (§4.2).

### 4.2 Facts that must remain byte-identical (HALT on any change, in every phase)

| Class | Facts |
| --- | --- |
| repository pins (`PRESERVED_PINS`, cross-checked by tests against the accepted tool constants) | K-ACT CURRENT blob `6a61c350…`; K-ACT publication `d7647976…`; K-WIT blob `f8759370…`; registry-root anchor `bc5f00a7…`; witness anchor `be360da2…`; registry `46b0bfc5…`; ledger head `19bf9091…1630`; witness genesis `ac892dc2…`; `chain/1.json` = `witness.json` `252c3220…`; hold listing exactly `[1ee1b7d5….json]` with HELD `c713ea1d…`; broker `ed35e343…` / `3411` / baseline `ff3a432d…` / preservation PASS; the complete host activation line |
| host facts recorded at U0 (`PRESERVED_HOST_FACTS`) | CURRENT and K-WIT blob lstat identities, host-key identity (never read), credstore / custody / witness-credential listings, ledger bytes, owner-input bytes, installed signer and witness unit files, installed CLIs |
| signer (`SIGNER_DARK`) | inactive / dead / PID 0 / no InvocationID / NRestarts 0 / static / **no drop-ins** / **no K-ACT invocation ever** |

A reboot (boot id change) is a **material STOP**, not a HALT. It ends the incarnation and the sockets, and needs
owner re-baselining.

### 4.3 What ends, what is loaded, what is new

- **Ends** (separate owner authorization, E19-GO-STOP): incarnation `8af12bd6…` / `1580`. The stop covers the
  service **and both sockets**. The sockets are `Accept=no` and `Service=lilith-recovery-witness.service`, so a
  listening socket with a stopped service would start the witness, and load K-WIT, on the next connection. A
  stopped service with any socket active is `US_WITNESS_TRANSITIONAL`. No reviewed stop tool exists:
  `mb9_operator` never stops a running unit.
- **Loaded** (separate owner authorization, E19-GO-START): one start of both sockets and the service (the M-B9a
  `START_COMMAND` form), from `releases/<NEW>`. The journal must show **exactly one** witness invocation since the
  baseline, and it must equal the running InvocationID. A failed attempt is a counted load (`US_REPLACEMENT_START_FAILED`).
  Two invocations is `US_KWIT_LOADS_NOT_EXACTLY_ONE`. There is no automatic retry and no automatic K-WIT reload.
- **New:** the replacement incarnation (new InvocationID / MainPID, NRestarts 0, cwd `releases/<NEW>`, health
  `CONSISTENT` with K-WIT `5d778701…`). It is the same custodied key and blob. It is **not** a new key, a rebinding,
  or a continuation of `8af12bd6…`.
- **New POST9A-R and acceptance:** before `releases/aee323e` is retired, the owner must record a verbatim acceptance
  of the replacement. It is B3-shaped and names the InvocationID / MainPID, the go, exactly one load,
  `W10_1_HELD_EXACT` under NEW tooling, and an unchanged genesis, chain, HELD, ledger and broker. A merged record then
  pins `ACCEPTED_REPLACEMENT_INCARNATIONS` (empty here). Without it, the single-NEW state is
  `US_RETIRED_BEFORE_INCARNATION_ACCEPTED`, never U5.
- **Replaced pins and targets:** §7, §8.

## 5. State machine

| Phase | Releases | `current` | Witness | Next step (proposed) | Owner act |
| --- | --- | --- | --- | --- | --- |
| `U0_P1B10_EXACT` | {OLD} | OLD | ending incarnation, from OLD | `STAGE_NEW_RELEASE` | E19-GO-STAGE (installer stage not implemented) |
| `U1_NEW_STAGED_WITNESS_ON_OLD` | {OLD, NEW} | OLD | the same incarnation, from OLD | `STOP_WITNESS_SERVICE_AND_SOCKETS` | E19-GO-STOP (ends `8af12bd6…`) |
| `U2_WITNESS_STOPPED_OLD_SELECTED` | {OLD, NEW} | OLD | stopped; service and sockets inactive; no load | `SELECT_NEW_RELEASE` | E19-GO-SELECT |
| `U3_NEW_SELECTED_WITNESS_STOPPED` | {OLD, NEW} | NEW | stopped; no load | `START_REPLACEMENT_WITNESS` | E19-GO-START (one K-WIT load) |
| `U4_REPLACEMENT_RUNNING_ON_NEW` | {OLD, NEW} | NEW | the replacement, from NEW; exactly one load | `POST9A_R`, then owner acceptance, then retire OLD | acceptance record, then E19-GO-RETIRE |
| `U5_OLD_RETIRED_REPLACEMENT_ACCEPTED` | {NEW} | NEW | the **accepted** replacement, from NEW | final POST and first-deploy DR-5, then owner completion | E19 completion acceptance |

Each verdict carries `authorizes: "NOTHING"` and `packageReadyAdmissible: false`.

Ordering rationale:

1. **Stage first.** Staging touches neither `current` nor the witness. A failed stage leaves U0 intact apart from
   residue.
2. **Stop before select.** The ending witness never runs while `current` points at the NEW release.
3. **Select while stopped.** The atomic symlink-and-rename leaves `current` at exactly one target.
4. **Start from NEW.** The replacement never runs from OLD.
5. **Accept before retire.** OLD is removed only when nothing runs from it and the replacement is accepted.

There is **no rollback path**. Reversing the selection would be another witness restart and another K-WIT load; it
is not part of this contract and is never automatic.

**The staging exception, exactly.** Two installed releases are permitted only in U1 … U4
(`TWO_RELEASE_PHASES`), with entries exactly {OLD, NEW}, `current` at one of them, and both trees verifying. In that
scope:

- package READY is refused twice: by `package_ready_admissible` (`TWO_RELEASE_INTERMEDIATE`), and by the judge's own
  E-01 (`verify_installed_release` → `RELEASE_SET_UNEXPECTED`, tested for both selector targets);
- the routine DR-5 has no target (§7), and deploys are frozen;
- `status --expect P1B-10` fails `RELEASE_SET`.

U0 is also refused, because E-19 cannot pass on aee323e. Package READY is admissible **only** in U5 on the accepted
NEW release. U5 is still not package READY: M-B12 and its OD-M11-12 gates are unchanged.

Precedence, as in W11: HALT (proven, even with other facts unknown), then UNKNOWN, then the STOP classes, then the
exact phases.

## 6. Interrupted steps: safe STOP and recovery (synthetic tests, all pass)

| Interrupted / unsafe state | Class | Safe resting point and recovery |
| --- | --- | --- |
| `.<NEW>.staging` left in `releases/` | `US_STAGING_RESIDUE` | The witness and `current` are untouched. Removing the residue is one separate owner act. No auto-clean. |
| NEW tree does not verify, or is unobserved | `US_NEW_TREE_INVALID` / `US_UNKNOWN` | NEW is never selected or started. Owner adjudication. |
| stop interrupted: deactivating, failed, auto-restart, or a socket still listening | `US_WITNESS_TRANSITIONAL` | No retry. Owner adjudication. A listening socket is a load risk. |
| stopped before staging | `US_OUT_OF_ORDER` | Not this order. Owner adjudication. |
| `.current.tmp` left after select | `US_SELECTOR_RESIDUE` | `current` is one exact target (atomic rename). The witness stays stopped. Residue removal is one separate owner act. |
| select while the ending incarnation runs | `US_WITNESS_RUNNING_ACROSS_SELECT` | Never an endpoint. The only exit is the separately authorized stop. |
| start: a load happened and the witness is not running | `US_REPLACEMENT_START_FAILED` | No retry without a new go. Each attempt is counted. |
| start: two or more loads, zero loads, or NRestarts > 0 | `US_KWIT_LOADS_NOT_EXACTLY_ONE` / `US_WITNESS_TRANSITIONAL` | STOP. Owner adjudication (cf. OD-M11-11 for the signer). |
| replacement started before select, so it runs from OLD | `US_REPLACEMENT_ON_OLD_RELEASE` | Not this contract. Owner adjudication. |
| replacement health not `CONSISTENT`, or a different K-WIT | `US_REPLACEMENT_NOT_CONSISTENT` | STOP. It is never accepted. |
| the ending incarnation restarted, changed PID or health, or a historical identity appears | `US_ENDING_INCARNATION_CHANGED` | STOP. Owner forensics. |
| retire interrupted (OLD tree partial), replacement accepted | `US_RETIRE_PARTIAL` | The replacement runs from NEW only. Completing the removal is one separate owner act. |
| retire before acceptance, or OLD changed | `US_OLD_TREE_CHANGED` / `US_RETIRED_BEFORE_INCARNATION_ACCEPTED` | STOP. Owner adjudication. |
| retire while a witness runs from OLD | `US_WITNESS_ON_RETIRED_RELEASE` | Never an endpoint. |
| retire before any replacement | `US_OUT_OF_ORDER` | Forward only, by a separate go. |
| a third release, a duplicate, a non-SHA entry, or a foreign selector | `US_RELEASE_SET_FOREIGN` | Owner forensics. |
| reboot | `US_BOOT_CHANGED` | Re-baseline under owner adjudication. |
| any preserved fact moved | `UH_PRESERVED_FACT_CHANGED` (HALT) | Freeze. Owner forensics. |
| signer active, enabled, drop-ins, or any K-ACT invocation | `UH_SIGNER_NOT_DARK` (HALT) | Freeze. M-B11 rules. |

## 7. DR-5 implications

`scripts/deployer_authority_boundary_proof.sh` names a release at exactly two sites: the `releases/` listing and the
`current` target. A test pins both. The accepted single-release texts therefore contain
`DENIED: test -w /opt/lilith-authority-dev/releases/aee323e…` twice in the result set and twice in the DR-5 block,
and never in the pre-deploy block.

`derive_release_swap` derives the NEW single-release targets from the accepted W10_1 texts (`WITNESS_RUNNING_HELD`,
`…_STOPPED_HELD`). It moves exactly those lines in place and nothing else. Over the accepted post-M-B6 fixture with
a synthetic NEW SHA:

- the result set and the DR-5 block change in exactly two lines;
- the pre-deploy block is unchanged;
- every W9 invariant still holds.

It refuses an intermediate text (three release lines), a NEW SHA that is already present, and any other line that
names the OLD release.

- The replaced targets (`WITNESS_RUNNING_HELD_E19`, `WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19`) have **no pins**.
  They can be pinned only once NEW exists, and accepted only by the owner.
- U1 … U4 have **no DR-5 target** (`NO_BASELINE_STOP`). The script itself fails on a `.staging` entry, and routine
  deploys stay frozen for the whole transition.
- The first deploy after U5 must be EQUAL to the derived NEW targets. It is not compared with the `aee323e` W10_1
  targets (`593c90e1…`, `ace51f27…`), which stay valid only while `aee323e` is installed.

## 8. Release pin and preservation implications

Every tool with an `aee323e` binding is classified. A test fails on any unclassified new binding.

| Binding | Kind | After a swap |
| --- | --- | --- |
| `mb6_operator` (`RELEASE_SHA`, 38 module pins incl. `pr1_acceptance` `e0928854…`), reused by `mb9_operator.readiness_ok` and therefore by **every `mb10_operator` host POST** | current read path | **Fails closed** (`readiness` not exact, `status --expect … aee323e` FAIL). The routine preservation read must be re-pinned to NEW **before** any transition, by a separate slice. `mb6_operator` itself is a completed ceremony and stays byte-identical, so the successor read path needs its own pins. |
| `mb9_operator` (`RELEASE_SHA` = M6) | current read path | as above |
| `mb11_signer_verifier` (`RELEASE_SHA` / `RELEASE_CWD`) | current (W11) | re-pin |
| `mb11_restart_boundary_install` (`RELEASE_SHA`; fragments byte-unchanged) | current (P1B-10R) | re-pin the SHA; fragment pins unchanged |
| `mb12_os_denial_proof` (fragment provenance text) | current | text only; bytes unchanged |
| `mb12_pr3_material`, `mb12_readiness_inputs` (`releaseSha`, manifest `1d578ca7…`) | current (M-B12) | re-pin to NEW and its attested manifest |
| `mb10_dr5_target` / `mb11_dr5_target` targets | current | replaced by derived `…_E19` targets (§7) |
| `mb4_mb5_operator`, `mb6_ledger_verifier`, `mb7_mb8_operator` | historical | unchanged. They refuse NEW by their own pins. |

Preservation that is outstanding regardless of this slice:

- DR-5 W10_1 EQUAL and a fresh `mb10` host POST after the PR #186 deploy (`38251273420`) and after the PR #187 merge;
- the same after this PR's merge, if it is merged.

Merging this PR changes no release, so the routine deploy's DR-5 must still be W10_1 EQUAL on `aee323e`. The swap
itself would need all of the following, none of which exists:

- a freeze that covers U0 … U5;
- re-pinned host reads (§8 rows 1–2);
- an upgrade observer;
- the installer stages;
- a reviewed stop path and a reviewed start path;
- POST9A-R;
- the owner records.

## 9. Minimizing release changes

| Pending capability | Needs a release change? |
| --- | --- |
| **E-19 judge** (OD-M12-5) | **Yes**: `pr1_acceptance` is release payload, and the root verifier imports it from `current`. |
| `OS_DENIAL`, `SECRET_HYGIENE`, `PRESERVATION_SET` producers (PR-B2), PR-2 inventory, PR-3 material, readiness-input builder (PR-B1) | No: owner-side tools outside the release tree. |
| P1B-10R restart boundary (OD-M11-11) | No: an `/etc/systemd/system/*.d` overlay, not release content. |
| **OD-M11-15** (how readiness inputs reach the host) | **No, on the path already built**: `read_envelope` and the streamed in-process `readiness_pair` read stdin without a host file. Only the installed root CLI route (`lilith_authority_root.cli._document`, regular file only) would need a release change. Not decided here. |
| **OD-M11-13** (E-25 … E-28) | **Only if the owner chooses the release route.** That route adds `PACKAGE_CHECKS`, input fields and material for record 1 / envelope 1 / freshness / P3-3, which is M-B13 design that does not exist. The owner-side amendment needs no release. Not decided here. |
| OS package or security updates | Never bundled by default. Kernel and `libcrypto` updates are separate material events (M-R1, Condition 3). |

**Recommendation (not a decision).** One coordinated transition is justified only by what must ride in it. Today
that is E-19 alone. However, OD-M11-13 must be **decided before** the transition ceremony. If it later takes the
release route, a second swap means a second ending incarnation, a second K-WIT load and a second set of re-pins.
If the owner chooses the release route now, E-25 … E-28 should be designed and bundled before the NEW release is
built. Otherwise E-19 ships alone. OD-M11-15 does not require bundling.

## 10. Owner decisions (PROPOSED; none accepted)

| ID | Proposal | Blocks |
| --- | --- | --- |
| **E19-D1** | Accept the E-19 judge correction (§2: exact complete line, `str`-only, null evidence for malformed values) as the content of the next authority release (resolves OD-M12-5) | building the NEW release |
| **E19-D2** | Accept `UPGRADE_FROM_P1B10_DEV_SYNTHETIC` as the maintenance contract, covering: entry only from the exact U0 baseline; the U0 … U5 order (stage → stop → select → start → accept → retire); the two-release exception scoped to U1 … U4 with package READY refused; single-release restored at U5; no rollback; no automatic cleanup, retry or K-WIT reload. Then authorize the follow-on source slices: installer stages, a read-only upgrade observer, stop and start paths | any implementation beyond synthetic |
| **E19-D3** | The witness boundary. Decide: (a) that ending `8af12bd6…` / `1580` is a custody-relevant event needing its own go; (b) that the replacement start is one go with exactly one K-WIT load, judged from the journal; (c) whether the witness unit's `Restart=on-failure` / `StartLimitBurst=3` needs a proven bound before the start, as OD-M11-11 required for the signer, or whether the 2026-10-09 restart precedent suffices; (d) the POST9A-R content and the acceptance wording before retiring OLD | stop / start |
| **E19-D4** | Pins and targets. Re-pin the current read path (§8 rows 1–2) before the ceremony, and the M-B11 / M-B12 tools after NEW exists. Derive the NEW DR-5 targets by §7. Keep the historical operators unchanged. Require a PR-1A-style build attestation of NEW (manifest, runtime digests) | the ceremony |
| **E19-D5** | Scope and timing. Ship E-19 alone, or bundle E-25 … E-28 (OD-M11-13, release route). Schedule the transition **before M-B11**: a signer running across a swap would need another K-ACT load. Bundle no OS updates | building NEW |

## 11. Readiness for owner review

- **Ready for owner review:** the E-19 correction, the contract, the state machine, the failure and recovery
  rules, the DR-5 delta rule, and the pin map.
- **Not ready for any live step:**
  - E19-D1 … D5 are open;
  - NEW does not exist;
  - there are no installer stages, no observer and no stop or start tooling for this mode;
  - the current host-read path would fail closed after a swap;
  - post-#186 and post-#187 preservation is not established.

No accepted contract had to be weakened. The single-release invariant holds outside U1 … U4, and the judge's E-01
enforces it independently.

## 12. Validation

- `services/owner-memory-control/tests` (full, WSL Ubuntu-24.04, root, `/root/l1deps`): **1663 tests OK, 16 skipped**
  (the aee323e git-history test skips without `.git`; it was run separately against the commit).
- `services/authority-dev/tests` (full): **241 OK**.
- New: `test_b1b3e_e19_release_maintenance.py`, 39 tests:
  - the E-19 judge and evidence;
  - pins, reversal, payload delta and the bindings map;
  - every exact phase; every interrupted and unsafe class; HALT on every preserved fact in every phase;
  - package READY refusal, including the judge's own E-01;
  - DR-5 swap derivation over the accepted fixture;
  - source guards.
- `scripts/validate_repository.py`, `compileall`, `git diff --check`.

## 13. State

```text
E19_JUDGE = CORRECTED IN SOURCE (pr1_acceptance 0d2e6cca…); INSTALLED RELEASE aee323e STILL DEFECTIVE
UPGRADE_FROM_P1B10_DEV_SYNTHETIC = PROPOSED CONTRACT; SYNTHETIC TESTS ONLY; NO INSTALLER STAGES / OBSERVER / RESTART PATH
NEW_RELEASE = NOT BUILT; NEW_DR5_TARGETS = UNPINNED; ACCEPTED_REPLACEMENT_INCARNATIONS = EMPTY
RUNNING WITNESS (expected) = 8af12bd64d024d0eba56bbcedbc534a6 / 1580 / 0; LAST PASS = 09-POST 2026-10-12T10:54:58Z
B3 INCARNATION 5136ea7a… / 143946 = HISTORICAL (ended 2026-10-09 M-R1)
POST-#186 / POST-#187 PRESERVATION = NOT ESTABLISHED
E19-D1 … E19-D5 = PROPOSED;  OD-M11-13, OD-M11-15, OD-M12-5 = PROPOSED
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  RELEASE / current / WITNESS / K-WIT / CUSTODY / HELD / LEDGER = UNCHANGED
SIGNER = INACTIVE;  K-ACT = NOT LOADED;  AUTHORITY_ACTIVE = NO;  authorityGranted = false
```
