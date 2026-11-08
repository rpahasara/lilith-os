"""P-3 batch 2: L16 meta-signals and causal controls (R&D plan 04 §4, 06 §2). Deterministic; no model call.

Every signal here names the control it may trigger, the metric that shows the control helped, and its cost
(DeepSeek D14: no decorative metacognition). The model's own stated confidence is never used (SM-19).

Signal `recall_gap`
    An owner asks about their own personal facts ("what's my sister's name?", "how did my interview go?") and nothing
    LILITH holds for this turn (the approved profile projection USER.md / MEMORY.md and the canonical memory note)
    mentions the thing asked about. This is the turn where a reply model is most likely to invent a personal detail.
Controls (router.yaml `metacognition_recall_control`)
    ask       G-ASK: the reply gets a short note: don't guess personal details; say so, or ask. Same model, same call.
    escalate  G-ESCALATE: a lean (fast-path) turn moves to the tool-capable agent, which can search its own memory,
              and carries the same note. One agent call instead of a lean call.
Metric
    E-5: hallucinated-personal-fact rate on recall-gap scenarios, and false asks on grounded ones.
Cost
    0 extra calls; about 60 prompt tokens on gated turns only.

Owner turns only (owner data is the grounding; no owner data is read on any other turn). Technical / work / help
turns are never gated. Questions the profile covers are never gated: silence beats a wrong control.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Set

_PERSONAL_Q_RE = re.compile(
    r"\b(?:what|who|when|where|which|how\s+(?:old|long|many|much))\b(?:'s|\s+(?:is|was|are|were|did|do|does|have|has))?"
    r"[^?.!\n]{0,40}?\b(?:my|i)\b|"
    r"\bhow\s+did\s+(?:my|i)\b|"
    r"\bdo\s+you\s+(?:know|remember)\s+(?:my|what\s+i|where\s+i|when\s+i|who\s+i|how\s+i)\b|"
    r"\bwhat\s+did\s+i\s+(?:say|tell|do|eat|buy|decide|pick|choose|name|get)\b|"
    r"\bdid\s+i\s+(?:ever\s+)?(?:tell|mention|say)\b",
    re.IGNORECASE,
)
# advice, opinion and how-to questions are not recall questions
_NOT_RECALL_RE = re.compile(
    r"\b(?:should|could|would|can|shall|might|must|will)\s+i\b|\bwhat\s+(?:do|can)\s+i\s+do\b|"
    r"\bhow\s+(?:do|can|should|would)\s+i\b|\bwhat\s+do\s+you\s+think\b|\bdo\s+i\s+look\b|"
    r"\bwhat\s+am\s+i\s+(?:supposed|meant|going)\b|\bwhere\s+(?:do|should)\s+i\s+(?:start|begin|go\s+from)\b|"
    r"\bwhat\s+(?:if|about)\s+i\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z][a-z0-9'’-]{2,}")
_STOP = frozenset("""
what who when where which how old long many much did does do have has had was were are is the and for with you your
yours that this there their them they his her she him mine my me myself again really actually exactly ever remember
know tell told said say mention mentioned last first time today yesterday week weekend month year name names called
thing things stuff kind type favourite favorite about from into then than just even still also please lol haha hey
okay right sure gonna wanna get got going went like any some one all can could would should will
""".split())


def personal_fact_question(message: str) -> bool:
    text = message or ""
    if not _PERSONAL_Q_RE.search(text) or _NOT_RECALL_RE.search(text):
        return False
    return "?" in text or bool(re.match(r"\s*(?:what|who|when|where|which|how|do you|did i)\b", text, re.I))


def _stem(w: str) -> str:
    w = w.replace("’", "'")
    for suf in ("'s", "s'"):
        if w.endswith(suf):
            w = w[: -len(suf)]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def key_terms(message: str) -> Set[str]:
    """The content words a question asks about (stemmed), without question words, pronouns and generic nouns."""
    return {_stem(w) for w in _WORD_RE.findall((message or "").lower()) if _stem(w) not in _STOP and w not in _STOP}


def covered(terms: Iterable[str], grounding: str) -> bool:
    words = {_stem(w) for w in _WORD_RE.findall((grounding or "").lower())}
    return any(t in words for t in terms)


def recall_gap(message: str, grounding: str) -> Optional[dict]:
    """The recall-gap signal for an owner turn, or None. Returns metadata only (counts, no words)."""
    if not personal_fact_question(message):
        return None
    terms = key_terms(message)
    if not terms:
        return None                                   # nothing specific asked: no signal
    if covered(terms, grounding):
        return {"signal": "recall_gap", "fired": False, "terms": len(terms)}
    return {"signal": "recall_gap", "fired": True, "terms": len(terms)}


# The note (new wording, not a tone line; it is not shown to the owner). Rendered by turn_context.
ASK_NOTE = ("[Nothing you know about them covers this. Don't guess or fill in personal details: if you don't know, "
            "say so plainly in your own voice, and ask if that helps.]")
ESCALATE_NOTE = ("[Nothing in your notes about them covers this. Check your memory or past conversations if you can; "
                 "if nothing turns up, say you don't know rather than guess.]")
CONTROLS = ("ask", "escalate")


def note_for(control: Optional[str]) -> Optional[str]:
    return {"ask": ASK_NOTE, "escalate": ESCALATE_NOTE}.get(control or "")
