# Track B B3 + B4: K-PAN ceremony tooling and E-23 release program (source + rehearsal build). Result 2026-10-25

**Authorization:**
- local preparation of the B3 K-PAN ceremony tooling and the B4 authority-dev release program, offline;
- the owner's installer decision: **versioned successor** (`install_authority_dev_v2.py`), with the V1 installer byte-identical.

**Verdict: `TRACK_B_B3B4_PACKAGE_READY_FOR_REVIEW`.**

**Boundary held:** no DEV, PROD or GCP contact; no key generated; nothing installed; nothing pushed.
- The worktree `lilith-os-trackb` is uncommitted.
- The only commit is a LOCAL rehearsal commit in a separate throwaway clone, never pushed.

Supersedes `TRACKB-B3B4-PREP-STATUS.md`. The partial in-place re-pin (Option 1) was reverted; its patch is kept for the record only (`trackb-b4-option1-wip.patch`).

## Source (worktree diff vs origin/main 3f6b909f)

**Patch:** `trackb-b1b2b3b4-cumulative.patch`, 41 files: Track B B1 + B2 + B3 + B4.

**B4 release program:**
- `services/authority-dev/ceremony/install_authority_dev_v2.py` (NEW): archive layout v2 = V1 + `lilith_recovery_witness/privacy_anchor.py` + `lilith_memory/privacy_anchor_contracts.py`.
  - Every other name is delegated to V1.
  - `check_payloads` / `verify_archive` run the V1 code with the V2 set bound during the call; no logic is duplicated.
  - V1 `install_authority_dev.py` stays **`fe10d9a3…` byte-identical**, so no operator, record or owner-approved go text changes.
- `release_file_set.py`:
  - `SHARED_HASHES` + `privacy_anchor_contracts.py` `58e954af…` (an addition; no re-pin);
  - CEREMONY/TEST file lists + the V2 installer, the fixture helper and the V2 tests.
- `build_authority_dev_release.py` and `attest_authority_dev_build.py` import V2.
  - The attested recipe adds `install_authority_dev_v2.py`.
  - Neither tool is pinned anywhere, so no cascade.
- `tools/e23_privacy_anchor_upgrade.py` (NEW, pure, `PROPOSED_NOT_ACCEPTED`):
  - OLD = installed E-22 `129f2be` / manifest `fc7dbf08`; NEW = None until a merged owner pin.
  - `PAYLOAD_DELTA`: 4 changed (witness `credential.py`, `server.py`, the witness unit, tmpfiles), each `(old, new)` sha.
  - `PAYLOAD_ADDED`: 2 members.
  - `check_payload` / `new_payload_pins`.
  - Constants: the K-PAN credential name / blob path / key id and the anchor state dir.
- **Host pins stay on OLD until the transition completes (E-22 practice):**
  - the E-19 restart-boundary `FRAGMENTS` `9f78130c`;
  - the M-B6 installed module pins.
