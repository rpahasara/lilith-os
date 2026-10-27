# F9c2 DEV_SYNTHETIC FORGET drill: result (2026-10-25)

**Result: `F9C2_DEV_SYNTHETIC_FORGET=PASS`.** The drill ran on lilith-dev-01 only, with exactly one FORGET.

**Authorization:** single-use reference `owner-g0-f9c2-drill-20261025`. The owner extended its scope after `F8R2_SYNTHETIC_SCOPE=VERIFIED` (`devops/scope/`).

## Steps

| Step | UTC | Script sha16 | Result |
|---|---|---|---|
| S6 precheck (read-only) | 09:18:03 | `d0728bf0766a301d` | S6_PASS |
| S7 D-2 + D-3 | 09:21:22 | `2b86637ff35dfa8e` (worker `e6a2bfab2ef422de`) | S7_PASS: 24 OK, 0 FAIL |
| Re-read (read-only) | after S7 | `48194a214198dd51` | worker exited; outputs hashed |

**S6 precheck findings:**
- release f293e72-f9c2; Core API `3f6b909f`, healthy, pid 268361/0 restarts (unchanged since U-3b);
- no intent, marker, receipt or epoch; drill state idle;
- ledger `68b4057e…` byte-identical; budget 5/5 exhausted, key not loaded;
- no unit pending a daemon reload; probe stores absent;
- DR-5 EQUAL; protected-service parity unchanged.

**S6 inventory = the accepted scope:**
- 73 items, with the exact per-backup and per-kind counts;
- the 42 F8r2 items are byte-identical to the verified scope (`d2a4c92c…`);
- full 73-item digest `1be65aff…`;
- live store: 1 session, 3 user rows, 0 non-canary user rows.

**Transport:** S7 returned rc=1 only because of the launcher's final `pgrep … && echo` line (the worker had already exited). All results were re-read from DEV.

## Pass criteria (G-0 §"Pass criteria")

1. **Hold-first and gateway isolation, while held:**
   - the intent is `root:lilith-forget 640`;
   - the relay returned `503 FORGET_HOLD_ACTIVE`;
   - the gateway was not active and 9901 was closed;
   - lilith could not remove the intent;
   - the F9-C gateway drop-in (conditions on the intent and marker) was loaded.

   **Deliberate deviation:** `systemctl start hermes-gateway-dev` was NOT probed on DEV. Both `hermes-forget-hold.service` and `hermes-forget-executor.service` declare `Conflicts=hermes-gateway-dev.service`, so a start job would stop them, possibly SIGTERMing a running executor. The start refusal was proven in the mirror (H2-restart, D-1-blocked). On DEV it is shown from its inputs: the drop-in is loaded, the intent exists, the gateway is inactive and the port is closed.
2. **Tool output:**
   - `"status": "COMPLETE"`;
   - `completedOwners` = `L04, L18_V2, HERMES_DEV_CONVERSATION`, `pendingOwners` = [];
   - authorization digest `efd5f6d9a47616ee`.
3. **Receipt:** exactly one, `erase.415eb104….receipt.json` (`root:lilith-forget 640`).
   - status COMPLETE, `LOGICAL_ERASURE_VERIFIED`, `ATTESTED_ZDR_NOT_VERIFIED`, scope `WHOLE_STORE_SINGLE_PRINCIPAL`, erasureEpoch 1;
   - all 7 phases COMPLETE and all 10 checks true;
   - receiptDigest `456159ad…` verified.

   `epochs.log` has exactly 1 line (epoch 1).
4. **Release order** (from the journal):
   - hold `HELD` 09:21:23.650 → `GATEWAY_STOPPED` 09:21:23.677;
   - executor `INTENT_RELEASED` 09:21:29.079 → `COMPLETE` 09:21:29.080.

   The intent and marker are gone, and the gateway restarted (pid 272365, active, 9901 open).
