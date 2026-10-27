# F7 local Hermes DEV reconstruction and offline validation (2026-10-23)

**Scope:** an infrastructure smoke-test build only, with every cognitive lane OFF and an import stub for
`world_context`. It is NOT the complete LILITH cognitive runtime. No PROD/DEV contact, no services, keys, model calls,
repository copies or commits.

## Assembly

| Part | Source | Verification |
|---|---|---|
| `hermes-agent/` | local clone of verified upstream NousResearch/hermes-agent `f293e7206b4ddd66042329442c6afebc19a8808d` | HEAD recorded in `hermes-agent.HEAD` |
| `gateway/run.py` | upstream + quarantine diff (Router V2 seam + Slice 9) | `2774eee5…2c2553` = PROD |
| 4 containment files | upstream + repo `slice-15b2a/patch_slice15b2a.py` (LF) | all = PROD |
| `tools/legacy_canonical_containment.py` | repo `slice-15b2a/` | `c1667e62…` = PROD |
| tree state | `git status`: 5 modified + 1 new, +186/-5 | identical to PROD |
| `hermes-home-dev/lilith_router` | 7 quarantine originals + `gateway_integration`, 16 modules from repo history, 4 rebuilt by repo patchers | 27/28 modules = PROD |
| DEV-only | `world_context.py` import stub, fresh `router.yaml`, hardened `plugins/lilith_os/adapter.py`, fresh `config.yaml` | see dev-candidate `CHANGES.md` |
| venv | `uv sync --frozen --no-dev`, CPython 3.11.16 (= PROD), uv.lock `64a66f8a…` | 65 dists, `venv-dists.txt` |

**PROD drift:** PROD's venv is not a pure `uv.lock` install. Of the shared packages, 42 have the same version and 17
are newer on PROD; 52 packages are PROD-only (messaging extras plus lazy installs), and the 6 DEV-only packages are
Windows-specific. DEV uses the lock.

**This is a Windows build:** it validates source, configuration and logic. The DEV installation must rebuild the venv
on Linux from the same `uv.lock` and re-run these tests there.

## Offline tests: `tests/test_f7_offline.py`, 19/19 OK (`tests/last-run.log`)

- **Adapter (real plugin discovery):** missing or short token gives 503; wrong or absent token gives 401; the correct
  token gives 200 with `{reply, state, session}`; a 70 KiB body gives 413; empty or invalid JSON gives 400; the bind is
  127.0.0.1 and the console is unreachable on the LAN IP. Negative control: PROD's original adapter fails 4 of these
  checks (no-token and short-token accepted, no size cap).
- **Tools:** the DEV pin plus the deny-list expose 0 tools. With every Hermes toolset enabled, the deny-list still
  leaves 0 tools (negative control without it: 34 tools, including `terminal` and `write_file`). Forced kanban mode
  also leaves 0.
- **Router V2:** all paths resolve under the DEV HERMES_HOME. Shadow mode never overrides. Live social without Groq
  credentials fails open. Live social with a synthetic runtime routes to Groq, with no network call. A lane enabled
  with the stub fails open. `enforce_reply` passes replies through.
- **Background writers:** memory, user profile, nudges, background review, curator, kanban dispatch, agent cron, MCP
  and lazy installs are all off. Sessions: idle reset after 24 h, auto-prune at 7 days, at most 4 concurrent.
- **Venv immutability:** no package installed during the run (an earlier run without the kill-switch lazily installed
  edge-tts and aiohttp from PyPI; the venv was restored with `uv sync --frozen`).
- **Home isolation:** no write to any fallback `~/.hermes`.
