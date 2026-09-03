/**
 * Hsin Speaking Motion — Phase 1 POC
 *
 * Restrained conversational body motion layered on top of Natural Idle V2 while
 * Hsin is SPEAKING. Like the ambient idle scheduler, this module is intentionally
 * pure: it holds no three.js references and only emits bounded per-bone Euler
 * offsets (in degrees). The renderer post-multiplies these onto the normalized
 * bones via the existing `addMicroMotion` seam, so speaking motion is purely
 * additive and always returns to exactly the canonical neutral when it winds
 * down — it can never corrupt the canonical neutral, the frozen Path-B arms,
 * fingers, springs, or the expression stack.
 *
 * Two layers:
 *  1. MICRO-MOTION — continuous, subtle torso/head engagement (chest, upperChest,
 *     neck, head) that reads as "slightly more alive than idle" while speaking,
 *     plus an occasional tiny head nod. Scaled by a speaking envelope that ramps
 *     in (~0.4 s) when speech starts and out (~0.5 s) when it stops.
 *  2. GESTURE — a single, carefully restrained right-arm conversational beat that
 *     may fire at most occasionally during a multi-second speaking sequence. It
 *     begins and ends from the frozen canonical arm neutral (offsets = 0), lifts
 *     only modestly, bends the elbow slightly, and never rotates the palm toward
 *     the viewer. Fingers are never touched by this module.
 *
 * Scope (Phase 1): additive offsets only, one gesture, no arms beyond the right
 * upper/lower arm + hand, no springs, no IK, no priority arbitration beyond the
 * renderer suppressing ambient idle while this enabled layer owns the bones.
 */

export type SpeakingMicroBone = "chest" | "upperChest" | "neck" | "head";
export type SpeakingGestureBone =
  | "rightUpperArm"
  | "rightLowerArm"
  | "rightHand";

export type SpeakingBoneOffset = { x: number; y: number; z: number };

export type SpeakingMicroOffsets = Partial<
  Record<SpeakingMicroBone, SpeakingBoneOffset>
>;
export type SpeakingGestureOffsets = Partial<
  Record<SpeakingGestureBone, SpeakingBoneOffset>
>;

export type SpeakingGesturePhase = "idle" | "enter" | "hold" | "exit";

/** Dev A/B: V1 = original restrained beat, V2 = visibility-tuned beat. */
export type SpeakingGestureVariant = "v1" | "v2";

export interface SpeakingMotionConfig {
  /** Speaking envelope ramp-in rate (per second): reaches 1 in ~1/rate s. */
  envelopeInRate: number;
  /** Speaking envelope ramp-out rate (per second). */
  envelopeOutRate: number;
  /** Gesture smoothstep ramp-in duration (seconds). */
  gestureEnter: number;
  /** Gesture full-weight hold window (seconds, randomized). */
  gestureHoldMin: number;
  gestureHoldMax: number;
  /** Gesture smoothstep ramp-out duration (seconds). */
  gestureExit: number;
  /** Minimum continuous speaking time before an auto gesture is eligible (s). */
  gestureMinSpeakingElapsed: number;
  /** Auto-gesture probability per second once eligible (one gesture / speech). */
  gestureChancePerSecond: number;
  /** Deterministic RNG seed (reproducible session for debugging). */
  seed: number;
}

export const DEFAULT_SPEAKING_MOTION_CONFIG: SpeakingMotionConfig = {
  envelopeInRate: 2.5, // ~0.4 s to full
  envelopeOutRate: 2.0, // ~0.5 s to zero
  // Visibility tuning pass: slower, more readable beat (was 0.5 / 0.5-0.8 / 0.7).
  // neutral -> small emphasis -> brief readable hold -> relaxed return, not a twitch.
  gestureEnter: 0.6,
  gestureHoldMin: 0.9,
  gestureHoldMax: 1.2,
  gestureExit: 0.9,
  gestureMinSpeakingElapsed: 2.0,
  gestureChancePerSecond: 0.25,
  seed: 4242,
};

/**
 * Continuous micro-motion amplitudes (degrees), applied at full envelope. Kept
 * subtle — a touch more engaged than Natural Idle V2 — using incommensurate
 * frequencies so it never reads as a repetitive bob. Each entry is
 * [amplitude, frequency(rad-ish per s), phase].
 */
