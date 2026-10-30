# `dev-workspace-private-trace` overlay (CANDIDATE, in no release)

`workspace.py` with one change: `build_trace` records counts, not candidate ids.

**Why:** a candidate id is an unsalted hash that stays the same across turns, so ids in the decision log link turns about one
item. Nothing reads them: `selected_primary_id`, `selected_secondary_ids` and `suppressed_ids` appear only in this function. Shadow
needs to know how many items were selected, and of which class, not which ones.

| Removed | Added | Kept |
|---|---|---|
| `selected_primary_id`, `selected_secondary_ids`, `suppressed_ids` | `selected_secondary_count`, `suppressed_count` | `selected_primary_class`, `source_type_counts`, `candidate_count`, `deciding_rule`, the per-turn `correlation_id` |

The in-memory snapshot still has ids, which ranking needs. It is ephemeral and never logged.

**The remaining record** still has `chat_id` and timing, like every other record, under the same 7-day retention and full FORGET
purge of `logs/`. The tests pin both controls.

**Lost:** a shadow record can no longer show that the same item won twice. If that is needed later, use a per-session salted value,
destroyed with the session, not a stable hash.

**To adopt:** add the file as a release member with its digest in the next Workspace candidate.
