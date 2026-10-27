# VM-only source gaps

Deployed artifacts whose bytes exist only on a host (and in that host's disk snapshot), not in Git and not on any
development machine. Status of every row: `VM_ONLY_SOURCE_PENDING_SEPARATE_EXPORT`. None may be reconstructed by
guesswork or replaced by a DEV file. Closing a row needs a separately approved, owner-run, sanitized export of that
host, then a reviewed PR. Recorded 2026-10-27 from the read-only PROD and DEV audits of that day.

Current preservation: PROD files are on `lilith-01` and in GCP snapshot `lilith-01-preserve-20261027`; DEV files are
on `lilith-dev-01` and in `lilith-dev-01-preserve-20261027`. A disk snapshot is crash-consistent recovery, not a
source archive.

## PROD `lilith-01` (`~` = `/home/lilith/.hermes`)

| # | Deployed artifact | Full SHA-256 (PROD audit) | Kind | Should enter Git? | Target path after review |
|---|---|---|---|---|---|
| 1 | `~/lilith_router/world_context.py` (91,351 B): Working Memory assembly and seven-lane orchestration | `46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104` | source | yes | `integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py` |
| 2 | `~/lilith_router/world_context.py.bak.*` (9 construction stages) | not hashed | source lineage | yes, after review | `integrations/hermes/history/prod/world_context/` |
| 3 | `~/lilith_router/router.yaml` (every lane live) | `7d14b571abc73766782fbe2d534e85a4fb1fef628592b478b9747f7c76639586` | configuration (non-secret; one Discord channel id) | yes, reviewed | `integrations/hermes/home/variants/prod-lilith-01/router.yaml` |
| 4 | `~/lilith_router/_patched/` (`config.py` `0a9949ba…`, `gateway_integration.py` `9feac66c…`, `router.yaml` `ca451e5f…`, `world_context.py` `e507154e…`, `planning.py`, `test_planning.py` `db84d6f9…`) | as listed | patch staging copies | yes, as history | `integrations/hermes/history/prod/_patched/` |
| 5 | `~/lilith_router/tests/*` (15 Router V2 tests, e.g. `test_world_context.py` `afc7623d…`, `test_workspace.py` `56e36e55…`) | recorded per file in the PROD audit | tests | yes | `integrations/hermes/home/variants/prod-lilith-01/lilith_router/tests/` |
| 6 | `~/lilith_router/CURRENT_STATE.md` | `1a4bfbbf0212fffa8c892a2790b521760ae0725ba63113cb7cadf6f486612de2` | operator notes | yes, after privacy review | `integrations/hermes/history/prod/` |
| 7 | `~/lilith_router/tools/probe_groq.py` | `0b0a184d108c936d52a7a32ac790d484792e54b372d58ca51b04fb8f55d58d31` | utility (Groq probe) | yes, after review | `integrations/hermes/home/variants/prod-lilith-01/lilith_router/tools/` |
| 8 | `~/lilith-os/apps/career/*.py` (10 files, e.g. `career_watcher.py` `5aa0193f…`, `career_extractor_v2.py` `8ec99391…`) | recorded per file in the PROD audit | source (World Model feed) | yes, after review for embedded addresses | `services/career/` (new, reviewed) |
| 9 | `~/automation/productivity/*.py`, `prompts/morning_brief.txt`, `config.json` | not hashed | source + configuration | source yes; `config.json` only as a template | `services/automation/` (new, reviewed) |
| 10 | `~/lilith-os/api/app.py.bak.*` (20, including the hand-patched `743a804a` era) | not hashed | Core API lineage | yes, as history | `integrations/hermes/history/prod/core-api/` |
| 11 | `/home/lilith/*.py` 2026-08-26 experiments, `lilith_conversation_router.py` | not hashed | pre-Router V2 prototypes | yes, as history | `integrations/hermes/history/prod/prototypes/` |
| 12 | `~/config.yaml` (Hermes PROD) | not hashed | configuration with provider settings | template only, secrets removed | `integrations/hermes/release/prod-lilith-01/templates/` |
| 13 | `~/SOUL.md` `d082db5a…`, `~/memories/USER.md` `6d7804ef…`, SOUL backups | as listed | **private persona / profile** | **no** (ADR-0008, ADR-0016); a separate Privacy decision | none |

Never part of a source export: `.env`, `auth.json`, `*.env`, Google tokens, authority `*.key` files, `state.db` and
other databases. These belong to separate custody and backup domains.

PROD Hermes code itself is not a gap: upstream `f293e72` + `integrations/hermes/patches/prod-lilith-01.patch`
rebuild every patched file byte-exact. The PROD virtualenv (111 distributions, not built from a lock) is not
reproducible exactly; that is a dependency gap, not a source gap.

## DEV `lilith-dev-01`

| Artifact | Kind | Status |
|---|---|---|
| `/etc/hermes-provider-gate-dev/gate.json` with the live client token, the Groq project key, the console token | credentials | host-only **by design**; never in Git |
| `60-origin-executor.conf` drop-ins (×3), `/etc/hermes-forget/executor.json`, `/etc/hermes-gateway-dev/critical.sha256` | generated configuration | regenerable from `integrations/hermes/release/dev-f9c2/bin/install_f9c.sh`, `pin_critical.sh` and the FM-2 transition tooling |
| `/etc/lilith-os-dev/canonical-runtime.json`, owner registration | host configuration | host-only; protected by the DEV snapshot and the transition records |
| The authoring diff that produced DEV `gateway_integration.py` `5ce4bbd4…` | source lineage | the result bytes are in Git; the authoring patch was never kept as a file |