type Osc = { amp: number; freq: number; phase: number };
type MicroAxes = { x?: Osc; y?: Osc; z?: Osc };

const MICRO: Record<SpeakingMicroBone, MicroAxes> = {
  // Chest carries the "breathing while talking" emphasis + a small roll sway.
  // Visibility pass: nudged up slightly (was 1.0 / 0.5) — still subtle.
  chest: {
    x: { amp: 1.2, freq: 1.9, phase: 0.0 },
    z: { amp: 0.6, freq: 0.83, phase: 1.1 },
  },
  // UpperChest adds a slight forward emphasis + tiny yaw shift.
  // Visibility pass: nudged up slightly (was 0.7 / 0.4) — still subtle.
  upperChest: {
    x: { amp: 0.9, freq: 2.1, phase: 0.6 },
    y: { amp: 0.5, freq: 0.77, phase: 2.3 },
  },
  // Neck follows the head lightly.
  neck: {
    x: { amp: 0.4, freq: 1.7, phase: 1.9 },
    y: { amp: 0.6, freq: 1.1, phase: 0.4 },
  },
  // Head gives the conversational emphasis (yaw + a little pitch/roll).
  head: {
    x: { amp: 0.6, freq: 2.3, phase: 0.9 },
    y: { amp: 1.0, freq: 1.3, phase: 2.7 },
    z: { amp: 0.4, freq: 0.91, phase: 0.2 },
  },
};

/**
 * Occasional tiny nod: a discrete downward head-pitch pulse that fires now and
 * then while speaking, so emphasis never becomes a constant bob. Amplitude is
 * additive on top of the head micro-oscillator.
 */
const NOD_AMPLITUDE = 1.6; // degrees, head pitch (x)
const NOD_RISE = 0.22; // s
const NOD_FALL = 0.34; // s
const NOD_INTERVAL_MIN = 3.5; // s between nods
const NOD_INTERVAL_MAX = 6.5; // s

/**
 * Restrained conversational beat — full-weight (weight = 1) right-arm offsets in
 * degrees (local XYZ = pitch/yaw/roll), post-multiplied on the frozen canonical
 * arm neutral. Deliberately small: the upper arm lifts only modestly, the elbow
 * bends slightly more with the forearm coming a little forward/inward, and the
 * hand only follows the forearm — wrist rotation stays very close to canonical
 * and the palm is never turned toward the viewer. Fingers are untouched. Both
 * variants stay well short of T-pose and cannot invert.
 *
 * V1 = original Phase 1 POC (too subtle at presentation scale).
 * V2 = visibility-tuning pass. The chain was tuned intentionally, not scaled
 * uniformly: the upper-arm lift and (primarily) the elbow flex grow so the beat
 * reads clearly, the forearm-inward yaw grows modestly, and the hand stays
 * extremely conservative so the palm is never driven toward the viewer.
 */
const GESTURE_VARIANTS: Record<SpeakingGestureVariant, SpeakingGestureOffsets> = {
  v1: {
    rightUpperArm: { x: 6, y: 2, z: 0 },
    rightLowerArm: { x: 10, y: 4, z: 0 },
    rightHand: { x: 3, y: 0, z: 0 },
  },
  v2: {
    rightUpperArm: { x: 9, y: 3, z: 0 },
    rightLowerArm: { x: 14, y: 5, z: 0 },
    rightHand: { x: 4, y: 0, z: 0 },
  },
};

/** mulberry32 — tiny deterministic PRNG. */
function makeRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Classic smoothstep on [0, 1]. */
function smoothstep01(v: number): number {
  const x = v < 0 ? 0 : v > 1 ? 1 : v;
  return x * x * (3 - 2 * x);
}

function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

export interface SpeakingMotionState {
  envelope: number;
  gesturePhase: SpeakingGesturePhase;
  gestureWeight: number;
  gestureFiredThisSpeech: boolean;
}

export interface SpeakingMotionFrame {
  micro: SpeakingMicroOffsets;
  gesture: SpeakingGestureOffsets;
  envelope: number;
  gesturePhase: SpeakingGesturePhase;
  gestureWeight: number;
}

