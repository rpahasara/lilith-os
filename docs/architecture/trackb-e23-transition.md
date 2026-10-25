# Track B E-23 — Controlled Transition Tooling (E0 … E8)

Status:

- **PROPOSED — SOURCE ONLY.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `7c77e3d8a20bf018378532519c520b4c8f12ddc1` (the PR #252 merge: E-23 NEW pinned).
- **Owner authorization (2026-10-25): OFFLINE PREPARATION ONLY.** This adds the transition tooling and its offline
  rehearsal. It authorizes no stage, select, unit change, credential load, restart or retirement. Each of those needs
  its own owner go (§3).
- The release, its pins and its attestation are accepted ([pin record](trackb-e23-new-release-pin.md)). Nothing here
  rebuilds or re-pins them.

```text
tooling merged != any go;  status != permission;  VERIFIED != accepted;  E8 != Privacy active
```

## 1. What is reused, what is new

| Piece | Source |
| --- | --- |
| Release contract (OLD `129f2be`, NEW `57bff671`, 4 changed + 2 added) | `e23_privacy_anchor_upgrade.py`, merged, unchanged |
| Host reads (unit facts, cwd, manifests, selector temp path) | `e19_release_stages.py`, unchanged |
| Signer RUNNING / STOPPED rule, running-signer installer allowance | `e22_release_stages.py`, unchanged |
| Installer (archive verification, O_EXCL writes, release-tree check, `status`) | `install_authority_dev.py` V1 `fe10d9a3…`, unchanged |
| Transport (DEV-only IAP and pinned-host-key routes), marker, records, signer/witness stop and start commands | `e22_operator.py`, unchanged (its own tool-pin chain is re-checked) |
| **New:** E-phase status and stages | `services/owner-memory-control/tools/e23_release_stages.py` |
| **New:** operator (go texts, step chain, verification, acceptance) | `services/owner-memory-control/tools/e23_operator.py` |

The archive layout v2 is bound inside the stage call (`layout_v2`). It is exactly
`install_authority_dev_v2._layout_v2`, and a test proves the two are equal. V2 itself is not sent to DEV: its import
puts its own directory on `sys.path`, which under the BOOT bundle would be the remote working directory.

## 2. Phases and ordering (E-22 order plus one units step)

| Phase | Releases | `current` | Signer | Witness | Witness unit + tmpfiles |
| --- | --- | --- | --- | --- | --- |
| E0_OLD_EXACT | OLD | OLD | OLD (E-22 accepted `efbc0784…`/128648) | OLD (`8cbfbed2…`/127192) | OLD |
| E1_NEW_STAGED | OLD, NEW | OLD | OLD | OLD | OLD |
| E2_SIGNER_STOPPED | OLD, NEW | OLD | — | OLD | OLD |
| E3_WITNESS_STOPPED | OLD, NEW | OLD | — | — | OLD |
| E4_NEW_SELECTED | OLD, NEW | NEW | — | — | OLD |
| E5_WITNESS_UNITS_NEW | OLD, NEW | NEW | — | — | NEW, reloaded, anchor dir created |
| E6_WITNESS_RUNNING | OLD, NEW | NEW | — | NEW (K-WIT + K-PAN) | NEW |
| E7_SIGNER_RUNNING | OLD, NEW | NEW | NEW (K-ACT) | NEW | NEW |
| E8_OLD_RETIRED | NEW | NEW | NEW | NEW | NEW |

**Witness requirements:**

- **K-PAN first.** From E5 on, the witness unit names the encrypted K-PAN credential. So `e23-witness-units` refuses
  unless `lilith-recovery-witness.privacy-anchor.cred` already exists as root:root 0600. Every phase from E5 on is a
  STOP without it.
- **K-WIT unchanged.** Credentials are judged by lstat metadata only; their bytes are never opened.
- **Sockets and unit modes.** The owner and signer witness sockets, and every other unit file, are checked by the
  installer `status`. Only the two contract members change.
- **Separate anchor storage.** `/var/lib/lilith-privacy-anchor` is 0700, owned by the witness, and outside the witness
  state directory. E-23 writes no chain version.

## 3. Operator forms and owner gates

Each mutation runs the same sequence:

1. The owner's verbatim go (byte-identical to `render`).
2. Every earlier step consumed and reached.
3. A fresh read-only gate in exactly the pre-phase.
4. One `O_EXCL` marker.
5. One remote invocation.
6. A read-only post-status.

A step that does not reach its post-phase is a STOP. It is never retried, and no later step can be rendered.

| Form | Gate |
| --- | --- |
| `preflight` (read-only) | E0 exact: DEV_SYNTHETIC host (hostname, machine-id), OLD only, pinned NEW, the E-22 accepted incarnations, OLD units. Records the baseline: K-WIT and K-PAN metadata, signer credential names, and the Core API / Hermes / provider gate / broker incarnations |
| `stage` | E23-GO-STAGE, E0 → E1 |
| `stop-signer` | E23-GO-SIGNER-STOP, E1 → E2 |
| `stop-witness` | E23-GO-WITNESS-STOP, E2 → E3 |
| `select` | E23-GO-SELECT, E3 → E4 |
| `witness-units` | E23-GO-WITNESS-UNITS, E4 → E5. The go names the K-PAN blob's inode and size; the gate re-checks them |
| `start-witness` | E23-GO-WITNESS-START, E5 → E6 |
| `verify WITNESS` (read-only), then `accept-witness` | E6 |
| `start-signer` | E23-GO-SIGNER-START, E6 → E7; names the accepted witness |
| `verify SIGNER` (read-only), then `accept-signer` | E7 |
| `retire` | E23-GO-RETIRE, E7 → E8. Names both accepted replacements; no process may use OLD (cwd, executable or mapped file) |

**Acceptance (`verify`):**

- NEW manifest = pin.
- One replacement start each: a new InvocationID with NRestarts 0.
- Witness runtime credentials exactly K-WIT + K-PAN.
- K-WIT metadata unchanged since preflight; K-PAN metadata unchanged since the units gate.
- Anchor directory with no chain version; witness units NEW.
- Signer credential names unchanged.
- Core API, Hermes, provider gate and broker incarnations unchanged since preflight (no restart; F9c2 state untouched).

## 4. Offline verification

| Suite | Result |
| --- | --- |
| `test_trackb_e23_release_stages.py` (WSL, fake systemd) | 21 OK |
| `test_trackb_e23_operator.py` (WSL, operator → BOOT bundle → real stage tool → fake host) | 15 OK |
| Mutations of the key guards | 16 / 16 caught. The one survivor, a double acceptance, is also blocked by the `O_EXCL` record |

**Negative cases covered:**

- missing or unsafe K-PAN;
- K-PAN removed between render and gate;
- wrong OLD, NEW or manifest pins;
- an unexpected signer identity or an implicit restart;
- a transitional unit;
- an extra installer failure;
- OLD in use, by cwd or by a mapped file;
- an interrupted units step (files replaced, reload failed);
- a pending reload at E5;
- a clean exit that does not reach the phase;
- out-of-band steps;
- a non-DEV hostname;
- a foreign-unit restart at verification.

## 5. Owner decisions before a live run (not blockers to the tooling)

1. **K-PAN keygen (B3 live).** It must run before `witness-units`, under its own go (`trackb_kpan_keygen.py`).
   Once the blob exists, the installer `status` reports `LISTING:/etc/lilith-recovery-witness/credentials`. The E-23
   stages admit exactly that one name. The pinned historical reads (M-B11/W11, readiness) do not, so they read as
   failing until the post-E8 completion re-pin.
2. **K-ACT load count 3.** The signer payload is unchanged, but its process must leave OLD before retirement. E7 is
   therefore the third K-ACT load (E-22 ended at 2). The owner accepts it by the SIGNER_START go.
3. **No OD-M12-11 journal window.** Loads are judged by one new InvocationID with NRestarts 0 and the exact runtime
   credential names. The journal-counted windows of E-22 are not replicated. If the owner wants them, that is a
   separate addition.
4. **Post-E8 completion re-pin.** This is the E-22 completion pattern: the E-19 restart-boundary fragment pin
   `9f78130c`, the installed-release bindings, and an E-23 DR-5 target (release-line swap, `e22_dr5_target`
   pattern). Until then the next deploy's DR-5 compare against the E-22 target is expected to read DRIFT.
5. **Deploy freeze.** No Core API, Hermes or broker deploy or restart may run from preflight to E8. A deploy would
   change a foreign-unit incarnation and turn `verify` into a STOP.
6. **Ending incarnations.** These are pinned from the E-22 completion record. If DEV restarted either unit since
   (the post-#251 check observed them unchanged), `preflight` STOPs for owner adjudication.

## 6. State

```text
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  INSTALLED = 129f2be;  NEW = 57bff671 PINNED (not staged)
K-PAN = NOT GENERATED;  E-23 TRANSITION = NOT AUTHORIZED;  PRIVACY ACTIVATION (B5/B6) = NOT STARTED
```
