# Track B — Privacy Activation Integration (local; live activation owner-controlled)

Status:

- **LOCAL INTEGRATION — PROPOSED.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `0cb7e4ea96d53c8b448281adc681744350661951` (E-23 closed: release `57bff671`, K-PAN loaded by the witness, anchor
  directory empty, DR-5 EQUAL).
- It connects the existing Track B pieces. No new contract, key, service or unit. Merging it activates nothing: the
  host steps run only when invoked, and no DEV service composes canonical memory serving yet.

```text
anchored != checkpointed != unlocked != serving;  every step is one explicit owner action
```

## 1. What already existed (reused unchanged)

| Requirement | Existing implementation |
| --- | --- |
| Anchor, checkpoint and unlock contracts (K-PAN / K-PCK domains; FRESH / OLDER / DIVERGED / REPLAYED / UNVERIFIABLE) | `lilith_memory/privacy_anchor_contracts.py` |
| Witness-held K-PAN anchor; `READ` / `GENESIS` / `ADVANCE`; owner socket only (peer uid 0); fail-closed store | `lilith_recovery_witness/privacy_anchor.py` + `server.py` (installed in `57bff671`, K-PAN loaded) |
| Off-host K-PCK checkpoint chain (fork alarm) and boot unlock (self-verified FRESH only) | `owner-memory-control/tools/privacy_checkpoint_tool.py` |
| Root challenge / unlock / checkpoint steps and the per-boot tmpfs marker | `privacy_freshness.issue_challenge` / `apply_unlock` / `apply_checkpoint` |
| Fail-closed serving gate (marker of this boot, no pending intent, L == S) | `privacy_freshness.PrivacyFreshnessGate` + `FreshPrivacyHoldResolver` |
| Canonical reads and admissions behind the gate | `memory_v2.restore_gated_hold_resolver` (requires the gate). The read facade, canonical store, learning and L04 adapter all consult it, and a refusal is explicit (`PrivacyFreshnessNotReady` / `PRIVACY_STATE_UNAVAILABLE`), never a miss |
| Durable-before-erase barrier | `privacy_freshness.DurabilityBarrier` + the runner's barrier hook |

## 2. What was missing (this change)

1. **`lilith_memory/privacy_freshness_host.py`** (new): the root host steps.
   - It connects the witness owner socket to the root steps and the owner tool's files. The frame is byte-compatible
     with `privacy_anchor.encode_frame` (tested).
   - Every witness chain is re-verified under the installed K-PAN public pin.
   - Genesis and advance need the owner's explicit expected set head (`plan` prints it). The local Privacy set must
     extend the anchored set.
   - The challenge is kept root-only for its boot and is single-use.
   - The tool never signs, generates a key or reads a private key.
2. **`privacy_forget_runner.py`**: the durability barrier is now **required**. A runner without one is refused
   (`DURABILITY_BARRIER_REQUIRED`), so no composition can erase before the anchor and the owner checkpoint.
3. **Tests:**
   - `test_privacy_activation_integration.py` (new);
   - `test_privacy_forget_runner.py`: an explicit, named `DURABLE_FOR_TEST` barrier where that suite's subject is the
     owner sequence, plus a test that a missing barrier is refused.

## 3. Synthetic end-to-end proof (`test_privacy_activation_integration.py`)

It uses the real witness anchor service through `server.py`'s owner-socket path, the real owner tool with temporary
custody, the new host steps, and the real Privacy, L04, L18 V2, gate and runner. Keys are TEST-ONLY per test.

1. **Untrusted until activation.** Every canonical read refuses `FRESHNESS_MARKER_UNAVAILABLE`, and no challenge
   exists without an anchor.
2. **Genesis.** A wrong set head signs nothing. Genesis gives v1, and a second genesis is refused. The owner's
   off-host checkpoint 1 follows. Anchored plus checkpointed is still locked.
3. **Boot unlock.** The marker is bound to `boot-1`, and the challenge is consumed. Codename and First Interaction
   memory then serve.
4. **Whole-host rollback.** Privacy, memory and the witness anchor are restored to the pre-FORGET image and the host
   reboots. The owner tool refuses `UNLOCK_REFUSED:OLDER_THAN_CHECKPOINT` and records a fork alarm. Memory stays locked
   and the forgotten data is never served.
