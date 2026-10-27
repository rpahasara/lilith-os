# F8r4: DEV Phase B installation runbook (upgrade from the accepted F8r2)

**Status:** PREPARED and LOCALLY VALIDATED (WSL DEV mirror, synthetic Groq).
- Not installed.
- No Groq credential exists; no provider egress enabled; no model call made.
- No PROD contact, commit or push.

**Package:** `hermes-gateway-dev-f293e72-f8r4.tar.gz`, sha256 **`16c7417dc97a11ba6cf65fe44ef639e255bff22257f65d5f9bcefaab1af9d41a`**. MANIFEST `bd8bcec1e31eaf68ccb7c9384a16ac490238b024935faad2d66354e46258fd82` (14,307 entries). Deterministic: two builds, identical bytes.

**Relationship to the accepted design:** f8r4 = the owner-accepted f8r3 design (`3938796f…`) plus the install-safety hardening below. Nothing else changed: the same adapter `8c3b0055…`, config, profiles, units and sandbox.

## 0. What f8r4 changes vs f8r3 (all in response to the 10 safety-gate points)

| # | Hardening | Why |
|---|---|---|
| H-1 | The budget is an **append-only ledger**: one fsync'd `R` line per reserved request; `RESET` only by an owner-approved tool. An unreadable or malformed ledger **fails closed** (refuses everything) instead of reading as zero. | f8r3 kept a JSON cache written without fsync, and treated a missing or corrupt file as "0 spent" (a silent budget reset). |
| H-2 | The reservation is made **only after** policy, key and budget checks, DNS resolution to a **global** address, and a **verified TLS handshake** with `api.groq.com`. Failures before that send nothing and spend nothing. Every failure after it stays spent (never refunded, never retried), so it is never double-spent. | f8r3 spent budget on DNS or TLS failures and checked the address after reserving. |
| H-3 | Policy also rejects `tool`/`function` messages and assistant `tool_calls`, chunked request bodies and a non-boolean `stream`. Over-cap token reports are flagged (`token_cap_anomaly`). The provider's `x-ratelimit-*` headers are logged. | zero-tool policy on every path; independent rate-limit evidence |
| H-4 | `preserve_f8r2.sh` and `restore_f8r2.sh`: the accepted F8r2 install is preserved byte-for-byte, including its runtime state, and can be restored and proven identical. | f8r3's upgrade plan quarantined F8r2 with no tested restore. |
| H-5 | An owner-approved RESET also clears the day counters (one explicit owner act). | — |

## 1. Owner actions BEFORE authorization (Groq console; none taken by Claude)

The key must never be pasted into chat, a file, a ticket or a commit. It is typed only into the hidden prompt on lilith-dev-01 at G-5b.

| ID | Action | Evidence to give in chat (non-secret) |
|---|---|---|
| O-1 | In the Groq organization you intend to use, create a **separate project**, e.g. `lilith-dev-f8`. | project name |
| O-2 | **Data Controls → Zero Data Retention: enable org-wide** (or per feature, covering chat completions). Confirm it is shown as enabled. | "ZDR shown enabled", date |
| O-3 | Project **rate limits** for `openai/gpt-oss-120b`: set the lowest values offered (e.g. RPM 2; RPD if offered). Also read the org Limits page (free or Developer numbers for gpt-oss-120b). | the RPM/RPD/TPM/TPD values shown |
| O-4 | Billing: **free tier** (no spend-limit feature exists; usage is bounded by rate limits and the gate budget), or **paid** with an org-wide **spend limit** (minimum allowed, ≈ USD 5) + usage alert. Spend limits are org-wide, not per key or project, and lag 10–15 min. | tier; spend limit if paid |
| O-5 | Create **one project-scoped API key** in that project (name e.g. `f8-dev-gate`). Do not store it anywhere; keep the console tab open until G-5b. | the key's display name only |
| O-6 | State in chat the separate **installation authorization** for package `16c7417dc97a11ba6cf65fe44ef639e255bff22257f65d5f9bcefaab1af9d41a`, with O-1…O-5 confirmed. | authorization text |

## 2. Preconditions (re-checked at G-0; stop if any fails)

1. DEV is still the accepted Phase A state: `current → releases/f293e72-f8r2`, gateway active, DR-5 equals `7fe21378…`.
2. No DEV deploy since b9eb32c; the expected DR-5 block is unchanged.
3. Not within 45 min of `apt-daily*`, no dpkg lock, no unrelated pending reload or queued job. install, preserve and restore enforce this.
4. ≥ 2 GiB free; ≥ 1 GiB memory available.
5. No other DEV operation or freeze in progress (owner).

## 3. Gates

All SSH goes to **lilith-dev-01 only** (IAP), with scripts as gzip+base64 in `--command` (no stdin). The known plink crash (`0xC0000005`) means the output is not accepted until it is re-read from DEV files. `P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4`, `R=/opt/hermes-gateway-dev/current`.

