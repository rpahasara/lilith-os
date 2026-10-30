# `dev-goals-hardening` overlay (CANDIDATE, in no release)

A candidate governed adapter: the deployed `dev-unified-cognition` adapter with exactly two changes. Nothing assembles,
installs or references this directory.

| Change | Effect |
|---|---|
| The adapter's I/O seam replaces PROD `_GOAL_QUERY_RE` and `_GOAL_CREATE_RE` | Casual uses of "goal" no longer trigger the lane, so they can no longer send the goal store to the provider |
| The seam replaces `_goal_title_for` | A refused create no longer reads `/career/applications` |

The PROD module's bytes stay pinned and unchanged; only its runtime names are replaced, as the adapter already does for
its I/O helpers.

## Measurements

[`tests/test_goals_hardening_overlay.py`](tests/test_goals_hardening_overlay.py), on a corpus written before the
expressions were run against it:

| Detector | Queries | Creates | False matches of 14 | False creates |
|---|---|---|---|---|
| Deployed | 15/15 | 8/8 | 6 | not the target of this comparison |
| Candidate | 15/15 | 8/8 | 0 | 0 |

**Limit:** the same author wrote the corpus and the expressions, and it holds 37 messages. Real shadow records are the
better measure. Do not tune the expressions against the held-out corpus.

## To adopt it

1. Add the file to an `OVERLAY.json` entry with its digest, in a new release.
2. Pin the new digest in that release's verifier (`WORLD_CONTEXT_ADAPTER_SHA256`).
3. Ship in shadow first, then compare records against the previous detector.

The change also affects Reasoning, whose precedence calls `detect_goal_intent`: a casual "goal" message that the deployed
detector claims for Goals could now reach the Reasoning detector.
