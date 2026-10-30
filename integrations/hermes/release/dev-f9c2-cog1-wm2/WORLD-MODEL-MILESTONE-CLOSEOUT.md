# Close-out: World Model integration on DEV (wm1 shadow, wm2 live, synthetic belief S0–S4), 2026-10-28 – 2026-10-29

**Decision:** the owner accepted the World Model milestone as complete **within its tested scope** on 2026-10-30.
This record is documentation only. It authorizes no deployment, lane change, budget change or PROD action.

**Original S2 result: FAIL, unchanged.** Positive grounding is accepted only through the **separate**
S2-SUPPLEMENTAL ACCEPTANCE (section 3), not through a re-graded S2.

## 1. What was tested and accepted

| Stage | Release / window | Result | Owner decision |
|---|---|---|---|
| WM1 shadow | `f293e72-f9c2-cog1-wm1`, 2026-10-28 | PASS | Accepted (shadow only); see `../dev-f9c2-cog1-wm1/ACCEPTANCE-20261028.md` |
| WM2 live, empty state | `f293e72-f9c2-cog1-wm2` window W1–W7, 2026-10-28 17:56–18:03Z | PASS | Accepted for empty-state integration |
| S0 read-only preflight | 2026-10-29 09:20Z | PASS | – |
| S1-P isolated probe | 2026-10-29 09:44Z | PASS | – |
| S1-W synthetic belief write | 2026-10-29 09:50Z | PASS | – |
| **S2** live window (positive + control) | 2026-10-29 10:15–10:25Z | **FAIL** (validation defect, section 2) | **Remains FAIL** |
| S2-C negative control only | 2026-10-29 10:37–10:47Z | PASS | Accepted separately as S2-SUPPLEMENTAL |
| S3 synthetic-belief cleanup | 2026-10-29 11:30Z | PASS | Accepted |
| S4 backup disposition | 2026-10-29 19:01Z | PASS | Accepted |

**Capabilities demonstrated on DEV:**
- **WM shadow:** World Model routing in shadow on `lilith_os` only. It made 0 Core API reads and 0 provider calls,
  and its decision records held no message text.
- **WM live, empty state:** a belief question made exactly one read-only `GET /os/world` for the asked entity and 0
  writes. With no stored belief, the reply honestly said it had none.
- **WM live, stored belief (S2 turn A):** with one synthetic `TEST_ONLY` belief stored for `career.application` 999,
  the same single read grounded the reply. The reply reproduced the belief's status token, lifecycle (ACTIVE),
  epistemic state (Observed) and confidence (0.8, high), with 0 Core API writes.
- **WM live, unrelated message (S2-C):** a fresh-session small-talk turn made 0 Core API accesses and wrote one
  routing record only. Under the normalized leak rule, the reply did not contain the synthetic token.
- **Reversibility:** every window returned DEV to wm1 shadow by the reviewed `install_wm2.sh revert` path. S3
  restored the DB to its pre-S1 content and schema; S4 removed the temporary backup.

## 2. The S2 validation defect

- **The check:** S2 compared the reply byte-for-byte against the ASCII spelling of the synthetic status token.
- **What happened:** the model rendered the token with U+2011 NON-BREAKING HYPHEN, so the check reported it absent.
- **Effect:** by the reviewed failure path, the control turn (turn B) was never sent, and the window returned to wm1.
- **Fix:** S2-C used an explicit look-alike folding rule, which only maps listed hyphen and space look-alikes and
  removes zero-width characters. A positive match needs the exact-case full token; a leak is the token in any case or
  its distinctive word. The rule was tested offline against the recorded evidence.

## 3. S2-SUPPLEMENTAL ACCEPTANCE (separate record, owner-accepted 2026-10-29)

wm2 live World Model grounding on DEV is accepted on the combined evidence of:
- **(a) S2 turn A:** positive grounding under the documented U+2011 deviation;
- **(b) S2-C C4:** the negative control.