const EMPTY_FRAME: SpeakingMotionFrame = {
  micro: {},
  gesture: {},
  envelope: 0,
  gesturePhase: "idle",
  gestureWeight: 0,
};

export class HsinSpeakingMotion {
  private readonly config: SpeakingMotionConfig;
  private rng: () => number;

  private time = 0; // continuous oscillator time (advances with envelope > 0)
  private envelope = 0; // 0..1 speaking engagement
  private wasSpeaking = false;
  private speakingElapsed = 0;

  private gesturePhase: SpeakingGesturePhase = "idle";
  private gestureTimer = 0;
  private gestureDuration = 0;
  private gestureWeight = 0;
  private gestureFiredThisSpeech = false;

  private nodTimer = 0;
  private nextNodAt: number;
  private nodActive = false;
  private nodElapsed = 0;

  private variant: SpeakingGestureVariant = "v2";

  constructor(config: Partial<SpeakingMotionConfig> = {}) {
    this.config = { ...DEFAULT_SPEAKING_MOTION_CONFIG, ...config };
    this.rng = makeRng(this.config.seed);
    this.nextNodAt = this.randRange(NOD_INTERVAL_MIN, NOD_INTERVAL_MAX);
  }

  /** Dev A/B: select which gesture amplitude set the beat uses. */
  setVariant(variant: SpeakingGestureVariant): void {
    this.variant = variant;
  }

  /** Return everything to neutral immediately (used when the layer is disabled). */
  reset(): void {
    this.time = 0;
    this.envelope = 0;
    this.wasSpeaking = false;
    this.speakingElapsed = 0;
    this.gesturePhase = "idle";
    this.gestureTimer = 0;
    this.gestureWeight = 0;
    this.gestureFiredThisSpeech = false;
    this.nodTimer = 0;
    this.nodActive = false;
    this.nodElapsed = 0;
    this.nextNodAt = this.randRange(NOD_INTERVAL_MIN, NOD_INTERVAL_MAX);
  }

  /** Dev affordance: begin the conversational beat immediately (from enter). */
  triggerGesture(): void {
    this.gesturePhase = "enter";
    this.gestureTimer = 0;
    this.gestureDuration = this.config.gestureEnter;
    this.gestureFiredThisSpeech = true;
  }

  private randRange(min: number, max: number): number {
    return min + this.rng() * (max - min);
  }

  /**
   * Advance the scheduler by `dt` seconds. `speaking` is the current speaking
   * state (speechPlayback.status !== "idle"). Returns the bounded offsets to
   * apply this frame; everything is scaled toward zero as the envelope falls.
   */
  update(dt: number, speaking: boolean): SpeakingMotionFrame {
    // Rising edge of speech: re-arm a fresh single-gesture budget.
    if (speaking && !this.wasSpeaking) {
      this.speakingElapsed = 0;
      this.gestureFiredThisSpeech = false;
    }
    this.wasSpeaking = speaking;

    // Speaking engagement envelope.
    const rate = speaking
      ? this.config.envelopeInRate
      : this.config.envelopeOutRate;
    const target = speaking ? 1 : 0;
    if (this.envelope < target) {
      this.envelope = Math.min(target, this.envelope + rate * dt);
    } else if (this.envelope > target) {
      this.envelope = Math.max(target, this.envelope - rate * dt);
    }

    if (speaking) this.speakingElapsed += dt;

    // Advance oscillator time only while there is engagement to show.
    if (this.envelope > 0) this.time += dt;

    // Auto-gesture: at most one per speaking sequence, only after the minimum
    // elapsed, only while actively speaking and idle. Short speech may never
    // trigger; longer speech triggers occasionally.
    if (
      speaking &&
      this.gesturePhase === "idle" &&
      !this.gestureFiredThisSpeech &&
      this.speakingElapsed >= this.config.gestureMinSpeakingElapsed &&
      this.rng() < this.config.gestureChancePerSecond * dt
    ) {
      this.triggerGesture();
    }

    this.advanceGesture(dt);
    this.advanceNod(dt, speaking);

    if (this.envelope <= 0 && this.gestureWeight <= 0) return EMPTY_FRAME;

    return {
      micro: this.buildMicro(),
      gesture: this.buildGesture(),
      envelope: this.envelope,
      gesturePhase: this.gesturePhase,
      gestureWeight: this.gestureWeight,
    };
  }

