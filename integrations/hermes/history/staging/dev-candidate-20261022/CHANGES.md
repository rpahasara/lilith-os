# DEV candidate 2026-10-22 (derived from quarantine-20261022-222752; the originals there are unchanged)

## Files that differ from the verified PROD originals

| DEV candidate file | Original PROD sha256 | Change |
|---|---|---|
| `plugins/lilith_os/adapter.py` | `39fa27b90cd676c27e42e1741aced744dadbdde66f8a9c5cf296840067d4b709` | `LILITH_OS_TOKEN` is mandatory (POST returns 503 if it is unset or shorter than 32 characters); `hmac.compare_digest` replaces `!=`; request body capped at 64 KiB (413). Diff: `adapter.py.dev-candidate.diff`. |
| `lilith_router/world_context.py` | (PROD `46b8187e…`, not exported) | DEV-only **import stub**. Valid only while every cognitive lane is off. Stage 2 export is required before enabling any lane. |

All other DEV source is used byte-identical to a verified source:

- **Quarantine originals:** `lilith_router/{__init__,config,state,classifier,policy,social_guard,gateway_integration}.py`,
  `plugins/lilith_os/{plugin.yaml,__init__.py}` and `plugins/model-providers/groq/{plugin.yaml,__init__.py}`.
- **Upstream** NousResearch/hermes-agent `f293e7206b4ddd66042329442c6afebc19a8808d`, plus:
  - `gateway/run.py`: quarantine `run.py` diff, which must produce `2774eee5…2c2553`;
  - `tools/write_approval.py`, `tools/memory_tool.py`, `tools/skill_manager_tool.py` and `agent/background_review.py`:
    repo `docs/architecture/slice-15b2a/patch_slice15b2a.py`, LF endings, producing `38deca1e…`, `1c792dae…`,
    `82b82a75…` and `c0e929cc…`;
  - `tools/legacy_canonical_containment.py`: repo `docs/architecture/slice-15b2a/`, `c1667e62…`.

Config templates (`config-templates/`) are fresh DEV files containing placeholders only; nothing is copied from PROD.