This record is not a full S2 re-run, and S2 remains FAIL.

## 4. Evidence (owner workstation, `%USERPROFILE%`; not in Git)

Each folder holds its scripts, `raw/` output and a `SHA256SUMS*` manifest. All manifests below were re-verified
intact on 2026-10-30, after S4.

| Record | Folder | Manifest | SHA-256 |
|---|---|---|---|
| Synthetic-belief plan | `lilith-dev-wm-synthetic-belief-plan-20261029` | `PLAN.md` | `053822b44c1b5c82888094e01f1e22c3742abc596e95e357a0c7aa1e8d12ea7f` |
| WM1 shadow test | `lilith-dev-wm1-shadowtest-20261028` | `SHA256SUMS` | `a23b1a1963af8a7d1c5a9904f7fc1e077338337ffcdc8bbf493dd06b3efbf7da` |
| WM1 dump removal | `lilith-dev-wm1-followup-20261028` | `SHA256SUMS` | `64bb65563f24f7e5061b9613e1108432e52ed01e4babe0fb0ee5767affa4278c` |
| WM2 empty-state window run | `lilith-dev-wm2-g2g3-window-20261028` | `SHA256SUMS.run` | `da483c00c49219a954ea0649964117513290d2287472f292fe3e881970ce1347` |
| WM2 empty-state acceptance | same | `SHA256SUMS.accept` | `426ed969d9f62f85dde2f88041e60309f459d047fc48ef65c2e09bb360640719` |
| S0 package (v2, as run) | `lilith-dev-wm-synthetic-belief-s0-20261029` | `SHA256SUMS.v2` | `7b6c922dd5462273df47357ed8cac2f91ed4c3f9bd35643e43ce73f328fd27d8` |
| S0 run | same | `SHA256SUMS.run` | `a711bbde8bbf6971cc6c2815b5d801bc35907884155713e2e2214e9ef92635ad` |
| S1 package | `lilith-dev-wm-synthetic-belief-s1-20261029` | `SHA256SUMS` | `459f41685e94ea391d30a38b05b25c4ae546b3b47a1e59384a91be2c9c42d175` |
| S1-P run | same | `SHA256SUMS.s1p-run` | `a00a4b544f25f293d3c97b84710ea04406d2c586a0cee24383f9ce7eced576fa` |
| S1-W run | same | `SHA256SUMS.s1w-run` | `924cb1b65a062727ee20cca542d3704df016ea5bda90b12ac55100a92bb12ce9` |
| S2 package | `lilith-dev-wm-synthetic-belief-s2-20261029` | `SHA256SUMS` | `1604c6aee0464a6cce883c2479a41ce28231d06202ec82986c4daa6925789d00` |
| **S2 run (FAIL)** | same | `SHA256SUMS.run` | `799992a864d52a5a575c7e629bd02e0a4a880e3ba1ca6a83c6c4cb98ca79c481` |
| S2-C package | `lilith-dev-wm-synthetic-belief-s2c-20261029` | `SHA256SUMS` | `21e19f6c74e9a1f42239c933fe0bc05a46f18bfd8bff8910cbe7d11a2c53e5a2` |
| S2-C run | same | `SHA256SUMS.run` | `ba56e4d2fde6be9503505f00d4d0656ab99da924efb4a577319bb8853abe750b` |
| S2-SUPPLEMENTAL ACCEPTANCE | same | `SHA256SUMS.accept` | `fb4ac55a12ff0f445189575c26d4c9b9b8e8e7f0252a97578f4406cd332c1c1f` |
| S3 package | `lilith-dev-wm-synthetic-belief-s3-20261029` | `SHA256SUMS` | `cd9f2f50695dff6245de6ad755e22c72b7033e2c7eb8e0a657a24a40d8806f64` |
| S3 run | same | `SHA256SUMS.run` | `9f61111719e784725afb9250f49073087e0e1396e00c91903ad7071adf8e888b` |
| S4 package | `lilith-dev-wm-synthetic-belief-s4-20261029` | `SHA256SUMS` | `179190ce2ab27d244e8a785fb7b6c7220c3d6cbf21f5e55305e7a8286e9510b4` |
| S4 run | same | `SHA256SUMS.run` | `867089667c47df16b149e1a2aa70a76673d67cb529f32b64b82a27e90dbf7ad5` |

