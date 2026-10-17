# Slice 15B2b-B1b-3e — M-B11 START_SIGNER: The One-Shot Signer-Start Operator (Repository Only)

Status:

- **SOURCE AND SYNTHETIC TESTS ONLY. NOT RUN.** This slice adds the owner-laptop operator `mb11_operator.py` and its
  read-only host tail `mb11_start_remote.py`. Nothing contacted DEV. No signer started and no K-ACT was loaded. No unit,
  release, installer, workflow, pin or record was changed.
- **M-B11 stays NOT AUTHORIZED.** A live start needs:
  - a PASS gate;
  - the owner's verbatim `MB11-GO-START` (rendered by the operator);
  - the owner readiness inputs (§5). These are blocked on OD-M12-3.
- It builds on the [M-B11 design record](slice-15b2b-b1b3e-mb11-signer-start-design.md) (unchanged) and the
  owner-accepted effective restart boundary ([P1B-10R receipt](slice-15b2b-b1b3e-mb11-p1b10r-owner-acceptance.md),
  Option A).

```text
gate W11_0 != go;  go != start;  one start invocation != one K-ACT load (journal-counted);  W11_1 != owner acceptance
HEALTH (B4) = a signer claim;  E / F = the release root verifier over the same captured HEALTH;  UNKNOWN != success
```

## 1. What the operator does

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: a clean control checkout, every pinned tool exact (§6), and the accepted replacement witness equal to `e19_completion_record.json` |
| `gate <repo> <workdir> <envelope>` | **read-only DEV**: one BOOT bundle, form `gate`. PASS (`MB11_GATE_W11_0`) only for exactly `W11_0_PRE_SIGNER_EXACT` (rules below the table) |
| `render <repo> <workdir>` | local: the exact go text, bound to the latest PASS gate |
| `start <repo> <workdir> <go>` | **the only mutation** (sequence below the table) |
| `current <repo> <workdir>` | **read-only DEV**: one BOOT bundle, form `current` (§10). No W11, no HEALTH, no marker |

`gate` PASS also requires:

- the signer was never started (0 loads, STOPPED);
- W10 is `W10_1_HELD_EXACT`, both directly and with the signer side judged separately;
- the witness is the accepted E-19 replacement `90b28f9d06fd48a1a1bdc3ae39474fb1` / `69238`;
- the restart boundary is effective (`boundary_reasons == []`);
- the journal tail cursor and the ledger DB SHA-256 were captured.

`start` runs in this order:

1. The go bytes must equal `render` exactly. A newer gate makes an older go non-canonical.
2. The `mb11-start` marker must be absent.
3. A **fresh read-only gate** must be PASS, with the same ledger DB bytes, witness and envelope.
4. The `O_EXCL` marker `attempts/mb11-start.json` is written. **The go is consumed here.**
5. **One** `sudo -n /usr/bin/systemctl start lilith-authority-dev.service` runs over the pinned `gcloud compute ssh`
   route.
6. **One** read-only `post` bundle runs (HEALTH capture + W11).
7. `START.json` is recorded with the result.

**Result.** `MB11_START_REACHED_W11_1_SIGNER_STARTED_EXACT` requires start rc 0, post `W11_1`,
`kActLoadCount == 1` and a HEALTH capture. Every other outcome is one of:

- `MB11_START_STOP:<phase>`;
- `MB11_START_UNKNOWN_POST_NOT_RECEIVED`.

**Never:** a retry, a second invocation, a stop (OD-M11-4 is not accepted), an enable, a daemon-reload, a socket
start, or any repair or rollback.

**Service path only (OD-M11-2 direction).** The signer socket carries `RefuseManualStart=yes` (P1B-10R). The service
`Requires=` the socket, so starting the service pulls the socket in as a dependency. The E-19 PR #190 systemd 255
probe established that a service-only start still works under `RefuseManualStart`. No form names the socket unit.

## 2. The host tail (`mb11_start_remote.py`)

It runs as root under the release interpreter, in the reviewed mb6 BOOT stdin bundle. Bundle order:

1. the unchanged W10 chain (`mb4_mb5_trust_install_verifier`, `mb6_ledger_verifier`, `mb8_owner_input_verifier`,
   `mb9_witness_verifier`, `mb10_held_verifier`);
