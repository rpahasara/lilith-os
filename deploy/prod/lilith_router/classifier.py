"""Conversation Intelligence classifier for LILITH.

Decides the *mode* of the current turn — ``social`` (playful / affectionate /
light-emotional companion talk) vs ``technical`` vs ``work`` — from more than
keywords. It considers:

  - semantic construction of the current message (is a technical term the
    SUBJECT of a troubleshooting request, or just casually name-dropped inside
    a social/reminiscing frame?)
  - recent conversation turns
  - the previous mode (continuity / stickiness)
  - explicit intent shifts ("anyway", "where were we", topic pivots)

Mapping to providers is done by the caller:
  - ``social``            -> Groq / Qwen (social brain)
  - ``technical``/``work`` -> Hermes gpt-5.6-sol (native path, no override)

This module is PURE and deterministic: no I/O, no network, no secrets. It is
unit-tested offline. When in genuine doubt it defaults to the SAFER route
(keep technical on Hermes) rather than risk a weak technical answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

SOCIAL = "social"
TECHNICAL = "technical"
WORK = "work"

# ── Lexicons ────────────────────────────────────────────────────────────────

# Technical subject-matter terms. Presence alone does NOT decide the route;
# the *construction* around them does.
_TECH_TERMS = (
    r"kubernetes", r"k8s", r"kubectl", r"pod", r"deployment", r"helm",
    r"terraform", r"ansible", r"jenkins", r"github actions?", r"gitlab",
    r"ci/?cd", r"devops", r"devsecops", r"sre", r"aws", r"azure", r"gcp",
    r"docker", r"container", r"linux", r"systemd", r"nginx", r"apache",
    r"\bapi\b", r"endpoint", r"database", r"\bsql\b", r"postgres", r"redis",
    r"python", r"javascript", r"typescript", r"golang", r"rust",
    r"traceback", r"stack ?trace", r"exception", r"segfault", r"null pointer",
    r"firewall", r"\bdns\b", r"\bssl\b", r"\btls\b", r"\bvpn\b", r"subnet",
    r"kernel", r"regex", r"compiler", r"runtime", r"webhook", r"oauth",
    r"latency", r"throughput", r"schema", r"migration", r"repo",
    r"pull request", r"\bpr\b", r"merge conflict", r"rebase",
    r"cluster", r"node", r"ingress", r"load ?balancer", r"proxy",
)

# Words that indicate an active troubleshooting / build request when they
# co-occur with a technical term.
_TROUBLESHOOT = (
    r"error", r"failing", r"failed", r"broken", r"crash", r"crashing",
    r"pending", r"stuck", r"timeout", r"timing out", r"not working",
    r"won'?t start", r"can'?t", r"cannot", r"debug", r"fix", r"deploy",
    r"configure", r"config", r"install", r"set ?up", r"build",
    r"why is", r"why does", r"why won", r"how do i", r"how to", r"what'?s wrong",
    r"logs?", r"exit code", r"status", r"restart", r"rollback",
)

# Work / planning / assistant-task intent.
_WORK_TERMS = (
    r"recruiter", r"interview", r"\bcv\b", r"resume", r"cover letter",
    r"standup", r"manager", r"client", r"stakeholder", r"application",
    r"\bjob\b", r"follow[- ]?up", r"draft", r"email", r"reply to",
    r"schedule", r"calendar", r"meeting", r"agenda", r"proposal", r"invoice",
    r"deadline", r"report", r"summary", r"document",
)

# Request / imperative construction ("send me a draft", "write an email").
_REQUEST_VERBS = (
    r"send", r"write", r"draft", r"prepare", r"compose", r"schedule",
    r"summari[sz]e", r"organi[sz]e", r"plan", r"remind", r"book", r"create",
)

# Social / relational / emotional signal words.
_SOCIAL_WORDS = (
    r"\blol\b", r"\blmao\b", r"\bhaha+\b", r"\bhehe+\b", r"\bbro\b", r"\bdude\b",
    r"\bbabe\b", r"\bhun\b", r"miss(ed)? (you|me)", r"\bhug\b", r"\bkiss\b",
    r"exhaust(ed|ing)", r"tired", r"drained", r"rough day", r"long day",
    r"happy", r"\bsad\b", r"lonely", r"excited", r"stressed", r"anxious",
    r"love (you|u)", r"\bcute\b", r"\bsweet\b", r"you'?re the best",
    r"good ?(morning|night|evening)", r"\bhey\b", r"\bhii+\b", r"\byo\b",
    r"how (are|r) (you|u)", r"what'?s up", r"\bwyd\b", r"\bsup\b",
    r"thank (you|u)", r"\bthanks\b", r"proud of", r"\bhuh\b",
)

# Reminiscence / continuity-shift markers that reframe a message as social even
# when it name-drops a technical term.
_REMINISCE = (
    r"where (were|was) we", r"before .* interrupt", r"remember when",
    r"\banyway\b", r"anyways", r"as i was saying", r"back to (us|what)",
    r"\bearlier\b", r"the other day", r"speaking of us", r"forget (about )?the",
)

# Emoji (broad ranges) — a strong casual/social signal.
_EMOJI = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF" "\U00002B00-\U00002BFF" "\U0000FE00-\U0000FE0F" "]",
    flags=re.UNICODE,
)


def _any(patterns, text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


def _first(patterns, text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


@dataclass
class Decision:
    mode: str
    confidence: float
    reason: str
    signals: dict = field(default_factory=dict)


def classify(
    message: str,
    recent: Optional[List[str]] = None,
    previous_mode: Optional[str] = None,
) -> Decision:
    """Return a :class:`Decision` for the current turn.

    ``recent`` is a bounded list of prior message texts (most recent last),
    used only for light continuity signals. ``previous_mode`` is the last
    routed mode for this conversation.
    """
    text = (message or "").strip()
    if not text:
        # Nothing to classify — inherit previous mode, else stay social/native.
        return Decision(previous_mode or SOCIAL, 0.3, "empty message")

    low = text.lower()

    tech = _any(_TECH_TERMS, low)
    trouble = _any(_TROUBLESHOOT, low)
    work = _any(_WORK_TERMS, low)
    req_verb = _first(_REQUEST_VERBS, low)
    social = _any(_SOCIAL_WORDS, low)
    reminisce = _first(_REMINISCE, low)
    emoji = 1 if _EMOJI.search(text) else 0
    question = 1 if "?" in text or re.match(r"^(why|how|what|where|when|which|is|are|does|do|can)\b", low) else 0
    short = len(low.split()) <= 6

    signals = dict(
        tech=tech, trouble=trouble, work=work, req_verb=int(req_verb),
        social=social, reminisce=int(reminisce), emoji=emoji,
        question=question, short=int(short),
    )

    # 1) Reminiscence / explicit social reframe dominates a lone tech mention.
    #    "anyway where were we before kubernetes interrupted us 😂" -> social.
    if reminisce and trouble == 0:
        return Decision(SOCIAL, 0.9, "reminiscence/relational reframe", signals)

    # 2) Active technical troubleshooting/build request -> technical.
    #    "why is my kubernetes pod Pending?" -> technical.
    if tech and (trouble or (question and tech >= 1)):
        return Decision(TECHNICAL, 0.9, "technical troubleshooting construction", signals)

    # 3) A technical term with a code/log artifact or imperative build verb.
    if tech and req_verb and not social:
        return Decision(TECHNICAL, 0.75, "technical build request", signals)

    # 4) Work/planning assistant task -> work (Hermes, native).
    #    "send me a follow-up draft for the recruiter" -> work.
    if work and (req_verb or question) and not reminisce:
        return Decision(WORK, 0.8, "work/planning request", signals)
    if work >= 2 and not social:
        return Decision(WORK, 0.7, "work-heavy context", signals)

    # 5) Clear social/emotional/playful signals -> social.
    #    "you missed me huh 😏", "bro today was exhausting".
    if social or emoji or reminisce:
        return Decision(SOCIAL, 0.85, "social/emotional signal", signals)

    # 6) Bare technical term, no social frame -> stay safe on technical.
    if tech:
        return Decision(TECHNICAL, 0.6, "bare technical term (safe default)", signals)

    # 7) Continuity: short/ambiguous follow-up inherits the previous mode.
    if previous_mode in (SOCIAL, TECHNICAL, WORK) and short:
        return Decision(previous_mode, 0.55, "continuity of previous mode", signals)

    # 8) Default: conversational companion -> social.
    return Decision(SOCIAL, 0.5, "conversational default", signals)
