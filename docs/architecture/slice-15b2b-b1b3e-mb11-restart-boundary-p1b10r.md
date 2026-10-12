# Slice 15B2b-B1b-3e — M-B11 PR-A2: Signer Restart Boundary Install and Verification Controls (`P1B-10R`)

Status:

- **DESIGN AND TOOLING ONLY. NOT RUN. NOTHING INSTALLED.** This record defines the provisional stage `P1B-10R`:
  a control-side install of the two O2-D drop-ins proven on a disposable runner by PR-A1 (#183), its read-only
  status / effective-unit verifier, and the W11 verifier extension. No live installation, no daemon-reload, no
  signer start and no DEV contact are authorized or were performed.
- **OD-M11-11 (O2-D) and the E-6 / RR-33 amendment (§7) are PROPOSED, not accepted.** The accepted release `aee323e`
  and its unit fragments are unchanged; the tooling lives outside the release-controlled `services/authority-dev`
  tree (`release_file_set.check_source_tree` passes).
- M-B11, Registry V1 effectiveness, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.

```text
drop-ins installed != daemon-reload performed != effective configuration verified != signer startup authorized
effective restart boundary = accepted release fragments (unchanged) + the pinned owner-controlled overlay (PROPOSED)
the overlay is NOT invisible: the host observer and the W9 / W10 unit checks see it (§6)
```

## 1. What is pinned

| Item | SHA-256 |
| --- | --- |
| candidate `lilith-authority-dev.service.d/10-no-implicit-restart.conf` (`[Service] Restart=no`) | `e3faf9efa91f0238ee6110a33cf6c9f024aca1029fe05bd26fba4c21679c6b92` |
| candidate `lilith-authority-dev.socket.d/10-no-reactivation.conf` (`[Unit] StopWhenUnneeded=yes`, `RefuseManualStart=yes`) | `85589f80764311f7e1152cf0e9ea51208662bce25806ceb524777961f579b9b9` |
| release fragment `/etc/systemd/system/lilith-authority-dev.service` (`aee323e`) | `11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254` |
| release fragment `/etc/systemd/system/lilith-authority-dev.socket` (`aee323e`) | `bff5e9275ad1478dd068855465d65542ceb338e5e9236e43d1bd43d7c50c194f` |
| `services/owner-memory-control/tools/mb11_restart_boundary_install.py` (activation-line correction, §10) | `e052b2511013ef37a047a074e85a8c711d9c06bba4f01cb56dc906ee6994a803` |
| superseded original of the same tool (PR-A2 #184, merged `7f8406d`; refused the real activation line, §10) | `b67f9ecf29dba235b8be76ad70c41a267cf5f09a22871beea85a6a189f075792` |
| `services/owner-memory-control/tools/mb11_signer_verifier.py` (W11, extended) | `020ab5b15b02ac7d46b2cc8dd402481576646fbebcab708522df50f96e8782ad` |

The candidate bytes are the exact PR-A1 files (`mb11_restart_boundary.DROPINS`); the runner proof (all 20 assertions,
CI run `38215106519`) is reused, not rebuilt. Installed form: directories `root:root 0755`, files `root:root 0644`,
one link each, under `/etc/systemd/system/<unit>.d/`.

## 2. Four separate transitions

| # | Transition | Actor | Tool form | Writes |
| --- | --- | --- | --- | --- |
| 1 | install the overlay | root, one owner go naming the plan digest | `install <plan-digest>` | the two directories (`mkdir`) and two files (`O_EXCL`), nothing else |
| 2 | daemon-reload | the owner's own command | none: **the tool never reloads** | systemd's loaded unit state |
| 3 | verify the effective configuration | root, read-only | `expect P10R_2_EFFECTIVE_EXACT` | nothing |
| 4 | signer startup (M-B11) | a separate owner authorization | none: **the tool never starts, stops or enables a unit** | — |

`plan` (read-only) prints the plan digest of an exact `P10R_0` pre-state (fragments, unit properties without volatile
IDs, shadow paths, activation line, candidate pins). `install` re-observes, requires `P10R_0` and the same digest, and
refuses otherwise: no silent overwrite, repair, completion or rollback.

## 3. Phases (`mb11_restart_boundary_install.classify`)

| Phase | Exactly when | Route |
| --- | --- | --- |
| `P10R_0_PRE_INSTALL_EXACT` | release fragments exact (bytes, `root:root 0644`, `FragmentPath` in `/etc`); no overlay and no shadow anywhere; both units inactive, no InvocationID, static, loaded, `NeedDaemonReload=no`, `DropInPaths` empty, release defaults loaded; activation exactly the complete dark line (§10) | install only by plan digest and go |
| `P10R_1_INSTALLED_RELOAD_PENDING` | overlay exact; both units `NeedDaemonReload=yes` and still the release defaults (`DropInPaths` empty) | the owner's separate daemon-reload |
| `P10R_2_EFFECTIVE_EXACT` | overlay exact; `DropInPaths` exactly the two candidates; `Restart=no`, `StopWhenUnneeded=yes`, `RefuseManualStart=yes`; `NeedDaemonReload=no`; units inactive and static | verified; startup is separate |
| `P10R_PARTIAL_INSTALL` | a strict prefix of the install's own write order (incl. an `O_EXCL` file created but not yet written) | STOP; never completed or removed by a tool |
| `P10R_FOREIGN_OR_ALTERED` | any other entry, altered bytes or metadata, a symlink, an extra link, a non-prefix order, or any shadow fragment / drop-in for these names in the other systemd search paths | HALT |
| `P10R_UNIT_NOT_EXACT` | fragments changed, enabled, unloaded, `FragmentPath` elsewhere, an unexpected reload state, an unexpected drop-in path, or an inexact effective property | STOP / revalidate |
| `P10R_SIGNER_NOT_INACTIVE` | a signer unit is active or has an InvocationID | STOP (W11 judges a running signer) |
| `P10R_AUTHORITY_NOT_DARK` | the activation output is not exactly one line `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false` with exit 1 (§10) | HALT |
| `UNCLASSIFIED_STOP` | units or activation unreadable, or reload pending yet partly effective | STOP; UNKNOWN is never success |

Every result carries `startupAuthorized`, `reloadPerformedByTool`, `authorityGranted`, `registryEffective`,
`authorityActive` and `accepted` all false and `issuanceAuthority: NONE`.

## 4. W11 extension

`mb11_signer_verifier.py` now observes `FragmentPath`, `DropInPaths`, `Restart`, `StopWhenUnneeded` and
`RefuseManualStart` and reads the effective boundary with the same judgement (`boundary_reasons`, read-only,
production owner `root:root`). Every exact W11 phase (`W11_0_PRE_SIGNER_EXACT`, `W11_1_SIGNER_STARTED_EXACT`,
`W11_1S_STOPPED_AFTER_FIRST_LOAD`) requires the boundary exactly in force; unobserved is `UNCLASSIFIED_STOP`, inexact
is `W11_UNEXPECTED_UNIT_STATE`. The unchanged W10 / W9 judgements are still composed as before.

## 5. Owner decisions before any live installation

| # | Decision |
| --- | --- |
| OD-M11-11 | accept O2-D (drop-ins) over O2-R (release change) |
| OD-M11-16 | accept the E-6 / RR-33 amendment of §7 |
| OD-M11-17 | authorize a P1B-10R sequence: fresh read-only rebaseline and `plan`, then the `install` go, then the separate daemon-reload, then `expect P10R_2_EFFECTIVE_EXACT`, then a host POST and DR-5 |
| OD-M11-18 | if DEV shows pre-existing drop-ins (type-level `service.d` / `socket.d`, vendor files) for these units, `P10R_0` refuses (`DropInPaths` must be empty); the owner pins that set or stops |
| OD-M11-19 | the procedure for a `P10R_PARTIAL_INSTALL` or `P10R_FOREIGN_OR_ALTERED` result (no tool removes anything today) |
| OD-M11-20 | whether removing the overlay before the first K-ACT load is ever permitted (after it: never without a new design) |

## 6. What other observations see (the overlay is not invisible)

| Observation | Effect |
| --- | --- |
| PR-1A host observer (`observe_authority_dev_host.py`, run by host POST) | after install + reload exactly: `units.show.<signer unit>.DropInPaths` = the candidate path; `units.enablementOrDropInEntries` gains the two candidate files; `namespaceInventory./etc/systemd/system` gains the two `.d` directories. `observer_delta_reasons(pre, post)` judges that nothing else changed (clocks excluded) |
| W9 / W10 unit checks (`systemctl show`) | between install and reload `NeedDaemonReload=yes` on the signer units: W9 is UNCLASSIFIED, so a host POST in that window is `MB10_HOST_POST_NOT_PASS` by design; after reload the observed properties are unchanged and W10 preservation is expected byte-identical |
| installer `status --expect P1B-10` (pinned, unchanged) | blind to the overlay; never evidence of it |
| routine deployer DR-5 | unchanged: no list of the pinned script names a path at or beneath the overlay directories, and `/etc/systemd/system` is a write-denied parent (`prove_dr5_unaffected`); W10 and W11 DR-5 targets stand |
| broker preservation | its authority-custody paths do not include the overlay; expected unchanged |

## 7. Proposed E-6 / RR-33 amendment (PROPOSED)

> The effective `lilith-authority-dev` service and socket configuration consists of the accepted release fragments
> (byte-equal to the release assets, unchanged) plus exactly the owner-controlled drop-ins pinned in the M-B11
> P1B-10R record. E-6 ("unit bytes = release asset") continues to bind the fragments; a separate evidence item binds
> the overlay: exact bytes, ownership, modes, `DropInPaths` and the effective `Restart=no`, `StopWhenUnneeded=yes`,
> `RefuseManualStart=yes`. RR-33's single-release rule is unchanged: the overlay is configuration, never a second
> executable release. Until accepted, no live installation may rely on this amendment.

The release root verifier (release payload) cannot observe the overlay, so the M-B13 package needs the overlay
evidence as an owner-side item beside E-25 … E-28 (an M-B12 / M-B13 dependency, OD-M11-13).

## 8. Tests

`services/owner-memory-control/tests/test_b1b3e_mb11_restart_boundary_install.py` (synthetic roots; fake
`systemctl show` whose reload is simulated): exact flow `P10R_0` → install → `P10R_1` → simulated reload → `P10R_2`;
replay after install and after reload; malformed, wrong and stale plan digests; every partial prefix; an interrupted
install (empty `O_EXCL` file → PARTIAL, torn bytes → FOREIGN, nothing rolled back); extra file, altered bytes, wrong
mode, symlink, extra link, non-prefix order, three shadow locations; fragment, enablement, FragmentPath, reload,
unexpected drop-in path, active service / socket, activation not dark or unreadable, units unreadable; every
effective-property mismatch after reload and a partly effective reload; the W11 reader equals this judgement; the
observer delta; DR-5 unaffected (and a mutated script refused); static: only `install` writes, only `systemctl show`,
no reload / start / stop / enable. The M-B11 W11 tests gain the boundary cases (unobserved → UNCLASSIFIED, not effective
→ `W11_UNEXPECTED_UNIT_STATE`, including before start).

## 9. State

```text
P1B_10R = DESIGN / REPOSITORY ONLY; NOT RUN
OVERLAY = NOT INSTALLED ON DEV
OD-M11-11 = PROPOSED (O2-D); NOT ACCEPTED
E6_RR33_AMENDMENT = PROPOSED; NOT ACCEPTED
RUNNER_PROOF = PR-A1 20/20 (CI 38215106519); REUSED
M-B11 = NOT AUTHORIZED
SIGNER = INACTIVE
K_ACT_LOADS = 0
HELD = PRESENT / EXACT / FORWARD ONLY (unchanged)
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
ISSUANCE_AUTHORITY = NONE
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
```

## 10. Activation-line correction (after the first read-only preflight)

**What happened.** On 2026-10-12 the owner authorized one read-only DEV preflight and `plan` against `7f8406d`.
`observe` reported everything in the `P10R_0` shape: fragments exact, no overlay, no shadow, units inactive, static
and loaded, `NeedDaemonReload=no`, `DropInPaths` empty, release defaults loaded. `plan` was then refused with
`REFUSED NOT_P10R_0:P10R_AUTHORITY_NOT_DARK` (route `HALT_PENDING_OWNER_ADJUDICATION`). No plan and no digest were
produced, and DEV was not changed. That HALT stays recorded as it happened. This correction does not reclassify it,
does not turn it into a plan, and does not let any later step reuse that preflight.

**The defect.** The original tool (`b67f9ecf…`) required the activation line to equal
`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`. The B1c verifier (`scripts/dev_deployer/lilith_activation_verify.py`)
always appends a final `advisoryConfigEnabled=<true|false|unreadable>` field. Every preserved root custody read,
host/06-POST and the preflight's host/07-POST included, shows the same complete line:
`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false`. The tests had built their fake
activation from the tool's own constant, so they could not catch the mismatch.

**The correction** (`e052b251…`):

- `ACTIVATION_DARK` is now that complete line.
- `activation_dark` accepts by exact equality only. Prefix, substring and field-wise acceptance are not used.
- The production reader (`activation_line`) takes the raw bytes and the exit code. It returns the line only when
  the verifier printed exactly one ASCII line ending in LF and exited 1.
- Anything else becomes an `UNEXPECTED_ACTIVATION_OUTPUT` marker, which can never be dark. That covers another exit
  code, an extra preceding or following line (the original tool kept only the last line), a missing LF, CR or
  non-ASCII bytes. Empty output stays `UNCLASSIFIED_STOP`.
- These forms are all refused, never `P10R_0`: `advisoryConfigEnabled=true`, `unreadable` or capitalised values, a
  missing, empty or duplicated field, an extra field, reordered fields, another reason or status, and surrounding
  whitespace. The original three-field line is also refused, as a missing field.

**What did not change.** The phases, routes, plan-digest body, install writes and every other judgement are
unchanged. W11 (`mb11_signer_verifier.py`, still `020ab5b1…`) is not affected: it reads the boundary with
`activation=None`, judges only `boundary_reasons`, and never compares the activation line.

**Tests.** They now use the independently observed host stdout bytes, not the tool constant, and pin the B1c emitter
format. They reproduce the recorded refusal for the original constant, cover every unsafe variant above at both the
predicate and the stage level (the install refuses with nothing written), and cover the strict byte and exit-code
parse.

**What a later P1B-10R needs.** The corrected tool must be merged and deployed, followed by its own preservation,
before any later P1B-10R. That later run needs a new owner authorization for a fresh read-only preflight and `plan`
under this pin. Nothing in this section authorizes an installation, a daemon-reload or a signer start. The §9 state
block is left unchanged by this correction.
