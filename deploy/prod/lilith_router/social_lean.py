"""Lean social reply: LILITH's casual turns on Groq within free-tier limits.

A full Hermes turn costs ~23K input tokens before any history (SOUL.md ~8K,
Hermes system prompt ~5.7K, tool schemas ~9.4K; measured on PROD 2026-11-02),
which is over Groq Free's 8,000 tokens/minute for a single request. For a live
social turn, this module instead makes ONE tool-less chat call carrying:

  * SOUL.md's own identity and voice sections, verbatim, read from the live
    file (SOUL.md is never edited; technical turns still load all of it),
  * the social policy,
  * Hermes' USER.md / MEMORY.md profile, as stored,
  * the last few user/assistant turns of this session.

It never raises. Every refusal returns ``(None, reason)`` and the caller uses
the native model with the social policy, so nothing is lost on failure: tool
work, links, long messages, budget exhaustion and Groq errors all take the
full path. No secret or message text is logged.
"""

from __future__ import annotations

import contextvars
import logging
import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional, Tuple

logger = logging.getLogger(__name__)

# SOUL.md sections that ARE LILITH's identity and voice. All must be present or
# the lean reply is refused: it never speaks with a partial identity.
SOUL_CORE_SECTIONS = (
    "Identity",
    "Core Character",
    "Human-Like Interaction",
    "Communication Style",
    "Serious Mode",
    "Personality Continuity",
    "Voice",
    "Prime Directive",
    "CONVERSATION INTELLIGENCE V1",
)

# Turns that may need a tool, a lookup, a durable write or an outside action.
_ACTION_RE = re.compile(
    r"https?://|www\.|"
    r"\b(remember|memori[sz]e|remind|reminder|note (that|this|down)|save|forget|schedule|calendar|meeting|"
    r"e-?mail|inbox|send|text (him|her|them)|message (him|her|them)|search|look ?up|google|find out|"
    r"research|weather|news|price|image|picture|photo|selfie|draw|generate|voice note|call me|"
    r"file|attach|download|upload|install|timer|alarm|buy|order|translate)\b",
    re.IGNORECASE,
)
# Natural reminder / follow-up requests (2026-11-15): "ping me tomorrow", "check in on me later". Only the full agent
# has the scheduler (Hermes' cronjob tool); on the lean path any "I'll ping you" is a promise nothing backs. Base-form
# requests aimed at LILITH only: "she pinged me", "my alarm woke me up", "I'll follow up with my manager" stay lean.
_DAYS = r"(?:mon|tues|wednes|thurs|fri|satur|sun)day"
_WHEN = (r"(?:at\s+\d|in\s+(?:a|an|\d+|a\s+few|half\s+an)\b|tomorrow|tonight|later|this\s+(?:morning|afternoon|evening)"
         r"|before\b|after\b|by\s+\d|on\s+" + _DAYS + r"|next\s+(?:week|" + _DAYS + r"))")
_REMINDER_RE = re.compile(
    r"\b(?:ping|nudge|buzz)\s+me\b|"
    r"\bwake\s+me(?:\s+up)?\s+(?:at|in|tomorrow|before|by|on)\b|"
    r"\btext\s+me\s+(?:when|once|if|" + _WHEN + r")|"
    r"\bcheck\s+(?:in|back)\s+(?:on|with)\s+me\b|"
    r"\bfollow[\s-]*up\s+with\s+me\b|"
    r"\blet\s+me\s+know\s+" + _WHEN + r"|"
    r"\btell\s+me\s+(?:again\s+|that\s+again\s+)?" + _WHEN,
    re.IGNORECASE,
)
# Explicit scheduling words already route through _ACTION_RE; together with the natural phrasings they mark a turn
# whose agent gets the reminder note (turn_context.REMINDER_NOTE).
_EXPLICIT_REMINDER_RE = re.compile(
    r"\bremind\s+me\b|\bset\s+(?:up\s+)?(?:a|an|the|my)\s+(?:reminder|timer|alarm|check[\s-]?in|follow[\s-]?up)\b|"
    r"\bschedule\s+(?:a|an|the|my)\s+(?:reminder|check[\s-]?in|follow[\s-]?up|nudge)\b|"
    r"\b(?:a|an)\s+(?:reminder|timer)\s+(?:for|at|in)\b|\bdon['’]?t\s+let\s+me\s+forget\b",
    re.IGNORECASE)


def reminder_request(message: str) -> bool:
    """A request that LILITH remind or follow up with them later (natural or explicit wording)."""
    text = message or ""
    return bool(_REMINDER_RE.search(text) or _EXPLICIT_REMINDER_RE.search(text))


