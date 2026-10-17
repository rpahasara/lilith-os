# Slice 15B2b-B1b-3e — M-B12 PR-B2: OS_DENIAL, SECRET_HYGIENE and PRESERVATION_SET Proof Producers

Status:

- **REPOSITORY ONLY. SOURCE AND SYNTHETIC TESTS. NOTHING RUN LIVE.** This slice adds the three proof producers that
  [PR-B1](slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md) §6 recorded as missing, and wires their exact
  transcript contracts into the PR-B1 readiness builder. No DEV or S25 contact, no transport investigation, no live
  proof collection, no P1B-10R installation, no signer start, no K-ACT load, no HELD / ledger / witness / broker
  change, no release or release-pin change (`SHARED_HASHES` and `pr1_acceptance.py` `e0928854…` unchanged).
- **No DEV transcript or baseline is accepted, and none is fabricated.** `DEV_ACCEPTED_PROOF_TRANSCRIPTS` stays `{}`;
  `mb12_preservation_set_proof.ACCEPTED_BASELINES` is `{}`; every DEV build still refuses (`FRESHNESS_CUTOFF_UNDECIDED`,
  OD-M12-3). SECRET_HYGIENE cannot produce a PASS on the real scope today (§3.2): M-B11 has not occurred, M-B9b's end
  time is unrecorded, and the K-ACT L2b scope question is open.
- Base: main `25bf73ebe2d58805c37f300d32ff9b521269e865` (PR #186 merge). Its deployment `38251273420` succeeded (the
  routine DEV helper deployment and service health), but it **did not establish DR-5 `W10_1` EQUAL or a fresh M-B10
  host POST**: post-PR-#186 M-B10 preservation is OUTSTANDING, not implied.
- Revised after the PR #187 owner review (CHANGES REQUIRED on `d77589e`): §8 lists the corrections.
- The OD-M11-14 mapping (PROPOSED) names a producer for all seven proof names. OD-M12-7 and OD-M12-8 (§6) are
  PROPOSED, not accepted.

```text
producer PASS != accepted evidence (needs a merged owner record pin);  proof != authority
OS_DENIAL (unit property) != SIGNER_DENIAL (namespace probe, NOT PERFORMED)
SECRET_HYGIENE clean = no specified marker in the scanned scope  !=  no secret ever leaked
PRESERVATION_SET equality != DR-5 equality != HELD / custody / witness / ledger preservation != broker continuity
```

## 1. What is added and changed

