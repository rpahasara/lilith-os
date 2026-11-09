"""P-3: one shared, ephemeral TurnContext per turn, and the typed StyleDirective (R&D plan 04 §2-§3).

Before P-3 each lane kept its own per-turn variable and its own prompt fragment (the tone note, the P-2 preference note,
the correction hint) and two places glued them together. Now:

- `route_turn` starts a fresh TurnContext (channel, owner) and every lane writes TYPED fields into it: the classifier
  mode, the Social Cognition line keys, the selected approved preferences, the correction flag, and (later batches)
  meta-signals and appraisal signals. Lanes keep their responsibilities and ready-answer short-circuits.
- One renderer turns the context into prompt text for both reply paths. It reproduces the owner-approved wording byte
  for byte: the StyleDirective holds approved line KEYS, never free text.
- Nothing persists. The context is discarded when the next turn starts (V1 §7a: Working Memory is ephemeral). The
  trace gets a metadata summary only (keys, ids, flags), never message or memory text.

A non-owner turn renders nothing: the owner guidance never reaches another channel.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from dataclasses import replace as dataclasses_replace  # noqa: F401  (used by lanes to update the directive)
from typing import Any, Dict, List, Optional, Tuple

# Social Cognition line keys that come from an explicit request in the message (correction, comfort, humour,
# formality), as opposed to a weaker clue (playful, difficulty, mixed).
EXPLICIT_LINES = frozenset({"correction", "support", "humor", "formal"})


@dataclass(frozen=True)
class StyleDirective:
    """Typed style for this turn. `lines` are approved Social Cognition line keys; the renderer maps them to the
    approved wording. `confidence` low means render no tone lines (silence beats a wrong note)."""
    register: str = "casual"                     # casual | formal  (an explicit request beats a cue)
    focus: str = "social"                        # social | task    (technical / help-request gate, #346)
    lines: Tuple[str, ...] = ()
    preference_refs: Tuple[str, ...] = ()        # approved owner-memory entry ids that shaped it
    appraisal_refs: Tuple[str, ...] = ()         # appraisal signal ids that shaped it (P-3 batch 3)
    confidence: str = "low"                      # low | medium | high


def directive(lines, *, focused: bool, preference_refs=(), appraisal_refs=()) -> StyleDirective:
    lines = tuple(lines or ())
    if not lines:
        conf = "low"
    elif any(k in EXPLICIT_LINES for k in lines):
        conf = "high"
    else:
        conf = "medium"
    return StyleDirective(register="formal" if "formal" in lines else "casual",
                          focus="task" if focused else "social", lines=lines,
                          preference_refs=tuple(preference_refs), appraisal_refs=tuple(appraisal_refs),
                          confidence=conf)


@dataclass
class TurnContext:
    """The per-turn broadcast. Typed fields only; prompt text is produced by render_*()."""
    channel: Optional[str] = None
    owner: bool = False
    mode: Optional[str] = None                   # classifier mode (social / technical / work ...)
    focused: bool = False
    style: StyleDirective = field(default_factory=StyleDirective)
    preferences: Tuple[Any, ...] = ()            # selected SocialPreferenceV1 (approved, scope-matched)
    preferences_live: bool = False               # P-2 note switch: live renders them, shadow only traces them
    correction: bool = False                     # an explicit durable correction routed to the agent (P-2)
    meta: Dict[str, Any] = field(default_factory=dict)        # L16 meta-signals -> gate decisions (batch 2)
    appraisal: Tuple[Any, ...] = ()              # deterministic appraisal signals (batch 3)
    goals: Tuple[Any, ...] = ()                  # related ACTIVE tracked goals (id, title, state) for G-WIDEN
    appraisal_live: bool = False                 # appraisal switch: live renders the goal line, shadow only traces
    responsibility: Tuple[Any, ...] = ()         # P4-5c: LILITH's unresolved commitments to own (live only)

    def summary(self) -> Dict[str, Any]:
        """Metadata for the turn-end trace record. Keys, ids and flags only."""
        out = {"style_lines": list(self.style.lines), "style_confidence": self.style.confidence,
               "style_focus": self.style.focus, "pref_refs": list(self.style.preference_refs),
               "pref_applied": bool(self.preferences_live and self.preferences), "correction": self.correction}
        if self.meta:
            out["meta"] = dict(self.meta)
        if self.responsibility:
            out["responsibility"] = len(self.responsibility)
        if self.appraisal:
            out["appraisal"] = [getattr(a, "kind", str(a)) for a in self.appraisal]
            out["appraisal_refs"] = list(self.style.appraisal_refs)
        return out


_CURRENT: contextvars.ContextVar = contextvars.ContextVar("lilith_turn_context", default=None)


def begin(channel: Optional[str] = None, owner: bool = False) -> TurnContext:
    ctx = TurnContext(channel=channel, owner=bool(owner))
    _CURRENT.set(ctx)
    return ctx


def current() -> TurnContext:
    """This turn's context (an empty, non-owner one when none was started, so readers never fail)."""
    ctx = _CURRENT.get()
    if ctx is None:
        ctx = begin()
    return ctx


