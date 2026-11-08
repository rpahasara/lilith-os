"""Router configuration loader.

Config lives OUTSIDE Hermes' config.yaml so the core config surface is never
touched: ``~/.hermes/lilith_router/router.yaml``. All values have safe
defaults; a missing or malformed file yields a disabled router (fail-safe).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


CONFIG_PATH = _hermes_home() / "lilith_router" / "router.yaml"


@dataclass
class RouterConfig:
    enabled: bool = False           # master switch; False => router is a no-op
    mode: str = "shadow"            # "shadow" (log only) | "live" (may switch)
    live_channels: List[str] = field(default_factory=list)  # "platform:chat_id"; ["*"] = all
    groq_model: str = "qwen/qwen3.8-27b"
    groq_provider: str = "groq"
    # Fallback (Hermes "GPT-5.6 Sol") for when the Groq social turn fails,
    # rate-limits, or times out. Applied per-social-turn only, so technical/work
    # turns keep their native (unchanged) fallback behavior.
    hermes_model: str = "gpt-5.6-sol"
    hermes_provider: str = "openai-codex"
    # Full-agent provider fallback (2026-11-08): Hermes' own fallback chain for EVERY routed turn, appended after the
    # social fallback above. Hermes switches on auth / billing / rate-limit / overload / timeout / missing-model errors
    # and retries only the failed model call (tools already run stay in the history), then restores the primary on the
    # next turn. Empty = no fallback (previous behavior).
    full_agent_fallback: List[Dict[str, str]] = field(default_factory=list)
    recent_turns: int = 6
    decision_log_max_bytes: int = 2_000_000   # P-1 T-6: rotate decisions.log to .1 at this size (100K..50M)
    social_preferences_mode: str = "off"   # P-2: off | shadow (log selection only) | live (apply on owner turns)
    social_corrections_mode: str = "off"   # P-2: off | live (explicit durable owner corrections -> full agent + hint)
    metacognition_mode: str = "off"        # P-3: off | shadow (log L16 signals) | live (apply their controls)
    metacognition_recall_control: str = "ask"   # P-3 recall gap: ask (note, same call) | escalate (lean -> agent)
    turn_trace_enabled: bool = True     # P-1: turn_id on decision-log records + one turn-end record (metadata only)
    log_path: str = ""              # decisions log; empty => <home>/lilith_router/decisions.log

    # ── Slice 7.2: World-Model-first cognitive lane (independent rollout) ────
    # Additive and OFF by default so deploying the code changes NO behavior.
    # Stage: cognitive_enabled:true + cognitive_mode:shadow (log only) ->
    # cognitive_mode:live + cognitive_channels:["lilith_os"] (Home) ->
    # add "telegram" -> ["*"]. Read per-turn (router.yaml edits are live, no
    # gateway restart). This lane governs belief/pending/draft turns ONLY and
    # never alters social/technical/work routing.
    cognitive_enabled: bool = False
    cognitive_mode: str = "shadow"  # "shadow" (detect+log only) | "live" (inject)
    cognitive_channels: List[str] = field(default_factory=list)
    # Slice 7.3: deterministic semantic de-dup of career follow-up drafts. When
    # true (default), a create request reuses an existing UNSENT follow-up draft
    # for the same application instead of creating a duplicate; multiple existing
    # unresolved drafts surface a reconciliation notice. Set false to restore the
    # pre-7.3 always-create behaviour without reverting code.
    cognitive_draft_dedup: bool = True

    # -- Slice 8: Goal / Executive lane (additive; reuses cognitive_channels).
    # Independent rollout: goals_enabled + goals_mode:shadow (detect+log) ->
    # goals_mode:live (inject durable Goal/Executive grounding; create only on
    # an explicit 'track as a goal'). Channel scope reuses cognitive_channels.
    goals_enabled: bool = False
    goals_mode: str = "shadow"

    # -- Slice 9: Reasoning lane (additive; reuses cognitive_channels). --
    # reasoning_enabled + reasoning_mode:shadow (detect+log) -> live (bounded
    # tool-less reasoning answer). Analytic framings only; yields to 7.2/8.
    reasoning_enabled: bool = False
    reasoning_mode: str = "shadow"

    # -- Slice 10: Global Workspace / Attention lane (additive; reuses
    # cognitive_channels). workspace_enabled + workspace_mode:shadow (build+log
    # snapshot only) -> live (snapshot bounds the Slice 9 ReasoningInput).
    # workspace_capacity = secondary capacity, hard-bounded [0,8] downstream.
    workspace_enabled: bool = False
    workspace_mode: str = "shadow"
    workspace_capacity: int = 4

    # -- Slice 11: Motivation / Homeostasis lane (additive; reuses
    # cognitive_channels). motivation_enabled + motivation_mode:shadow
    # (build+log snapshot only) -> live (eligible MOTIVATION_DRIVE candidates
    # merge into the Workspace pool + bounded motivationSummary on the
    # ReasoningInput). Ordinal only; no numeric tuning. Read per-turn.
    motivation_enabled: bool = False
    motivation_mode: str = "shadow"

    # -- Slice 12: Planning / Replanning lane (additive; reuses cognitive_channels).
    # planning_enabled + planning_mode:shadow (build+validate+log a plan snapshot
    # only, NO user-facing answer) -> live (a PLAN_PROPOSED / USER_DECISION_REQUIRED
    # snapshot's natural answer becomes the turn's final_response). Proposal-only:
    # no task/draft/goal/belief writes, no tools, no execution. planning_max_steps
    # bounds the plan, hard-clamped [1,8] downstream. Read per-turn.
    planning_enabled: bool = False
    planning_mode: str = "shadow"
    planning_max_steps: int = 6

    # -- Slice 13: Ethical Deliberation lane (additive; reuses cognitive_channels).
    # ethics_enabled + ethics_mode:shadow (build+validate+log an advisory result
    # only, NO user-facing answer) -> live (a grounded advisory answer becomes the
    # turn final_response). ADVISORY ONLY: no ALLOW/DENY, no execution, no approval/
    # verification, no goal/plan/belief/draft mutation, no Policy impersonation.
    # ethics_max_concerns/tensions hard-clamped downstream. Read per-turn.
    ethics_enabled: bool = False
    ethics_mode: str = "shadow"
    ethics_max_concerns: int = 4
    ethics_max_tensions: int = 3

    # -- Slice 14: Social Cognition observer (TURN-only; shadow is the sole V1 mode).
    # Computes validated ephemeral semantics + safe trace only. It never changes
    # prompts, routing, replies, Social Guard, or Presence rendering.
    social_cognition_enabled: bool = False
    social_cognition_mode: str = "shadow"

    # -- Slice 15A: offline Learning / Consolidation foundation.
    # SHADOW is the sole V1 mode. The one-shot worker records bounded Learning
    # metadata only; it has no conversation, retrieval, or canonical-LTM path.
    memory_consolidation_enabled: bool = False
    memory_consolidation_mode: str = "shadow"

    # -- Slice 15B1: canonical LTM apply kill switch. --
    # Missing or non-boolean configuration is invalid and therefore disabled.
    canonical_ltm_enabled: bool = False
    canonical_ltm_config_valid: bool = False

    # -- Lean social reply (fits Groq free-tier limits). OFF by default. --
    # On a live social turn in social_lean_channels, LILITH answers through one
    # tool-less Groq call carrying SOUL.md's own identity/voice sections, the
    # social policy, USER.md and recent turns, instead of the full ~23K-token
    # agent request. Action/tool intents, links, long messages, budget
    # exhaustion, and any Groq error use the native model with the social
    # policy. Budgets default under Groq Free (8,000 TPM, 200,000 TPD).
    social_lean_enabled: bool = False
    social_lean_channels: List[str] = field(default_factory=list)
    social_lean_history_turns: int = 12
    social_lean_max_output_tokens: int = 600
    social_lean_tpm_budget: int = 7500
    social_lean_tpd_budget: int = 190000
    social_lean_timeout_s: float = 20.0

    def social_lean_is_on(self, platform: str) -> bool:
        return bool(self.social_lean_enabled) and (
            "*" in self.social_lean_channels or platform in self.social_lean_channels)

    def social_preferences_is_active(self) -> bool:
        """P-2 selection runs (shadow logs it; live also applies it). Owner turns only, checked by the caller."""
        return self.social_preferences_mode in ("shadow", "live")

    def social_preferences_is_live(self) -> bool:
        return self.social_preferences_mode == "live"

    def social_corrections_is_live(self) -> bool:
        """Explicit durable owner corrections go to the tool-capable agent (with the proposal hint). Independent of
        the preference note; preferences live also implies it (unchanged behaviour)."""
        return self.social_corrections_mode == "live" or self.social_preferences_is_live()

    def channel_is_live(self, platform: str, chat_id: str) -> bool:
        """True when live switching is allowed for this channel."""
        if self.mode != "live":
            return False
        if not self.live_channels:
            return False
        if "*" in self.live_channels:
            return True
        key = f"{platform}:{chat_id}"
        return key in self.live_channels or platform in self.live_channels or _owner_label_in(self.live_channels)

    def _cognitive_channel_match(self, platform: str, chat_id: str) -> bool:
        if not self.cognitive_channels:
            return False
        if "*" in self.cognitive_channels:
            return True
        key = f"{platform}:{chat_id}"
        return key in self.cognitive_channels or platform in self.cognitive_channels \
            or _owner_label_in(self.cognitive_channels)

    def cognitive_is_active(self, platform: str, chat_id: str) -> bool:
        """The cognitive lane is engaged for this channel (shadow or live)."""
        return bool(self.cognitive_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def cognitive_is_live(self, platform: str, chat_id: str) -> bool:
        """The cognitive lane may actually inject context / create drafts."""
        return self.cognitive_is_active(platform, chat_id) and self.cognitive_mode == "live"

    def goals_is_active(self, platform: str, chat_id: str) -> bool:
        """The goal/executive lane is engaged for this channel (shadow or live)."""
        return bool(self.goals_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def goals_is_live(self, platform: str, chat_id: str) -> bool:
        """The goal lane may inject Goal/Executive grounding / create goals."""
        return self.goals_is_active(platform, chat_id) and self.goals_mode == "live"

    def reasoning_is_active(self, platform: str, chat_id: str) -> bool:
        """The reasoning lane is engaged for this channel (shadow or live)."""
        return bool(self.reasoning_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def reasoning_is_live(self, platform: str, chat_id: str) -> bool:
        """The reasoning lane may run the bounded tool-less reasoning call."""
        return self.reasoning_is_active(platform, chat_id) and self.reasoning_mode == "live"

    def workspace_is_active(self, platform: str, chat_id: str) -> bool:
        """The workspace/attention lane is engaged for this channel (shadow or live)."""
        return bool(self.workspace_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def workspace_is_live(self, platform: str, chat_id: str) -> bool:
        """The workspace snapshot may bound the ReasoningInput (else shadow: log only)."""
        return self.workspace_is_active(platform, chat_id) and self.workspace_mode == "live"

    def motivation_is_active(self, platform: str, chat_id: str) -> bool:
        """The motivation/homeostasis lane is engaged for this channel (shadow or live)."""
        return bool(self.motivation_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def motivation_is_live(self, platform: str, chat_id: str) -> bool:
        """Eligible drive candidates may merge into the Workspace pool (else shadow: log only)."""
        return self.motivation_is_active(platform, chat_id) and self.motivation_mode == "live"

    def planning_is_active(self, platform: str, chat_id: str) -> bool:
        """The planning lane is engaged for this channel (shadow or live)."""
        return bool(self.planning_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def planning_is_live(self, platform: str, chat_id: str) -> bool:
        """A proposed plan snapshot's answer may become the turn's final_response
        (else shadow: build+validate+log only, no user-facing answer)."""
        return self.planning_is_active(platform, chat_id) and self.planning_mode == "live"

    def ethics_is_active(self, platform: str, chat_id: str) -> bool:
        """The ethical-deliberation lane is engaged for this channel (shadow or live)."""
        return bool(self.ethics_enabled) and self._cognitive_channel_match(platform, str(chat_id))

    def ethics_is_live(self, platform: str, chat_id: str) -> bool:
        """A grounded advisory result answer may become the turn final_response
        (else shadow: build+validate+log only). ADVISORY ONLY; never authorises."""
        return self.ethics_is_active(platform, chat_id) and self.ethics_mode == "live"

    def social_cognition_is_active(self, platform: str, chat_id: str) -> bool:
        """The TURN-only Slice-14 observer runs for this channel (shadow or live).

        Unknown modes fail open by disabling Slice 14 for the turn. Channel
        scope deliberately reuses ``cognitive_channels``.
        """
        return (
            bool(self.social_cognition_enabled)
            and self.social_cognition_mode in ("shadow", "live")
            and self._cognitive_channel_match(platform, str(chat_id))
        )

    def social_cognition_is_live(self, platform: str, chat_id: str) -> bool:
        """The tone note may reach the reply model. The router adds it ONLY on an owner turn
        (canonical_memory.owner_turn()); every other channel stays shadow."""
        return self.social_cognition_is_active(platform, chat_id) and self.social_cognition_mode == "live"

    def memory_consolidation_is_active(self) -> bool:
        """True only for the manually invoked Slice 15A shadow worker."""
        return (
            bool(self.memory_consolidation_enabled)
            and self.memory_consolidation_mode == "shadow"
        )

    def canonical_ltm_is_enabled(self) -> bool:
        """True only for an explicitly present, strictly boolean true setting."""
        return self.canonical_ltm_config_valid and self.canonical_ltm_enabled is True

    def resolved_log_path(self) -> Path:
        if self.log_path:
            return Path(os.path.expanduser(self.log_path))
        return _hermes_home() / "lilith_router" / "decisions.log"


def _owner_label_in(channels) -> bool:
    """An owner-channel label in a channel list (e.g. "discord_owner_dm") matches only this turn's verified owner
    channel, so the verified DM joins without its id in router.yaml. Never matches "public"."""
    try:
        from . import canonical_memory as _cm
        label = _cm.current_channel()
    except Exception:
        return False
    return label != "public" and label in channels


def parse_fallback_chain(raw) -> List[Dict[str, str]]:
    """[{provider, model[, api_mode]}], at most 3 entries; anything malformed is dropped (never raises)."""
    out: List[Dict[str, str]] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        provider, model = str(entry.get("provider") or "").strip(), str(entry.get("model") or "").strip()
        if not provider or not model:
            continue
        item = {"provider": provider, "model": model}
        mode = str(entry.get("api_mode") or "").strip()
        if mode in ("chat_completions", "codex_responses"):
            item["api_mode"] = mode
        if item not in out:
            out.append(item)
        if len(out) == 3:
            break
    return out


def load() -> RouterConfig:
    """Load config from disk. Never raises — returns defaults on any error."""
    try:
        import yaml  # Hermes ships pyyaml
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return RouterConfig()
        cfg = RouterConfig()
        cfg.enabled = bool(raw.get("enabled", cfg.enabled))
        cfg.mode = str(raw.get("mode", cfg.mode)).strip().lower() or "shadow"
        lc = raw.get("live_channels", [])
        cfg.live_channels = [str(x) for x in lc] if isinstance(lc, (list, tuple)) else []
        cfg.groq_model = str(raw.get("groq_model", cfg.groq_model))
        cfg.groq_provider = str(raw.get("groq_provider", cfg.groq_provider))
        cfg.hermes_model = str(raw.get("hermes_model", cfg.hermes_model))
        cfg.hermes_provider = str(raw.get("hermes_provider", cfg.hermes_provider))
        cfg.full_agent_fallback = parse_fallback_chain(raw.get("full_agent_fallback"))
        cfg.recent_turns = int(raw.get("recent_turns", cfg.recent_turns))
        cfg.turn_trace_enabled = raw.get("turn_trace_enabled", True) is not False
        mode = str(raw.get("social_preferences_mode", "off")).strip().lower()
        cfg.social_preferences_mode = mode if mode in ("off", "shadow", "live") else "off"
        mode = str(raw.get("social_corrections_mode", "off")).strip().lower()
        cfg.social_corrections_mode = mode if mode in ("off", "live") else "off"
        mode = str(raw.get("metacognition_mode", "off")).strip().lower()
        cfg.metacognition_mode = mode if mode in ("off", "shadow", "live") else "off"
        ctl = str(raw.get("metacognition_recall_control", "ask")).strip().lower()
        cfg.metacognition_recall_control = ctl if ctl in ("ask", "escalate") else "ask"
        try:
            cfg.decision_log_max_bytes = max(100_000, min(50_000_000, int(raw.get(
                "decision_log_max_bytes", cfg.decision_log_max_bytes))))
        except (TypeError, ValueError):
            pass
        cfg.log_path = str(raw.get("log_path", cfg.log_path) or "")
        # Slice 7.2 cognitive lane (additive; safe defaults keep it OFF).
        cfg.cognitive_enabled = bool(raw.get("cognitive_enabled", cfg.cognitive_enabled))
        cfg.cognitive_mode = str(
            raw.get("cognitive_mode", cfg.cognitive_mode)
        ).strip().lower() or "shadow"
        cc = raw.get("cognitive_channels", [])
        cfg.cognitive_channels = [str(x) for x in cc] if isinstance(cc, (list, tuple)) else []
        cfg.cognitive_draft_dedup = bool(raw.get("cognitive_draft_dedup", cfg.cognitive_draft_dedup))
        cfg.goals_enabled = bool(raw.get("goals_enabled", cfg.goals_enabled))
        cfg.goals_mode = str(raw.get("goals_mode", cfg.goals_mode)).strip().lower() or "shadow"
        cfg.reasoning_enabled = bool(raw.get("reasoning_enabled", cfg.reasoning_enabled))
        cfg.reasoning_mode = str(raw.get("reasoning_mode", cfg.reasoning_mode)).strip().lower() or "shadow"
        cfg.workspace_enabled = bool(raw.get("workspace_enabled", cfg.workspace_enabled))
        cfg.workspace_mode = str(raw.get("workspace_mode", cfg.workspace_mode)).strip().lower() or "shadow"
        try:
            cfg.workspace_capacity = int(raw.get("workspace_capacity", cfg.workspace_capacity))
        except (TypeError, ValueError):
            pass
        cfg.motivation_enabled = bool(raw.get("motivation_enabled", cfg.motivation_enabled))
        cfg.motivation_mode = str(raw.get("motivation_mode", cfg.motivation_mode)).strip().lower() or "shadow"
        cfg.planning_enabled = bool(raw.get("planning_enabled", cfg.planning_enabled))
        cfg.planning_mode = str(raw.get("planning_mode", cfg.planning_mode)).strip().lower() or "shadow"
        try:
            cfg.planning_max_steps = int(raw.get("planning_max_steps", cfg.planning_max_steps))
        except (TypeError, ValueError):
            pass
        cfg.ethics_enabled = bool(raw.get("ethics_enabled", cfg.ethics_enabled))
        cfg.ethics_mode = str(raw.get("ethics_mode", cfg.ethics_mode)).strip().lower() or "shadow"
        try:
            cfg.ethics_max_concerns = int(raw.get("ethics_max_concerns", cfg.ethics_max_concerns))
        except (TypeError, ValueError):
            pass
        try:
            cfg.ethics_max_tensions = int(raw.get("ethics_max_tensions", cfg.ethics_max_tensions))
        except (TypeError, ValueError):
            pass
        cfg.social_cognition_enabled = bool(
            raw.get("social_cognition_enabled", cfg.social_cognition_enabled)
        )
        cfg.social_cognition_mode = str(
            raw.get("social_cognition_mode", cfg.social_cognition_mode)
        ).strip().lower() or "shadow"
        cfg.memory_consolidation_enabled = bool(
            raw.get("memory_consolidation_enabled", cfg.memory_consolidation_enabled)
        )
        cfg.memory_consolidation_mode = str(
            raw.get("memory_consolidation_mode", cfg.memory_consolidation_mode)
        ).strip().lower() or "shadow"
        canonical_value = raw.get("canonical_ltm_enabled")
        if isinstance(canonical_value, bool):
            cfg.canonical_ltm_enabled = canonical_value
            cfg.canonical_ltm_config_valid = True
        else:
            cfg.canonical_ltm_enabled = False
            cfg.canonical_ltm_config_valid = False
        try:  # a bad lean value disables only the lean reply, never the router
            sl = raw.get("social_lean_channels", [])
            cfg.social_lean_channels = [str(x) for x in sl] if isinstance(sl, (list, tuple)) else []
            for key, lo, hi in (("social_lean_history_turns", 0, 40), ("social_lean_max_output_tokens", 64, 1024),
                                ("social_lean_tpm_budget", 1000, 8000), ("social_lean_tpd_budget", 1000, 200000)):
                setattr(cfg, key, max(lo, min(hi, int(raw.get(key, getattr(cfg, key))))))
            cfg.social_lean_timeout_s = max(2.0, min(60.0, float(
                raw.get("social_lean_timeout_s", cfg.social_lean_timeout_s))))
            cfg.social_lean_enabled = raw.get("social_lean_enabled") is True
        except (TypeError, ValueError):
            cfg.social_lean_enabled = False
        return cfg
    except FileNotFoundError:
        return RouterConfig()
    except Exception:
        logger.debug("lilith_router: config load failed; using safe defaults", exc_info=True)
        return RouterConfig()
