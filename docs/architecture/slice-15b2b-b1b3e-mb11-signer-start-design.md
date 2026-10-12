# Slice 15B2b-B1b-3e — M-B11 / START_SIGNER: Design Record and W11 Verification (Repository Only)

Status:

- **DESIGN AND VERIFICATION TOOLING ONLY. NOT RUN.** This record defines what M-B11 is, the W11 host classification,
  the post-start DR-5 targets and the proposed owner decisions. It adds a read-only W11 verifier, a DR-5 target tool
  and synthetic tests. It adds **no** start-capable operator, changes no unit, release, installer or workflow, and
  contacted no live system.
- **Every OD-M11 decision below is PROPOSED. None is accepted.** The owner accepted only the design direction of the
  M-B11 review (2026-10-12): M-B11 is `START_SIGNER` after HELD; HEALTH, root HOLD_RELEASE_ELIGIBILITY and root
  FULL_READINESS are separate evaluations; a single controlled service start; socket-first startup rejected; one owner
  go and a consumed attempt; a startup supervisor is **not** a lifetime bound on K-ACT loads.
- **LIVE STARTUP BLOCKER.** A proven restart and socket-reactivation bound is required before any live M-B11 start.
  The mechanism is an open owner decision (§6, OD-M11-11). Nothing in this slice provides it.
- M-B11 itself, Registry V1 effectiveness, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.

```text
signer started != signer verified != readiness != signing permission != Registry effective != authority active
HEALTH (B4) = a signer claim;  B1 = B2 = B3 = B4 (+ B5, B6) = the binding;  root readiness != owner acceptance
one owner go != one operator invocation != one K-ACT load;  a 4-second supervisor != a lifetime bound
stopped after the first K-ACT load != W10_1 (the load is a permanent custody fact);  UNKNOWN != success
derived DR-5 target != accepted baseline;  DR-5 EQUAL != signer evidence
```

## 1. Canonical purpose and sources