**Key fingerprints:**
- **Pre-S1 logical DB digest** (schema plus every table): `4faaa5fd910ae81f0d2ae6dbeaf49d31c3d60873d55511217b7701ddbfa7608c`.
  It was recorded in S1-W, re-matched after S3, and re-matched before and after S4.
- **Removed backup:** file SHA-256 `bf95c7358c588e2483769b23c63cf0ceec13b16d3d3509ff3653b141066fd3cf`.

**Note on S0's first manifest:** S0's original `SHA256SUMS` (v1) no longer matches two revised S0 files. That
revision was approved and run as `SHA256SUMS.v2`, which verifies.

## 5. Final DEV state (S4 post-check, 2026-10-29 19:01:20Z)

- **Release:** `current` = `f293e72-f9c2-cog1-wm1`, router `4035f0a1`: World Model **shadow** on `lilith_os`, every
  other lane off. Gateway 351364 running, 0 restarts.
- **Other releases:** `f9c2`, `cog1`, `wm1` and `wm2` are intact. Two inert retired wm2 copies are kept:
  `.wm2-retired-20261029T101813Z` and `.wm2-retired-20261029T104039Z`.
- **DEV database:** every table has 0 rows, integrity is ok, there are no side files, and the logical digest equals
  the pre-S1 reference. No synthetic World Model record remains.
- **Provider budget:** **4 of 5 used, 1 request open**; ledger 20 lines, append-only. No reset was made.
- **Services:** FORGET idle with its units active. Core API, memory broker, authority, recovery witness and provider
  gate are unchanged. No failed units. The 7-day retention timer is active.
- **Backup:** the temporary backup file was removed; its directory `/var/backups/lilith-wm-synth-20261029` remains,
  root-only and empty.
- **PROD:** not accessed at any point.

## 6. Limitations (not claimed)

- **Coverage:** one synthetic belief, one entity type (`career.application`), and one positive and one unrelated
  turn, each on a fresh session. No populated real data, no multi-belief or conflict reasoning, and no claim that
  grounding *caused* every element of the reply beyond the reproduced fields.
- **The unified S2 protocol never passed:** the positive and control turns never ran in one window under one rule.
- **Control scope:** the control covers one unrelated phrasing only.
- **Channels:** only the `lilith_os` channel was exercised; Telegram and Discord were not.
- **Other lanes:** Goals, Reasoning, Workspace, Motivation, Planning and Ethics remained off throughout.

## 7. Remaining synthetic artifacts (no action taken)

- **Sessions:** Hermes data for the test sessions `wm2-live-test-20261028`, `wm2-synth-a-20261029` (its reply holds
  the synthetic token) and `wm2-synth-c-20261029`, plus their content-free decision-log records. These remain under
  the existing 7-day retention and FORGET.
- **Ledger:** provider-gate ledger lines (metadata, append-only).
- **Backup directory:** the empty directory named in section 5. Removing it needs separate approval.

## 8. Outstanding work

1. **Goals and Executive (Slice 8) on DEV:** shadow validation first, live validation only if separately authorized.
   `GET /os/goals/focus` writes a `goal_trace` row, and first reads can create missing goal tables. This must be
   resolved before any read-only claim.
2. **Remaining recovered lanes:** Reasoning, Workspace, Motivation, Planning and Ethics, one at a time on DEV.
3. **Unified PROD release:** promotion is a separate, later decision. Nothing here changes PROD.
4. **Remaining provider request:** it stays unused until a separately approved window.