# Durable preferences and facts about the owner go to the full (tool-capable) path, where LILITH can stage a memory
# proposal in the conversation; the lean reply has no tools and must never imply it saved anything (2026-11-06).
_MEMORY_STATEMENT_RE = re.compile(
    r"\b(from now on|going forward|in (the )?future|i'?d (rather|prefer)|i prefer|i'?d like you to|"
    r"my (real |actual |full |legal )?name is|i always|i never|i usually|keep in mind)\b",
    re.IGNORECASE,
)
_THINK_RE = re.compile(r"<think>.*?</think>|<think>.*$", re.IGNORECASE | re.DOTALL)
_MAX_MESSAGE_CHARS = 1500
_MAX_TURN_CHARS = 1500
_MAX_PROFILE_CHARS = 4000


def estimate_tokens(text: str) -> int:
    """Hermes' rough rule (agent.model_metadata.estimate_tokens_rough): ~4 chars/token."""
    return (len(text or "") + 3) // 4


def skip_reason(message: str) -> str:
    """Why this social turn should take the full (tool-capable) path, or ''."""
    text = (message or "").strip()
    if not text:
        return "empty"
    if len(text) > _MAX_MESSAGE_CHARS:
        return "long_message"
    if _ACTION_RE.search(text):
        return "action_intent"
    if _REMINDER_RE.search(text):
        return "reminder_request"
    if _MEMORY_STATEMENT_RE.search(text):
        return "memory_statement"
    return ""


_soul_cache: dict = {}


def soul_core(path: Path) -> Optional[str]:
    """SOUL.md's title plus its identity/voice sections, verbatim and in file order.

    Returns None if the file is unreadable or any core section is missing.
    """
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
        if key in _soul_cache:
            return _soul_cache[key]
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parts = re.split(r"(?m)^(?=## )", text)
    head, sections = parts[0], parts[1:]
    kept, found = [], set()
    for sec in sections:
        title = sec.splitlines()[0][3:].strip()
        for name in SOUL_CORE_SECTIONS:
            if title == name or title.startswith(name + " "):
                kept.append(sec.rstrip() + "\n")
                found.add(name)
                break
    core = None
    if found == set(SOUL_CORE_SECTIONS):
        core = head.rstrip() + "\n\n" + "\n".join(kept)
    _soul_cache.clear()
    _soul_cache[key] = core
    return core


def profile(home: Path) -> str:
    """Hermes' own USER.md and MEMORY.md, as stored (bounded)."""
    out = []
    for name, label in (("USER.md", "About them"), ("MEMORY.md", "Things you remember")):
        try:
            t = (home / "memories" / name).read_text(encoding="utf-8").strip()
        except OSError:
            t = ""
        if t:
            out.append("[%s]\n%s" % (label, t[:_MAX_PROFILE_CHARS]))
    return "\n\n".join(out)


