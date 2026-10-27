# DEV overlays outside the f9c2 release

## `dev-origin-forget-executor/` (installed and active on DEV)

The relationship-origin FORGET executor installed at `/opt/lilith-hermes-forget-executor/` on `lilith-dev-01`
(2026-10-26) and selected by three `60-origin-executor.conf` drop-ins.

| File | SHA-256 | Note |
|---|---|---|
| `hermes_forget_executor.py` | `2dafbfec8b88b36f…` | the installed executor |
| `origin-forget-executor.patch` | `31ea9dc26214a5de…` | applied with `patch` to the f9c2 `bin/hermes_forget_executor.py` (`4992f932…`) it yields `2dafbfec…` exactly |
| `tests/test_origin_intent_executor.py` | | offline tests for the origin intent |

The drop-ins, `/etc/hermes-forget/executor.json` and the pinned Core API copies are generated on the host by the
installers (`release/dev-f9c2/bin/install_f9c.sh --repin`); the Core API files are the repository's own.

## `dev-planned-memory-context/` (PLANNED, not deployed)

An optional canonical-memory context route for the `lilith_os` console adapter. It is not installed on any host.

- `lilith-os-adapter-memory-context.patch` applies to the 2026-10-22 DEV candidate adapter (`76948218…`), not to the
  f9c2 adapter (`8c3b0055…`). `adapter.py` (`7414a7e66c2f…`) is the staged result.
- The context module it imports is `services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py`
  (same bytes as the staged `lilith_memory_context.py`).
- Re-basing it onto the f9c2 adapter, and enabling it, are future, separately approved work.