- **Tests:**
  - authority-dev: `installed_layout.py` (fixtures that stage through V1 build the INSTALLED 129f2be layout from `git show`, i.e. exactly what main's fixtures built) + `test_trackb_layout_v2.py` (3);
  - OMC: `e23_installed.py` + `test_trackb_e23_contract.py` (6);
  - 5 repository-vs-installed guards (E-19 maintenance ×2, E-22 judge, M-B6 module pins + probe) and the WRB fixtures/pins now compare the INSTALLED bytes from history.

**B3 ceremony:** `tools/trackb_kpan_keygen.py` (NEW, never installed, streamed `python3 -I -B - keygen`).
- It mirrors the accepted K-WIT keygen form without changing that release CLI.
- **Preconditions:**
  - root, isolated interpreter, the DEV host id, no swap;
  - the host credential key 0400 and `systemd-creds` 0755;
  - the witness parent/credentials dirs 0700, holding exactly the K-WIT blob.
- **Steps:**
  - the key lives in memory only, and its PKCS#8 goes ONLY to `systemd-creds encrypt --with-key=host --name=privacy-anchor-signing-key - -`;
  - the blob is written `O_EXCL|O_NOFOLLOW` via a dir fd: `/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.privacy-anchor.cred` (0600), with fsyncs;
  - K-WIT is re-observed unchanged, else `FAILED KWIT_CHANGED`.
- **Output:** the public pin only (`LILITH_PRIVACY_KEY_PIN_V1`, K-PAN, `kpan.dev-synthetic.01`); the owner tool reads it as-is.
- **Tests:** `test_trackb_kpan_keygen.py` (5).

## Tests (main measured in the identical environment)

| Suite | Track B | origin/main | Delta |
|---|---|---|---|
| recovery-witness (WSL) | 59/59 OK | 44/44 OK | +15 new |
| authority-dev (WSL) | **244/244 OK** | 241/241 OK | +3 new |
| owner-memory-control (WSL, bundle clone with history) | 2131, failure set **identical** to main | 2114, 3 env failures | +17 new, all pass; 0 Track B-only failures |
| Core API (Windows) | 316/316 OK | 293 | +23 (B1) |

The 3 env failures on main are `mb1_finalization` / `mb3` package pins: local-history artefacts, and identical on both trees. The Track B OMC tests on Linux were 11 OK; the E-19 maintenance guard is 66 OK.

## Rehearsal candidate build + attestation (local commit; NOT the release)

- **Source:** `candidateSha` `4d8e0806301a44bddaaf352533623d19477ea0f2`, a local commit on `rehearsal/trackb-e23` in `C:/Users/edufo/lilith-trackb-rehearsal-build-20261025/build-a/src`. It is origin/main 3f6b909f + `trackb-cumulative.patch` `993ca248`, byte-identical to the worktree (41 files).
- **Build A:** Windows, Python 3.13.5, fresh clone.
- **Build B:** WSL Ubuntu-24.04, Python 3.12.3, `env -i`, git bundle.
- **Results:** the two builds are byte-identical.
  - archive `6692bb5eb6d7771027c05205a8a3d6cc98074718025e68cc17a1625117f5ef60` (5,367,656 B);
  - stamp `d6eefb1a…`; manifest `f7c39a54b882d0d0cf9a6a005d50d3d4d253ced09adfd949d52c3fe6290399bf`;
  - identity `d9ef307c04d6dfb94cb353f9d9356e6e798a914ebf5c9857b91fea0091a7ee88`.
- **Attestation:** `PR1A_BUILD_ATTESTATION=REPRODUCED`, digest `f2b1d4c851c391d9375895e2905ba0aa8056bba3f38727697a1fc367533b4e8f`. `check` PASS on Windows AND in WSL.
- **Cross-check vs the attested installed E-22 archive** (`baa31726…`, = DEV current): changed = exactly the 4 contract members, added = exactly the 2, removed = none. `E23 contract delta exact: True`. Signer modules, CLIs, lock and wheels are byte-identical.
- **Evidence:** `C:/Users/edufo/lilith-trackb-rehearsal-build-20261025/EVIDENCE-SHA256SUMS` (`a1db5c87…`).

The real E-23 NEW must be built from the merge commit of the reviewed PR and pinned by a merged owner record, exactly as E-22 was. This rehearsal proves reproducibility and the exact delta only.

## What remains (each separately authorized)

1. **Review → PR → merge.** B1+B2+B3+B4 go as one governed change, because B2 cannot land without B4. A merge = DEV deploy of the Core API; it is inert for the authority release. Then the NEW build from the merge commit + a pin PR (E-23 `NEW_RELEASE` / `NEW_MANIFEST`).
2. **E-23 live-ladder tooling** (not yet written; the E-22 pattern): `e23_release_stages` / `e23_operator` / remote tail / DR-5 target. It differs from E-22 in two ways:
   - an extra witness unit + tmpfiles stage, with the K-PAN blob present BEFORE the new unit is loaded;
   - the signer payload is unchanged, but its process must move off OLD before RETIRE.
3. **B3 live:** the K-PAN keygen on DEV (owner go), then pin `kpan.dev-synthetic.01` on the owner device and in the Core API gate keys.
4. **B5:** the f9c3 package (boot challenge/unlock and advance/publish units, the gateway freshness condition, the runner with the durability barrier).
5. **B6:** genesis + genesis checkpoint, and a whole-host rollback rehearsal on DEV.
6. **R-8:** the K-PAN rotation/compromise procedure.