5. **Replay and divergence.**
   - A superseded challenge's unlock is `REPLAYED`.
   - Another boot's unlock has no challenge.
   - A forged signature is `UNVERIFIABLE`.
   - A forged Privacy row means `ANCHOR_BEHIND` everywhere, and no challenge is issued.
   - A Privacy-only restore means `OLDER_THAN_ANCHOR` everywhere.
6. **Pending FORGET.**
   - The barrier refuses (`ANCHOR_BEHIND`): nothing is erased, and all memory is locked meanwhile.
   - After the anchor advance it still refuses, because the checkpoint is pending.
   - An old checkpoint is refused.
7. **Correct new checkpoint.** It republishes the marker. The FORGET then completes, codename serves, and the First
   Interaction memory reads as suppressed (`None`), not resurrected.

**Results:**

- Integration: 5 OK (WSL).
- Privacy suites (WSL): 139 OK.
- Full Core API (Windows): 321 OK, 17 POSIX skips.
- Witness: 54 OK. Owner tool: 6 OK.
- 7 of 7 guard mutations caught.

## 4. Key compatibility (public pins only)

| Pin | Format | Environment | Key id |
| --- | --- | --- | --- |
| K-PAN (keygen output, 2026-10-25) | `LILITH_PRIVACY_KEY_PIN_V1`, 5 fields | `DEV_SYNTHETIC` | `kpan.dev-synthetic.01` (= the witness default) |
| K-PCK (owner custody pin) | `LILITH_PRIVACY_KEY_PIN_V1`, 5 fields | `DEV_SYNTHETIC` | `kpck.dev-synthetic.01` |

Both load through `privacy_freshness_host.load_pin` and the owner tool's `load_pin`. The witness, the gate and both
custody formats agree. **Compatible.**

## 5. Minimum DEV activation sequence (each line a separate owner decision)

| # | Step | Owner approval |
| --- | --- | --- |
| 0 | Merge this change. Its Core API deploy is inert: nothing composes the gate, and the module has no entry point or unit. Run the DR-5 compare | merge |
| 1 | Install `/etc/lilith-privacy-fresh/kpan.pin.json` and `kpck.pin.json` (root 0644, public pins) | **yes** (root file install) |
| 2 | `plan` (read-only): shows GENESIS with the existing Privacy suppression rows (the historical F9c2 row) and the expected set head | read-only |
| 3 | `genesis --expected-set-head <H>`, then `export-anchor` | **yes** (first K-PAN signature) |
| 4 | On the owner device: `privacy_checkpoint_tool checkpoint` over the exported chain | **yes** (K-PCK, off-host) |
| 5 | `challenge` → owner device `unlock` → `unlock --unlock … --checkpoint …` | **yes**, and after every reboot |
| 6 | Each later FORGET: `begin_forget` (hold) → `advance` → owner `checkpoint` → host `checkpoint` → runner `resume` | **yes**, per FORGET |

**Execution route.** The host tool has to run as root. The Core API code on DEV lives in a `lilith`-owned directory,
so root must not import it from there. The tool's imports fall back to the flat module names, and `main(argv)` matches
the BOOT loader. So run it as the existing hash-gated stream of `privacy_anchor_contracts.py`,
`privacy_freshness.py` and `privacy_freshness_host.py` under the root-owned authority-release interpreter
(`/opt/lilith-authority-dev/current/venv/bin/python`: rfc8785 and cryptography; `privacy_anchor_contracts.py` is
already in `57bff671`). Pass `--privacy-db /home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db`.

## 6. Remaining (blockers vs optional)

**Blockers to live activation:**

- **The two pin files** (step 1).
- **One owner-run local driver** for the hash-gated stream (the K-PAN keygen driver pattern).
- **No canonical serving runtime on DEV yet.** First Memory is not served by any DEV service. Once one exists, it must
  compose its resolver through `memory_v2.restore_gated_hold_resolver(..., freshness=PrivacyFreshnessGate(...))`. That
  is the only factory and it requires the gate. Wiring it is the First Memory step itself, not Privacy work.

**Not blockers (optional):**

- The unattended unlock (path a);
- a systemd unit for the challenge;
- surfacing the freshness code through the L04 adapter's `PRIVACY_STATE_UNAVAILABLE`.

**Consequence of the mandatory barrier.** Any further DEV FORGET now requires an activated anchor (steps 1–5) first.
That is intended.