  private advanceGesture(dt: number): void {
    if (this.gesturePhase === "idle") {
      this.gestureWeight = 0;
      return;
    }
    this.gestureTimer += dt;
    switch (this.gesturePhase) {
      case "enter": {
        this.gestureWeight = smoothstep01(this.gestureTimer / this.gestureDuration);
        if (this.gestureTimer >= this.gestureDuration) {
          this.gestureWeight = 1;
          this.gesturePhase = "hold";
          this.gestureTimer = 0;
          this.gestureDuration = this.randRange(
            this.config.gestureHoldMin,
            this.config.gestureHoldMax,
          );
        }
        break;
      }
      case "hold": {
        this.gestureWeight = 1;
        if (this.gestureTimer >= this.gestureDuration) {
          this.gesturePhase = "exit";
          this.gestureTimer = 0;
          this.gestureDuration = this.config.gestureExit;
        }
        break;
      }
      case "exit": {
        this.gestureWeight =
          1 - smoothstep01(this.gestureTimer / this.gestureDuration);
        if (this.gestureTimer >= this.gestureDuration) {
          this.gestureWeight = 0;
          this.gesturePhase = "idle";
          this.gestureTimer = 0;
        }
        break;
      }
    }
  }

  private advanceNod(dt: number, speaking: boolean): void {
    if (this.nodActive) {
      this.nodElapsed += dt;
      if (this.nodElapsed >= NOD_RISE + NOD_FALL) {
        this.nodActive = false;
        this.nodElapsed = 0;
        this.nodTimer = 0;
        this.nextNodAt = this.randRange(NOD_INTERVAL_MIN, NOD_INTERVAL_MAX);
      }
      return;
    }
    // Only schedule new nods while genuinely speaking and engaged.
    if (!speaking || this.envelope < 0.5) return;
    this.nodTimer += dt;
    if (this.nodTimer >= this.nextNodAt) {
      this.nodActive = true;
      this.nodElapsed = 0;
    }
  }

  private nodOffset(): number {
    if (!this.nodActive) return 0;
    const w =
      this.nodElapsed < NOD_RISE
        ? smoothstep01(this.nodElapsed / NOD_RISE)
        : 1 - smoothstep01((this.nodElapsed - NOD_RISE) / NOD_FALL);
    return NOD_AMPLITUDE * clamp01(w);
  }

  private oscValue(osc: Osc | undefined): number {
    if (!osc) return 0;
    return Math.sin(this.time * osc.freq + osc.phase) * osc.amp;
  }

  private buildMicro(): SpeakingMicroOffsets {
    const env = this.envelope;
    if (env <= 0) return {};
    const out: SpeakingMicroOffsets = {};
    (Object.keys(MICRO) as SpeakingMicroBone[]).forEach((bone) => {
      const axes = MICRO[bone];
      let x = this.oscValue(axes.x);
      const y = this.oscValue(axes.y);
      const z = this.oscValue(axes.z);
      if (bone === "head") x += this.nodOffset();
      out[bone] = { x: x * env, y: y * env, z: z * env };
    });
    return out;
  }

  private buildGesture(): SpeakingGestureOffsets {
    const w = this.gestureWeight * this.envelope;
    if (w <= 0) return {};
    const source = GESTURE_VARIANTS[this.variant];
    const out: SpeakingGestureOffsets = {};
    (Object.keys(source) as SpeakingGestureBone[]).forEach((bone) => {
      const o = source[bone];
      if (!o) return;
      out[bone] = { x: o.x * w, y: o.y * w, z: o.z * w };
    });
    return out;
  }

  getState(): SpeakingMotionState {
    return {
      envelope: this.envelope,
      gesturePhase: this.gesturePhase,
      gestureWeight: this.gestureWeight,
      gestureFiredThisSpeech: this.gestureFiredThisSpeech,
    };
  }
}
