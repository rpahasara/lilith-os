# First Memory FM-1 — Signer Release Transition (57bff671 → e2324a5)

Status:

- **SOURCE ONLY.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE` in this change. Base: main `e2324a5` (PR #258).
- Tooling for `UPGRADE_FM1_FIRST_MEMORY_SIGNER_DEV_SYNTHETIC`: `fm1_signer_upgrade.py` (contract and release pin),
  `fm1_release_stages.py` (host stages, F-phase) and `fm1_operator.py` (owner laptop). Each reuses the E-23 tool
  it mirrors, unchanged ([E-23 completion](trackb-e23-completion.md)).
- **Not claimed:** owner registration, memory creation, First Memory, a DR-5 target, or PROD.

## 1. The release pin

The NEW release is built from the PR #258 merge commit, using the existing V3 builder, with no new builder. Evidence:
`C:\Users\edufo\lilith-fm-final-build-e2324a5…\`, `EVIDENCE-SHA256SUMS` `e7c73120…`.

| Field | Value |
| --- | --- |
| NEW release | `e2324a5f89200aa5f374c4a43a13cb76b36376f9` |
| Manifest | `a2f32664133bf3aff48f621e475f4b8455c3cff51ddb029df53c45ab191db859` |
| Archive | `6924ed9f…` (5,384,365 B), builder stamp `974b848b…` |
| Attestation | `c07701d0…` REPRODUCED (Windows A = WSL B, identity `decd8c9d…`); `check` PASS on both archives |
| Delta vs installed `57bff671` | exactly 10 changed signer members + 2 added (`issuance.py`, `verifier.py`) + manifest |
| Witness payload | byte-identical: all 16 witness members; `recoveryWitnessReleaseDigest` `c911b733…` in both attestations |

`PinTests` proves the delta against `git show 57bff671:<source>` and the repository bytes.

## 2. Why the witness also restarts

The witness payload does not change. But the witness unit runs from the shared `current` selector with
`Restart=on-failure`. A witness left running from OLD across the select would come back from NEW after any failure,
and nobody approved that version switch. The ladder is therefore the E-22 order, without E-23's witness-units step:

1. stop both units;
2. select NEW;
3. start the unchanged witness from NEW (one K-WIT and one K-PAN load, with its own owner go and acceptance);
4. start the signer (one K-ACT load).

A unit running from OLD after the select is a STOP (`FS_UNIT_RUNNING_FROM_OLD_AFTER_SELECT`). So is an automatic
restart (`NRestarts` ≠ 0).

| Phase | Releases | `current` | Signer | Witness |
| --- | --- | --- | --- | --- |
| F0_OLD_EXACT | OLD | OLD | OLD | OLD |
| F1_NEW_STAGED | OLD, NEW | OLD | OLD | OLD |
| F2_SIGNER_STOPPED | OLD, NEW | OLD | — | OLD |
| F3_WITNESS_STOPPED | OLD, NEW | OLD | — | — |
| F4_NEW_SELECTED | OLD, NEW | NEW | — | — |
| F5_WITNESS_RUNNING | OLD, NEW | NEW | — | NEW |
| F6_SIGNER_RUNNING | OLD, NEW | NEW | NEW | NEW |
| F7_OLD_RETIRED | NEW | NEW | NEW | NEW |

**Fixed in every phase:**

- The witness unit and tmpfiles files stay at the installed E-23 bytes, with no reload pending.
- K-PAN stays present exact.
- The Privacy anchor directory keeps only the anchor service's names, and its chain files are reported by digest.
- The operator requires the credential metadata, the anchor and the foreign incarnations to equal the preflight
  baseline.
- No stage starts, stops or reloads a unit, or touches a credential, custody, HELD, the ledger or the witness state.

**Retirement** needs three things:

- both accepted replacements are running from NEW;
- the gate status reports no process using `releases/<OLD>` (`/proc` cwd, exe and maps);
- the stage tool's own `release_users` guard passes.

If anything still uses OLD, the operator refuses before it consumes the go, and OLD stays installed.

## 3. Owner approvals, in order

Each approval below is a separate go, rendered by `fm1_operator render`, run once and never retried.

| # | Approval | Effect on DEV |
| --- | --- | --- |
| 0 | Merge this PR (`CONTROL_ONLY_NO_DEPLOY`: no Core API deploy or restart) | none |
| 1 | TRANSFER: copy the archive and stamp into `/home/<oslogin>/lilith-fm1-transfer` (as done for E-23) | 2 files |
| — | `preflight` (read-only; records the F0 baseline) | none |
| 2 | FM1-GO-STAGE | `releases/e2324a5…` beside OLD |
| 3 | FM1-GO-SIGNER-STOP | ends signer `639a814d…`/281830 |
| 4 | FM1-GO-WITNESS-STOP | ends witness `86ba4cc2…`/281470 (service and both sockets) |
| 5 | FM1-GO-SELECT | `current` → NEW |
| 6 | FM1-GO-WITNESS-START | **one K-WIT and one K-PAN load**; unchanged witness from NEW |
| 7 | Witness acceptance (verbatim, after `verify WITNESS`) | none |
| 8 | FM1-GO-SIGNER-START | **one K-ACT load** (the 4th); signer from NEW |
| 9 | Signer acceptance (verbatim, after `verify SIGNER`) | none |
| 10 | FM1-GO-RETIRE (only when no process uses OLD) | removes `releases/57bff671…` |

Credentials, K-ACT, K-WIT and K-PAN, are loaded only, never replaced.

**Deploy freeze:** no deploy or restart of the Core API, Hermes or broker runs from preflight to F7 or a STOP, and no
memory creation happens before F7.

**Deferred, not needed for First Memory:** a post-F7 re-pin of the installed-release bindings (`DEV_PINS`,
`DEV_EXPECTED`) and a DR-5 target. This is the E-23 completion pattern, and it is a separate change.

## 4. STAGE STOP: owner adjudication (PROPOSED until merged)

```text
adjudicated STOP != reached step;  chain continuation != any go;  the next step still needs its own fresh gate and go
```

On 2026-10-26, FM1-GO-STAGE (canonical go `d62eeedd4b4b59445f1ff8d082d882170ea981946b985dfeca7ff5c1ab605da0`) ran
**once** from control `7702b01`. Evidence is in `C:\Users\edufo\lilith-fm1-transition-7702b01\`
(`SHA256SUMS.seal-2-stage-stop` `469c7b0a…`).

| Item | Value |
| --- | --- |
| Gate | observation 02: `F0_OLD_EXACT` |
| Marker | `attempts/fm1-stage.json`, consumed |
| Remote | one `fm1-stage`, rc 0, mutation `STAGED`; its own post-check reported `F1_NEW_STAGED`, PASS |
| Post | observation 03: local exit code `3221225477` (`0xC0000005`, the known Cloud SDK plink exit crash), so the operator judged `STATUS_NOT_RECEIVED`. The output was complete and re-judges to `F1_NEW_STAGED` |
| Step record | `steps/01-STAGE/STEP.json`, result `FM1_STAGE_STOP`, SHA-256 `b82b4a5b94451313b84818860a5b8d0e06fc4815c275966c8b35d252f5e7fb4e` |
| Re-observation | observation 04, one read-only `status` with no go and no marker: rc 0, `F1_NEW_STAGED`. Its bytes (`420f785a…`) are identical to observation 03 |

The host is exactly F1:

- releases `{57bff671, e2324a5}`, with `current` → OLD;
- the NEW manifest is the pin `a2f32664…`;
- signer `639a814d…`/281830 and witness `86ba4cc2…`/281470 are unchanged and still on OLD;
- credentials, anchor and foreign units equal the preflight baseline.

No retry and no repair was made.

**Adjudication.** `fm1_operator.ADJUDICATED_STEPS` pins exactly that `STEP.json` digest. The STAGE step then counts as
reached for the step chain only:

- it never runs again, because its marker stays consumed;
- the next step (SIGNER_STOP) still needs its own owner go and a fresh read-only gate reading `F1_NEW_STAGED`;
- any other record digest, or any other STOP, still blocks the chain.