2. `mb11_restart_boundary`, `mb11_restart_boundary_install` (P1B-10R, pinned `10147341…` / `428d93b4…`);
3. the unchanged W11 verifier `mb11_signer_verifier` (`e21fd26f…`);
4. one **generated data module** `mb11_start_evidence` (`DOC`, one JSON literal);
5. the tail.

**Owner inputs (OD-M11-15).** They arrive as that data module. It is pinned in the bundle like every module and
bound by the canonical evidence digest in argv. This means:

- there is no host input file and no argv size limit;
- `main` refuses before any host read unless the digest and form match.

**Forms:**

- **`gate`** takes the journal tail cursor **before** judging. It sets the ledger DB SHA-256 observed here as the
  baseline, then runs `evaluate` with no HEALTH, `firstLoadRecorded=false` and the journal from its start
  (cursor `None`: no invocation ever).
- **`post`** runs `evaluate` over the **go-bound** baseline (gate cursor, gate DB bytes, accepted witness) with
  `firstLoadRecorded=true`, after the HEALTH capture described below.

**HEALTH capture (OD-M11-5: one frame, reused for E and F):**

- It uses the release's own `lilith_authority_root.clients.signer_health`.
- It is attempted **only** while `systemctl show` reports the service active/running with an InvocationID and
  MainPID, and the socket active.
- It is bound to that InvocationID and MainPID before and after the frame. W11 STOPs on any difference.
- A stopped or failed signer is never contacted.

The tail never starts, stops, enables or reloads a unit, never reads a credential and never writes.

## 3. Bindings