# ------------------------------------------------------------------------------------------------- renderer ---
# The approved wording lives where it always did (social_cognition.TONE_*, social_preferences.CORRECTION_HINT /
# render); imported lazily so this module stays a leaf.

def tone_text(ctx: TurnContext) -> Optional[str]:
    if not ctx.owner or ctx.style.confidence == "low" or not ctx.style.lines:
        return None
    from . import social_cognition as sc
    return sc.TONE_HEADER + "\n" + "\n".join("- " + sc.TONE_LINES[k] for k in ctx.style.lines)


def preference_text(ctx: TurnContext) -> Optional[str]:
    if not (ctx.owner and ctx.preferences_live and ctx.preferences):
        return None
    from . import social_preferences as sp
    return sp.render(list(ctx.preferences))


def correction_text(ctx: TurnContext) -> Optional[str]:
    if not (ctx.owner and ctx.correction):
        return None
    from . import social_preferences as sp
    return sp.CORRECTION_HINT


def meta_text(ctx: TurnContext) -> Optional[str]:
    """The L16 control note when a gate fired and its mode is live (P-3 batch 2)."""
    if not (ctx.owner and ctx.meta.get("applied")):
        return None
    from . import metacognition as mc
    return mc.note_for(ctx.meta.get("control"))


def goal_text(ctx: TurnContext) -> Optional[str]:
    """G-WIDEN: the related tracked goal, when appraisal is live (P-3 batch 3)."""
    if not (ctx.owner and ctx.appraisal_live and ctx.goals):
        return None
    from . import appraisal as ap
    return ap.goal_note(list(ctx.goals))


def responsibility_text(ctx: TurnContext) -> Optional[str]:
    """P4-5c: a missed commitment for LILITH to own (live only; the full agent only)."""
    if not (ctx.owner and ctx.responsibility):
        return None
    from . import commitments as cm
    return cm.note(list(ctx.responsibility))


def agent_hint(ctx: TurnContext, status_hint: Optional[str] = None) -> Optional[str]:
    """The API-only turn hint for the main agent (run.py `turn_hint`). A goals-status question carries its status hint
    instead of the tone and correction lines; approved preferences ride on either."""
    if not ctx.owner:
        return None
    parts: List[Optional[str]] = [status_hint] if status_hint else [correction_text(ctx), tone_text(ctx)]
    parts += [preference_text(ctx), meta_text(ctx)]
    if not status_hint:                          # a goals-status turn already carries its goals
        parts.append(goal_text(ctx))
    parts.append(responsibility_text(ctx))       # agent path only: never rendered on the lean path (N-48)
    return "\n\n".join(p for p in parts if p) or None


def lean_suffix(ctx: TurnContext) -> str:
    """Appended to the lean social policy after the canonical note: the tone lines, then approved preferences.
    (A durable correction never reaches the lean path: it routes to the agent.)"""
    if not ctx.owner:
        return ""
    return "".join("\n\n" + p for p in (tone_text(ctx), preference_text(ctx), meta_text(ctx), goal_text(ctx))
                   if p)
