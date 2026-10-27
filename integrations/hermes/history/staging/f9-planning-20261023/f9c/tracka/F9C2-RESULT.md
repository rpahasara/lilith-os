# F9-C f9c2: dedicated DEV_SYNTHETIC drill stores + operator tool. LOCAL result (2026-10-24)

**Status:** local only.
- **Not done:** no DEV or PROD contact, no DEV database change, no Groq call or budget change, nothing merged or deployed.
- **Unchanged:** the finalized UI and SOUL.md.

## Package

| Item | Value |
|---|---|
| `hermes-gateway-dev-f293e72-f9c2.tar.gz` | sha256 **`4b0b0110dde1cccd585203ea9a92cfe8b8cbe31d8e1a6e4edb461ba2c09c3ba5`** (two builds byte-identical) |
| MANIFEST | `c78a8bd2d00c80dc3c3cca5f2dac3cd55a748405412730e48f68e0b3e9ff46dd` (14,324 entries = f9c1 + 1) |
| Windows copy | `tracka/release-f9c2/` (tarball, sha, MANIFEST, RELEASE_ID, evidence; 67 files verified) |
| f9c1 | untouched: `/root/f9ca/out` still `4f899311…` and the Windows backup verifies |

**Changes vs f9c1:**

| Path | Change |
|---|---|
| `systemd/hermes-forget-{executor,reconcile}.service` | bind `…/lilith-os-dev/f9-drill/privacy_governance.f9drill.db` (+ `-wal`/`-shm`) and its secret, instead of the probe's `data/privacy_governance.dev.db` |
| `bin/install_f9c.sh` | fixed drill paths (no env override); refuses unless the drill dir is `lilith 0700`, and the secret and DB are `lilith 0600` (what the Core API's owner-only loader requires) |
| `bin/f9c_dev_drill.py` (new) | `provision`, `forget`, `resume`, `status` (detail below) |

**`f9c_dev_drill.py` phases** (it runs as lilith with the deployed Core API venv and imports the **deployed** Core API):
- **`provision`** uses the DEV probe's exact library sequence:
  - cognitive DB: memory_store → 15B2a → canonical v2 → First Interaction family;
  - Privacy DB: 15B2a v1 → v2 → Hermes floor;
  - owner-only secrets.

  It is one-time only.
- **`forget`** is the governed hold-first FORGET. **The real actor-evidence contract** is used: the drill actor authority issues one single-use evidence, keyed to `--owner-approval REF`. The owner set is L04, L18_V2 (given the relay's capture path) and Hermes. Privacy Governance stays the only authority.
- **Refusals:** the tool refuses root, any path in or under `data/`, a second pending intent (before issuing evidence) and a reused approval reference.

## Tests

| Layer | Result |
|---|---|
| Drill tool, offline (real Privacy, real evidence, real L04/L18_V2, resolving mock executor) | **5/5**: provision is one-time and v2 + floor; **FORGET with NO First Interaction rows → L04, L18_V2 and Hermes all record COMPLETE**, Privacy completion proven, suppression 1, replay `ALREADY_COMPLETE`; a pending intent refuses a second FORGET before evidence; consumed evidence leaves the intent blocking; guards |
| Executor matrix (unchanged executor code) | 46/46 (Track A run; no executor change in f9c2) |
| **Integrated rehearsal on f9c2** (WSL real systemd, real gateway, real Core API, F8r4 → f9c2 → rollback → F8r4) | **57/61 functional OK**; the 4 not-OK rows explained below |

**Rehearsal highlights:**
- **B-2:** provision PASS, and a second provision is refused.
- **Before the drill:** H2, H9 and H6-stall PASS; R-0 is refused before any change; cancel works.
- **D-1, the tool's forget:** while held, the relay returns 503, a gateway start is refused, the port is closed and lilith cannot remove the intent. Then COMPLETE; root released the intent and marker; the gateway restarted.
- **Status:** `completed: true, inFlight: false`. A reused approval is refused.
- **Clean:** canaries 0 (HERMES_HOME, backups incl. the F8r4 quarantine, executor state); namespace journal 0.
- **Rollback:** R-2 and R-3 PASS; the F8r4 key is byte-identical; DR-5 EQUAL at M0, after the install and at the end.

**The 4 not-OK rows** (`U-3-probe-baseline`, `B-2-probe`, `D-1-probe`, `R-3-drill-kept`) are all the new "probe paths absent" check. The mirror still holds `data/privacy_governance.dev.db`, dated **21:39**: a leftover of the **f9c1** rehearsal's test fixture, written before this run started. f9c2 never wrote it (its mtime is unchanged), and the drill stores lived only in `f9-drill/`. The check correctly reports mirror residue. On DEV, the same condition is checked by the B-4 preflight (such a file would also block the deploy probe).

**Not re-run:** the executor-sandbox probe P-1 for the new binds. The f9c2 D-1 shows the executor **read** the drill Privacy DB and secret through them (it independently verified the authorization). The read-only property of the new bind was not re-probed.

## Remaining blockers to a safe DEV installation

1. **Merges (owner):**
   - **#250 first.** It unblocks CI and has no Core API change. A merge triggers deploy-dev, which redeploys an unchanged Core API.
   - **Then re-run #249 CI once and merge #249.** Merging it **is** the DEV Core API deploy of F9-C, which is inert on F8r4.
2. **B-4 read-only DEV preflight** (owner approval to connect read-only). It must show `data/*.dev.db` absent, no F9-C leftovers, the F8r4 release digest, DR-5 EQUAL, and systemd clean.
3. **G-0** owner authorization for the install and one synthetic drill. This includes **one Core API restart** after `install_f9c.sh` (so the process gains `lilith-forget`); that is a protected-service operation on DEV.

## Minimum DEV order (after 1–3)

1. U-1: `preserve_f8r4.sh`.
2. `backup_pre_install.sh`; `install.sh` (f9c2).
3. Root: `install -d -o lilith -g lilith -m 0700 …/f9-drill`.
4. Lilith: `f9c_dev_drill.py provision`.
5. `install_f9c.sh`.
6. Core API restart.
7. Console token; `verify_release.py --full`; gateway start.
8. 2–3 synthetic canary turns (no provider: `KEY_NOT_PROVISIONED`).
9. Lilith: `f9c_dev_drill.py --owner-approval <G-0 ref> forget`.
10. Canary scan, `status`, DR-5.

**Rollback:** `rollback.sh remove` (refused while a FORGET is pending), then `restore_f8r4.sh <preserved>`.

## Final local validation (2026-10-25; package unchanged, `4b0b0110…`)

| Run | Result |
|---|---|
| Executor real-systemd mirror on the f9c2 units | **18 PASS / 0 FAIL**. P-1: the drill Privacy DB is read-only, the drill secret is readable, and the probe's `data/` DB is ABSENT in the sandbox while present on the host. P-2: gateway isolation. M1, M3 (SIGKILL + resume), M5, M6 (locked → fail closed → retry), M7 (finalization window) |
| Integrated F8r4 → f9c2 → drill → rollback rehearsal (stale f9c1 mirror fixture removed first) | **61/61 OK** |
| B-4 preflight on an F8r4-installed mirror | **44 checks, `F9C2_B4 PASS`**; host snapshot identical before and after (read-only proven) |

Evidence: `release-f9c2/evidence-final/` (sha256-verified on Windows). Approval packet: `devops/F9C2-DEV-G0.md`. Preflight: `devops/f9c2-b4-preflight.sh`.
