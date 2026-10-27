# Router V2 and plugins (`HERMES_HOME` code tree)

The LILITH-authored code that Hermes loads from `HERMES_HOME`: the Router V2 package `lilith_router` (routing,
policy, social guard, and the cognitive lanes) and the plugins `lilith_os` (the Command Center console platform) and
`model-providers/groq`. Hermes itself is described in `integrations/hermes/README.md`.

## One copy of each module

[MODULES.json](MODULES.json) lists, for each environment, every file of the deployed tree with its full SHA-256 and
the single repository path that holds those bytes:

- **Lane and memory modules already tracked** under `docs/architecture/slice-*` or `services/core-api/lilith_memory`
  (motivation, reasoning, planning, ethics, presence contract, canonical memory and Privacy modules, and more) are
  referenced, not copied. The deployed bytes equal those tracked files exactly.
- **Modules not tracked anywhere else** and identical in PROD and DEV are under `lilith_router/` and `plugins/`.
- **Files that differ between environments** are under `variants/prod-lilith-01/` and `variants/dev-f9c2/`.

[tools/assemble_home.py](tools/assemble_home.py) builds the tree for one environment from those paths and checks
every digest:

```bash
python integrations/hermes/home/tools/assemble_home.py --variant dev-f9c2 --out /tmp/hermes-home
```

## PROD and DEV differ here

| File | PROD `lilith-01` | DEV `lilith-dev-01` (f9c2) |
|---|---|---|
| `lilith_router/gateway_integration.py` | `aef31314…` (35,150 B) | `5ce4bbd4…` (35,276 B): DEV wiring and stub handling, +21 −10 lines |
| `lilith_router/world_context.py` | `46b8187e…0104` (91,351 B): Working Memory assembly and seven-lane orchestration. **Not in Git: VM_ONLY_SOURCE_PENDING_SEPARATE_EXPORT** | `5c1fbf98…` (723 B): import-only stub, every lane off |
| `router.yaml` | `7d14b571…`: every lane live. **Not in Git: VM_ONLY_SOURCE_PENDING_SEPARATE_EXPORT** | `7bb4fbb5…`: shadow mode, every lane off |
| `plugins/lilith_os/adapter.py` | `39fa27b9…` (14,339 B): optional token, no body-size cap | `8c3b0055…` (16,345 B): mandatory token, request-size cap, hardened |

All other files are byte-identical in both environments. The DEV stub must never be read as the PROD cognitive lane;
the hashes and sizes differ and the test suite checks that the PROD entry has no source here.

## Cognitive integration coverage

| Component | Where the source is | Complete? |
|---|---|---|
| Lane modules: motivation, workspace, reasoning, planning (+capabilities), ethics (+principles), social cognition, presence contract | `docs/architecture/slice-9..14/` and `lilith_router/` here | yes, byte-exact |
| L18 learning (Router V1), learning store and worker, router memory store | `lilith_router/` here and `services/core-api/lilith_memory/` | yes |
| Canonical memory, authority, Privacy governance, 15B2a migration | `docs/architecture/slice-15b2a/`, `services/core-api/lilith_memory/` | yes |
| World Model, goals, tasks, drafts, the maintenance thread | `services/core-api/app.py` | yes |
| Gateway seam that calls the router | `integrations/hermes/patches/` (`gateway/run.py`) | yes |
| PROD gateway wiring | `variants/prod-lilith-01/lilith_router/gateway_integration.py` | yes |
| **PROD Working Memory assembly that invokes the lanes** (`world_context.py`) | PROD host only | **no** |
| **PROD lane configuration** (`router.yaml`) | PROD host only | **no** |

The per-slice `world_context*` blocks and router patchers under `docs/architecture/slice-8..13/` show how each slice
extended `world_context.py`, but the Slice 7.2 base they were applied to has no source in the repository, so they do
not rebuild the 91 KB PROD file exactly. Nothing here enables a lane; DEV runs every lane off.