5. **Status:** `"completed": true`, `"inFlight": false`, `"intent": "ABSENT"`, suppressionSelectors 1.
6. **Erasure:**
   - canary scan = 0 files in HERMES_HOME, `/var/backups/hermes-gateway-dev`, `/var/lib/hermes-forget` and `/run/hermes-forget`, and 0 namespace-journal hits;
   - `scan_backups` = 0 items;
   - 1 tombstone (`1792920087-efd5f6d9a47616ee.json`) listing 73 removed items: HERMES_HOME_CONVERSATION 45, STATE_DB 6, JOURNAL_COPY 2, TAR_MEMBER 20;
   - the live store after restart has 0 sessions and 0 messages.
7. **Probe stores:** `data/*.dev.db` are absent.
8. **Budget, health and parity:**
   - ledger byte-identical (no upstream request, no reset); gate 5/5 `BUDGET_EXHAUSTED`, `key_loaded false`, gate pid 268511 unchanged;
   - `F8_VERIFY_PASS full f293e72-f9c2`; Core API healthy, pid 268361 unchanged; F9-C path, hold and reconcile units active;
   - DR-5 `F8_DR5_EQUAL`;
   - broker 3411 / authority 128648 / witness 127192, 0 restarts.

## Evidence hashes (on DEV, `/var/tmp/f8/f9c2-run` unless noted)

| File | sha256 |
|---|---|
| s7-worker.out | `555f369ced16a90e4592f9645718d9fae1eeb00a7ae1479a100b70a342f01587` |
| s7-worker.sh | `e6a2bfab2ef422de30795e8117f2c5fa7d0cd16508b2e36e812387e25cddf76d` |
| d2-forget.json | `61a05eef0dc0b45842618b0707959a199fc10a6cc466c853c7cedcba77b3c826` |
| receipts/erase.415eb104….receipt.json | `aaa06e1e09e00ce6322229371dca3b91c60dbe47d6bf63810c4c0e0497061acd` |
| epochs/epochs.log | `a466587639fc64b907a46595c800fc4aebc41b0b035d47ff3b3a325c087a25ac` |
| FORGET-TOMBSTONES/1792920087-efd5f6d9a47616ee.json | `ad97f246cda26fb635e8c6df3cc034d7ec59f7eef9e578bdf320989268ccb1ad` |

Local copies are in `devops/phaseb/s6-precheck.out` and `s7-d2.out`, plus `phaseb/reread/reread-s7.out`.

## Retained synthetic data (outside the executor's erasure scope; NOT erased)

This drill does **not** establish complete historical erasure on DEV. The following known synthetic copies remain by design:

- **F8r4 Phase B evidence in `/var/backups/hermes-gateway-dev`:**
  - files: `A0.txt`, `A2b.txt`, `A5.txt`, `G-7.txt`, `G-7r.txt`, `G-7r-resume.txt`;
  - Router V2 decision logs with message previews: `f8r4-evidence/lilith-router-decisions.log` and `f8r4-evidence/lilith-router-decisions-a5.log`.

  They contain synthetic F8r4 markers (f8b-s*) and previews, and `scan_backups` does not match them.
- **F9c2 step outputs in `/var/tmp/f8/f9c2-run`** (e.g. `d1-turn*.json`, the D-1 relay responses with the synthetic provider-failure reply; `d2-held.json`, the 503 response). They held no canary text before the FORGET.
- **The F9-C record stores, kept by design:** the drill Privacy store (the FORGET record), `/var/lib/hermes-forget` (epochs and receipt) and the tombstone (path digests, sizes and hashes only).
- **Provider side:** `ATTESTED_ZDR_NOT_VERIFIED` (Groq ZDR is attested, not verified).

## State left

- **Running:** F9c2 gateway 272365 and gate 268511.
- **Budget:** exhausted at 5/5, no key.
- **Not started:** no rollback, Track B or First Memory; each needs separate owner authorization.
- **Reference:** `owner-g0-f9c2-drill-20261025` is consumed and must not be reused.
