# Owner-run, read-only PROD export for the LILITH Hermes DEV reconstruction (NOT EXECUTED)

The authorized operator runs this in their own PowerShell terminal. Claude Code does not run it: the auto-mode
permission classifier refused Claude-run PROD content transfer, and that refusal is respected rather than overridden.
Every remote command only reads, as user `lilith`. Nothing on lilith-01 is written, restarted or reconfigured.

## What is exported, and why so little

The public upstream NousResearch/hermes-agent @ `f293e7206b4ddd66042329442c6afebc19a8808d` (hermes-agent 0.20.5) has
been fetched and verified against PROD's git HEAD fingerprints. Everything else that can be rebuilt from upstream plus
repo patchers byte for byte (verified by SHA-256 against PROD) is **not** exported:

- 4 Slice 15B2a containment files (`background_review.py`, `memory_tool.py`, `skill_manager_tool.py`,
  `write_approval.py`), from upstream + `docs/architecture/slice-15b2a/patch_slice15b2a.py` (LF line endings)
- `tools/legacy_canonical_containment.py`, `learning.py`, `learning_store.py`, `memory_store.py`, `workspace.py`, plus
  16 router modules held verbatim in `docs/architecture/slice-*` and git history

**Stage 1** exports only the remaining custom source. It is listed with PROD SHA-256 values in `ALLOWLIST.tsv`:
the `gateway/run.py` delta (Router V2 seam + Slice 9), 7 router base modules and the `lilith_os` + Groq plugins
(12 files plus one diff, about 110 KB).

**Stage 2** (`world_context.py`, 91 KB, higher personal-data risk) is requested **only if** the Stage 1 review shows
`gateway_integration.py` imports it unconditionally. Cognitive lanes stay off on DEV.

**Never exported:** `config.yaml`, `router.yaml`, `CURRENT_STATE.md`, any `.env`/`*.env`/`auth.json`/`*.key`, `state.db`
or other DBs, memories, `SOUL.md`, `decisions.log`, backups (`*.bak*`), `_patched/`, `checkpoints/`, tests and
`tools/probe_groq.py`. Fresh DEV `config.yaml`/`router.yaml` are generated from `config.py` defaults instead.

## Before running

1. Review `ALLOWLIST.tsv` and `verify_quarantine.py` (fingerprints are in this folder's `SHA256SUMS`).
2. Choose a quarantine folder **outside any git working tree**, for example
   `C:\Users\edufo\lilith-hermes-staging\quarantine-<date>\`. Exports stay there until signed off.

## Stage 1 commands (PowerShell, operator only)

```powershell
$g = "C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$Q = "C:\Users\edufo\lilith-hermes-staging\quarantine-$(Get-Date -Format yyyyMMdd)"
New-Item -ItemType Directory -Force $Q | Out-Null
$ssh = @("compute","ssh","lilith-01","--zone=asia-southeast1-b","--project=lilith-agent-260823-27389","--tunnel-through-iap","--quiet","--command")

# 1a. The Router V2 + Slice 9 delta to upstream gateway/run.py (read-only git; no index refresh)
& $g @ssh "sudo -n -u lilith env GIT_OPTIONAL_LOCKS=0 git -C /home/lilith/.hermes/hermes-agent --no-optional-locks diff HEAD -- gateway/run.py | base64 -w0" | Out-File -Encoding ascii "$Q\run.py.diff.b64"

# 1b. Exactly the 12 allowlisted files, as an uncompressed tar (paths relative to /home/lilith/.hermes)
& $g @ssh "sudo -n -u lilith tar -C /home/lilith/.hermes -cf - lilith_router/__init__.py lilith_router/config.py lilith_router/state.py lilith_router/classifier.py lilith_router/policy.py lilith_router/social_guard.py lilith_router/gateway_integration.py plugins/lilith_os/plugin.yaml plugins/lilith_os/__init__.py plugins/lilith_os/adapter.py plugins/model-providers/groq/plugin.yaml plugins/model-providers/groq/__init__.py | base64 -w0" | Out-File -Encoding ascii "$Q\stage1.tar.b64"
```

## Verify and review (local, no PROD access)

```powershell
python C:\Users\edufo\lilith-hermes-staging\export-plan\verify_quarantine.py $Q --stage 1
```

- **Exit 2 means integrity failure.** Discard the quarantine folder. Nothing in it is usable.
- **Exit 0 means every file matched its PROD hash**, `upstream run.py + diff == PROD run.py (2774eee5…)`, and the
  files were written read-only to `$Q\extracted\`. `$Q\REVIEW.md` then lists every secret-like, personal-data and
  confidential-path finding, with secret values masked.
- **The owner reviews `REVIEW.md` and signs off file by file.** A file with any unresolved SECRET finding is never used.
  Personal references in persona text (`policy.py`, `social_guard.py`, `classifier.py`) are either accepted for DEV or
  replaced with DEV-neutral text in a reviewed derivative. The originals stay in quarantine.
- Nothing is copied into any repository or DEV host until that sign-off. Exported code is never imported or executed
  during review.

## Stage 2 (only if required)

```powershell
& $g @ssh "sudo -n -u lilith tar -C /home/lilith/.hermes -cf - lilith_router/world_context.py | base64 -w0" | Out-File -Encoding ascii "$Q\stage2.tar.b64"
python C:\Users\edufo\lilith-hermes-staging\export-plan\verify_quarantine.py $Q --stage 2
```

## Permissions involved

- **The operator's own gcloud identity** (IAP tunnel + SSH to lilith-01; passwordless `sudo -u lilith` for reads).
  Nothing else is needed.
- **Claude Code** keeps its current permissions. It does not run the commands above. After the owner places the
  outputs in the quarantine folder, Claude may run `verify_quarantine.py` locally and read `REVIEW.md` and the
  extracted files, if the owner asks.
- **Separate approvals are still required later:** DEV provider credentials, installing Hermes on lilith-dev-01,
  copying sanitized sources into the repo, and any commit/PR/deploy.
