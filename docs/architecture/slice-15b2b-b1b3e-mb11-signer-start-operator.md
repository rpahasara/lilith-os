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

**Hard blocker for a live start: OD-M12-3 (UNDECIDED).**

- `gate` requires the owner readiness inputs envelope (`ownerInputs`). Without it, E/F cannot be evaluated and W11_1
  is unreachable.
- `mb12_readiness_inputs build` refuses every DEV build until `mb12_pr2_inventory.DEV_FRESHNESS_NOT_BEFORE` is
  decided (OD-M12-3).
- `DEV_ACCEPTED_PROOF_TRANSCRIPTS` is empty, so proofs stay missing (NOT_READY downstream, recorded not judged at
  M-B11).
- The operator never defaults or synthesizes inputs: `owner_inputs` is `read_envelope` over the exact envelope bytes,
  and any refusal is a STOP.

## 6. Tools and pins

| Tool | SHA-256 |
| --- | --- |
| `mb11_operator.py` | `5dbfb4cce949cad752c190bac0952d19828fa1c1a912689a6c51f8de639c81a4` |
| `mb11_start_remote.py` | `13914b3b6bc8509f552b4753ea2c7d0ceb3140e1213a44fdea49f921075abbef` |

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
MB11 START = BLOCKED: owner readiness inputs (OD-M12-3 undecided) + MB11-GO-START
RESTART_BOUNDARY = EFFECTIVE, OWNER-ACCEPTED (P1B-10R Option A)
SIGNER = INACTIVE;  K_ACT_LOADS = 0
REGISTRY_EFFECTIVE = NO;  AUTHORITY_ACTIVE = NO;  ISSUANCE_AUTHORITY = NONE
FIRST_MEMORY_READY = NOT REACHED;  PROD = NOT AUTHORIZED
```