| Gate | Action (root on DEV unless noted) | PASS criterion / STOP |
|---|---|---|
| G-0 | Record O-6 and the package hash. | — |
| U-0 | Read only: `readlink $R`, `sha256sum < $R/RELEASE.sha256` (full digest; its prefix must be `ffaed494e2643b2d`, from the Phase A record); gateway PID and state; DR-5 read via the f8r2 tooling. | F8r2 identity confirmed; record `F8R2_SHA` |
| G-2 | Transfer + `sha256sum -c` + MANIFEST | OK |
| G-1 | `bash $P/bin/backup_pre_install.sh` (with F8r2 running) | `F8_BACKUP_DONE`; this observation is the **rollback target** |
| G-1b | `bash $P/bin/dr5_check.sh …/dr5-pre.txt` | `F8_DR5_EQUAL 7fe21378…` |
| U-1 | `F8R2_RELEASE_SHA=<F8R2_SHA> bash $P/bin/preserve_f8r2.sh` | `F8R2_PRESERVED <dir>`. STOP on `F8_PRESERVE_FAIL` / HOLD. |
| G-3 | `bash $P/bin/install.sh` | `F8_INSTALL_STAGED f293e72-f8r4` (the only FAIL line allowed is `.env` MISSING) |
| G-3b | DR-5 | EQUAL |
| G-4 | F7 suite as lilith (RUNBOOK-f8r2 §7 block, with `$P` of f8r4) | `Ran 19 … OK` |
| G-5 | `bash $P/bin/provision_console_token.sh`; `verify_release.py --full` | `F8_TOKEN_PROVISIONED`; `F8_VERIFY_PASS full f293e72-f8r4` |
| **G-5b (OWNER)** | In **your own** terminal: `gcloud compute ssh lilith-dev-01 --zone=asia-southeast1-b --project=lilith-agent-260823-27389 --tunnel-through-iap`, then `sudo bash /var/tmp/f8/hermes-gateway-dev-f293e72-f8r4/bin/provision_provider_key.sh`. Paste the key at the hidden prompt, then clear the clipboard. | `F8_KEY_PROVISIONED sha256_prefix=…`; give only the prefix in chat |
| G-5c | `verify_release.py --full` | PASS (credential file root 0600 in a 0700 dir) |
| G-6 | `systemctl start hermes-gateway-dev` (pulls in the gate and the timer; never `enable`). Wait ≤ 90 s for 9901. | gateway + gate active, 0 restarts, static; listeners exactly `127.0.0.1:9901`, `127.0.0.1:9911`; `gate_budget.sh show` → `key_loaded:true, budget_used:0, available:true`; no unit pending reload; protected services unchanged |
| G-6b | `bash $R/bin/sandbox_probe.sh`; `bash $R/bin/gate_probe.sh` (**before any provider call**) | 23/23 including the explicit P7; gate probe PASS |
| **G-7** | `$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase B --core-api` (**the first real Groq requests: 4**) | `F8_SMOKE_PASS phase=B turns=4 35/35`: real replies; R0/R1 shadow decisions 4/4; budget +4; 4 FORWARDED with status 200, ≤ 1024; no refused POST; K0–K2 |
| G-7d | `journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat \| grep FORWARDED` | every line: `token_cap_anomaly:false`, model pinned, `ratelimit` headers present. Compare the limits with O-3. |
| G-8 | retention oneshot | success |
| G-9 | `observe_host.sh` + `compare_observations.sh <G-1>` + DR-5 | `F8_OBSERVATION_EQUAL`, `F8_DR5_EQUAL` |
| G-10 | **5th and last request:** UI on `127.0.0.1` (unmodified devui, DEV-only env, as in Phase A), one synthetic message | reply + its Router V2 decision; afterwards `budget_used:5, state:BUDGET_EXHAUSTED` |
| G-11 (owner) | Groq console → project usage | exactly 5 requests in project `lilith-dev-f8`; cost as expected |

Then **STOP for owner acceptance**. The OPERATE profile (`apply_profile.sh operate`) only after acceptance. A budget reset is a separate owner decision.

### STOP conditions (any → stop, R-1, report)

- any FAIL line, or any F8_*_FAIL;
- any `token_cap_anomaly:true`;
- a provider status other than 200 during G-7/G-10;
- a refused POST;
- a missing Router V2 decision for a turn (B-7);
- budget delta ≠ turns;
- a protected-service PID, restart or InvocationID change;
- a DR-5 or observation difference;
- any non-loopback connection from the gateway;
- any key appearance (K1);
- a gate destination outside `api.groq.com`'s global address;
- unexpected reply content (non-synthetic, tool-like output);
- an unexpected Groq console usage count.

## 4. Rollback (all moves, never deletes; tested in the mirror)

