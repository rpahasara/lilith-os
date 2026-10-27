# PROD `lilith-01` source history

Historical source recovered from the original PROD VM on 2026-10-27 by the owner-approved, bounded read-only export.
Every file was hash-verified against the PROD read-only audit of the same day, where that audit hashed it. It
explains how PROD's Router V2, Working Memory and Core API reached their deployed state.

**Nothing here is active code.** Nothing installs, imports or runs it. Several scripts call providers or act on a
host; they are kept for provenance only.

| Path | Contents |
|---|---|
| `world_context/` | the 8 distinct construction stages of the deployed Working Memory module. `…bak.20260908-091656` is the Slice 7.2 base |
| `lilith_router/` | `.bak` versions of the router modules (config, gateway_integration, policy, social_guard, state, ethics, learning_store) and of `router.yaml`; `_patched/` (Slice 12 staging copy); the 08-26 checkpoint; two superseded test versions; `tools/probe_groq.py` (a provider probe, never run here); `CURRENT_STATE.md` (operator record of Slices 7.2–15) |
| `hermes-home/lilith-os/api/` | the `app.py` backups not already in Git, from the first 6,772-byte API of 08-25 to the hand-patched `743a804a…` that the 2026-09-13 git import replaced |
| `hermes-home/lilith-os/apps/career/`, `hermes-home/automation/productivity/`, `systemd/` | career pipeline, automations and units (each with its own README) |
| `home-lilith/` | the 08-26 pre-Router-V2 prototypes from `/home/lilith`: Groq and social-voice bake-offs and `lilith_conversation_router.py` |
| `provenance/` | per-change-set JSON: PROD path, size, PROD and Git SHA-256, transform |
| `tests/` | offline checks for these trees |

## Not duplicated

- Files whose bytes are already on `main` or in Git history were not copied again. The provenance JSON lists only
  what each change set added. Examples: the git-imported `app.py` `bb0a4139…`, and module backups equal to the slice
  files under `docs/architecture/`.
- Byte-identical copies within the export were kept once.

## Changes from the PROD bytes

- `router.yaml` versions and `CURRENT_STATE.md`: the one Discord channel id is replaced by
  `__LILITH_DISCORD_CHANNEL_ID__`.
- Career scripts: the owner's two mailbox addresses are replaced by `__OWNER_PRIMARY_EMAIL__` and
  `__OWNER_SECONDARY_EMAIL__`.
- Everything else is byte-exact. The provenance files mark each case `BYTE_EXACT` or `SANITIZED_FOR_GIT`; the
  original bytes stay in owner custody.

## Finding: the hand-patched `app.py` lost nothing

`app.py.bak.gitdeploy.20260913T153019Z` is `743a804a…`, the hand-patched API that the 2026-09-13 git import replaced
with `bb0a4139…` (repo commit `519b309`). It has the same routes and the same top-level functions as `bb0a4139…`. The
import only made the data paths configurable (`HERMES_HOME`, `LILITH_DATA_DIR`, `LILITH_DB_PATH`) and fixed one
`os`/`_os` reference in the World Model maintenance loop. The read-only audit had left this question UNKNOWN.

## Left on PROD

- The 08-26 checkpoint of Hermes `run.py` (1,519,743 B, `dba8b053…`). The export's credential pre-scan matched it
  once (`keyed_literal`), so its bytes were withheld by rule. It is an upstream-derived Hermes file from before the
  Router V2 seam.
- The checkpoint `config.yaml` (PROD Hermes runtime configuration; template only by policy).
- The superseded `CURRENT_STATE.md` backups; the final file supersedes them.
- Persona, profile, credentials, databases, logs and conversation data were never read.
