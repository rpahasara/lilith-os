# Slice 15B2b-B1b-3e — PR-1A M-A1: Stage the Attested Release

Status:

- **M-A1 LIVE MUTATION**
- **STAGED RELEASE ONLY**
- **ACTIVE RELEASE UNCHANGED** (`current -> releases/9ac7de2…`)
- **M-A2 NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A1_PASS`**

Branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, from main `d7f9f06`.
That is `CONTROL_SHA` plus the docs-only merge of the
[final gate record](slice-15b2b-b1b3e-pr1a-final-readonly-gate.md).

```text
staged release != selected release != active release
M_A1_PASS      != M-A2 authorization
```

## 1. Pinned identities and authorization

| Identity | Value |
| --- | --- |
| `PAYLOAD_SOURCE_SHA` (NEW) | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |
| OLD (active) | `9ac7de22bf977385ceb954624677e33f0bae062b` |

**Authorization.** The owner's first M-A1 instruction allowed transferring
only the archive. The reviewed `upgrade-stage` takes five arguments
(`<OLD> <NEW> <archive> <stamp> <baseline>`) and reads the stamp and the
baseline as regular files. I stopped before any DEV contact and asked the
owner. The owner then authorized a clarified scope:

- three inputs:
  - the archive;
  - the builder stamp bound by the attestation;
  - one canonical owner-baseline JSON;
- one transient `0700` directory, `~/b1b3e-pr1a-ma1-stage/`;
- the reviewed stage behaviour, including the offline venv build and the
  `runuser` import check as `lilith-authority-dev`.

Nothing beyond that was authorized.

## 2. Source freeze

- `origin/main` = `d7f9f06`. The only commit after `CONTROL_SHA` is the
  docs merge of the final-gate record (two docs files). There is no payload,
  installer, ceremony, or authority-semantics change, and `CONTROL_SHA` was
  not switched.
- The streamed tools are byte-equal to `git show c1eb568:<path>`:

  | Tool | SHA-256 (prefix) |
  | --- | --- |
  | installer | `fe10d9a3` |
  | observer | `a2f21b45` |
  | attestation tool | `709cd552` |
  | broker verifier | `bbca69bc` |
  | needrestart probe | `edd23ac7` |

## 3. Inputs (verified locally, then on DEV before use)

| Input | Full SHA-256 | Size |
| --- | --- | --- |
| archive `lilith-authority-dev-release.tar.gz` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` | 5 354 725 |
| builder stamp `lilith-authority-dev-release.attestation.json` (= attestation `builderStampSha256`) | `9441c985ab5724f68bd9e0199ac98593b930236150ef10778c242f673bdb1b42` | 342 |
| owner baseline `owner-baseline.json` | `8cc1a58a8f2655963374ac691bdae34d772b49b6505e93cdafefd7eb45e7b73e` | 558 |

**Baseline.**
- The baseline is `install_authority_dev.canonical()` of exactly the
  reviewed `BASELINE_FIELDS`:
  - `baselineType`, `schemaVersion`, `oldRelease`;
  - `currentBlob`: `kind`, `device`, `inode`, `size`, `uid`, `gid`,
    `mode`, `mtimeNs`, `ctimeNs`, `sha256`;
  - `hostKey`: the same identity fields without `sha256`; stat only;
  - `signerAccount`: `uid`, `gid`.
- Every value equals the accepted preflight §15 baseline and the final-gate
  re-observation.
- There are no secrets, notes, or timestamps. The reviewed `parse_baseline`
  accepted it locally.

**Artifact check.**
- `SHA256SUMS` passed.
- `attest_authority_dev_build.py check` returned `PASS` with attestation
  digest `86ed2659…c683`.

## 4. Live contact

