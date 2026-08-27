/**
 * Presence Engine V2 — the normalized, renderer-agnostic contract.
 *
 * The engine decouples Lilith's *state* from how she is *rendered*. A single
 * {@link PresenceSignal} drives the orb today and, later, a 3D avatar, a
 * screen-edge peek, or a voice waveform — without any renderer knowing where
 * the signal came from, and without any application module knowing which
 * animation clip plays.
 *
 * State is split into orthogonal axes so personality logic never leaks into
 * animation components:
 *   - activity   — what she is doing
 *   - emotion    — how she feels about it
 *   - attention  — how engaged she is with the user
 *   - placement  — where on screen she sits
 *   - intensity  — global energy (0..1), drives glow / motion amplitude
 *   - speaking   — gate for future visemes / lip-sync
 *   - importance — of the driving event; feeds the interruption model
 */

/** Which renderer is currently drawing the presence. */
export type RendererKind = "orb" | "avatar" | "edge" | "voice";

/** How Lilith feels. Reserved for the avatar; the orb currently ignores it. */
export type Emotion =
  | "neutral"
  | "attentive"
  | "focused"
  | "amused"
  | "pleased"
  | "concerned"
  | "alert";

/** What Lilith is doing. This is the axis the orb renderer reads. */
export type Activity =
  | "idle"
  | "listening"
  | "thinking"
  | "working"
  | "speaking"
  | "waiting";

/** How engaged she is with the user right now. */
export type Attention = "away" | "ambient" | "engaged" | "locked";

/** Where the presence sits on screen. Only "center" is wired in V1. */
export type Placement =
  | "center"
  | "top-peek"
  | "left-edge"
  | "right-edge"
  | "bottom-corner"
  | "floating"
  | "background"
  | "hidden";

/** Importance of the event driving a state change — feeds interruption. */
export type Importance = "passive" | "normal" | "notable" | "urgent";

/** The complete, normalized presence state. */
export interface PresenceSignal {
  activity: Activity;
  emotion: Emotion;
  attention: Attention;
  placement: Placement;
  /** 0..1 — reserved for the avatar / future renderers. */
  intensity: number;
  /** Gate for future speech visemes / lip-sync. */
  speaking: boolean;
  /** Importance of the driver behind the current signal. */
  importance: Importance;
}

/** The resting state Lilith returns to. */
export const IDLE_SIGNAL: PresenceSignal = {
  activity: "idle",
  emotion: "neutral",
  attention: "ambient",
  placement: "center",
  intensity: 0.4,
  speaking: false,
  importance: "passive",
};

/* -------------------------------------------------------------------- events */

/**
 * Semantic presence events. Modules emit these; the engine maps them to
 * signals. Events carry *meaning only* — never payloads, PII, tokens, or raw
 * backend data. `meta` is limited to primitive labels for debugging/telemetry.
 *
 * V1 wires the `conversation.*`, `meeting.starting_soon`, and
 * `automation.failed` events. The remaining types are mapped in
 * `map-events.ts` but not yet emitted by application modules.
 */
export type PresenceEventType =
  // conversation lifecycle (wired in V1)
  | "conversation.input_focus"
  | "conversation.input_blur"
  | "conversation.typing"
  | "conversation.user_message"
  | "conversation.response_started"
  | "conversation.response_complete"
  | "conversation.error"
  // ambient module events (wired in V1)
  | "meeting.starting_soon"
  | "automation.failed"
  // future — mapped for architecture, not yet emitted
  | "career.interview_detected"
  | "mail.urgent_received"
  | "system.attention_required";

export interface PresenceEvent {
  type: PresenceEventType;
  /** Epoch ms; the engine stamps this if omitted. */
  at?: number;
  /** Primitive, non-sensitive labels only. */
  meta?: Record<string, string | number | boolean>;
}

/** Numeric rank for importance comparisons. */
export const IMPORTANCE_RANK: Record<Importance, number> = {
  passive: 0,
  normal: 1,
  notable: 2,
  urgent: 3,
};
