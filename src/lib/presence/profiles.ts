/**
 * Orb-renderer-local interpretation of a {@link PresenceSignal}.
 *
 * These numbers used to live in `lib/presence.ts` as the `PRESENCE` table.
 * They are now renderer-local data: the *engine* speaks in the normalized
 * signal, and the orb translates it here. Other renderers (avatar, edge) will
 * bring their own mapping tables — none of this leaks into the engine.
 *
 * The four conversation activities (idle/listening/thinking/speaking) keep
 * their exact original values, so the orb looks and behaves identically to the
 * pre-refactor build for the whole conversation lifecycle.
 */

import type { Activity, Importance, PresenceSignal } from "./types";

/** Surface params the orb shader damps toward. */
export interface OrbParams {
  /** Displacement amplitude of the orb surface. */
  amplitude: number;
  /** Animation speed multiplier. */
  speed: number;
  /** 0 = fully violet, 1 = fully cyan. */
  colorMix: number;
  /** Rim / glow intensity. */
  intensity: number;
}

/**
 * Per-activity base profile. idle/listening/thinking/speaking are the original
 * values — do not retune without intent, they define the shipped orb look.
 * working/waiting are new activities introduced with V2 (used by ambient
 * events); they were chosen to sit tastefully between the existing profiles.
 */
const ACTIVITY_ORB: Record<Activity, OrbParams> = {
  idle: { amplitude: 0.12, speed: 0.5, colorMix: 0.28, intensity: 1.0 },
  listening: { amplitude: 0.22, speed: 1.1, colorMix: 0.55, intensity: 1.35 },
  thinking: { amplitude: 0.34, speed: 1.8, colorMix: 0.12, intensity: 1.5 },
  speaking: { amplitude: 0.28, speed: 1.4, colorMix: 0.7, intensity: 1.7 },
  working: { amplitude: 0.3, speed: 1.5, colorMix: 0.35, intensity: 1.45 },
  waiting: { amplitude: 0.16, speed: 0.7, colorMix: 0.4, intensity: 1.15 },
};

/**
 * Importance lifts the orb's glow so ambient alerts read as "brighter/more
 * awake" without any colour or shape change. passive/normal = 1.0, so the
 * conversation lifecycle (all normal-importance) is unchanged.
 */
const IMPORTANCE_GAIN: Record<Importance, number> = {
  passive: 1.0,
  normal: 1.0,
  notable: 1.12,
  urgent: 1.28,
};

/** Translate a normalized signal into orb shader targets. */
export function orbParamsFromSignal(signal: PresenceSignal): OrbParams {
  const base = ACTIVITY_ORB[signal.activity] ?? ACTIVITY_ORB.idle;
  const gain = IMPORTANCE_GAIN[signal.importance] ?? 1.0;
  return { ...base, intensity: base.intensity * gain };
}

/** Human-facing copy per activity — used by the hero hint + state chips. */
export interface ActivityMeta {
  label: string;
  hint: string;
}

export const ACTIVITY_META: Record<Activity, ActivityMeta> = {
  idle: { label: "Idle", hint: "Present. Listening for you." },
  listening: { label: "Listening", hint: "Focused and attentive." },
  thinking: { label: "Thinking", hint: "Processing deeply." },
  speaking: { label: "Speaking", hint: "Sharing what matters." },
  working: { label: "Working", hint: "On it." },
  waiting: { label: "Waiting", hint: "Standing by." },
};

/** Activities exposed as manual chips in the hero (the original four). */
export const CHIP_ACTIVITIES: Activity[] = [
  "idle",
  "listening",
  "thinking",
  "speaking",
];