# Casual-only context (experiment X). The same Telegram thread also holds long, formatted answers from the full
# routes (technical, career, recall). Passed to the lean reply, they dominated its 12-message window and Qwen
# copied their vocabulary and formatting. Selection is by SHAPE, never by topic words: an assistant message that
# is long or document-formatted is left out, except an answer to a question about them or your shared history,
# which is kept as plain text (it carries the personal specifics affection needs); every user message is kept, in
# order; stored history is never touched.
_CASUAL_WINDOW = 8
_MAX_CASUAL_REPLY_CHARS = 1200
_MAX_RECALL_NOTE_CHARS = 600
_STRUCTURED_RE = re.compile(r"```|^\s{0,3}#{1,6}\s|^\s*\|.*\|\s*$|\*\*[^*\n]+\*\*", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S", re.MULTILINE)
_PERSONAL_Q_RE = re.compile(r"\b(remember|recall|memor(y|ies)|know about me|about me|about us|last time|we talked|"
                            r"you said|i told you|our (history|past|story|conversations?))\b", re.IGNORECASE)
_MARKUP_RE = re.compile(r"```[a-z]*|`|\*\*|^\s{0,3}#{1,6}\s*|^\s*(?:[-*•]|\d+[.)])\s+|^\s*\|", re.MULTILINE)


def full_route_reply(text: str) -> bool:
    """True for an assistant message shaped like a full-route answer rather than conversation."""
    return (len(text) > _MAX_CASUAL_REPLY_CHARS or bool(_STRUCTURED_RE.search(text))
            or len(_LIST_ITEM_RE.findall(text)) >= 2)


def casual_context(messages: List[dict], k: int) -> List[dict]:
    """Chronological user/assistant messages minus full-route-shaped assistant replies; the last ``k``.

    A full-route answer to a personal question ("what do you remember about me?") stays, as plain text.
    """
    kept = []
    for i, m in enumerate(messages):
        if m["role"] == "assistant" and full_route_reply(m["content"]):
            asked = messages[i - 1]["content"] if i > 0 and messages[i - 1]["role"] == "user" else ""
            if not _PERSONAL_Q_RE.search(asked):
                continue
            plain = " ".join(_MARKUP_RE.sub("", m["content"]).split())[:_MAX_RECALL_NOTE_CHARS]
            m = dict(m, content=plain)
        kept.append(m)
    return kept[-k:] if k > 0 else []


def recent_turns(runner, session_key: str, k: int) -> List[dict]:
    """Recent conversational user/assistant messages of this session from Hermes' own store (read only)."""
    if k <= 0:
        return []
    try:
        store = runner.session_store
        sid = store.peek_session_id(session_key)
        msgs = store.load_transcript(sid) if sid else []
    except Exception:
        logger.debug("social_lean: transcript unavailable", exc_info=True)
        return []
    out = []
    for m in msgs or []:
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip() and not m.get("tool_calls"):
            out.append({"role": role, "content": content.strip()})
    return [dict(m, content=m["content"][:_MAX_TURN_CHARS])
            for m in casual_context(out[-60:], min(k, _CASUAL_WINDOW))]


class Budget:
    """Process-local view of Groq Free's per-minute and per-day token limits."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._minute: Deque[Tuple[float, int]] = deque()
        self._day_key = ""
        self._day_used = 0

    def _roll(self, now: float) -> None:
        while self._minute and now - self._minute[0][0] >= 60.0:
            self._minute.popleft()
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        if day != self._day_key:
            self._day_key, self._day_used = day, 0

    def allow(self, tokens: int, tpm: int, tpd: int, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            self._roll(now)
            in_minute = sum(t for _, t in self._minute)
            return in_minute + tokens <= tpm and self._day_used + tokens <= tpd

    def record(self, tokens: int, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._roll(now)
            self._minute.append((now, int(tokens)))
            self._day_used += int(tokens)


BUDGET = Budget()


def build_messages(core: str, policy: str, prof: str, history: List[dict], message: str) -> List[dict]:
    system = core.rstrip() + "\n\n" + policy.strip() + ("\n\n" + prof if prof else "")
    hist = list(history)
    if hist and hist[-1]["role"] == "user" and hist[-1]["content"] == message.strip():
        hist = hist[:-1]
    return [{"role": "system", "content": system}] + hist + [{"role": "user", "content": message.strip()}]


def _default_client(runtime: dict, timeout: float):
    from openai import OpenAI

    return OpenAI(base_url=runtime["base_url"], api_key=runtime["api_key"], timeout=timeout, max_retries=0)


# P-1 T-2: token usage of this turn's lean call (numbers and model name only), read by the turn-end record.
LAST_USAGE = contextvars.ContextVar("lilith_lean_usage", default=None)


def reply(*, runner, cfg, home: Path, session_key: str, message: str, policy: str, runtime: dict,
          client_factory=None, now: Optional[float] = None, include_profile: bool = False) -> Tuple[Optional[str], str]:
    """One lean Groq reply, or (None, reason). Never raises."""
    try:
        core = soul_core(home / "SOUL.md")
        if not core:
            return None, "soul_core_missing"
        if not runtime or not runtime.get("api_key") or not runtime.get("base_url"):
            return None, "no_api_key"
        # USER.md / MEMORY.md only on an owner channel (owner decision 2026-11-06); default: none
        msgs = build_messages(core, policy, profile(home) if include_profile is True else "",
                              recent_turns(runner, session_key, cfg.social_lean_history_turns), message)
        need = sum(estimate_tokens(m["content"]) for m in msgs) + cfg.social_lean_max_output_tokens
        if not BUDGET.allow(need, cfg.social_lean_tpm_budget, cfg.social_lean_tpd_budget, now):
            return None, "budget"
        client = (client_factory or _default_client)(runtime, cfg.social_lean_timeout_s)
        try:
            resp = client.chat.completions.create(
                model=cfg.groq_model, messages=msgs, max_tokens=cfg.social_lean_max_output_tokens,
                temperature=0.7, extra_body={"reasoning_effort": "none"})
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status in (413, 429):
                BUDGET.record(cfg.social_lean_tpm_budget, now)  # back off for the rest of the minute
                return None, "groq_%d" % status
            return None, "groq_error:%s" % type(exc).__name__
        usage = getattr(resp, "usage", None)
        BUDGET.record(int(getattr(usage, "total_tokens", 0) or need), now)
        try:
            LAST_USAGE.set({"model": cfg.groq_model, "provider": cfg.groq_provider,
                            "tokens_in": int(getattr(usage, "prompt_tokens", 0) or 0),
                            "tokens_out": int(getattr(usage, "completion_tokens", 0) or 0)})
        except Exception:
            pass
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        text = _THINK_RE.sub("", text).strip()
        return (text, "") if text else (None, "empty_reply")
    except Exception as exc:
        logger.debug("social_lean: failed (fail-open)", exc_info=True)
        return None, "error:%s" % type(exc).__name__
