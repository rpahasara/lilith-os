/**
 * Event → signal mapping. This is the *only* place presence "personality"
 * lives: which event makes Lilith look attentive, focused, concerned, or
 * alert, how long a reaction holds, and how insistent it is. Animation
 * components never see this — they only ever receive a resolved signal.
 *
 * Each entry is pure data. Retuning Lilith's demeanour is a table edit here,
 * never a change to a renderer.
 */

import type {
  Importance,
  PresenceEventType,
  PresenceSignal,
} from "./types";

export interface EventMapping {
  /** Fields to merge onto the current steady signal. */
  patch: Partial<PresenceSignal>;
  /** Importance of this event — drives interruption priority + orb glow. */
  importance: Importance;
  /**
   * If set, the reaction is *transient*: it shows for `holdMs`, then the engine
   * restores the steady signal. If omitted, the patch updates the steady
   * signal persistently.
   */
  holdMs?: number;
  /**
   * For transient reactions, optionally change what Lilith restores *to* once
   * the reaction fades (e.g. a completed response ends by returning to idle,
   * not to the "thinking" it was in while generating).
   */
  steadyPatch?: Partial<PresenceSignal>;
  /** Minimum ms between firings of the same `cooldownKey`. */
  cooldownMs?: number;
  /** Cooldown bucket; defaults to the event type. */
  cooldownKey?: string;
  /**
   * External (non-conversation) events with importance below "urgent" are
   * suppressed while the user is actively typing. Conversation events are the
   * user's own flow and are never suppressed.
   */
  external?: boolean;
}

/**
 * The mapping table. `conversation.*`, `meeting.starting_soon`, and
 * `automation.failed` are wired to real emitters in V1. The remaining entries
 * are defined so the architecture is complete; their emitters land later.
 */
export const EVENT_MAP: Record<PresenceEventType, EventMapping> = {
  /* ------------------------------------------------ conversation lifecycle */
  "conversation.input_focus": {
    patch: { activity: "listening", emotion: "attentive", attention: "engaged" },
    importance: "normal",
  },
  "conversation.input_blur": {
    patch: { activity: "idle", emotion: "neutral", attention: "ambient" },
    importance: "normal",
  },
  // Typing does not change the visible signal; it only arms typing-suppression
  // in the orchestrator so ambient events don't interrupt mid-sentence.
  "conversation.typing": {
    patch: {},
    importance: "passive",
  },
  "conversation.user_message": {
    patch: { activity: "listening", emotion: "attentive", attention: "locked" },
    importance: "normal",
  },
  "conversation.response_started": {
    patch: { activity: "thinking", emotion: "focused", attention: "locked" },
    importance: "normal",
  },
  // Transient: show "speaking" for a beat, then settle back to idle.
  "conversation.response_complete": {
    patch: {
      activity: "speaking",
      emotion: "pleased",
      attention: "engaged",
      speaking: true,
    },
    importance: "normal",
    holdMs: 2600,
    steadyPatch: {
      activity: "idle",
      emotion: "neutral",
      attention: "ambient",
      speaking: false,
    },
  },
  "conversation.error": {
    patch: { activity: "idle", emotion: "concerned", attention: "ambient" },
    importance: "normal",
    holdMs: 2200,
    steadyPatch: { activity: "idle", emotion: "neutral", attention: "ambient" },
  },

  /* -------------------------------------------------- ambient module events */
  "meeting.starting_soon": {
    patch: { activity: "waiting", emotion: "attentive", attention: "ambient" },
    importance: "notable",
    holdMs: 5000,
    cooldownMs: 60_000,
    external: true,
  },
  "automation.failed": {
    patch: { activity: "waiting", emotion: "concerned", attention: "ambient" },
    importance: "urgent",
    holdMs: 4000,
    cooldownMs: 30_000,
    external: true,
  },

  /* --------------------------------------- future (mapped, not yet emitted) */
  "career.interview_detected": {
    patch: { activity: "waiting", emotion: "alert", attention: "ambient" },
    importance: "notable",
    holdMs: 5000,
    cooldownMs: 60_000,
    external: true,
  },
  "mail.urgent_received": {
    patch: { activity: "waiting", emotion: "alert", attention: "ambient" },
    importance: "notable",
    holdMs: 4000,
    cooldownMs: 45_000,
    external: true,
  },
  "system.attention_required": {
    patch: { activity: "waiting", emotion: "alert", attention: "ambient" },
    importance: "urgent",
    holdMs: 4000,
    cooldownMs: 30_000,
    external: true,
  },
};