| Step | Command | Result |
|---|---|---|
| R-1 | `bash $R/bin/rollback.sh stop` | gateway + gate + timer stopped; 9901/9911 closed; the Core API console returns 502 (as before Phase A) |
| R-2 | `bash $P/bin/rollback.sh remove` | every f8r4 path, **including the Groq key and the gate ledger**, moved to `/var/backups/hermes-gateway-dev/rollback-<ts>/` (0700). **Owner: revoke the key in the Groq console.** |
| R-3 | `bash $P/bin/restore_f8r2.sh /var/backups/hermes-gateway-dev/f8r2-preserved-<ts>` | F8r2 moved back exactly; inventory identical (every file hash, owner, mode, including state.db and logs); `RELEASE.sha256` digest = U-0; C-3-guarded reload with protected-service parity; F8r2 verify PASS; F8r2 gateway started (`F8R2_RESTORED`) |
| R-3v | F8r2 `smoke_console.py --phase A --core-api`; observation vs **G-1** (F8r2 running) + DR-5 | `F8_SMOKE_PASS phase=A 22/22`, `F8_OBSERVATION_EQUAL`, `F8_DR5_EQUAL` |

- If R-3 stops (`F8_RESTORE_FAIL`), the F8r2 quarantine is untouched. The owner decides.
- If a HOLD occurs (another unit pending), the owner decides on the reload.

## 5. Allowlist additions vs F8r2 (everything else as in RUNBOOK-f8r2 §4)

- **Gate files:** `/etc/hermes-provider-gate-dev/gate.json` (root 0644, critical-pinned) and `/etc/hermes-provider-gate-dev/credentials/` (root 0700; `groq-api-key` 0600, written only by the owner at G-5b).
- **Gate state:** `/var/lib/private/hermes-provider-gate-dev/ledger.log` (dynamic uid 0600) + the `/var/lib/hermes-provider-gate-dev` symlink, plus `/var/lib/private/` (0700) if absent.
- **Runtime:** `/run/credentials/hermes-provider-gate-dev.service/` (ramfs, gate uid only).
- **Gate unit:** `/etc/systemd/system/hermes-provider-gate-dev.service`, static, pulled in by the gateway.
- **Preserved F8r2:** `/var/backups/hermes-gateway-dev/f8r2-preserved-<ts>/` (record + inventory) and its quarantine.
- **Network:** only the gate process may reach the public internet. The gateway stays at `127.0.0.1/32`.

## 6. Mirror validation

WSL DEV mirror (real Core API b9eb32c, DEV unit texts, real deployer sudoers), synthetic Groq (`fake_groq.py`, test CA, `api.groq.com` → 1.2.3.4). **No real provider was contacted.**

| Run | Rows | Result | Evidence (sha256) |
|---|---|---|---|
| run 4 | 69 | 54 PASS + 14 CLEAN + 1 SUCCESS, **0 FAIL** | `f8r4-run4-evidence.tgz` 8d690bda…03ee |
| run 5 (confirmation) | 69 | 54 PASS + 14 CLEAN + 1 SUCCESS, **0 FAIL** | `f8r4-run5-evidence.tgz` df8692b8…6832 |
| gate matrix M01–M60 (each run) | 45 | **45 PASS / 0 FAIL** | `evidence/H-matrix.log` |

Coverage, by group:
- **Upgrade (U):** the F8r2 replica runs with state → `preserve_f8r2.sh` reports `F8R2_PRESERVED files=18410`. The guard refuses a missing install and a digest mismatch.
- **Install and gate (H):** G-3…G-7c, startup race, 5 synthetic turns, budget stop at 5, policy rejects, upstream 500 = spent with no retry, no key → no egress. The matrix covers redirect, rebinding, untrusted certificate, CONNECT, absolute-form, TE, oversize, tools, streaming, ledger crash and tamper, and the key never appearing in logs. Then G-8, G-9 obs/DR-5 EQUAL, the operate profile, R-1, R-2 including key removal.
- **Restore (R3):** `F8R2_RESTORED f293e72-f8r2 files=18410 (inventory identical)`. Identity, state, the Phase A smoke at 22/22, obs EQUAL to pre-upgrade, and DR-5 EQUAL.
- **Failure injection (FI ×8, PF, PG):** every stage stops cleanly and rolls back. Gate crash and config tamper fail closed. A pending reload or rollback HOLD stops the run.
- **FINAL:** obs EQUAL, DR-5 `F8_DR5_EQUAL 7fe21378…68f1c`.

Fix history inside this candidate's validation (mirror only):
- run 1: the upgrade backup was renamed `upgrade-pre-*`.
- run 2: modes are re-applied from the inventory after F8r2's quarantine chmod.
- run 3: a path with spaces led to the tab-separated inventory.
- runs 4 and 5: green.