| Source | Definition |
| --- | --- |
| [PR-1 preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md) §27, row M-B11 | systemd starts the signer socket/service, **not enabled**. POST: `HEALTH B4 = B3`; `NOT_READY` with only the hold reason. Rollback: stop. Authority: none. Custody: **K-ACT loaded (first time)**. STOP if B4 ≠ B3 or any other reason |
| [P3-5 sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §3, step 13 | `START_SIGNER`: `INITIAL_CUSTODY_HELD` → `SIGNER_STARTED`; no PONR; `REQUIRED_CURRENT` + `ACCEPTANCE_COMPLETE`; the first start journals nothing (§4.4); HELD must precede it (§15.4) |
| `pr1b_sequencing.STEPS` | evidence keys `healthB4EqualsB3`, `notReadyOnlyHoldReason`, `signerNotEnabled` |
| preflight §25 | the signer starts for the first time in PR-1B, after the ledger, the V2 genesis and HELD; never enabled (T-5) |

M-B11 is **signer startup only**. It is not credential provisioning (the CURRENT blob exists since B1b-3d L2b and
must stay identical), not installation (release `aee323e` is installed inert; no release change is part of M-B11),
not eligibility (M-B12), not RELEASED (M-B14), not Registry effectiveness (step 17 only), not issuance (RR-39: refused
even at FULL_READINESS) and not activation (a separate dark grant, `GRANT_ABSENT`, throughout PR-1).

## 2. Accepted starting state and custody bindings

The starting state is the accepted M-B10 world: `W10_1_HELD_EXACT`, HELD `1ee1b7d5….json` /
`c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d` bound to the committed genesis
`ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`, the first post-freeze deploy `EQUAL`
([addendum](slice-15b2b-b1b3e-mb10-first-post-freeze-deploy.md)), signer inactive, credentials and socket absent.
Historical verification is not proof of an unchanged live host: a fresh read-only rebaseline precedes any M-B11 gate.

| Binding | Value (repository record) | Nature |
| --- | --- | --- |
| B1 | the single current key of Registry V1 at the witnessed head (`test-only.dev-synthetic.actor.b1b3d.1`) | root-reproduced |
| B2 | CURRENT blob SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3` (preflight B-5, §24) | root-observed, never decrypted |
| B3 | K-ACT publication `publicKeySha256 = dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed`; publication file SHA-256 `d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032` ([M-B3 completion](slice-15b2b-b1b3e-mb3-registry-sign-completion.md)) | owner record |
| B4 | HEALTH `publicKeySha256` | **signer claim** |
| B5 | exactly one `LoadCredentialEncrypted=owner-actor-signing-key:<CURRENT>` in the installed unit | root-observed |
| B6 | credential inventory `STEADY` (credstore = CURRENT only) | root-observed |

## 3. The first K-ACT load

systemd decrypts the CURRENT blob with the host key into `/run/credentials/lilith-authority-dev.service` on **every
service exec attempt**, before the signer's Python runs; the signer then derives B4 from it and drops its key
reference (process-memory zeroization **NOT_PROVEN**). Consequences:

- the first load closes L2 U5 (blob decrypts to the published key) only if B4 = B3; a decrypt failure or B4 ≠ B3 is a
  custody incident (HALT);
- the load is a permanent custody fact: after a stop, the host files look like W10_1 again, but the world is not
  W10_1. The W11 classifier never maps a stopped-after-load host to the pre-start phase;
- a Python refusal (exit 2 identity / environment, 3 absent, 4 invalid) happens **after** a load.

| Count | What it is |
| --- | --- |
| one owner go (D2) | authorizes one operator start invocation |
| one operator invocation | `systemctl start lilith-authority-dev.service` (starts the socket in the same transaction) |
| K-ACT loads | one per service exec attempt: the initial exec, every automatic restart, every socket-triggered activation. Counted from the journal invocation set, never inferred from the go |

## 4. HEALTH and readiness are separate evaluations

| Evaluator | Source | Sees HELD? |
| --- | --- | --- |
| signer HEALTH (B4, a claim) | `core.health()` + `state.self_view` | **no** (`InaccessiblePaths`); identical with or without HELD |
| root HOLD_RELEASE_ELIGIBILITY / FULL_READINESS | `successor_readiness` via the release root verifier | yes, over the complete hold observation |
| PR-1 package E-01 … E-24 | `pr1_acceptance` | wraps readiness (E-17) and adds PR-2 / PR-3 and the proofs |

In FULL mode `hold_binding_reason` returns `CEREMONY_HOLD_HELD` before it checks the binding; only ELIGIBILITY READY
proves the HELD binding (kind, ceremony, successor, genesis witness). Expected results (the synthetic column names the
test that proves it on the synthetic PR-1 host with the REAL signer core and the REAL root verifier):

| State | Signer HEALTH | ELIGIBILITY | FULL | Synthetic proof |
| --- | --- | --- | --- | --- |
| A signer stopped, HELD exact | unavailable (no socket; nothing connects) | `LOADED_KEY_BINDING:BINDING_INPUT_MISSING` (detail `B4_HEALTH`) | that, plus `CEREMONY_HOLD:CEREMONY_HOLD_HELD` | `test_a_stopped_signer_misses_only_the_binding_input` |
| B signer running, HELD exact, K-ACT loaded | exactly H (§5) | READY, `()` | exactly `CEREMONY_HOLD:CEREMONY_HOLD_HELD` | `test_real_core_health_over_the_owner_socket_is_exactly_h`, `test_e_and_f_with_the_real_health_and_the_real_root_verifier` |
| C as B, PR-2 / PR-3 absent | as B | READY | as B | package fails exactly E18, E20, E21 (recorded, not judged at M-B11) |
| D as B, every package input present | as B | READY; package READY | as B; package E16 / E17 fail | `test_after_the_canonical_release_…` (approval step) |
| E after the canonical RELEASED (M-B14) | unchanged (never READY) | `CEREMONY_HOLD:HOLD_NOT_HELD` | READY; fact `issuanceReady: true` is a **name only**: issuance stays unwired | `test_after_the_canonical_release_full_readiness_is_outside_m_b11_and_halts_the_darkness_check` |

## 5. OD-M11-1 (PROPOSED): the testable POST conditions

Over one root observation after the start, bound to the observed signer InvocationID and MainPID:

- **H (HEALTH, a claim):** status OK; exactly the fields `profile`, `signingDomain`, `foundation`, `service`,
  `credential`, `publicKeySha256`, `signing`, `readiness`, `reasons`; `profile=DEV_SYNTHETIC`,
  `signingDomain=OWNER_ACTOR`, `foundation=B1B3D_L1_SOURCE_FOUNDATION`, `service=SERVICE_AVAILABLE`,
  `credential=CREDENTIAL_PRESENT_UNVERIFIED`, `publicKeySha256` = B3, `signing=SIGNING_NOT_AVAILABLE`,
  `readiness=NOT_READY`, and `reasons` exactly, in order, `CREDENTIAL_INVENTORY_UNOBSERVABLE_BY_SIGNER`,
  `HOLD_STORE_UNOBSERVABLE_BY_SIGNER`, `ISSUANCE_UNWIRED`.
- **E (binding):** root HOLD_RELEASE_ELIGIBILITY over the complete hold observation is READY with no reason,
  including `LOADED_KEY_BINDING` PASS (B1 = B2 = B3 = B4, B5, B6).
- **F (hold):** root FULL_READINESS over the same observation and the same captured HEALTH has exactly the reason
  `CEREMONY_HOLD:CEREMONY_HOLD_HELD`, with detail `INITIAL_CUSTODY_BOOTSTRAP`.
- **G (darkness):** every result has `authorityGranted=false`, `liveEntryAuthorized=false`; FULL facts
  `issuanceReady=false`, `successorCurrent=false`; package flags `authorityGranted`, `activationGranted`,
  `issuanceWired` false.

`healthB4EqualsB3` = H(fingerprint) ∧ E; `notReadyOnlyHoldReason` = H(reasons) ∧ E ∧ F ∧ G. The PR-1 package E-level
results are recorded, not judged (M-B12 / M-B13 own them). Any other value is STOP; READY or signing available is
HALT. This needs a wording erratum to the preflight §27 M-B11 row, not a code change. These are design targets
proven on synthetic hosts, **not** evidence of live readiness.

## 6. Startup, restart and socket reactivation (OPEN; live startup blocker)

From the installed unit and socket (release assets, unchanged; asserted by
`test_the_signer_unit_and_socket_are_the_release_assets`): `Restart=on-failure`, `RestartSec=5s`,
`StartLimitIntervalSec=60`, `StartLimitBurst=3`, `Accept=no`, `TriggerLimitBurst=3`, no `[Install]`. Documented
systemd behaviour, **not yet proven on a systemd runner**:

- a decrypt failure fails the exec with `243/CREDENTIALS`; exit codes 2 / 3 / 4 / 243 all trigger `on-failure`;
- in a fast failure loop the start limit allows at most 3 exec attempts (3 loads) per 60 s, then `start-limit-hit`;
  crashes spaced beyond the window restart again, so the lifetime count is **unbounded**;
- with `Accept=no`, any connection to a listening socket while the service is inactive starts it and loads K-ACT.
  **Socket-first startup is rejected** (owner direction): it merges the load into the first connection;
- `systemctl stop` cancels a pending auto-restart; stopping the socket stops the service (`Requires=`).

A startup supervisor reacting within seconds is **not** accepted as a lifetime bound (owner direction). Candidate
mechanisms, each needing a decision and a systemd-runner proof (OD-M11-11); none is implemented here:

| Candidate | Bound | Cost / risk |
| --- | --- | --- |
| release change: `RestartPreventExitStatus=2 3 4 243` (crash restarts kept) or `Restart=no`, and a socket that cannot reactivate a stopped service | hard, in the unit | a new reviewed release and a PR-1A-style upgrade with re-pins (E-1, unit bytes, DR-5 preservation) |
| runtime drop-in under `/run/systemd/system/lilith-authority-dev.service.d/` (`Restart=no`) | hard until reboot | the effective unit differs from the release asset (E-6, `DropInPaths`); a host mutation and a daemon-reload |
| runtime mask after one verified start (`systemctl mask --runtime`) | blocks later starts and socket activation until reboot | `UnitFileState` becomes `masked-runtime` (installer and W11 expect `static`); a host mutation |
| supervisor plus detection only | detects, does not prevent | rejected as a bound |

**Systemd-runner dependency.** A meaningful proof needs a disposable runner with systemd as PID 1 (for example an
ephemeral GitHub-hosted Ubuntu 24.04 runner, systemd 255): a synthetic copy of the unit with a dummy credential
encrypted under the runner's own host key and a failing `ExecStart`, counting `_SYSTEMD_INVOCATION_ID` values per
start, the start-limit and trigger-limit behaviour, stop cancellation of auto-restart, and socket-only activation.
That requires a privileged workflow job. **None is added in this slice**; it needs its own review. WSL here has no
systemd. Until that proof and OD-M11-11 exist, live startup stays blocked.

## 7. W11 classification (`mb11_signer_verifier.py`)

Read-only. It never opens, connects to or binds a socket (a connection could start the service), never reads a
credential (names and metadata only), runs only `systemctl show` and `journalctl`, and writes nothing. It runs the
unchanged W10 verifier twice: once directly (`w10PhaseDirect`, `W10_SIGNER_OR_LATER_STATE` while the signer runs) and
once with only the signer side judged here (`w10PhaseSignerJudgedSeparately`: the two signer runtime paths read as
absent, the two signer units as inactive, loaded and static). The substitution must be consulted or the result is
`UNCLASSIFIED_STOP`. HEALTH is supplied evidence captured elsewhere and bound to InvocationID / MainPID before and after
the capture; E and F are computed by the release root verifier over that same HEALTH.

| Phase | Exactly when | Route | Fact or claim |
| --- | --- | --- | --- |
| `W11_0_PRE_SIGNER_EXACT` | W10 (signer judged here) = W10_1; signer stopped; journal complete with no invocation; no load recorded | gate and go only after the restart bound is proven | observed |
| `W11_1_SIGNER_STARTED_EXACT` | W10_1; signer running (service running, socket listening); one LOADED invocation = the running one; `NRestarts=0`; HEALTH bound to it and exactly H; E, F, G; process cwd `releases/aee323e…`, argv the unit's `ExecStart`, signer uid / gid; credentials directory with exactly one name; owner socket `root:root 0600`; ledger bytes = baseline, no sidecar | SAFE_ADOPT (POST11, owner acceptance; authorizes nothing further) | H = claim; E / F / G / units / paths / ledger = observed |
| `W11_1S_STOPPED_AFTER_FIRST_LOAD` | W10_1; signer stopped cleanly; exactly one load recorded and in the journal | forward only: any restart is a new load and a new go | observed |
| `W11_HOLD_NOT_EXACT` | any W10 hold HALT (malformed, misbound, unexpected, foreign) | HALT | observed |
| `W11_LEDGER_CHANGED` | the logical ledger not exact (W9 / M-B6), WAL frames, a foreign entry, or DB bytes ≠ baseline with no sidecar | HALT | observed |
| `W11_KEY_MISMATCH` | HEALTH fingerprint ≠ B3, or the binding fails with a key / blob / publication mismatch | HALT; pre-authorized safe stop only (OD-M11-4) | claim + observed |
| `W11_CREDENTIAL_FAILED` | a journal credential setup failure, `ExecMainStatus` 3 / 4 / 243, or HEALTH `CREDENTIAL_ABSENT` / `CREDENTIAL_INVALID` | HALT; attempt consumed | observed + claim |
| `W11_AUTHORITY_NOT_DARK` | HEALTH READY or signing available, or any authority flag true (incl. FULL `issuanceReady`) | HALT | claim + observed |
| `W11_WITNESS_NOT_EXACT` | W10 phase ≠ W10_1 (incl. witness stopped) or witness incarnation ≠ baseline | STOP_REVALIDATE | observed |
| `W11_RESTARTED_OR_INCARNATION_CHANGED` | more than one load, `NRestarts` > 0, HEALTH from another InvocationID / MainPID, or the running invocation is not the loaded one | STOP; attempt consumed | observed |
| `W11_START_FAILED_OR_AMBIGUOUS` | failed, activating or auto-restart; running without a load; an invocation with unknown credential outcome; a recorded load the journal does not show | STOP | observed |
| `W11_UNEXPECTED_UNIT_STATE` | enabled / enableable, unloaded, reload pending, socket listening without the service, wrong process, extra credential name, wrong socket metadata | STOP | observed |
| `W11_UNEXPECTED_HEALTH` | HEALTH fields or reasons not exactly H | STOP | claim |
| `W11_READINESS_NOT_EXPECTED` | E not READY / binding not PASS, or F not exactly the hold reason and detail | STOP | observed |
| `W11_LEDGER_SIDECAR_RESIDUE` | an empty WAL and / or shm left by an interrupted reader | STOP; owner adjudication, never removal | observed |
| `UNCLASSIFIED_STOP` | units, journal, ledger or W10 unreadable; seam not consulted; baseline or load record missing | STOP; UNKNOWN is never success | — |

**Precedence:** HALT facts first, in the order hold, ledger, key, credential, darkness (a proven HALT is reported even
when other parts are unknown); then UNKNOWN; then STOP, in the order witness, restart, start, unit, HEALTH, readiness,
residue; then the exact phases.

## 8. W11 DR-5 targets (`mb11_dr5_target.py`)

The rule stays `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`. The tool runs the pinned M-B10 derivation (unchanged)
and applies a delta it proves from the pinned script (`9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43`):
`/run/credentials/lilith-authority-dev.service` is one `AB_LATER` item; `ab_check_later_state` prints one
`DEFERRED_UNTIL_OBJECT_EXISTS` line while it is absent and `DENIED: test -w`, `-r`, `-x` once present;
`/run/lilith-authority-dev` and `/var/lib/lilith-authority-dev` are already present as `DENIED` lines; no other list
names a path at or beneath them.

| W11 phase | Target | Result set | DR-5 block | Pre-deploy |
| --- | --- | --- | --- | --- |
| `W11_1_SIGNER_STARTED_EXACT` | `SIGNER_RUNNING_WITNESS_RUNNING_HELD` | 194 `8c8b6eacb144e1d3587a9e6ea1694ff122c0c219ac6e9b90f1f2addd9b41ce93` | 155 `ba39512d64bbc0966dca4125ab1d390adf2d3b41718a279d57e5a4aa4e6d1e59` | 29 `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` |
| `W11_1S_STOPPED_AFTER_FIRST_LOAD` | `SIGNER_STOPPED_AFTER_FIRST_LOAD_WITNESS_RUNNING_HELD` | 192 `593c90e1…ff65` (the post-HELD text) | 153 `ace51f27…fd5a` | 29 `f5087042…4cae` |

Every other phase, every W9 and W10 phase included, is `NO_BASELINE_STOP`. Cross-check (owner-local, read-only): the
observed `W10_1_HELD_EXACT` result set and DR-5 block of deploy `38162573937`, with the proven substitution applied,
equal the derived W11 texts byte for byte. The targets are derived and **not accepted**; no live W11 deployment
observation exists. DR-5 cannot see HEALTH, the loaded key or the hold store.

## 9. Ledger preservation

The HEALTH path opens the WAL ledger `mode=rw`, reads schema, meta, journal mode and journal, and closes; it issues no
write. The only ledger write path is `append_recovery`, reached only through the three recovery operations, which the
synthetic test refuses under the real INITIAL_CUSTODY HELD with zero writes and no witness call.

- **Logical invariants (authoritative):** the W9 / M-B6 byte-level WAL reconstruction (no open, no shm, no
  checkpoint): schema fingerprint, meta, sequence 1 and the accepted head.
- **Byte invariants (supporting):** with no sidecar, the DB SHA-256 equals the pre-start baseline. Synthetic proof
  (REAL ledger, REAL signer core): 25 HEALTH reads leave bytes and listing unchanged; a reader killed mid-read leaves a
  0-byte WAL and an shm with DB bytes unchanged (`W11_LEDGER_SIDECAR_RESIDUE`); one clean read removes them. A WAL with
  frames, a foreign entry or changed DB bytes with no sidecar is `W11_LEDGER_CHANGED`.
- Observations are serialized: no ledger directory observation while a HEALTH frame is in flight.

## 10. Tests and how they run

`services/owner-memory-control/tests/test_b1b3e_mb11_signer_start.py`:

| Layer | Runs where | Covers |
| --- | --- | --- |
| stdlib | everywhere (CI) | pins (reused tools and the DR-5 script unchanged; the 12 P1B-12 rows and 9 namespace rows unchanged and not used); the unit / socket exposure unchanged; the DR-5 derivation, script mutations, source tampering, compare refusals, CLI; the classifier: every exact phase, every HALT, precedence, UNKNOWN, every STOP class, routes, journal parsing and cursor refusal; static boundaries (no socket, no credential, no unit verb, no write; no `mb11_operator.py`; no workflow names M-B11); both records |
| contract | POSIX + cryptography (CI) | REAL signer core HEALTH over a socketpair from a TEST_ONLY credential (exactly H; non-root peers get nothing; constants equal the release's); REAL root verifier E and F; stopped signer; wrong key; the canonical RELEASED (FULL READY → darkness HALT); REAL ledger bytes and crash residue; recovery refusal under real HELD |
| synthetic host | POSIX + root (WSL Ubuntu 24.04 locally; skipped on CI) | the UNCHANGED W9 / W10 over the M-B10 synthetic root with the REAL hold writer: `W11_0` → running (`w10PhaseDirect = W10_SIGNER_OR_LATER_STATE`, separately judged `W10_1`) → `W11_1` → stopped → `W11_1S`, never `W11_0`; hold tampering HALTs through the masked W10 |

Not tested here (named obligations): systemd restart / socket behaviour (§6), the live journal message set, the HEALTH
capture step (no capture tool exists), the live process facts.

## 11. Proposed owner decisions (none accepted)

| # | Proposal | Blocks |
| --- | --- | --- |
| OD-M11-1 | the H / E / F / G POST conditions of §5, with the §27 wording erratum | design / tooling |
| OD-M11-2 | a single controlled service start (`systemctl start lilith-authority-dev.service`); never the socket alone | design / tooling |
| OD-M11-3 | one go = one invocation; W11_1 requires exactly one load; more than one load or any failure consumes the attempt; credential failure HALTs; a retry is a linked successor after adjudication | design / tooling |
| OD-M11-4 | one pre-authorized safe stop (service and socket) for `W11_KEY_MISMATCH`, `W11_RESTARTED_OR_INCARNATION_CHANGED`, `W11_UNEXPECTED_HEALTH` | design / tooling |
| OD-M11-5 | a fixed HEALTH budget (one capture, reused for E and F); no live ISSUE or recovery frame in M-B11 | design / tooling |
| OD-M11-6 | signer lifetime: continuous M-B11 → M-B15 (one load, long window) versus stop and restart per milestone (each restart a new load and go); prepare every non-signer M-B12 input first | live startup |
| OD-M11-7 | freeze scope; pending security updates of libssl3t64 / python3.12 / libsqlite3 checked before start; a reboot leaves the signer stopped; any restart needs a new go | live startup |
| OD-M11-8 | owner-freshness evidence class for this `REQUIRED_CURRENT` step (the M-B10 laptop + S25 pattern) | live startup |
| OD-M11-9 | accept the W11 DR-5 targets of §8 after a real W11 observation | live startup |
| OD-M11-10 | record the first K-ACT load (count, InvocationID) as a custody event | live startup |
| OD-M11-11 | the restart and socket-reactivation bound (§6): mechanism and systemd-runner proof | **live startup (hard blocker)**; a release change also blocks tooling |
| OD-M11-12 | the meaning of M-B12 `eligibilityReady` (§12) | M-B12 design |
| OD-M11-13 | E-25 … E-28 (§12) | M-B12 / M-B13 design |
| OD-M11-14 | the mapping of the seven proof names to tools (§12) | M-B12 design |
| OD-M11-15 | how readiness inputs reach the host (a stdin bundle with no host file, or a host `inputs.json`) and the HEALTH capture step | tooling (next slice) |

## 12. Recorded contract discrepancies (not resolved here)

- **M-B12 eligibility versus the PR-1 package.** The preflight §27 M-B12 row requires "eligibility READY", but §20 and
  §28 place PR-3 full material after P1B-12, and the package cannot be READY without E-18, E-20 and E-21 (the
  synthetic package fails exactly those three when PR-2 / PR-3 are absent). Whether `eligibilityReady` means readiness
  READY (E-17) or package READY is OD-M11-12. Nothing here reinterprets a check to produce READY.
- **E-25 … E-28.** Sequencing §11 says the canonical package digest covers them; `pr1_acceptance.PACKAGE_CHECKS` ends
  at E-24 and the verifier input has no field for them; the installed verifier equals HEAD. Adding them means a
  release change, or an owner amendment keeping them owner-side (OD-M11-13). Nothing here implements either.
- **Proof names.** None of `SIGNER_DENIAL`, `DEPLOYER_DENIAL`, `BROKER_DENIAL`, `BROKER_PRESERVATION`, `OS_DENIAL`,
  `SECRET_HYGIENE`, `PRESERVATION_SET` is mapped to a tool by any record (OD-M11-14).
- **PR-3 full material / PR-2.** No record declares PR-3 full material (E-21) complete; the accepted PR-2 record
  predates K-WIT and the bootstrap state. Both are M-B13 prerequisites.
- **Deferred denial rows.** The 12 `DEFERRED_UNTIL_PHASE: P1B-12` rows of `scripts/authority_custody_denial_proof.py`
  and its 9 signer-namespace rows stay **NOT PERFORMED**: row 11 and all namespace rows need the running signer, and
  the script has no partial phase. They belong to M-B12.

## Tools and pins

| Tool | SHA-256 |
| --- | --- |
| `services/owner-memory-control/tools/mb11_signer_verifier.py` | `2fb0fe0d7781c2758d71d3dcc3968e1bb415be0b41881c47933ea1e2423aa614` |
| `services/owner-memory-control/tools/mb11_dr5_target.py` | `c72cf1b2a5713a32471f0de5ad1afd56a1a65edfa6992386f1452207ce1db6fc` |

Reused unchanged: `mb10_held_verifier.py` `73a8fe9aec48fab7fb628a3427bc690876b55a4ae1ead55f1b7e00032075b8e3`,
`mb10_dr5_target.py` `29c359617605f67e812732c4bb6a9ca1b9439bfffcf22285e44d9f6c1999ccf0`, `mb9_dr5_target.py`
`d176864a2f15cd9a64462c1ffc0bb46364428e97d3ec64b5fd547bb380ef1675`, the DR-5 script and the release `aee323e`.

## 13. State

```text
MB11 = DESIGN / REPOSITORY ONLY; NOT RUN
MB11_DESIGN_DIRECTION = OWNER-REVIEWED (2026-10-12; direction only)
OD-M11-1..OD-M11-15 = PROPOSED; NONE ACCEPTED
RESTART_AND_SOCKET_REACTIVATION_BOUND = NOT PROVEN (LIVE STARTUP BLOCKER)
W11_DR5_TARGETS = DERIVED; NOT ACCEPTED; NO LIVE W11 OBSERVATION
MB11_OPERATOR = NOT BUILT
M-B11 = NOT AUTHORIZED
SIGNER = INACTIVE
K_ACT_LOADS = 0
HELD = PRESENT / EXACT / FORWARD ONLY (unchanged)
P1B12_DEFERRED_ROWS = 12 NOT PERFORMED
P1B12_NAMESPACE_ROWS = 9 NOT PERFORMED
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
ISSUANCE_AUTHORITY = NONE
FIRST_MEMORY = NOT AUTHORIZED
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
```
