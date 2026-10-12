# Slice 15B2b-B1b-3e — M-B12 PR-B2: OS_DENIAL, SECRET_HYGIENE and PRESERVATION_SET Proof Producers

Status:

- **REPOSITORY ONLY. SOURCE AND SYNTHETIC TESTS. NOTHING RUN LIVE.** This slice adds the three proof producers that
  [PR-B1](slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md) §6 recorded as missing, and wires their exact
  transcript contracts into the PR-B1 readiness builder. No DEV or S25 contact, no transport investigation, no live
  proof collection, no P1B-10R installation, no signer start, no K-ACT load, no HELD / ledger / witness / broker
  change, no release or release-pin change (`SHARED_HASHES` and `pr1_acceptance.py` `e0928854…` unchanged).
- **No DEV transcript is accepted and none is fabricated.** `DEV_ACCEPTED_PROOF_TRANSCRIPTS` stays `{}`;
  `mb12_preservation_set_proof.ACCEPTED_BASELINES` is `{}`; every DEV build still refuses (`FRESHNESS_CUTOFF_UNDECIDED`,
  OD-M12-3). A producer PASS on DEV would still need a merged owner record before the builder admits it (OD-M12-6).
- Base: main `25bf73ebe2d58805c37f300d32ff9b521269e865` (PR #186 merge). Its deployment `38251273420` succeeded (the
  routine DEV helper deployment and service health), but it **did not establish DR-5 `W10_1` EQUAL or a fresh M-B10
  host POST**: post-PR-#186 M-B10 preservation is OUTSTANDING, not implied.
- The OD-M11-14 mapping (PROPOSED) now names a producer for all seven proof names. OD-M12-7 (scope) and OD-M12-8
  (baseline) are new and PROPOSED.

```text
producer PASS != accepted evidence (needs a merged owner record pin);  proof != authority
OS_DENIAL (unit property) != SIGNER_DENIAL (namespace probe, NOT PERFORMED)
SECRET_HYGIENE scan clean != no secret ever existed
PRESERVATION_SET equality != DR-5 equality != HELD / custody / witness / ledger preservation
```

## 1. What is added and changed

