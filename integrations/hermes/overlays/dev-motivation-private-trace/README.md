# `dev-motivation-private-trace` overlay

`motivation.py` with one change: `build_trace` records counts, not goal ids or condition text.

**Why:** a blocked goal put its id in `per_drive[].relatedGoalIds`, in the decision log. The empty-store verifier rule made that unreachable at start, but it runs only at start, so it was not enough on its own.

| Removed | Added | Kept |
|---|---|---|
| `relatedGoalIds`, `resolutionConditions` | `relatedGoalCount`, `resolutionConditionCount` | drive type, intensity, cause codes, source count |

Cause codes are a fixed list. Nothing else in the module changes: the ephemeral snapshot keeps its ids, which the Live path would need.
