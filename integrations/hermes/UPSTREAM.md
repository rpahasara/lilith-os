# Upstream Hermes pin

| Field | Value |
|---|---|
| Project | NousResearch/hermes-agent |
| Repository | https://github.com/NousResearch/hermes-agent |
| Commit | `f293e7206b4ddd66042329442c6afebc19a8808d` (package version 0.20.5) |
| Licence | MIT, Copyright (c) 2025 Nous Research. Full text: [LICENSE-hermes-agent.txt](LICENSE-hermes-agent.txt) |
| Used by | PROD `lilith-01` and DEV `lilith-dev-01` |

## Why a pin and patches, not a vendored copy

The upstream tree is about 10,000 files. LILITH changes eight of them and adds one. A pin plus a reviewed patch set
rebuilds the exact bytes (see the README) and keeps the LILITH-authored part reviewable. The patches contain upstream
context lines; they are distributed under the upstream MIT licence, whose notice is kept here.

## What each patch changes

| File | PROD `prod-lilith-01` | DEV `dev-f9c2` | Origin |
|---|---|---|---|
| `gateway/run.py` | `2774eee5…` | `5928c9f0…` | Router V2 seam and Slice 9 hook (PROD); F8/F9 hardening on DEV |
| `agent/background_review.py` | `c0e929cc…` | same | Slice 15B2a: typed memory-lane turns removed before review |
| `tools/memory_tool.py` | `1c792dae…` | same | Slice 15B2a containment |
| `tools/write_approval.py` | `38deca1e…` | same | Slice 15B2a containment |
| `tools/skill_manager_tool.py` | `82b82a75…` | same | Slice 15B2a containment |
| `tools/legacy_canonical_containment.py` (new) | `c1667e62…` | same | Same bytes as `services/core-api/lilith_memory/legacy_canonical_containment.py` |
| `agent/agent_runtime_helpers.py` | upstream | `bdeecae2…` | F9 Privacy (DEV only) |
| `agent/turn_context.py` | upstream | `70f1ea4d…` | F9 Privacy (DEV only) |

`hermes_cli/personality.py` on PROD (`520cf5db…`) is unmodified upstream. Full digests are in
`patches/*.sha256`.

The repository-side Slice 15B2a patcher that first produced the containment changes is
`docs/architecture/slice-15b2a/patch_slice15b2a.py`; the patches here are its recorded result against the pin.

## Updating the pin

Moving to a newer Hermes is a change of runtime. It needs its own reviewed PR that regenerates both patch sets,
records the new digests, and keeps PROD and DEV separable. It is never part of a source-consolidation change.
