"""Candidate Goals detector (PROPOSAL, NOT WIRED). TEST_ONLY until an owner-approved release adopts it.

The deployed detector is the recovered PROD `detect_goal_intent`, whose bytes are pinned. Its query rule matches the bare
word "goal", and its create rule matches a track/set/start verb anywhere near "goal". This candidate keeps every other
alternative and tightens only those two rules.
"""
import re

_OTHER_QUERY = (
    r"trying to (do|accomplish|achieve|pursue|work on)|"
    r"what('?s| is| are)?\s*(you\s*)?(currently\s*)?(working on|focused on|pursuing)|"
    r"current focus|has priority|takes priority|"
    r"what('?s| is)?\s*(blocked|on hold|suspended|stalled)|"
    r"why (is|are)\b[^.?!]*\b(blocked|on hold|stalled)|"
    r"what should (i |you )?resume"
)
# "goal" counts only as the object of a question or a state request, never as a bare word in a statement.
_GOAL_WORD = (
    r"(what|which|show|list|any|how many)\b[^.?!]{0,30}\bgoals?\b|"
    r"\b(current|active|open|blocked|suspended)\s+goals?\b|"
    r"\bgoals?\s+(status|list|state)\b"
)
QUERY_RE = re.compile(r"\b(" + _OTHER_QUERY + r")\b|\b(" + _GOAL_WORD + r")", re.IGNORECASE)
# Explicit tracking only: "as a goal", "track this ... goal", or an imperative at the start of a sentence.
CREATE_RE = re.compile(
    r"\b(as a goal|track (this|that|it)\b[^.?!]*\bgoal)\b|"
    r"(^|[.!?]\s+|\b(please|can you|could you|let'?s)\s+)"
    r"(track|set|make|create|add|register|log|record|start)\b[^.?!]{0,40}\bgoal\b",
    re.IGNORECASE,
)


def classify(message):
    m = message or ""
    create = bool(CREATE_RE.search(m))
    query = bool(QUERY_RE.search(m)) and not create
    return {"any": create or query, "goal_create": create, "goal_query": query}