| Binding | Value | Source |
| --- | --- | --- |
| release | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` (sole installed) | E-19 U5; equals `mb11_signer_verifier.RELEASE_SHA` and `mb11_restart_boundary_install.RELEASE_SHA` (tested) |
| restart boundary | P1B-10R plan `2a004a4195116462d60fdff978229f9a2364427704e4d16d5dec729801106592`, `P10R_2_EFFECTIVE_EXACT`, Option A | every exact W11 phase requires `boundary_reasons == []` |
| witness | `90b28f9d06fd48a1a1bdc3ae39474fb1` / `69238` | `e19_completion_record.json` `replacementAcceptance` (checked by `pins`) |
| W10 inputs | `e19_operator.LEDGER_HEAD`, `GENESIS`, `GENESIS_UPDATED_AT` | unchanged |
| W11 DR-5 targets | running 194 `ff2468f0…` / 155 `4337f769…`; stopped = `WITNESS_RUNNING_HELD_E19` | `mb11_dr5_target.py` `775f43e8…` (pinned; applied by the post-deploy compare, not by the operator) |

## 4. The go (`render`)

The rendered go is plain ASCII with no `>`, so it survives the go-check normalisation. It names:

- the exact start command and "exactly one invocation of the service start path, never the socket";
- at most one K-ACT load, with no automatic retry, restart, stop, enable or daemon-reload;
- the release, the P1B-10R plan and Option A;
- the gate observation SHA-256, the journal cursor, the ledger DB SHA-256 and the witness;
- the owner readiness inputs envelope SHA-256;
- the control commit and the operator SHA-256;
- the non-authorizations: its acceptance, M-B12, Registry effectiveness, authority, First Memory, PROD.

`start` compares the go **byte for byte** with a fresh `render`.

## 5. Decisions and blockers

**Applied, as already owner-accepted:**

- OD-M11-11 (O2-D boundary, installed and accepted) and OD-M11-16 … OD-M11-20 (2026-10-12, chat; P1B-10R record §5).
- OD-M11-13 (E-19 transition).
- The 2026-10-12 design direction: a single controlled service start; socket-first rejected; one go and one
  consumed attempt; a supervisor is not a lifetime bound.

**Implemented as proposed, needing owner acceptance before the result is accepted:**

| Decision | Status in this slice |
| --- | --- |
| OD-M11-1 | H / E / F / G: the unchanged W11 classifier |
| OD-M11-3 | one go = one invocation; W11_1 needs exactly one load |
| OD-M11-5 | one HEALTH capture |
| OD-M11-15 | owner inputs as a pinned data module; no host file |

**Not implemented, owner decisions:**

| Decision | What remains |
| --- | --- |
| OD-M11-4 | a pre-authorized safe stop. The operator never stops; every HALT/STOP goes to owner adjudication |
| OD-M11-6 | signer lifetime M-B11 → M-B15 |
| OD-M11-7 | freeze scope and pending security updates |
| OD-M11-8 | owner-freshness evidence class |
| OD-M11-9 | accept the W11 DR-5 targets after the first real W11 deploy compare |
| OD-M11-10 | record the first K-ACT load as a custody event |
| OD-M11-12 | M-B12 `eligibilityReady` |
| OD-M11-14 | M-B12 proof-name mapping |

**Owner readiness inputs (OD-M12-3 ACCEPTED, §9).**

- `gate` requires the owner readiness inputs envelope (`ownerInputs`). Without it, E/F cannot be evaluated and W11_1
  is unreachable.
- `mb12_readiness_inputs build` now evaluates DEV evidence against the accepted cutoff (§9); a DEV envelope still
  needs authentic post-cutoff evidence that matches every DEV record pin.
- `DEV_ACCEPTED_PROOF_TRANSCRIPTS` is empty, so proofs stay missing (NOT_READY downstream, recorded not judged at
  M-B11).
- The operator never defaults or synthesizes inputs: `owner_inputs` is `read_envelope` over the exact envelope bytes,
  and any refusal is a STOP.

## 6. Tools and pins

| Tool | SHA-256 |
| --- | --- |
| `mb11_operator.py` | `1ec09faea0a7b8c4f2eb58622a8119aa513c297057e9bda1dd9a8db49bf36bcd` |
| `mb11_start_remote.py` | `04461ffe4d30d443c49e5ef2d314972fda41a0b3b8dda1765609fb64c1cad72f` |

Reused unchanged and pinned in `mb11_operator.TOOL_PINS`:

| Tool | SHA-256 |
| --- | --- |
| `e19_operator.py` | `b98328162b72795de0579d5e7abb58ff55f1bd7498e53b8699d91af5d453c1dd` |
| `mb11_signer_verifier.py` | `e21fd26fd68bcdea3d645a12ff53b647ef3aa8f62824e9c89712b8fcb85d4e1d` |
| `mb11_dr5_target.py` | `775f43e84e1e58c2c9d1e8b4f2f32dc955462d034963b74761a133003a16daf3` |
| `mb11_restart_boundary_install.py` | `428d93b4b36bdb8d7783e2c1f22d3961fd5cf3623ce0ee0d419ab3b81c53c8af` |
| `mb11_restart_boundary.py` | `10147341819c27bb3720a87264ffea78f1bf1c3c2a23d7804ac900370cfe7419` |
| `mb12_readiness_inputs.py` | `d325d07f9e2ba23b1c5d98e295d415275c8aab88d0d9c50ea8081f99eb19ce2b` |
| `e19_completion_record.json` | `31bc707ebc9b58b376d233a30594eaa0e1f4d3b32444b172c741dbaeec66b3b8` |

The W10 chain uses the `mb10_operator.TOOL_PINS` values.

## 7. Tests

`services/owner-memory-control/tests/test_b1b3e_mb11_operator.py`:

- **Setup.** A fake DEV sits behind the operator's transport seams. It runs the **real** host tail and the **real**
  W11 `evaluate` / `classify` over synthetic signer facts.
- **Paths covered:**
  - success (gate → render → start → W11_1, one mutation, one HEALTH);
  - replay denial;
  - stale approval (changed ledger bytes; an older go after a newer gate);
  - a tampered go;
  - wrong boundary;
  - unexpected signer state, wrong witness or missing cursor at the gate;
  - fresh-gate change before the marker;
  - credential failure, two loads, key mismatch and wrong release after the start (STOP; one invocation; no stop);
  - lost transport (rc unknown, never success);
  - a partial post (UNKNOWN);
  - no HEALTH unless the service runs;
  - exact, digest-bound evidence;
  - the real BOOT loader refusing off-host and refusing a wrong digest before any host read;
  - static boundaries;
  - pins and bindings.
- **Changed test.** `test_b1b3e_mb11_signer_start.test_no_live_capable_operator_or_workflow_change_in_this_slice`
  now requires exactly this operator, pinned by this record. The workflow guard is unchanged: no workflow may name
  `mb11_operator`.

## 8. State

```text
MB11_OPERATOR = BUILT (source + synthetic tests); NOT RUN; NOT AUTHORIZED
MB11 START = BLOCKED: an authentic DEV owner readiness envelope + MB11-GO-START (OD-M12-3 accepted, §9)
RESTART_BOUNDARY = EFFECTIVE, OWNER-ACCEPTED (P1B-10R Option A)
SIGNER = INACTIVE;  K_ACT_LOADS = 0
REGISTRY_EFFECTIVE = NO;  AUTHORITY_ACTIVE = NO;  ISSUANCE_AUTHORITY = NONE
FIRST_MEMORY_READY = NOT REACHED;  PROD = NOT AUTHORIZED
```

## 9. Addendum (2026-10-15): OD-M12-3 accepted

**Owner decision.** OD-M12-3 is ACCEPTED: `DEV_FRESHNESS_NOT_BEFORE = "2026-10-14T18:27:00Z"`. It is the immutable lower
freshness bound for M-B12 DEV evidence and follows the PR #198 deployment (`38614708729`, completed
2026-10-14T18:26:49Z).

- **One cutoff.** It is set only in `mb12_pr2_inventory.py` (now
  `49d46b9ca166bae853653300cdd174d2b7ddb0025e72a80123b408cbc7055008`; was `24370a37…`, the value recorded in the
  [PR-B1 record](slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md), which is not rewritten).
  `mb12_readiness_inputs.trust_for("dev")` reads it through its existing import (`I2.DEV_FRESHNESS_NOT_BEFORE`);
  `mb12_readiness_inputs.py` (`d325d07f…`, pinned by the operator) is unchanged.
- **Still fail-closed.** `DEV_ACCEPTED_INVENTORIES`, `DEV_ACCEPTED_CANDIDATES` and `DEV_ACCEPTED_PROOF_TRANSCRIPTS` stay
  empty. A DEV caller cannot override the trust. A synthetic fixture is never a package input. Evidence before the
  cutoff is refused (`INVENTORY_STALE`, `WINDOW_BEFORE_FRESHNESS_CUTOFF`, `INPUT_STALE`).
- **Tests.** `test_b1b3e_mb12_prb1_prerequisites` adds `OdM12_3CutoffTests` and `OdM12_3ReadinessTests`. The four
  existing tests that asserted the undecided cutoff now assert the accepted value and the next fail-closed refusal.

## 10. Addendum (2026-10-15): the read-only `current` form

**Owner decision.** The owner authorized exactly one read-only root DEV invocation of the release's canonical
`observe_current_blob`, over the existing pinned transport. No reviewed path emitted that form: the PR-1A observer's
`currentBlob` has a different shape (integer device / inode / times, `nlink`). This addendum adds only that narrow form.

- **Host tail** (`mb11_start_remote.py`, re-pinned in §6). Form `current` takes evidence `{"form": "current"}`
  (digest-bound like the other forms). It runs the same `main` gates first: the digest check, `require_dev_root`, and
  the release tree on `sys.path`. It then returns `lilith_authority_root.observers.observe_current_blob("/").to_dict()`
  (lstat identity plus the ciphertext SHA-256, never decrypted), the host UTC instants before and after, and the
  observer module path. It does no W11 judgement, no unit query, no HEALTH and no socket.
- **Operator** (`mb11_operator.py`, re-pinned in §6). `current <repo> <workdir>` runs `pins`, then ONE bundle, and
  records `current/NN-CURRENT/{remote.*, CURRENT.json}`. `MB11_CURRENT_EXACT` requires all of the following:
  - the exact `to_dict` field set;
  - the slot `SC.CURRENT_PATH`, `REGULAR`, `0600`, `0:0`;
  - `sha256 == DEV_PINS.pinnedCurrentSha256`;
  - canonical decimal strings;
  - `observedAt` at or after `DEV_FRESHNESS_NOT_BEFORE`;
  - an observer module under `/opt/lilith-authority-dev/current/`.

  Anything else is `MB11_CURRENT_STOP`. It never consumes the `mb11-start` marker.
- **Unchanged.** The `gate` / `post` / `start` behaviour, `GO_LINES`, the bundle order, every reused pin,
  `mb12_readiness_inputs.py` (`d325d07f…`) and the W11 verifier.
- **Tests.** `test_b1b3e_mb11_operator` adds `CurrentTests` (exact, seven STOP classes, not received) and extends the
  evidence and BOOT-loader tests with the `current` form.

```text
CURRENT observation = a readiness INPUT;  != readiness;  != a gate;  != a go
```

## 11. Addendum (2026-10-15): after the accepted start — the read-only `observe` form and the re-pin

The start ran once and was owner-accepted ([acceptance receipt](slice-15b2b-b1b3e-mb11-signer-start-acceptance.md)).
The `mb11-start` attempt is consumed. Two source changes follow, and neither authorizes anything:

- **`observe <repo> <workdir>` (new, read-only DEV).** After the start, `gate` correctly STOPs (`PHASE:W11_1…`), so
  no reviewed path re-observed the started signer. The routine post-deploy W11 DR-5 compare (`mb11_dr5_target compare
  <verified-w11-phase> <log>`) needs an independently verified phase. `observe` provides it:
  - it requires the consumed marker and exactly one `NN-START` step whose `START.json` reached W11_1 with one load and
    whose `postSha256` equals the saved `post.out`, bound to the latest gate;
  - it rebuilds the **identical** POST11 document (same gate baseline, same envelope) and refuses before any DEV
    contact unless its digest equals the accepted `post.out` `evidenceSha256`;
  - it runs ONE `post` bundle: the W11 judgement plus **one HEALTH query of the running signer** (OD-M11-5 frame);
  - `MB11_OBSERVE_W11_1_EXACT` requires W11_1 with reasons `[]`, one load with HEALTH, the accepted signer
    InvocationID / MainPID / NRestarts and HEALTH key, W10_1 with the accepted witness, the effective boundary and
    authority disabled. Anything else is `MB11_OBSERVE_STOP` (owner adjudication; no stop, restart or repair);
  - it writes `observe/NN-POST11/{remote.*, OBSERVE.json}` and never the marker, a gate or a step.
- **Re-pin.** Recording M-B11 in the E-22 scope changed `mb12_secret_hygiene_proof.py`, and with it the
  `PRODUCER_SCRIPT_SHA256` pin in `mb12_readiness_inputs.py`, which this operator pins.

These rows supersede §6:

| Tool | SHA-256 |
| --- | --- |
| `mb11_operator.py` | `43c2a6bfbcf16a4035d8c8c999193ab8279acdccbcc7f22486131fd2a8f62ac4` |
| `mb12_readiness_inputs.py` | `a1c68c7e054d3f7cb2d5368e8772bbeb19d977e7552a5d770c4f0461696b0435` |

Tests: `test_b1b3e_mb11_operator.ObserveTests` (exact repeat of the accepted POST11; refusal without the one reached
start or with tampered evidence, before DEV contact; five STOP classes; not received). Running `observe` live needs its
own owner authorization.

```text
observe W11_1 exact = an input to the W11 DR-5 compare;  != owner acceptance of the W11 targets (OD-M11-9);  != M-B12
```

## 12. Addendum (2026-10-15): E-22 producer stdin fix — re-pin only

The one owner-authorized E-22 journal scan (2026-10-15T10:41Z, evidence `lilith-mb12-hygiene-0bf0b8f`) STOPPED before
reading any journal: `mb12_secret_hygiene_proof.py` died at import (`IndexError`) because CPython sets
`__file__ = "<stdin>"` for `python3 -`, and its `REPO` line then resolved `parents[3]` of a shallow working directory.
The producer now treats `"<stdin>"` (or an unset `__file__`) as "no repository"; `test_b1b3e_mb12_prb2_proof_producers`
streams every producer through real CPython from a shallow cwd. Nothing else changed in any form. Pin cascade:

| Tool | SHA-256 |
| --- | --- |
| `mb12_secret_hygiene_proof.py` | `3a039a96c0a051aaa635d06879729a33978600551cbdf564ae778e81704b1355` |
| `mb12_readiness_inputs.py` | `4839c8fe3f2b059df99bd0063c98529808dc30cc00c2ff8872e825f1a2aef308` |
| `mb11_operator.py` | `1602d5dcd20a7f523b66690bf1d6ed85e27b6435efd6e2c705f48885e51339bb` |

These rows supersede §11. A new scan needs its own owner authorization.

## 13. Addendum (2026-10-15): E-22 marker attribution form — re-pin only

The corrected E-22 journal scan (owner-authorized, 2026-10-15T16:43–16:47Z, evidence `lilith-mb12-hygiene-f619a07`,
`SHA256SUMS` `0c236f8635222556c00d9a38b731459e033903747e39bc6c05f44c8ab08ea2e3`) completed with
`JOURNAL_SECRET_SCAN=FAIL`: `PEM_PRIVATE_KEY` count 12, 712019 entries, stream SHA-256
`332015ac0e21406db69a3158b36bd5d1538f0bbef3722c4d7c0cbd8bbb794c38`. That result stands and E-22 stays FAIL.

`mb12_secret_hygiene_proof.py` gains one read-only root form, `attribute`: the same journal read, plus per counted
match its boot, realtime, field name, `_SYSTEMD_UNIT`, `SYSLOG_IDENTIFIER`, text/binary, armour role and a heuristic
verdict (`COMPLETE_PEM_BLOCK` / `HEADER_OR_COMMAND_TEXT` / `UNKNOWN`). It never emits a value, byte, offset or
surrounding text, passes journal strings only through an allow-list (else `UNSAFE`), bounds output to 64 matches, and
FAILs unless every counted match lies inside one field value. `journal` and `prove` are unchanged. No verdict changes
the scan FAIL; resolving the finding is a separate security and owner decision. Running `attribute` needs its own
owner authorization. Pin cascade (supersedes §12):

| Tool | SHA-256 |
| --- | --- |
| `mb12_secret_hygiene_proof.py` | `8cedb1d0bb940da0a2c674ce08e1044264d11c0bd41b313c5f314e8345f39270` |
| `mb12_readiness_inputs.py` | `eed5cfe5909285a680a132b9f69447c0b7a2d86f611599c2b67639240329767e` |
| `mb11_operator.py` | `88ba2b803cd634711d81ba9c7a5af060e3e2eab6ae901274d2a9dc55a7a49c9e` |

## 14. Addendum (2026-10-16): E-22 session purpose form — re-pin only

The owner-authorized `attribute` run (2026-10-15T17:54–18:02Z, evidence `lilith-mb12-attribute-0420ca6`, `SHA256SUMS`
`dce427ad3c57b677a2cfe33d0cf2d8d414cd67d35b06ffe41150d66c55ae6091`) placed all 12 `PEM_PRIVATE_KEY` matches in three
`sudo` sessions of boot `24d1771d…` (2026-09-27 07:19:05 / 07:22:51 / 07:25:36Z), each verdict `UNKNOWN`. Off-host
records (ceremony documents, session logs, shell histories) could not verify the commands. E-22 stays FAIL.

`mb12_secret_hygiene_proof.py` gains one read-only root form, `purpose`. It reads only those three session scopes, through
journalctl's own `-b`, `--since`/`--until` and `_SYSTEMD_UNIT` filters (never the whole journal), and reports per session
closed enums of command STRUCTURE only: program class, `--grep` option, whether the single marker lies inside a
recognized search-pattern argument (`patternArgument`), operand class, MESSAGE/`_CMDLINE` agreement, marker counts,
complete-PEM / key-like / other-marker presence, and a verdict `LITERAL_PATTERN_SEARCH` / `EXPOSED_KEY_EVIDENCE` /
`UNKNOWN`. `LITERAL_PATTERN_SEARCH` needs `patternArgument=YES`: a closed grep shape (`[flags] [--] PATTERN /OPERAND`
or `[flags] (-e PATTERN)+ /OPERAND`) or journalctl `--grep`/`-g`/`--grep=`, where every pattern region is exactly one
joined word. journald joins argv with spaces, so a multi-word region cannot be told apart from a pattern plus further
operands; any such region, other option or position is `UNKNOWN`. The PEM marker contains a space, so for it the
argument boundary is never established: `patternArgument` is always `NO` and the verdict for these sessions can only
be `EXPOSED_KEY_EVIDENCE` or `UNKNOWN` (with the structural facts). The attribution's historical counts are required
exactly (3 sessions, each 1 marker-bearing
MESSAGE + 3 marker-bearing `_CMDLINE`, 4 markers; 12 overall), else `FAIL reason=HISTORICAL_COUNT_MISMATCH`. It never
emits a value, pattern, path or argument, and FAILs on any unexpected entry, missing session or count mismatch. No
verdict changes the scan FAIL. Running `purpose` needs its own owner authorization. Pin cascade (supersedes §13):

| Tool | SHA-256 |
| --- | --- |
| `mb12_secret_hygiene_proof.py` | `cf2369ffcb90d440d9f99d3133f770029492be5fdfeb14bb88d89bed8d5b6a2a` |
| `mb12_readiness_inputs.py` | `9272b49004fb914820b609052b327703cd8ac51a4b86ca61a69f3737a6e9998d` |
| `mb11_operator.py` | `c8ecfd43511f4fa9683aa444fc9b44a739930007f708fee06b11aa7a3201b2a5` |

## 15. Addendum (2026-10-16): OD-M12-6 owner decision — three proof transcripts pinned

**OD-M12-6 ACCEPTED by the owner (2026-10-16).** A DEV proof transcript is admitted as a package input only when it is
the producer's own stdout bytes from one owner-authorized run of the producer pinned in
`mb12_readiness_inputs.PRODUCER_SCRIPT_SHA256`, satisfies that producer's existing contract
(`mb12_readiness_inputs.CONTRACTS`), and its SHA-256 is listed under the proof name in `DEV_ACCEPTED_PROOF_TRANSCRIPTS`
by a reviewed, merged owner record (this addendum). No other signature system is introduced. The OD-M11-14 producer
mapping is accepted for `SIGNER_DENIAL`, `BROKER_DENIAL` and `OS_DENIAL` only; the other four names stay PROPOSED.

Evidence: one owner-authorized read-only `mb12_dev_reads.py e07 RUN` (2026-10-16T15:40Z, main `ef640377`, deploy
`38854041173`), evidence `lilith-mb12-e07-ef64037`, `SHA256SUMS`
`29c5a575ca7950207cbbc242c4f149ea70dd7d75753bbc168970a0ec33ca1674`. Both remote calls rc 0, stderr empty; no denial
probe obtained access.

| Proof | Producer (script SHA-256) | Transcript SHA-256 | Contract |
| --- | --- | --- | --- |
| `SIGNER_DENIAL` (E-07) | `scripts/authority_custody_denial_proof.py:P1B-12` (`f4e39c81…`) | `92dcb9aa87a40244ef02a38901f319491197b82e31fb064f6e356a57a9ec32c1` | PASS; 9 956 B, 144 lines, exit 0, byte-equal to the rebuilt PASS (134 principal + 9 signer-namespace DENIED) |
| `BROKER_DENIAL` (E-09) | the same P1B-12 transcript | `92dcb9aa87a40244ef02a38901f319491197b82e31fb064f6e356a57a9ec32c1` | PASS (the broker is an outsider in every row) |
| `OS_DENIAL` (E-07) | `services/owner-memory-control/tools/mb12_os_denial_proof.py:UNIT` (`e6754228…`) | `3cb0e744abda6a2540ad56a25e4ad1b144449833af296756eb37b0c21bd29b4a` | PASS; 762 B, exit 0, P1B-10R drop-in state |

**Still pending (not pinned):**

- `DEPLOYER_DENIAL` (E-08): no admissible transcript. `deploy-dev.yml` tees the DR-5 stdout to
  `${RUNNER_TEMP}/authority-boundary.txt` but does not retain it; the GitHub log interleaves gcloud stderr and timestamps,
  so the producer's exact bytes are not recoverable. A reconstruction is not admitted.
- `BROKER_PRESERVATION` (E-09 second half): no transcript bound. E-09 stays incomplete.
- `SECRET_HYGIENE` (E-22): BLOCKED; the original `JOURNAL_SECRET_SCAN=FAIL` remains authoritative.
- `PRESERVATION_SET` (E-23): waits on OD-M12-8.

A pinned transcript is not package READY, and E-17 READY is not M-B12 PASS. M-B12 NOT PASSED; custody HELD. Pin
cascade (supersedes §14):

| Tool | SHA-256 |
| --- | --- |
| `mb12_secret_hygiene_proof.py` | `cf2369ffcb90d440d9f99d3133f770029492be5fdfeb14bb88d89bed8d5b6a2a` |
| `mb12_readiness_inputs.py` | `67f78851287773a3c9ccce478cec6ee5fb707ef3d9ebc00955bfa69e818a3238` |
| `mb11_operator.py` | `e667487150987e0b3439dbb27af50e19920510ca7dfda7b63f5136770c7b4baa` |

## 16. Addendum (2026-10-17): E-09 BROKER_PRESERVATION transcript accepted under OD-M12-6

**Owner decision (2026-10-17):** under the OD-M12-6 mechanism (§15, unchanged), the owner accepts exactly one
`BROKER_PRESERVATION` transcript, for that proof name only. This grants no authority, custody release or package
readiness. The OD-M11-14 mapping is accepted for `BROKER_PRESERVATION` as well; `DEPLOYER_DENIAL`, `SECRET_HYGIENE` and
`PRESERVATION_SET` stay PROPOSED and unpinned.

| Field | Value |
| --- | --- |
| producer | `scripts/verify_broker_dev_current_incarnation.py:preservation` (`b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf`) |
| run | one owner-authorized read-only run, 2026-10-17T08:28:00–08:28:53Z (main `5994f6a5`, deploy `39013841952`), streamed hash-gated over the existing route; remote exit 0, stderr empty |
| transcript | `79387fe7d1db1e7eab0d8e508991656ba195d284cefac3889ffff9595f221c40`, 10 302 bytes, `BROKER_PRESERVATION=PASS`, `failures` `[]`; contract PASS |
| evidence | `lilith-mb12-broker-pres-5994f6a`, `SHA256SUMS` `8772d463f02a7415eb04e69f4f4b66451f94b2c6f52e4d8138662ab3f8c94ec5` (re-verified locally before this record) |

The transcript is byte-identical to the broker `preservation` output of the 2026-10-15 host U5 POST (before the signer
start): broker state is unchanged across the M-B11 start. Pin cascade (supersedes §15):

| Tool | SHA-256 |
| --- | --- |
| `mb12_secret_hygiene_proof.py` | `cf2369ffcb90d440d9f99d3133f770029492be5fdfeb14bb88d89bed8d5b6a2a` |
| `mb12_readiness_inputs.py` | `74c2af17248abc56a15f9d4695b62480a1c783835f368128228aea195f91002c` |
| `mb11_operator.py` | `9d73888f8e817bcb0685746b026ce39b45fd0a1e398079732288921563acfdbd` |

## 17. Addendum (2026-10-17): E-23 baseline pin — re-pin only

The owner accepted the E-23 preservation-set baseline `019e0117baaa7bd920b78047fb0ddcb6c49318bfd3a2d30d9dd134b98f78a0b5`
under OD-M12-8 (record `slice-15b2b-b1b3e-mb12-prb2-proof-producers.md` §11.3). `ACCEPTED_BASELINES` in the producer
now holds that one entry. This changes the producer's SHA-256, which `mb12_readiness_inputs.PRODUCER_SCRIPT_SHA256`
pins, and so the readiness and operator pins. No operator behaviour changes. Pin cascade (supersedes §16):

| Tool | SHA-256 |
| --- | --- |
| `mb12_preservation_set_proof.py` | `8b659beed2e50de6c62464cb273f1beac3d86a764750eb422b6276f42af7dde0` |
| `mb12_readiness_inputs.py` | `73d68e618f9cfd03485573489c16c239d9c525a751853490173a3af412d7f799` |
| `mb11_operator.py` | `a8efd3130828cb0d0d81d7af2c57ddabf8b5eef1efc1f4d528af11498749ddfd` |

## 18. Addendum (2026-10-17): E-23 `PRESERVATION_SET` transcript pin — re-pin only

The owner accepted the E-23 transcript `4692f3bae979aca82782a66605a3235939420223aa7841a931ad9a473f1e863e` under OD-M12-6
(record `slice-15b2b-b1b3e-mb12-prb2-proof-producers.md` §12). `DEV_ACCEPTED_PROOF_TRANSCRIPTS` gains
`PRESERVATION_SET`, which changes `mb12_readiness_inputs.py` and so the operator pin. The preservation producer and
its baseline are unchanged. Pin cascade (supersedes §17):

| Tool | SHA-256 |
| --- | --- |
| `mb12_preservation_set_proof.py` | `8b659beed2e50de6c62464cb273f1beac3d86a764750eb422b6276f42af7dde0` |
| `mb12_readiness_inputs.py` | `78fba8af76e8c45e1ff103a2de45f790fe6eb2ae6d59ed017fb92edd2fb8fbd6` |
| `mb11_operator.py` | `a6660d093744ab82cb5040b09102cc765620c3a92da0db59e47e4ccb7ce7b185` |