| File | Change | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb12_os_denial_proof.py` | new: OS_DENIAL producer (root, DEV, read-only) | `e67542287f869e6d8e56ee30321593424e41c964e682e5326fd8dc15a6fd8ef3` |
| `services/owner-memory-control/tools/mb12_secret_hygiene_proof.py` | new: SECRET_HYGIENE producer (`journal` root on DEV; `prove` off-host) | `a23886d91502fcdbe5b764b3a5aac9c9854762a3912fa4dccd39c2549c4ce5dc` |
| `services/owner-memory-control/tools/mb12_preservation_set_proof.py` | new: PRESERVATION_SET producer (`observe` root on DEV; `compare` off-host) | `369c854c450c4b187a8ae42d3d3b1dbe030b214c2519a95c2c284c38306e8e5f` |
| `services/owner-memory-control/tools/mb12_readiness_inputs.py` | mapping for the three names, pinned producer hashes, three exact contracts; DEV pins unchanged (empty) | `1d3b420aaadfa6301982f2057e765584a49e094aecdbb59239e8a1f64883167b` |
| `services/owner-memory-control/tests/test_b1b3e_mb12_prb2_proof_producers.py` | new: 29 synthetic tests | — |
| `services/owner-memory-control/tests/test_b1b3e_mb12_prb1_prerequisites.py` | the two assertions that the three names had no producer now expect the contracts | — |

The producers are self-contained stdlib scripts (streamable as `python3 -I -B - <form> < tool`, as the existing denial
proofs), outside the release tree. The builder loads them only after checking their pinned SHA-256, for constants and
pure functions (`main` runs under `__main__` alone).

## 2. Canonical definitions used

| Name | Package check | Definition | Source |
| --- | --- | --- | --- |
| `OS_DENIAL` | E-07 (with `SIGNER_DENIAL`) | "authority service denial of PREPARED/RETIRED: unit property + mount-namespace probe"; config level: "the installed unit bytes equal the NEW release asset and `systemctl show -p InaccessiblePaths` lists `/etc/lilith-authority-custody`"; runtime level: the namespace probe | preflight §19 E-7, §8 |
| `SECRET_HYGIENE` | E-22 | "journal, transcript, and publication scans clean for every PR-1B credential ceremony"; STOP on "any private-key pattern in output or journal" | preflight §19 E-22; B1b-3d §23 L2b |
| `PRESERVATION_SET` | E-23 | "preservation set (B1b-3d §23) unchanged: Stage III, broker, API unit"; the set: "the B1c helper, library, verifier, and sudoers; activation; the legacy broker release, selector, units, `dev.json`, and state file metadata; the Stage III artifacts; the API unit" | preflight §19 E-23; B1b-3d design §23 |

`OS_DENIAL` is taken as the **config-level half** of E-7; the runtime half is `SIGNER_DENIAL` (the custody denial
proof's 9 namespace rows, NOT PERFORMED). This resolves the PR-B1 §6 ambiguity as a proposal under OD-M11-14.

## 3. Producer contracts

### 3.1 `OS_DENIAL` — `mb12_os_denial_proof.py UNIT`

| | |
| --- | --- |
| identity / context | root on DEV, read-only; the signer may be stopped (nothing is started, reloaded, connected or decrypted) |
| observations | `systemctl show -p Id,LoadState,NeedDaemonReload,FragmentPath,DropInPaths,User,InaccessiblePaths lilith-authority-dev.service` (exactly those keys); the fragment `/etc/systemd/system/lilith-authority-dev.service` and the release asset `/opt/lilith-authority-dev/current/assets/lilith-authority-dev.service` (root-owned regular files, no symlink, bounded) |
| PASS requires | `LoadState=loaded`, `NeedDaemonReload=no`, `User=lilith-authority-dev`, `FragmentPath` = the fragment; fragment SHA-256 = `11b6d00f…` (`aee323e`) and asset bytes = fragment bytes; `DropInPaths` empty **or** exactly the P1B-10R service drop-in with its pinned bytes `e3faf9ef…`; effective `InaccessiblePaths` exactly the release's seven paths in order (including `/etc/lilith-authority-custody` and `/etc/credstore.encrypted`) |
| transcript | `UNIT:`, `FRAGMENT:`, `DROPINS: NONE` or `DROPINS: P1B-10R …`, seven `INACCESSIBLE:` lines, `OS_DENIAL_PROOF=PASS unit=lilith-authority-dev.service`; exit 0. FAIL: one `FAIL: <REASON>` row per deviation, `OS_DENIAL_PROOF=FAIL unit=…`, exit 1. Not root / wrong phase: a single `…=FAIL … reason=NOT_ROOT|USAGE` line (exit 1 / 2) |
| builder contract | PASS bytes must equal `expected_pass(NONE)` or `expected_pass(P1B-10R)` byte for byte; FAIL needs exit 1, the FAIL final line and at least one observed `FAIL:` row; a `reason=NOT_ROOT` refusal is **not** a proof result (`TRANSCRIPT_CONTRACT`) |

Limitation: the exact `systemctl show` rendering of `InaccessiblePaths` on DEV is not yet observed by this tool; a
rendering that differs from the unit's declared order fails closed (it can never pass wrongly).

### 3.2 `SECRET_HYGIENE` — `mb12_secret_hygiene_proof.py journal` and `prove <scope.json>`

| | |
| --- | --- |
| markers | `PEM_PRIVATE_KEY` (`PRIVATE KEY-----`), `OPENSSH_PRIVATE_KEY`, and the fixed Ed25519 PKCS#8 DER prefix the keygen emits (`ED25519_PKCS8_DER` raw, `_HEX` lower / upper, `_BASE64` standard and URL-safe). The source contains no marker (tested); a streaming scanner counts matches across chunk boundaries exactly once (tested at every split point) |
| `journal` | root on DEV; one read-only `journalctl --no-pager -o export` stream. PASS requires zero hits, at least one entry, and the oldest retained entry at or before `2026-10-06T08:59:59Z` (`JOURNAL_COVERAGE_NOT_AFTER_US`, the M-B2 window start = the first DEV PR-1B credential ceremony). Transcript: `JOURNAL: entries=… bytes=… sha256=… firstRealtimeUs=…`, then `JOURNAL_SECRET_SCAN=PASS coverageFromUs=…`; a rotated or volatile journal is `FAIL: JOURNAL_COVERAGE_INCOMPLETE` |
| `prove` | owner, off-host; a closed `LILITH_MB12_SECRET_HYGIENE_SCOPE` manifest: exactly the ceremonies of `PR1B_CREDENTIAL_CEREMONIES` in order, each with its required roles (M-B1: transcript + publication; M-B2: transcript + publication; M-B11: transcript), every item bound by SHA-256, plus the `journal` transcript (which must itself be an exact PASS). Transcript: `SCOPE: sha256=<manifest> ceremonies=M-B1,M-B2,M-B11`, one `ITEM: <ceremony> <role> sha256=… bytes=… CLEAN` per item, `JOURNAL_SCAN: sha256=… PASS`, `SECRET_HYGIENE_PROOF=PASS scope=<manifest>` |
| secrecy | output never contains a matched byte, an offset, an item path or key material, only marker classes and counts (tested with real PKCS#8 bytes) |
| builder contract | the scope line, only well-formed `ITEM` lines, every ceremony's required roles present, the `JOURNAL_SCAN … PASS` line, and a final line whose scope digest equals the first line; FAIL needs an observed `FAIL:` row |

Limitations: the scan finds the known encodings, not every conceivable one (nonclaim); `M-B11` has not happened, so
SECRET_HYGIENE cannot PASS before it; the ceremony scope and roles are PROPOSED (OD-M12-7); whether the DEV journal
still covers the M-B2 window after the 2026-10-09 M-R1 reboot is unknown (if not, the scan fails, by design).

### 3.3 `PRESERVATION_SET` — `mb12_preservation_set_proof.py observe` and `compare <baseline> <observation>`

| | |
| --- | --- |
| members (22, in order) | B1c helper `/usr/local/sbin/lilith-dev-deploy`, library tree `/usr/local/lib/lilith-dev-deploy`, verifier `/usr/local/sbin/lilith-activation-verify`, sudoers `/etc/sudoers.d/lilith-dev-deployer`; activation tree `/etc/lilith-os-dev`; broker releases listing and `current` selector, the three broker unit / tmpfiles files, `dev.json`, the owner and evidence DBs (metadata only); the Stage III vault tree, the dispatch / final attempt files, the authorization and its absent `.used` / arm / guard / ready paths; the API unit `/etc/systemd/system/lilith-os-api-dev.service` |
| excluded | every authority, custody, HELD, witness, ledger and credential path (`EXCLUDED_PREFIXES`; tested) |
| `observe` | root on DEV, read-only: `lstat` + bounded hash per member, never through a symlink, trees recursive with per-entry hashes, ABSENT recorded; one canonical JSON observation. An observation is evidence, never a proof |
| `compare` | owner, off-host: both documents strict and canonical with exactly the member list; the baseline SHA-256 must be in `ACCEPTED_BASELINES` (an owner-accepted observation; EMPTY → `BASELINE_NOT_ESTABLISHED`); the observation strictly later; every member equal **and** complete (an unhashable file or a truncated tree is never EQUAL). Transcript: `BASELINE:`, `OBSERVATION:`, 22 `EQUAL:` lines, the fixed `NONCLAIM:` line, `PRESERVATION_SET_PROOF=PASS baseline=<sha256>` |
| builder contract | baseline in the producer's `ACCEPTED_BASELINES`; PASS bytes equal `expected_pass(…)` rebuilt from the header; FAIL needs an observed `FAIL: CHANGED_OR_INCOMPLETE` row (a `BASELINE_NOT_ESTABLISHED` refusal is not a result) |

It does **not** use or imply DR-5 result equality, HELD / hold-store / CURRENT / credstore / witness / ledger
preservation (W10 / W11 verifiers, §24), or broker continuity (`BROKER_PRESERVATION`); the transcript states this.
The B1c helper's repository bytes equal the accepted pin (`85b260a2…`, the broker verifier's `DEPLOY_HELPER_SHA`), but
the expected values are the accepted baseline observation, never repository files: the API unit is edited in place on
the host and the existing broker verifier notes that routine B1c deployments change the API app and unit. Whether the
API unit is preserved across routine deployments (E-23) or rebaselined after each is OD-M12-8.

## 4. Builder integration and what the release verifier returns

`mb12_readiness_inputs.PROPOSED_PROOF_PRODUCERS` maps the three names to these producers;
`PRODUCER_SCRIPT_SHA256` pins their bytes; `CONTRACTS` holds the three exact checks. Admission still requires the
trust's accepted-transcript pin (`PROOF_PROVENANCE_NOT_ESTABLISHED` otherwise), so DEV admits nothing.

Synthetic end to end (TEST trust standing in for merged records; `Pr1Host`; the real root verifier): with all seven
producers' transcripts admitted and established PR-2 / PR-3, the package is NOT_READY on exactly
`E19_ACTIVATION_DARK: ACTIVATION_NOT_DARK`, the recorded release-judge defect (PR-B1 §8, OD-M12-5). No honest input
can close it without the release change.

## 5. Tests (failing / refused cases)

`test_b1b3e_mb12_prb2_proof_producers.py` (29): exact PASS transcripts for both admitted overlay states; every
OS_DENIAL deviation (missing custody path, empty list, reload pending, wrong user, foreign drop-in, P1B-10R path with
wrong bytes, fragment ≠ asset, fragment unobserved, properties unobserved); not root and wrong phase; marker
detection on real PKCS#8 bytes in all encodings and at every chunk split; journal leak (no secret echoed), rotation,
empty, unreadable, not root; scope role / ceremony missing, item digest mismatch, duplicate keys, a leak in a
publication, a failed or forged journal transcript; preservation unaccepted baseline, changed member, incomplete
member, observation not after baseline, member list not exact, non-canonical bytes; observe without root; and the
builder: forged PASS bytes, wrong exit, no-privilege transcript, a transcript from the wrong producer, an incomplete
scope, a wrong scope digest, a hand-written final line, an unaccepted baseline, unpinned provenance, a tampered
producer script, verified FAILs passing through as FAIL.

## 6. Remaining limitations and blockers (unchanged unless stated)

- DEV acceptance, confirmation and transcript pins are empty; `ACCEPTED_BASELINES` is empty (new).
- OD-M12-3 (freshness cutoff) undecided; OD-M12-6 (evidence authentication) open; OD-M12-7 (SECRET_HYGIENE scope)
  and OD-M12-8 (PRESERVATION_SET baseline and API-unit rule) PROPOSED.
- E-19 activation-line defect unfixed (release change, OD-M12-5).
- E-25 … E-28 bindings open (OD-M11-13).
- The 12 deferred P1B-12 denial checks and the 9 signer-namespace checks are NOT PERFORMED (`SIGNER_DENIAL`,
  `BROKER_DENIAL`).
- P1B-10R live installation pending; signer start and K-ACT load not authorized.
- M-B10 preservation after the PR #186 merge deploy (`38251273420`) is not freshly established (no DR-5 `W10_1` EQUAL,
  no fresh host POST).
- Live root capability for `OS_DENIAL`, `journal` and `observe` is unavailable in this slice; none was run.

## 7. State

```text
M-B12 PR-B2 PROOF PRODUCERS = REPOSITORY ONLY, READY FOR REVIEW
OS_DENIAL / SECRET_HYGIENE / PRESERVATION_SET PRODUCERS = SOURCE + SYNTHETIC TESTS;  NOT RUN ON DEV
DEV_ACCEPTED_PROOF_TRANSCRIPTS = {};  ACCEPTED_BASELINES = {};  EVERY DEV BUILD = REFUSED
E-19 = UNFIXED;  E-25 … E-28 = NOT BOUND;  P1B-12 ROWS (12) + NAMESPACE ROWS (9) = NOT PERFORMED
POST-#186 M-B10 PRESERVATION (DR-5 W10_1 EQUAL, HOST POST) = OUTSTANDING
OD-M11-12 … 15, OD-M12-1 … 8 = PROPOSED;  RELEASE aee323e / PINS / WITNESS / HELD = UNCHANGED
SIGNER START / K-ACT LOAD / AUTHORITY / FIRST MEMORY / PROD = NOT AUTHORIZED
```