| File | Change | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb12_os_denial_proof.py` | new: OS_DENIAL producer (root, DEV, read-only) | `e67542287f869e6d8e56ee30321593424e41c964e682e5326fd8dc15a6fd8ef3` |
| `services/owner-memory-control/tools/mb12_secret_hygiene_proof.py` | new: SECRET_HYGIENE producer (`journal` root on DEV; `prove` off-host) | `251fb5409eb75693316c2dba560ea0c8446fe66e4e22a15d0a744350cc3b97de` |
| `services/owner-memory-control/tools/mb12_preservation_set_proof.py` | new: PRESERVATION_SET producer (`observe` root on DEV; `compare` off-host) | `79f47ae8f25e5d20f0066485196e910f78e3949c03dc97bebfbbf84681e485f8` |
| `services/owner-memory-control/tools/mb12_readiness_inputs.py` | mapping for the three names, pinned producer hashes, three exact contracts; DEV pins unchanged (empty) | `1d7d771a825a2e7e3b8c0186eb0b728ce0d4acf24634e7204cf8c3d4d0215fe1` |
| `services/owner-memory-control/tests/test_b1b3e_mb12_prb2_proof_producers.py` | new: 46 synthetic tests | — |
| `services/owner-memory-control/tests/test_b1b3e_mb12_prb1_prerequisites.py` | the two assertions that the three names had no producer now expect the contracts | — |

The producers are self-contained stdlib scripts, streamable as `python3 -I -B - <form> < tool` exactly like the
existing denial proofs (they need no `__file__`, no `sys.modules` entry and no repository on DEV; a test executes
each without file context), outside the release tree. The builder loads them only after checking their pinned
SHA-256, for constants and pure functions (`main` runs under `__main__` alone).

## 2. Canonical definitions used

| Name | Package check | Definition | Source |
| --- | --- | --- | --- |
| `OS_DENIAL` | E-07 (with `SIGNER_DENIAL`) | "authority service denial of PREPARED/RETIRED: unit property + mount-namespace probe"; config level: "the installed unit bytes equal the NEW release asset and `systemctl show -p InaccessiblePaths` lists `/etc/lilith-authority-custody`"; runtime level: the namespace probe | preflight §19 E-7, §8 |
| `SECRET_HYGIENE` | E-22 | "journal, transcript, and publication scans clean for every PR-1B credential ceremony"; STOP on "any private-key pattern in output or journal" | preflight §19 E-22; B1b-3d §23 L2b |
| `PRESERVATION_SET` | E-23 | "preservation set (B1b-3d §23) unchanged: Stage III, broker, API unit"; the set: "the B1c helper, library, verifier, and sudoers; activation; the legacy broker release, selector, units, `dev.json`, and state file metadata; the Stage III artifacts; the API unit" | preflight §19 E-23; B1b-3d design §23 |

`OS_DENIAL` is the **config-level half** of E-7; the runtime half is `SIGNER_DENIAL` (the custody denial proof's 9
namespace rows, NOT PERFORMED). This resolves the PR-B1 §6 ambiguity as a proposal under OD-M11-14.

## 3. Producer contracts

### 3.1 `OS_DENIAL` — `mb12_os_denial_proof.py UNIT`

| | |
| --- | --- |
| identity / context | root on DEV, read-only; the signer may be stopped (nothing is started, reloaded, connected or decrypted) |
| observations | `systemctl show -p Id,LoadState,NeedDaemonReload,FragmentPath,DropInPaths,User,InaccessiblePaths lilith-authority-dev.service` (exactly those keys, no duplicate, no other line); the fragment and the selected release asset (root-owned, not group / world writable, regular, no symlink in the last component, bounded) |
| PASS requires | `LoadState=loaded`, `NeedDaemonReload=no`, `User=lilith-authority-dev`, `FragmentPath` = the fragment; fragment SHA-256 = `11b6d00f…` (`aee323e`) and asset bytes = fragment bytes; `DropInPaths` empty **or** exactly the P1B-10R service drop-in with its pinned bytes `e3faf9ef…`; effective `InaccessiblePaths` exactly the release's seven paths in order |
| transcript | `UNIT:`, `FRAGMENT:`, `DROPINS: NONE` or `DROPINS: P1B-10R …`, seven `INACCESSIBLE:` lines, `OS_DENIAL_PROOF=PASS unit=lilith-authority-dev.service`; exit 0. FAIL: one `FAIL: <REASON>` row per deviation, `OS_DENIAL_PROOF=FAIL unit=…`, exit 1. Not root / wrong phase: a single `…=FAIL … reason=NOT_ROOT|USAGE` line (exit 1 / 2) |
| builder contract | PASS bytes equal `expected_pass(NONE)` or `expected_pass(P1B-10R)` byte for byte; FAIL needs exit 1, the FAIL final line and at least one observed `FAIL:` row; a `reason=NOT_ROOT` refusal is not a proof result |

**Live uncertainty (kept):** systemd is not guaranteed by any record here to render `InaccessiblePaths` exactly as
the unit declares it (order, separators, a `-` prefix). Missing, truncated, reordered, prefixed, duplicated or extra
values all FAIL (tested); only the first live observation can show whether the expected form is the real one. The
uncertainty can only produce a FAIL, never a wrong PASS.

### 3.2 `SECRET_HYGIENE` — `mb12_secret_hygiene_proof.py journal` and `prove <scope.json>`

**Detection contract.** Markers: `PEM_PRIVATE_KEY` (`PRIVATE KEY-----`), `OPENSSH_PRIVATE_KEY`, and the fixed Ed25519
PKCS#8 DER prefix the keygen emits, as raw bytes (`ED25519_PKCS8_DER`), hex lower / upper (`_HEX`), and base64
standard and URL-safe at **all three byte alignments** (`_BASE64`; for an offset of 1 or 2 bytes only the 4-character
groups that depend on the prefix alone are kept). A streaming scanner counts each match once across chunk boundaries.
The source contains no marker. **Outside the contract (stated, not detected):** bare 32-byte seeds, separated or
mixed-case hex, other encodings. A clean result means only "no specified marker in the scanned scope", never "no
secret ever leaked". Output never contains a matched byte, an offset, an item path or key material (tested with real
PKCS#8 bytes).

**`journal` (root, DEV).** One read-only `journalctl --no-pager -o export` stream, parsed entry by entry (text fields,
binary fields with their little-endian length, the empty line between entries), every byte scanned. Each entry needs
`__REALTIME_TIMESTAMP` and `_BOOT_ID`; a truncated stream, an oversized field (16 MiB, checked before allocation), a
malformed entry, an empty journal or a non-zero `journalctl` exit FAILS. Transcript: `JOURNAL: entries=… bytes=…
sha256=… firstRealtimeUs=… lastRealtimeUs=… boots=…`, one `BOOT: <boot_id> firstRealtimeUs=… lastRealtimeUs=…
entries=…` line per retained boot, then `JOURNAL_SECRET_SCAN=PASS firstRealtimeUs=… lastRealtimeUs=…`.

**Coverage rule (what the contract requires, and its limit).** Two endpoint timestamps prove nothing about the time in
between: a reboot with a volatile journal, or rotation, can remove a whole boot. So `prove` requires every DEV
ceremony window `[start, end]` to lie inside **one** retained boot's `[first, last]` interval. A window that spans a
boot boundary, starts before the oldest retained entry or ends after the newest one FAILS `JOURNAL_DOES_NOT_COVER`. A
journal scan taken before the last DEV ceremony (M-B11) therefore cannot satisfy it. Residual nonclaim: within one
retained boot the export cannot show entries journald itself dropped (rate limits, corruption); journald rotation
removes whole files from the oldest end, which the boot interval does reflect.

**`prove` (owner, off-host).** A closed `LILITH_MB12_SECRET_HYGIENE_SCOPE` manifest lists exactly the ceremonies of
`CEREMONIES`, in order. For each one it lists at least one `TRANSCRIPT`, exactly its named `PUBLICATION` (or none),
each bound by SHA-256, plus one `journal` transcript. It then checks:

- the canonical record exists;
- a publication with a recorded full SHA-256 is exactly that file;
- every item scans clean;
- every DEV ceremony is covered as above, and an S25 ceremony is reported `OFFHOST` (no DEV journal);
- `UNRESOLVED_SCOPE` is empty.

The transcript is `SCOPE:`, then `ITEM:`, `COVERED:` and `OFFHOST:` lines, then `JOURNAL_SCAN: … PASS` and
`SECRET_HYGIENE_PROOF=PASS scope=<manifest sha256>`.

| Ceremony | Venue | Private material | Record | Named publication (pin) | DEV window (from the record) |
| --- | --- | --- | --- | --- | --- |
| M-B1 | S25 | K-ROOT generation | `slice-15b2b-b1b3e-mb1-kroot-completion.md` | `K_ROOT_PUBLIC_EXPORT` (`740cf10a…`) | — (off-host) |
| M-B2 | DEV | K-WIT generation | `slice-15b2b-b1b3e-mb2-kwit-completion.md` | `K_WIT_PUBLICATION` (no full SHA-256 in the record) | `2026-10-06T08:45:54Z`–`09:11:38Z` |
| M-B3 | S25 | K-ROOT signs Registry V1 | `slice-15b2b-b1b3e-mb3-registry-sign-completion.md` | `SIGNED_REGISTRY_V1` (`3f0a59c0…`) | — (off-host) |
| M-B9a | DEV | first K-WIT load | `slice-15b2b-b1b3e-mb9-package-b-completion.md` | none | `2026-10-09T04:44:18Z`–`04:59:49Z` (marker `mb9a-1` to marker `mb9b`) |
| M-B9b | DEV | K-WIT signs the V2 genesis | same | `GENESIS_CHAIN_1` (`252c3220…`) | start `2026-10-09T04:59:49Z`; **end not recorded** |
| M-B11 | DEV | first K-ACT load | **none (has not occurred)** | none | **not recorded (has not occurred)** |
| B1b-3d L2b | DEV | K-ACT generation (before PR-1B) | — | — | **UNRESOLVED (OD-M12-7)** |

With the real table `prove` FAILS today with `SCOPE_DECISION_UNRESOLVED B1B3D-L2b`, `CEREMONY_RECORD_ABSENT M-B11` and
`CEREMONY_WINDOW_NOT_RECORDED M-B9b` / `M-B11` (tested). A PASS needs a reviewed source change that records those
values from owner evidence; the tests use a separate TEST_ONLY table with synthetic windows and never claim M-B11
happened. The builder admits a SECRET_HYGIENE PASS only when the pinned producer's own scope is closed, every required
line is present and the coverage windows equal the producer's table.

### 3.3 `PRESERVATION_SET` — `mb12_preservation_set_proof.py observe` and `compare <baseline> <observation>`

| | |
| --- | --- |
| members (22, in order) | B1c helper `/usr/local/sbin/lilith-dev-deploy`, library tree `/usr/local/lib/lilith-dev-deploy`, verifier `/usr/local/sbin/lilith-activation-verify`, sudoers `/etc/sudoers.d/lilith-dev-deployer`; activation tree `/etc/lilith-os-dev`; the broker **release tree** `/opt/lilith-memory-broker/releases` (every file hashed) and `current` selector, the three broker unit / tmpfiles files, `dev.json`, the owner and evidence DBs (metadata only, §23); the Stage III vault tree, the dispatch / final attempt files, the authorization and its absent `.used` / arm / guard / ready paths; the API unit `/etc/systemd/system/lilith-os-api-dev.service` |
| excluded | every authority, custody, HELD, witness, ledger and credential path (`EXCLUDED_PREFIXES`; tested) |
| `observe` | root on DEV, read-only. Each member's parent and every directory are opened `O_DIRECTORY \| O_NOFOLLOW` and walked relative to the descriptor; each entry is `lstat`-ed through it; each regular file is opened `O_NOFOLLOW \| O_NONBLOCK` through it and its `fstat` (device, inode, size, mtime, type) must equal the `lstat` before and after the read, else `IDENTITY_CHANGED` / `CHANGED_DURING_READ`; symlinks are recorded by target, never followed; sockets, FIFOs and devices are `UNSUPPORTED_TYPE`. Trees record every entry (path, type, owner, mode, size, SHA-256), so additions, removals and in-place modifications change the observation |
| bounds (`LIMITS`, per member, checked before allocation) | 64 MiB per file, 65 536 entries, 1 GiB hashed bytes, depth 32. Justification: bounded memory (≈ 200 B of JSON per entry), time and output while admitting a Python venv of tens of thousands of files. The DEV broker release tree is **not observed**: if it exceeds a bound the member is `refused` and the proof cannot pass until an owner decision; it is never truncated. The limits are part of the observation and must equal the producer's |
| `compare` | owner, off-host: both documents strict and canonical with exactly the member list and limits; the baseline SHA-256 must be in `ACCEPTED_BASELINES` (EMPTY → `BASELINE_NOT_ESTABLISHED`); the observation strictly later; every member equal **and** free of any refusal (a refused member is never EQUAL, even against the same refusal). Transcript: `BASELINE:`, `OBSERVATION:`, 22 `EQUAL:` lines, the fixed `NONCLAIM:` line, `PRESERVATION_SET_PROOF=PASS baseline=<sha256>` |
| builder contract | baseline in the producer's `ACCEPTED_BASELINES`; PASS bytes equal `expected_pass(…)` rebuilt from the header; FAIL needs an observed `FAIL: CHANGED_OR_INCOMPLETE` row (a `BASELINE_NOT_ESTABLISHED` refusal is not a result) |

**The API unit.** The routine B1c helper (`/usr/local/sbin/lilith-dev-deploy`) restarts `lilith-os-api-dev.service`,
but it does not write the unit file (it installs the application under `/home/lilith/.hermes/lilith-os-dev` as the
application user; tested against the helper source). Only the controlled break-glass boundary installer
(`install_dev_deployer_boundary.sh`) edits the unit (its one `sed` of the canonical config path). The unit file
therefore stays a protected member; the service's runtime state (restarts, InvocationID, MainPID) is not a member.
The earlier wording of this record ("routine B1c deployments change the API app and unit") was wrong for the unit
file and is withdrawn.

It does **not** use or imply DR-5 result equality, HELD / hold-store / CURRENT / credstore / witness / ledger
preservation (W10 / W11 verifiers, §24), or broker continuity (`BROKER_PRESERVATION`); the transcript states this.

## 4. Builder integration and what the release verifier returns

`mb12_readiness_inputs.PROPOSED_PROOF_PRODUCERS` maps the three names to these producers; `PRODUCER_SCRIPT_SHA256`
pins their bytes; `CONTRACTS` holds the three exact checks. Admission still requires the trust's accepted-transcript
pin (`PROOF_PROVENANCE_NOT_ESTABLISHED` otherwise), so DEV admits nothing.

Synthetic end to end (TEST trust standing in for merged records, a TEST_ONLY closed SECRET_HYGIENE scope and a TEST
accepted baseline; `Pr1Host`; the real root verifier): with all seven producers' transcripts admitted and established
PR-2 / PR-3, the package is NOT_READY on exactly `E19_ACTIVATION_DARK: ACTIVATION_NOT_DARK`. **This is a test result,
not evidence that DEV is ready:** on DEV every one of those inputs is still absent or unestablished.

## 5. Evidence-availability limitations

- **The October 6 DEV journal window may be unrecoverable.** M-B2 ran on 2026-10-06; the M-R1 reboot followed on
  2026-10-09. If the DEV journal is volatile, or rotated past 2026-10-06T08:45:54Z, no retained boot covers M-B2 and
  SECRET_HYGIENE fails `JOURNAL_DOES_NOT_COVER M-B2` permanently. The rule is not relaxed and no log is reconstructed.
  Whether the journal still covers it can be learned only by an owner-authorized read-only DEV observation; if it does
  not, only an explicit owner amendment can decide how E-22 treats M-B2's journal.
- **Unrecorded windows.** The M-B9b end time is not in the Package B record; M-B11 has not occurred. Both must be
  recorded from owner evidence before SECRET_HYGIENE can pass.
- **Retention clock.** Even a persistent journal rotates; the post-M-B11 scan must run while every DEV window is still
  retained.
- **Unobserved DEV shapes.** The `InaccessiblePaths` rendering (§3.1) and the broker release tree size (§3.3) are
  unobserved; each can only fail closed.

## 6. OD-M12-7 and OD-M12-8 (PROPOSED; not accepted)

> **OD-M12-7 (PROPOSED).** The E-22 scope is every PR-1B ceremony that generated, signed with or loaded private
> credential material: M-B1 (K-ROOT generation, S25; its transcript and `K_ROOT_PUBLIC_EXPORT` `740cf10a…`), M-B2
> (K-WIT generation, DEV; transcript and `K_WIT_PUBLICATION`), M-B3 (K-ROOT signing Registry V1, S25; transcript and
> `SIGNED_REGISTRY_V1` `3f0a59c0…`), M-B9a (first K-WIT load, DEV; transcript), M-B9b (K-WIT signing the V2 genesis,
> DEV; transcript and `GENESIS_CHAIN_1` `252c3220…`) and M-B11 (first K-ACT load, DEV; transcript), each bound to its
> canonical completion record. One DEV journal observation, taken as root after the M-B11 POST, must cover every DEV
> ceremony window inside a single retained boot, ending after M-B11's end. S25 ceremonies need no DEV journal. The
> owner decides separately whether B1b-3d L2b (K-ACT generation, before PR-1B) is included, cited from its own
> records, or excluded; until then the scope is open and no PASS is produced. M-B4 … M-B8, M-B10 and Package C handled
> no private credential material and are outside the scope.

> **OD-M12-8 (PROPOSED).** The E-23 set is the complete B1b-3d §23 set as the 22 members of
> `mb12_preservation_set_proof.MEMBERS`, with the broker release contents hashed and the API unit file protected
> (routine B1c deployments restart the service but do not write the unit). Exactly one baseline is accepted: a root
> `observe` collected in a separately authorized read-only step, after the post-PR-#186 / #187 M-B10 preservation is
> re-established (DR-5 `W10_1` EQUAL and a host POST), independently checked, and named by its SHA-256 in a merged
> owner record that pins it in `ACCEPTED_BASELINES`; a digest supplied by a caller is never a baseline. Any later
> re-baseline needs its own accepted owner record naming the documented, authorized change to a member. No DEV
> baseline is accepted today.

## 7. Remaining limitations and blockers (unchanged unless stated)

- DEV acceptance, confirmation and transcript pins are empty; `ACCEPTED_BASELINES` is empty.
- OD-M12-3 (freshness cutoff) undecided; OD-M12-6 (evidence authentication) open; OD-M12-7 / OD-M12-8 PROPOSED.
- E-19 activation-line defect unfixed (release change, OD-M12-5). E-25 … E-28 bindings open (OD-M11-13).
- The 12 deferred P1B-12 denial checks and the 9 signer-namespace checks are NOT PERFORMED.
- P1B-10R live installation pending; signer start and K-ACT load not authorized.
- M-B10 preservation after the PR #186 merge deploy (`38251273420`) is not freshly established.
- The §5 evidence-availability limitations.

## 8. PR #187 review corrections (reviewed head `d77589e`, owner decision CHANGES REQUIRED)

| # | Finding | Now | Regression tests |
| --- | --- | --- | --- |
| 1 | the SECRET_HYGIENE scope omitted M-B3, M-B9a, M-B9b | six ceremonies with venues, records and named publications; the K-ACT L2b question kept open (`UNRESOLVED_SCOPE`) | `test_omitting_m_b3_m_b9a_or_m_b9b_fails`, `test_publication_rules`, `test_the_real_scope_fails_closed_today`, `test_secret_hygiene_admission_under_a_closed_test_scope` (dropped M-B3 / M-B9a / M-B9b lines) |
| 2 | the journal transcript gave only the oldest entry; a 1970 transcript passed; endpoints were treated as coverage | export parsed per entry; per-boot first / last; each DEV window inside one retained boot; `journalctl` exit checked | `test_journal_newest_entry_before_the_last_ceremony_fails`, `test_journal_oldest_entry_after_m_b2_fails`, `test_endpoints_alone_never_prove_coverage_across_a_boot_gap`, `test_malformed_truncated_oversized_and_unfinished_streams_fail`, `test_transcript_parser_rejects_tampering` |
| 3 | the broker release was names + selector only | the release tree is hashed recursively, descriptor-relative, no-follow, bounded, refused not truncated | `test_in_place_modification_addition_and_removal_are_detected`, `test_release_contents_are_hashed_and_links_not_followed`, `test_oversized_files_trees_depth_and_unsupported_types_are_refused` |
| 4 | base64 markers only at alignment 0 | all three alignments, standard and URL-safe | `test_base64_markers_at_every_byte_alignment`, `test_outside_the_contract_is_stated_not_detected` |
| 5 | no lstat / fstat identity check; `_read_bound` read the whole file first; API-unit wording | identity checked before and after each read; bounded read; wording corrected | `test_file_identity_change_during_observation_is_refused`, `test_read_bound_is_enforced_while_reading_and_never_follows_links`, `test_routine_helper_never_writes_the_api_unit` |
| — | (found while fixing) a `@dataclass` breaks when the producer is streamed or loaded without `sys.modules`; `REPO` used `__file__` | `NamedTuple`; `REPO` optional | `test_streamed_producers_need_no_file_context` |

## 9. State

```text
M-B12 PR-B2 PROOF PRODUCERS = REPOSITORY ONLY, CORRECTED FOR OWNER RE-REVIEW
OS_DENIAL / SECRET_HYGIENE / PRESERVATION_SET PRODUCERS = SOURCE + SYNTHETIC TESTS;  NOT RUN ON DEV
SECRET_HYGIENE REAL SCOPE = OPEN (B1B3D-L2b), M-B11 NOT OCCURRED, M-B9b END NOT RECORDED  ->  NO PASS POSSIBLE
DEV_ACCEPTED_PROOF_TRANSCRIPTS = {};  ACCEPTED_BASELINES = {};  EVERY DEV BUILD = REFUSED
E-19 = UNFIXED;  E-25 … E-28 = NOT BOUND;  P1B-12 ROWS (12) + NAMESPACE ROWS (9) = NOT PERFORMED
POST-#186 M-B10 PRESERVATION (DR-5 W10_1 EQUAL, HOST POST) = OUTSTANDING;  OCT-6 JOURNAL AVAILABILITY = UNKNOWN
OD-M11-12 … 15, OD-M12-1 … 8 = PROPOSED;  RELEASE aee323e / PINS / WITNESS / HELD = UNCHANGED
SIGNER START / K-ACT LOAD / AUTHORITY / FIRST MEMORY / PROD = NOT AUTHORIZED
```

## 10. Addendum (2026-10-17): M-B12 status checkpoint

Consolidated record of the M-B12 developments since §9. Earlier sections are unchanged and keep their historical meaning.
This addendum records evidence and dispositions; it makes **no new owner acceptance** and claims no unresolved proof.
Evidence directories are owner-laptop paths under `C:\Users\edufo\`; each is sealed by its `SHA256SUMS`.

### 10.1 E-22 secret hygiene: investigation closed, FAIL stands

| Step | Evidence (`SHA256SUMS`) | Result |
| --- | --- | --- |
| journal scan (`mb12_secret_hygiene_proof.py journal`, 2026-10-15 16:43–16:47Z) | `lilith-mb12-hygiene-f619a07` (`0c236f8635222556c00d9a38b731459e033903747e39bc6c05f44c8ab08ea2e3`) | `JOURNAL_SECRET_SCAN=FAIL`, `PEM_PRIVATE_KEY` count 12 (transcript `e1d70588…`) |
| marker attribution (`attribute`, 2026-10-15 17:54–18:02Z) | `lilith-mb12-attribute-0420ca6` (`dce427ad3c57b677a2cfe33d0cf2d8d414cd67d35b06ffe41150d66c55ae6091`) | all 12 in closed boot `24d1771d…`, three `sudo` sessions (`session-3837/3845/3850.scope`, 2026-09-27 07:19–07:26Z), 4 per session, role `OTHER`, verdict `UNKNOWN` ×12 |
| session purpose (`purpose`, 2026-10-16 13:14Z, PR #204 form) | `lilith-mb12-purpose-ef64037` (`8bda5cbb5684eb08d133a4d4b062503c6a9bb27e7dd6f05641ad408f1d62d310`) | `PURPOSE_VERIFICATION=COMPLETE literal=0 exposed=0 unknown=3`; bounded stream 14 entries / `31be8203…` |

Per session the purpose form found `program=GREP`, `operand=PUBLICATION_JSON` (`/root/b1b3d-l2b-publication.json`),
`pemBlock=NO`, `keyLikeRun=NO`, `otherMarkers=NO`, `patternArgument=NO` (unreachable for the PEM marker by design, §14
of the operator record), `cmdlineConsistent=NO`, verdict `UNKNOWN`.

**Disposition (owner, 2026-10-16): technical investigation CLOSED.** The structure is strongly consistent with an
owner-run grep of the L2b publication file for the PEM marker during the L2b.2 post-keygen checks, but that explanation
is **not verified**. No additional key indicator was found. The original `JOURNAL_SECRET_SCAN=FAIL` remains
authoritative, no exception is granted, and **E-22 stays BLOCKED**. Changing E-22 needs an explicit owner decision on
its scope (OD-M12-7). Local assessment: `lilith-mb12-e22-assessment-ef64037\ASSESSMENT.md`
(`8b1a175920b2ff9e4f1cd576f32487d07a38e8c8c9a064dd5199e92fc9329e6d`). No further investigation tooling or scans.

### 10.2 E-07 / E-09 denial proofs and OD-M12-6

One owner-authorized read-only `e07` run (2026-10-16T15:40Z, main `ef640377`, deploy `38854041173`; evidence
`lilith-mb12-e07-ef64037`, `SHA256SUMS` `29c5a575ca7950207cbbc242c4f149ea70dd7d75753bbc168970a0ec33ca1674`) gave
`AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-12` (143 DENIED incl. the 9 signer-namespace rows; 0 allowed) and
`OS_DENIAL_PROOF=PASS`. **OD-M12-6** (owner-accepted 2026-10-16) and the three transcript pins are recorded in
`slice-15b2b-b1b3e-mb11-signer-start-operator.md` §15, merged by PR #205 (`5994f6a5`). That record is authoritative;
it is not repeated here. The P1B-12 and namespace rows that §9 lists as NOT PERFORMED are now performed for this
transcript.

### 10.3 E-09 broker preservation (owner-accepted 2026-10-17)

One owner-authorized read-only `verify_broker_dev_current_incarnation.py preservation` run (2026-10-17T08:28Z, deploy
`39013841952`; evidence `lilith-mb12-broker-pres-5994f6a`, `SHA256SUMS`
`8772d463f02a7415eb04e69f4f4b66451f94b2c6f52e4d8138662ab3f8c94ec5`) gave `BROKER_PRESERVATION=PASS`, `failures` `[]`,
transcript `79387fe7d1db1e7eab0d8e508991656ba195d284cefac3889ffff9595f221c40`. The owner accepted that transcript, for
that proof name only, under OD-M12-6; the record and pin are `slice-15b2b-b1b3e-mb11-signer-start-operator.md` §16.
E-09 now has both halves pinned (`BROKER_DENIAL` §15, `BROKER_PRESERVATION` §16).

### 10.4 M-B11 preservation checkpoint (after PR #205)

Deploy `39013841952` (main `5994f6a53bbf7cc3c7d53abe87e17552d6f9fb1b`, success 2026-10-17T07:35:28Z): local W11 DR-5
compare `W11_1_SIGNER_STARTED_EXACT` → `EQUAL` (194 / 155 / 29 lines, fail 0; evidence `lilith-mb11-pr205-dr5-5994f6a`,
`009f9c5616723e55a125bae6ace364d92b468d4d5b2d2598435ea9dbf7485ede`). One owner-authorized `mb11_operator observe`
(07:53:17–07:53:36Z) → `observe/05-POST11` `MB11_OBSERVE_W11_1_EXACT`, `kActLoadCount` 1, reasons `[]`, remote output
`ff9c8ce79147d61c01c4c4bf52f97b411e06fc1a1981989ad17e722b617b36d5` = the accepted POST11 (evidence
`lilith-mb11-observe05-5994f6a`, `42cdd0192c4a449e6b0288394093985113e0348078aaeefbfceb4cd6b66ef792`). `01`–`04-POST11` and
the start seal are unchanged. Routine checkpoints after this one are kept as evidence only, not as repository records.

### 10.5 Remaining requirements

| Item | Status | Needs |
| --- | --- | --- |
| E-08 `DEPLOYER_DENIAL` | no admissible transcript: `deploy-dev.yml` tees the DR-5 stdout to `${RUNNER_TEMP}/authority-boundary.txt` but does not retain it; the GitHub log is not producer bytes | a reviewed retention of that file on a routine deploy, then an OD-M12-6 pin |
| E-20 PR-2 inventory | not collected; `DEV_ACCEPTED_INVENTORIES = {}` | a fresh inventory under the OD-M12-3 cutoff and an owner acceptance by digest (OD-M12-2) |
| E-21 PR-3 off-host material | not confirmed; `DEV_ACCEPTED_CANDIDATES = {}` | the owner off-host material and confirmation by candidate digest (OD-M12-4) |
| E-22 `SECRET_HYGIENE` | BLOCKED (§10.1) | owner decision on scope (OD-M12-7) |
| E-23 `PRESERVATION_SET` | no accepted baseline | OD-M12-8 |

Open owner decisions: OD-M12-1, OD-M12-2, OD-M12-4, OD-M12-7, OD-M12-8, OD-M11-12; OD-M11-14 for the three names not
covered by §15 / §16.

```text
E-07 SIGNER/OS_DENIAL, E-09 BROKER_DENIAL + BROKER_PRESERVATION = TRANSCRIPTS PINNED (OD-M12-6, §15 / §16)
E-08 = NO BYTE-EXACT TRANSCRIPT;  E-20 / E-21 / E-23 = OPEN;  E-22 = BLOCKED (JOURNAL_SECRET_SCAN=FAIL authoritative)
M-B11 = W11_1 PRESERVED (05-POST11 EXACT, DR-5 EQUAL at 39013841952);  M-B12 = NOT PASSED;  CUSTODY = HELD
AUTHORITY / FIRST MEMORY / PROD = NOT AUTHORIZED
```

## 11. Addendum (2026-10-17): OD-M12-8 accepted with one amendment; first E-23 baseline candidate

Earlier sections keep their historical meaning; this addendum supersedes the §6 / §9 / §10.5 status of OD-M12-8 only.
It is an established owner decision once reviewed and merged.

**OD-M12-8 ACCEPTED (owner, 2026-10-17)** as proposed in §6, with only the historical-state prerequisite amended. The
text "(DR-5 `W10_1` EQUAL and a host POST)" is replaced by:

> (on DEV's current accepted phase: DR-5 `W11_1_SIGNER_STARTED_EXACT` EQUAL on the immediately preceding successful
> routine deployment, followed by one exact `mb11_operator observe`; the M-B10 preservation history remains
> established by the accepted E-19 U5 and W11_0 records)

Everything else stands: exactly the 22 B1b-3d §23 members of `mb12_preservation_set_proof.MEMBERS`, the producer and its
`LIMITS`, the authority / custody / credential exclusions, exactly one independently verified baseline pinned in
`ACCEPTED_BASELINES` only by a merged owner record, a later observation strictly after the baseline, and any
re-baseline only by its own accepted owner record. **Why:** PR #186 / #187 merged on 2026-10-12. E-19 then replaced the
release and M-B11 started the signer, so a `W10_1` DR-5 text and the stopped-signer host POST no longer exist. The
M-B10 HELD preservation after #186 / #187 is carried by accepted records: the E-19 U5 host POSTs and DR-5 EQUAL
(`slice-15b2b-b1b3e-e19-completion-record.md`, owner-accepted in `slice-15b2b-b1b3e-e19-completion-acceptance.md`) and the 2026-10-15 03:54:40Z W11_0 gate (`w10PhaseDirect`
`W10_1_HELD_EXACT`; `slice-15b2b-b1b3e-mb11-signer-start-acceptance.md` §2). Those records are referenced, not rewritten.

### 11.1 Amended prerequisite, met (2026-10-17)

| Step | Evidence (`SHA256SUMS`) | Result |
| --- | --- | --- |
| routine deploy `39024555994` (main `c149c0cb`, PR #207) | `lilith-mb11-pr207-dr5-c149c0c` (`c498141e5023379af86c7c38ce30735a0bc0dd2f0d25965ac086f4f3e9cefb57`) | local DR-5 `W11_1_SIGNER_STARTED_EXACT` EQUAL, 194 / 155 / 29, 0 failures |
| one owner-authorized `mb11_operator observe`, 10:35:19–10:35:38Z | `lilith-mb11-observe06-c149c0c` (`7fcddacd6314a82d13857cc3da8fad35752e75bddca94a8e7248d835b52fde51`) | `06-POST11` `MB11_OBSERVE_W11_1_EXACT`, K-ACT load count 1, reasons `[]`, output `ff9c8ce7…` = the accepted POST11 |

### 11.2 First E-23 baseline candidate (NOT accepted)

One owner-authorized root read-only `mb12_preservation_set_proof.py observe` (producer `79f47ae8…`, readiness-pinned),
streamed hash-gated over the existing route, 2026-10-17T10:37:49Z: rc 0, stderr empty, no other DEV operation.

| Item | Value |
| --- | --- |
| observation SHA-256 | `019e0117baaa7bd920b78047fb0ddcb6c49318bfd3a2d30d9dd134b98f78a0b5` (485 064 bytes, `observedAt` `2026-10-17T10:38:08Z`) |
| members | 22, exact order, all complete (no `refused`); the broker DBs are metadata only |
| absent | `STAGE3_AUTHORIZATION_USED`, `STAGE3_ARM`, `STAGE3_GUARD`, `STAGE3_ACTIVATION_READY`: the unused / un-armed Stage III runtime paths (§3.3) |
| bounds | largest member `BROKER_RELEASES`: 3 212 entries, 2 822 files, 74 184 653 bytes (limits 65 536 / 1 GiB / 64 MiB per file); selector → `releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2` |
| evidence | `lilith-mb12-e23-baseline-c149c0c`, `SHA256SUMS` `1698571bd852b5f69ac9e327a84fb4c270c0cdd4b20a15e53d446c1c1ae07714` (original stdout bytes, preflight, driver, independent local verification 12/12) |

The candidate is **eligible** for owner acceptance: canonical, exact members, within bounds, no refusal and expected
absences only. It is **not** a baseline. `ACCEPTED_BASELINES` stays `{}` until an owner record names this SHA-256 and
a merged change pins it. E-23 then still needs a later, independent `observe` (strictly after `10:38:08Z`, normally
after a later routine deploy) and an off-host `compare` PASS, whose transcript is admitted under OD-M12-6. No
`compare` has been run, and no later observation exists.

### 11.3 E-23 baseline owner-accepted (2026-10-17)

**Owner decision (2026-10-17T10:53:18Z):** "I accept E-23 baseline observation
`019e0117baaa7bd920b78047fb0ddcb6c49318bfd3a2d30d9dd134b98f78a0b5` under OD-M12-8." The evidence was re-verified
before recording (`SHA256SUMS` `1698571b…`, observation bytes `019e0117…`, local verification PASS). Owner acceptance
record: `lilith-mb12-e23-acceptance-c149c0c\OWNER-ACCEPTANCE-RECORD.txt`, SHA-256
`d4359c02c8953208c4e629b5df5d0120a4385d73741a61998de8749a60c8b47e` (`SHA256SUMS` `1822674b…`; the decision verbatim,
its scope and the bound evidence; never self-referential).

Source pin: `mb12_preservation_set_proof.ACCEPTED_BASELINES = {019e0117… → d4359c02…}` (exactly one entry). Pin
cascade: `mb12_preservation_set_proof.py` `79f47ae8…` → `8b659beed2e50de6c62464cb273f1beac3d86a764750eb422b6276f42af7dde0`,
re-pinned in `mb12_readiness_inputs.PRODUCER_SCRIPT_SHA256`; `mb12_readiness_inputs.py` `74c2af17…` →
`73d68e618f9cfd03485573489c16c239d9c525a751853490173a3af412d7f799`; `mb11_operator.py` `9d73888f…` →
`a8efd3130828cb0d0d81d7af2c57ddabf8b5eef1efc1f4d528af11498749ddfd` (operator record §17). It takes effect on merge.

This is the E-23 baseline only, not a `PRESERVATION_SET` proof. E-23 still needs one later, independent root `observe`
(strictly after `2026-10-17T10:38:08Z`, normally after the next routine deploy) and an off-host
`compare <baseline> <observation>` PASS. Its transcript must then be pinned under OD-M12-6 before E-23 is admitted.

```text
OD-M12-8 = ACCEPTED (amended prerequisite);  E-23 BASELINE = 019e0117… OWNER-ACCEPTED (→ d4359c02…), EFFECTIVE ON MERGE
E-23 COMPARE = NOT RUN (needs a later observe);  E-07 / E-09 / E-20 = ACCEPTED (pins unchanged)
E-08 / E-21 = OPEN;  E-22 = BLOCKED (JOURNAL_SECRET_SCAN=FAIL authoritative)
M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```

## 12. Addendum (2026-10-17): E-23 `PRESERVATION_SET` transcript accepted under OD-M12-6

**Owner decision (2026-10-17):** under OD-M12-6, the owner accepts exactly one `PRESERVATION_SET` transcript,
`4692f3bae979aca82782a66605a3235939420223aa7841a931ad9a473f1e863e`, conditional on a final local verification, which
passed (18/18) before this record. The OD-M11-14 mapping is accepted for `PRESERVATION_SET` only. `DEPLOYER_DENIAL` and
`SECRET_HYGIENE` stay PROPOSED and unpinned. The decision grants no authority or custody release, and does not
complete M-B12.

| Item | Value |
| --- | --- |
| producer | `mb12_preservation_set_proof.py:compare` (`8b659beed2e50de6c62464cb273f1beac3d86a764750eb422b6276f42af7dde0`, main `c2cbb2d9`; byte-identical copy run in WSL, so LF stdout is exact) |
| baseline | `019e0117baaa7bd920b78047fb0ddcb6c49318bfd3a2d30d9dd134b98f78a0b5` (`2026-10-17T10:38:08Z`; pinned → `d4359c02…`, §11.3); evidence `lilith-mb12-e23-baseline-c149c0c` (`SHA256SUMS` `1698571b…`) |
| later observation | `5218f4af2e726cbdf5de8e7163059336f282c21739b88bf0459421408e6cca67` (`2026-10-17T11:15:43Z`, one owner-authorized root `observe` after deploy `39027536040`, DR-5 W11_1 EQUAL `0837d255…`); evidence `lilith-mb12-e23-observe-c2cbb2d` (`SHA256SUMS` `45aff903857f63c91944eca0403ce4510db80bf2d6a6db75e7d40373ec97d16f`) |
| transcript | 1 941 bytes: 22 `EQUAL` lines, `PRESERVATION_SET_PROOF=PASS`; exit 0, stderr empty (from the preserved `compare.rc` / `compare.err`); byte-identical to `expected_pass(…)`; `mb12_readiness_inputs.CONTRACTS` → `PASS` |
| evidence | `lilith-e23-compare-c2cbb2d`, `SHA256SUMS` `fc4d53913f35de77a71eb3ab9e60f7b5166bcdaa7e4980b5788dce869b7e8ce6` |

Source pin: `mb12_readiness_inputs.DEV_ACCEPTED_PROOF_TRANSCRIPTS["PRESERVATION_SET"] = {4692f3ba…}`. The four earlier
bindings are unchanged. The baseline and the producer are unchanged. Pin cascade: operator record §18.

Still outstanding (separate, unchanged): E-08 `DEPLOYER_DENIAL` (no byte-exact transcript retained), E-22
`SECRET_HYGIENE` (BLOCKED; `JOURNAL_SECRET_SCAN=FAIL` authoritative; OD-M12-7), E-21 (PR-3 material confirmation,
OD-M12-4) and E-25 … E-28 (OD-M11-13). E-23 PASS is not package READY.

```text
E-07 / E-09 / E-20 / E-23 = OWNER-ACCEPTED EVIDENCE PINNED;  E-08 / E-21 = OPEN;  E-22 = BLOCKED
M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```
