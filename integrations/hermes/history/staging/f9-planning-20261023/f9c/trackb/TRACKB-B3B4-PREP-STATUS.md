# Track B B3 + B4 preparation: status (2026-10-25). INCOMPLETE; stopped at the usage limit

**Authorization:** local preparation of the B3 K-PAN ceremony tooling and the B4 authority-dev release program, offline only.

**What was done:** analysis only. No source edits for B3 or B4 were made. No DEV contact. Nothing was committed, built or installed. The worktree `lilith-os-trackb` is unchanged since TRACKB-B2-RESULT.md: cumulative patch `830e6500…`, B1 part `7483e76a…`.

## Findings (source evidence)

1. **The installer change is just the path set.**
   - `install_authority_dev.py:170` `RUNTIME_PATHS` (via `EXPECTED_PATHS`, used by `check_payloads`) gates only NEW archives.
   - `release_tree_failures` (line 1145) checks an installed release against its OWN manifest, so the installed 129f2be stays valid under a new installer.
   - Needed: + `lilith_recovery_witness/privacy_anchor.py`, `lilith_memory/privacy_anchor_contracts.py`; plus the `release_file_set.SHARED_HASHES` entry. Simulated: authority-dev 241/241 OK.
2. **Pin cascade from the installer bytes.** `fe10d9a3…` is pinned in the `TOOL_PINS` of `mb4_mb5_operator.py` and `mb6_operator.py` (they check `git show HEAD:` of the control clone). It cascades by hash through the whole live operator chain:

   mb6 → mb7_mb8 → mb9 → pkgc / mb10_owner_eligibility → mb10 → e19_operator → mb11 → e22 → mb14 → mb15

   That is 13 tools in total, plus about 15 test files. A cascade script was used; rerun it to regenerate. The chain is live tooling (mb15 readiness), so a mechanical re-pin is required.
3. **WRB pin:** `e19_witness_restart_boundary_install.py` pins the accepted witness unit `9f78130c`. The B2 unit change breaks 14 tests, so it needs a new unit pin and a restart-boundary story for the changed unit.
4. **"Repository tracks the installed release" guards** (5 tests) need a new E-22-style contract module (proposed: `tools/e23_privacy_anchor_upgrade.py`, OLD_RELEASE = 129f2be, a multi-member PAYLOAD_DELTA including the 2 NEW members, the unit and the tmpfiles), and the guards re-expressed against it:
   - `test_b1b3e_e19_release_maintenance` `…differs_from_aee323e_in_exactly_one_member`;
   - `test_b1b3e_e22_judge_transition` `…differs_from_the_installed_release_in_exactly_one_member`;
   - `test_b1b3e_mb6_ceremony_package` `test_release_module_pins` and `test_real_probe…`.

   The mb6 `RELEASE_MODULES` pins of `credential.py` are HOST-installed pins. Following E-22 practice, they must stay until after the swap (completion PR).
5. **The live transition (E-23) differs from E-22:**
   - the signer payload is unchanged, but the signer's cwd is in OLD, so RETIRE still needs a signer restart (E-22 rule);
   - witness units change, so a unit stage is needed (E-22 had none);
   - the K-PAN encrypted blob must be installed BEFORE the new unit, otherwise `LoadCredentialEncrypted` fails the witness start.

   It needs `e23_release_stages`, an `e23_operator` subclass, a remote tail and a DR-5 target. This is NOT in the authorized list and should be the next tranche.
6. **Candidate build:** `candidateSha` is the source commit. A real NEW must be built from the merge commit (E-22 pattern). Any build from a local commit is a reproducibility rehearsal only.

## Remaining, in order

1. Installer + SHARED_HASHES edit.
2. Cascade re-pin of the 13 tools plus their tests.
3. `e23` contract module + the 5 guard updates.
4. WRB unit pin.
5. B3 K-PAN keygen ceremony tool: extend the existing `services/authority-dev/ceremony` keygen pattern (PKCS#8 → `systemd-creds encrypt --with-key=host --name=privacy-anchor-signing-key`), emitting the public pin only.
6. Full WSL suites (tar must include `docs/`): main = authority-dev 241 OK / OMC 2114 OK / witness 44 OK.
7. Rehearsal build A/B + attestation.
8. Record → owner review. The E-23 live-ladder tooling is a separate tranche.
