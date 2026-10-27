# F9c2 coordinated DEV installation + one synthetic FORGET drill: G-0 approval packet (2026-10-25)

**Scope:**
- lilith-dev-01 only, DEV_SYNTHETIC only, one synthetic FORGET.
- **Track A only.** Track B (rollback anchor), real owner authentication and consent remain prerequisites for First Memory and are out of scope.
- No PROD, no GCP resource change, no Groq call (the key stays quarantined), no budget reset, no UI or SOUL.md change, no signer/broker/witness/authority/DR-5 change.

## Version and hash dependencies

| Item | Value | Where |
|---|---|---|
| Core API with F9-C | PR #249 head `950fc0243b204ab5e7ddec2f646a649b85517548` (F9-C `8c9f07b` + the Next 16.4.3 cherry-pick); CI 4/4 success, run 40124757495 | merge = deploy-dev |
| Hermes package | `hermes-gateway-dev-f293e72-f9c2.tar.gz` sha256 **`4b0b0110dde1cccd585203ea9a92cfe8b8cbe31d8e1a6e4edb461ba2c09c3ba5`**, MANIFEST `c78a8bd2d00c80dc3c3cca5f2dac3cd55a748405412730e48f68e0b3e9ff46dd` | `tracka/release-f9c2/f9c2/` |
| Rollback target | installed F8r4 (`f293e72-f8r4`, package `16c7417d…`); its `RELEASE.sha256` digest **is read by B-4** and written here as `F8R4_RELEASE_SHA` | DEV `/opt/hermes-gateway-dev/current` |
| DR-5 expected block | `F8_DR5_EQUAL 7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c` | F8r4 and f9c2 `dr5/` |
| Preflight | `devops/f9c2-b4-preflight.sh` (read-only) | this folder |

## Owner decisions to record (G-0)

1. **Merge #249** at the start of the window. Its deploy-dev run is the F9-C Core API deploy and is inert on F8r4. Then decide #250: redundant after #249 (close it), or merge it first.
2. **Run B-4** (read-only) after the #249 deploy. It must end `F9C2_B4 PASS` with `coreapi-f9c-deployed yes`. Record `f8r4-release-sha`.
3. **Authorize U-1…D-3 below**, including **one Core API restart** (protected service) after `install_f9c.sh`.
4. **Drill approval reference** `REF` (`[A-Za-z0-9._:-]`, single-use), e.g. `owner-g0-f9c2-drill-20261025`. It becomes the intent and confirmation reference.

## Install order (each step stops on any FAIL; `P=/var/tmp/f8/hermes-gateway-dev-f293e72-f9c2`)

| # | As | Command | Pass condition |
|---|---|---|---|
| 0 | — | upload the f9c2 tarball + `.sha256` to `/var/tmp/f8/`; `sha256sum -c`; extract; `sha256sum -c MANIFEST.sha256` | tarball `4b0b0110…`, MANIFEST OK |
| U-1 | root | `F8R4_RELEASE_SHA=<B-4 value> bash $P/bin/preserve_f8r4.sh` | `F8R4_PRESERVED <dir>`; the Groq key is quarantined |
| U-2 | root | `bash $P/bin/backup_pre_install.sh`; `bash $P/bin/install.sh` | `F8_INSTALL_STAGED f293e72-f9c2` |
| B-2a | root | `install -d -o lilith -g lilith -m 0700 /home/lilith/.hermes/lilith-os-dev/f9-drill` | |
| B-2b | lilith | `$CORE/api-venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/f9c_dev_drill.py --core-api $CORE/current provision` | `"status": "PROVISIONED"`, `floorAdded: true` |
| U-3 | root | `F9C_CORE_API_DIR=$CORE/current/lilith_memory bash $P/bin/install_f9c.sh` | `F9C_INSTALLED f293e72-f9c2` |
| U-3b | root | `systemctl restart lilith-os-api-dev` (the one approved protected restart) | `/health` OK; the process carries `lilith-forget` |
| U-4 | root | `provision_console_token.sh`; `verify_release.py --full`; `systemctl start hermes-gateway-dev` | `F8_VERIFY_PASS full f293e72-f9c2`; 9901 listening; DR-5 EQUAL |
| D-1 | operator | 2–3 synthetic canary turns through the Core API relay (no provider: gate `KEY_NOT_PROVISIONED`) | canary only in `state.db` |
| D-2 | lilith | `… f9c_dev_drill.py --core-api $CORE/current --owner-approval REF forget` | see criteria below |
| D-3 | root | canary scan; `f9c_dev_drill.py status`; DR-5; protected-service parity | see criteria below |

`CORE=/home/lilith/.hermes/lilith-os-dev`.

## Pass criteria for the one synthetic FORGET

1. **While held:**
   - the intent is `root:lilith-forget 0640`;
   - the relay returns **503 `FORGET_HOLD_ACTIVE`**;
   - `systemctl start hermes-gateway-dev` is refused (`cond=no`);
   - 9901 is closed.
2. **Tool output:** `"status": "COMPLETE"`, with `completedOwners` = `L04, L18_V2, HERMES_DEV_CONVERSATION`.
3. **Receipt:** exactly one receipt (`root:lilith-forget 0640`, `COMPLETE`, `LOGICAL_ERASURE_VERIFIED`, `ATTESTED_ZDR_NOT_VERIFIED`, epoch 1); epochs.log has 1 line.
4. **Release:** root released the intent and marker only after Privacy completion; the gateway restarted.
5. **Status:** `"completed": true, "inFlight": false, "intent": "ABSENT"`.
6. **Canary scan:** 0 hits in HERMES_HOME, `/var/backups/hermes-gateway-dev` (incl. the F8r4 quarantine), `/var/lib/hermes-forget` and the namespace journal.
7. **Probe stores untouched:** `data/*.dev.db` absent (the next deploy's probe must still find a clean baseline).
8. **DR-5 EQUAL** and protected-service parity (broker, authority, witness, stage3 PIDs unchanged; the Core API changed only at U-3b).

**STOP and report** on any deviation. Never retry with a new REF while an intent is pending; use `resume`, or the owner-approved cancel (`hermes_forget_executor.py --cancel-intent --confirm-owner-approved`, refused while an authorization is in flight).

## Rollback (any time no FORGET is pending)

1. `bash /opt/hermes-gateway-dev/current/bin/rollback.sh remove` (refused, before changing anything, while an intent or marker exists).
2. `bash $P/bin/restore_f8r4.sh /var/backups/hermes-gateway-dev/f8r4-preserved-<ts>`. After a completed FORGET, the restored F8r4 starts with an empty conversation store; all non-conversation files must be identical.

**Kept by design:** `/var/lib/hermes-forget` (epochs: restore-guard input), the drill stores (the FORGET record), the `lilith-forget` group. The Core API stays on the merged `main` (inert without the package).

## Local evidence (WSL mirror, real systemd)

See `F9C2-RESULT.md` and the final run rows in this folder's `../release-f9c2` and `../evidence`.