| Item | Value |
| --- | --- |
| Window | 2026-09-28 `14:09:40Z` (PRE) to `14:26:17Z` (last POST) |
| Mutation | `upgrade-stage` ran `14:25:06Z`–`14:25:18Z` |
| Target | `lilith-dev-01` only. PROD was not contacted |
| Principal | OS Login `ravindupahasara2_gmail_com`, via `gcloud compute ssh` / `gcloud compute scp --tunnel-through-iap` |
| Privilege | the existing `sudo` to root for the streamed tools. The transfer and the staging directory were made as the operator, without sudo |
| Transport wrapper | local `drive.py`, SHA-256 in the evidence `SHA256SUMS` |
| Evidence | `C:\Users\edufo\lilith-b1b3e-pr1a-aee323e…\ma1\`, with `SHA256SUMS` |

## 5. PRE (read-only)

The reviewed observer's `stableSha256` was
`c6663364de56fb9b67a43b7b6466d3a51318e0cb0fb9654c045a9e6fd49d1818`. That is
identical to both final-gate runs, and **no section differs**. Everything
below matches the final gate:

- **Boot and broker:** boot `24d1771d-e1b5-4e5f-816d-da08ad8b367a`, no
  reboot. `BROKER_PRESERVATION=PASS`, incarnation `42af2691…`, PID 132976,
  start ticks 108213277, `NRestarts=0`.
- **Release:** `current -> releases/9ac7de2…`, and `releases/` =
  `[9ac7de2…]`. `status --expect L2b.2 9ac7de2…` passed.
- **CURRENT:** device 2049, inode 1738, size 219, ns times
  `1790493331258019177`, SHA-256 `6a61c350…73f3`.
- **Authority-dev:** inactive, `static`, never started.
- **PR-1:** every PR-1 object absent.
- **Activation:** `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.
- **Staging directory:** absent before this step.
- **Immediately before the stage:** `upgrade-status <OLD> <NEW> <baseline>`
  returned `state=EXISTING_ACCEPTED_OLD_RELEASE`, `result=PASS`,
  `failures=[]`. The stage was gated on this exact line.

## 6. Every mutation observed

| # | Mutation | By | Detail |
| --- | --- | --- | --- |
| 1 | created `/home/ravindupahasara2_gmail_com/b1b3e-pr1a-ma1-stage/` | operator | `mkdir -m 0700`, owned by the operator. Authorized transient transfer state |
| 2 | copied the three inputs into it | operator, `gcloud compute scp` | files `0664` inside the `0700` directory. On DEV they hashed to exactly the three pinned values. Two earlier attempts copied **nothing**: pscp refused `~`, and Git Bash rewrote `/home/…` into a Windows path. The third used an absolute path with `MSYS_NO_PATHCONV=1` |
| 3 | `install_authority_dev.py upgrade-stage 9ac7de2… aee323e… <archive> <stamp> <baseline>` | root, streamed from `CONTROL_SHA` | the reviewed M-A1. In order: re-checked the baseline, state, `status L2b.2 OLD`, and the deferred paths; ran `verify_archive`; created `releases/.aee323e….staging` (`0700`); wrote the 66 members; ran `python3 -m venv` and `pip install --no-index --require-hashes` from the attested wheels and lock; normalized ownership and modes in the staging tree only; ran the `runuser -u lilith-authority-dev` import check; renamed to `releases/aee323e…`; fsynced `releases/`; ran the full tree check. Report: `mutation=STAGED`, `state=STAGED_NEW_RELEASE`, `result=PASS`, `failures=[]` (the tree check is included) |

Side effects outside those paths:

- `/opt/lilith-authority-dev/releases` changed: `mtime`/`ctime` and
  `nlink` 3 → 4, as expected for a new entry.
- Session, `sudo`, and `runuser` PAM/journal accounting records, which
  cannot be avoided.
- `/nonexistent` is still **absent**: the offline pip created no home
  cache.

Nothing else changed (§7).

## 7. POST

