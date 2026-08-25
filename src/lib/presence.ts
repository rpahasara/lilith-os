/** The emotional / operational states Lilith's presence can occupy. */
export type PresenceState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking";

export interface PresenceProfile {
  label: string;
  hint: string;
  /** Displacement amplitude of the orb surface. */
  amplitude: number;
  /** Animation speed multiplier. */
  speed: number;
  /** 0 = fully violet, 1 = fully cyan — the presence color balance. */
  colorMix: number;
  /** Rim / glow intensity. */
  intensity: number;
}

export const PRESENCE: Record<PresenceState, PresenceProfile> = {
  idle: {
    label: "Idle",
    hint: "Present. Listening for you.",
    amplitude: 0.12,
    speed: 0.5,
    colorMix: 0.28,
    intensity: 1.0,
  },
  listening: {
    label: "Listening",
    hint: "Focused and attentive.",
    amplitude: 0.22,
    speed: 1.1,
    colorMix: 0.55,
    intensity: 1.35,
  },
  thinking: {
    label: "Thinking",
    hint: "Processing deeply.",
    amplitude: 0.34,
    speed: 1.8,
    colorMix: 0.12,
    intensity: 1.5,
  },
  speaking: {
    label: "Speaking",
    hint: "Sharing what matters.",
    amplitude: 0.28,
    speed: 1.4,
    colorMix: 0.7,
    intensity: 1.7,
  },
};