| Check | Result |
| --- | --- |
| `upgrade-status <OLD> <NEW> <baseline>` | `state=STAGED_NEW_RELEASE`, `result=PASS`, `failures=[]` |
| selector | `current -> releases/9ac7de22bf977385ceb954624677e33f0bae062b`. **Unchanged** |
| release set | `[9ac7de2…, aee323e…]`. No `.staging` leftover |
| OLD tree | observer facts identical to PRE: manifest `c9f2f76e…`, tree `ac62b1dd…`, venv `03bf7233…` |
| NEW tree `releases/aee323e…` | `root:root 0755`. Manifest `1d578ca707a95134dab218c826408b4380e7af0b5839160f47ede37232b94e8f` = attested `manifestSha256`. 65 files, 0 mismatched, 0 not in manifest, no unexpected entry; all `0:0`, modes `0644`/`0755`. Tree digest `675c94825e5c658c595e85812d825f8336f49defcf0062a004a8ee07e1c1393a` = the value recomputed locally from the attested archive (66 files including the manifest). Every `assets/` and `cli/` member equals the attested unit and CLI digests |
| NEW venv (derived staging content; drift reference) | 1391 entries, file-set digest `530c145309a6d9d56a51de3ab6f008006a4109506aeba79cacc3610e731fd781` |
| active host files | observer `hostFiles` identical to PRE. The unit `249f2ec9…`, socket, tmpfiles, and keygen `f1e7020b…` are still OLD bytes. The five new CLIs and the witness units are still absent |
| CURRENT | observer `currentBlob` identical to PRE: kind, uid/gid `0:0`, mode `0600`, device, inode, size, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| host key | stat identical to PRE; never opened |
| services | observer `units` section identical to PRE. `lilith-authority-dev.service`/`.socket` inactive, `static`, `NeedDaemonReload=no`, `NRestarts=0`, never started. Witness units `not-found`. No daemon-reload (`NeedDaemonReload=no`, and the unit files are unchanged) |
| accounts | identical: signer 995/985; no witness account |
| PR-1 objects | all absent: no custody root, PREPARED, RETIRED, K-WIT, ledger, witness state, hold store, registry, owner inputs, or skeleton |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`. Incarnation `42af2691…`, PID 132976, start ticks 108213277, `NRestarts=0`, boot `24d1771d…` |
| needrestart | `NEEDRESTART_LILITH_OVERRIDE=PASS` |
| observer sections changed PRE → POST | only `releases` and `listings`: the new release directory and the `releases/` directory times and nlink. `host` differs only in the volatile fields |
| `status --expect L2b.2 9ac7de2…` | `FAIL [RELEASE_SET]`. This is **expected**, because the transient `{OLD, NEW}` release set is exactly what that status contract refuses (preflight FI-4). `upgrade-status` is the governing POST for this phase. The command's nonzero exit made gcloud print its generic troubleshoot hint; there was no connectivity fault |

## 8. Result

```text
M_A1_PASS
```

The reviewed candidate release is staged, byte-identical to the attested
artifact, and the active system is still the accepted old baseline.

## 9. State left for the owner

- **Transient transfer directory.**
  `~/b1b3e-pr1a-ma1-stage/` stays, with its three inputs, until a separately
  authorized cleanup (like B1b-3d S-2).
- **Freeze.** Routine DEV deployment freeze (preflight §9): no merge to
  `main` should run a routine deployment between `upgrade-stage` and
  `upgrade-retire-old`.
  - DR-5 accepts two 40-hex release directories, but the accepted rule is a
    freeze.
  - This record's branch is therefore **not** proposed for merge yet.
- **Status contract.** Until M-A6, `status --expect L2b.2 9ac7de2…` fails
  `RELEASE_SET`. The PRE for M-A2 is `upgrade-status … STAGED_NEW_RELEASE`
  plus the observer, broker, and activation checks.

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A1
EXACT ATTESTED ARTIFACT USED
ACTIVE RELEASE STILL 9ac7de2
CURRENT CREDENTIAL UNCHANGED
NO SELECTOR SWITCH
NO UNIT REPLACEMENT
NO CLI REPLACEMENT
NO DAEMON-RELOAD
NO SERVICE START/STOP/RESTART
NO K-WIT
NO LEDGER
NO WITNESS
NO HOLD
NO REGISTRY CHANGE
NO KEY ROTATION
ACTIVATION STILL DARK
M-A2 NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
