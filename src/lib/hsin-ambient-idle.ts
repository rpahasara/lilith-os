/**
 * Hsin Ambient Idle — Phase 1 POC
 *
 * A small, deterministic scheduler that layers occasional subtle pose
 * variations on top of Natural Idle V2. It is intentionally pure: it holds no
 * three.js references and only emits bounded per-bone Euler offsets (in
 * degrees) for the six "safe" body bones. The renderer multiplies these onto
 * the normalized bones via the existing `addMicroMotion` seam, so ambient
 * motion is purely additive and can never corrupt the canonical neutral, the
 * Path-B asset, arms/hands, springs, or the expression stack.
 *
 * Lifecycle per gesture:  idle (cooldown) -> enter -> hold -> exit -> idle
 * Enter/exit use smoothstep weighting; hold is full-weight. Cooldown and hold
 * durations are randomized but bounded. The RNG is seeded so a session is
 * reproducible for debugging.
 *
 * Scope: torso/neck/head only, no arms/hands, no springs, no 360 turn, no
 * speaking gestures, no priority arbitration. Phase 1 shipped two variations
 * (weightShiftLeft, gentleHeadTurnRight); Phase 2 adds three more
 * (weightShiftRight, softPostureReset, curiousGlanceLeft) through the same
 * scheduler and selection logic — those two remain byte-for-byte unchanged.
 */

export type AmbientBone =
  | "hips"
  | "spine"
  | "chest"
  | "upperChest"
  | "neck"
  | "head";

export type AmbientBoneOffset = { x: number; y: number; z: number };

export type AmbientOffsets = Partial<Record<AmbientBone, AmbientBoneOffset>>;

export type AmbientPhase = "idle" | "enter" | "hold" | "exit";

export type AmbientVariationName =
  | "weightShiftLeft"
  | "gentleHeadTurnRight"
  // Phase 2 additions (torso/neck/head only, still no arms/hands):
  | "weightShiftRight"
  | "softPostureReset"
  | "curiousGlanceLeft";

export interface AmbientIdleConfig {
  /** Seconds of neutral idle before a variation may begin. */
  cooldownMin: number;
  cooldownMax: number;
  /** Smoothstep ramp-in duration (seconds). */
  enterDuration: number;
  /** Full-weight hold window (seconds). */
  holdMin: number;
  holdMax: number;
  /** Smoothstep ramp-out duration (seconds). */
  exitDuration: number;
  /** Deterministic RNG seed (reproducible session for debugging). */
  seed: number;
}

export const DEFAULT_AMBIENT_IDLE_CONFIG: AmbientIdleConfig = {
  cooldownMin: 25,
  cooldownMax: 45,
  enterDuration: 1.2,
  // Shorter hold for the POC visual-review pass (readable, not lingering).
  // Automatic hold can be lengthened later without touching the state machine.
  holdMin: 3,
  holdMax: 5,
  exitDuration: 1.4,
  seed: 1337,
};

/**
 * Full-weight (weight = 1) target offsets, in degrees, per variation. Kept
 * deliberately small — comparable to or just above Natural Idle V2's own
 * amplitudes — so the result reads as a subtle settle/turn, never a lurch.
 */
const VARIATIONS: Record<AmbientVariationName, AmbientOffsets> = {
  // Weight transfer / stance change (contrapposto), not a sideways lean. Two
  // couples combine:
  //  - Roll (z): the pelvis tilts onto one hip, and the spine/chest counter-roll
  //    back so residual roll at the head is near-zero (~0.7deg) — the upper body
  //    and head stay upright while the pelvis does the work.
  //  - Yaw (y): a small pelvis rotation with an equal-and-opposite spine/chest
  //    counter (net upper yaw ~0) reads as settling into a slightly turned
  //    stance while the shoulders stay front-facing (baseline preserved).
  // Neck/head carry only a touch of roll so the head remains visually balanced.
  weightShiftLeft: {
    hips: { x: 0, y: 1.1, z: 3.2 },
    spine: { x: 0, y: -0.6, z: -1.8 },
    chest: { x: 0, y: -0.5, z: -0.9 },
    upperChest: { x: 0, y: 0, z: -0.3 },
    neck: { x: 0, y: 0, z: 0.2 },
    head: { x: 0, y: 0, z: 0.3 },
  },
  // Brief glance to the side: the head leads clearly, the neck follows
  // moderately, and the torso follows only slightly, diminishing down the
  // spine (upperChest > chest). Reads as "noticing something to one side",
  // not a body turn. Hierarchy of yaw magnitude: head > neck > upperChest > chest.
  gentleHeadTurnRight: {
    chest: { x: 0, y: -0.9, z: 0 },
    upperChest: { x: 0, y: -1.4, z: 0 },
    neck: { x: 0, y: -3.8, z: 0 },
    head: { x: 0.5, y: -6.8, z: -0.9 },
  },
  // --- Phase 2 -----------------------------------------------------------
  // A. Weight transfer onto the OTHER hip — the complement of weightShiftLeft.
  // Same contrapposto structure (pelvis rolls/yaws one way; spine/chest
  // counter so the head stays near-upright), NOT a blind negation: magnitudes
  // are authored a touch smaller/asymmetric (3.0 vs 3.2, 1.7 vs 1.8, ...) so
  // the two shifts read as related-but-distinct natural settles.
  weightShiftRight: {
    hips: { x: 0, y: -1.0, z: -3.0 },
    spine: { x: 0, y: 0.5, z: 1.7 },
    chest: { x: 0, y: 0.4, z: 0.8 },
    upperChest: { x: 0, y: 0, z: 0.3 },
    neck: { x: 0, y: 0, z: -0.2 },
    head: { x: 0, y: 0, z: -0.25 },
  },
  // B. A quiet posture straighten / settle. Visibility-tuned: a clearer
  // chest/upperChest opening with a small spine base and a subtle head lift,
  // plus a tiny counter-roll (upperChest +0.2 / head -0.2) so it does NOT read
  // as a uniform forward/back pitch (i.e. not "breathing"). Still small: no
  // stretch, no dramatic chest push, no upward head snap. Slightly slower
  // enter/exit + longer hold (see VARIATION_TIMING) so the settle reads clearly.
  softPostureReset: {
    spine: { x: -0.6, y: 0, z: 0 },
    chest: { x: -1.1, y: 0, z: 0 },
    upperChest: { x: -0.9, y: 0, z: 0.2 },
    neck: { x: -0.3, y: 0, z: 0 },
    head: { x: -0.8, y: 0, z: -0.2 },
  },
  // C. A brief glance to the other side — the counterpart to gentleHeadTurnRight.
  // Head leads, neck follows, upperChest/chest follow only slightly (same
  // head > neck > upperChest > chest hierarchy). Authored a touch smaller than
  // the right turn (not a blind mirror) and given a shorter hold below so it
  // reads as "briefly noticing something", not a settled turn.
  curiousGlanceLeft: {
    chest: { x: 0, y: 0.7, z: 0 },
    upperChest: { x: 0, y: 1.2, z: 0 },
    neck: { x: 0, y: 3.5, z: 0 },
    head: { x: 0.4, y: 6.2, z: 0.8 },
  },
};

/**
 * Optional per-variation timing override (seconds). Any field omitted falls back
 * to the shared config value, so the scheduler stays a single state machine —
 * only the specified phase durations differ. Cooldown is always shared.
 */
const VARIATION_TIMING: Partial<
  Record<
    AmbientVariationName,
    { enter?: number; exit?: number; holdMin?: number; holdMax?: number }
  >
> = {
  // A posture straighten/settle: slightly slower enter/exit + longer hold so it
  // reads clearly as an intentional adjustment, not breathing.
  softPostureReset: { enter: 1.4, exit: 1.5, holdMin: 4, holdMax: 6 },
  // A glance is a brief notice, not a settled pose.
  curiousGlanceLeft: { holdMin: 2.5, holdMax: 4 },
};

const VARIATION_NAMES = Object.keys(VARIATIONS) as AmbientVariationName[];

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

export interface AmbientIdleState {
  phase: AmbientPhase;
  variation: AmbientVariationName | null;
  weight: number;
  /** Seconds left in the current phase. */
  timeRemaining: number;
}

export class HsinAmbientIdle {
  private readonly config: AmbientIdleConfig;
  private rng: () => number;

  private phase: AmbientPhase = "idle";
  private timer = 0;
  private phaseDuration: number;
  private weight = 0;
  private variation: AmbientVariationName | null = null;
  private lastVariation: AmbientVariationName | null = null;

  constructor(config: Partial<AmbientIdleConfig> = {}) {
    this.config = { ...DEFAULT_AMBIENT_IDLE_CONFIG, ...config };
    this.rng = makeRng(this.config.seed);
    this.phaseDuration = this.randomCooldown();
  }

  /** Return to neutral immediately and re-arm a fresh cooldown. */
  reset(): void {
    this.phase = "idle";
    this.timer = 0;
    this.weight = 0;
    this.variation = null;
    this.phaseDuration = this.randomCooldown();
  }

  /**
   * Dev affordance: begin a variation immediately, skipping the cooldown.
   * Successive triggers alternate variations (no immediate repeat). If a
   * gesture is already exiting/holding it is restarted cleanly from enter.
   */
  trigger(variation?: AmbientVariationName): void {
    this.variation = variation ?? this.pickVariation();
    this.lastVariation = this.variation;
    this.phase = "enter";
    this.timer = 0;
    this.phaseDuration = this.enterDuration();
  }

  private randRange(min: number, max: number): number {
    return min + this.rng() * (max - min);
  }

  private randomCooldown(): number {
    return this.randRange(this.config.cooldownMin, this.config.cooldownMax);
  }

  /** Enter ramp for the active variation (per-variation override, else default). */
  private enterDuration(): number {
    const t = this.variation ? VARIATION_TIMING[this.variation] : undefined;
    return t?.enter ?? this.config.enterDuration;
  }

  /** Exit ramp for the active variation (per-variation override, else default). */
  private exitDuration(): number {
    const t = this.variation ? VARIATION_TIMING[this.variation] : undefined;
    return t?.exit ?? this.config.exitDuration;
  }

  /** Hold window for the active variation (per-variation override, else default). */
  private randomHold(): number {
    const t = this.variation ? VARIATION_TIMING[this.variation] : undefined;
    const min = t?.holdMin ?? this.config.holdMin;
    const max = t?.holdMax ?? this.config.holdMax;
    return this.randRange(min, max);
  }

  private pickVariation(): AmbientVariationName {
    if (VARIATION_NAMES.length === 1) return VARIATION_NAMES[0];
    let next = VARIATION_NAMES[Math.floor(this.rng() * VARIATION_NAMES.length)];
    // Avoid repeating the same variation back-to-back.
    if (next === this.lastVariation) {
      const others = VARIATION_NAMES.filter((n) => n !== this.lastVariation);
      next = others[Math.floor(this.rng() * others.length)];
    }
    return next;
  }

  /**
   * Advance the scheduler by `dt` seconds and return the current bounded
   * offsets (degrees) to apply this frame. Returns an empty object while idle.
   */
  update(dt: number): AmbientOffsets {
    this.timer += dt;

    switch (this.phase) {
      case "idle": {
        this.weight = 0;
        if (this.timer >= this.phaseDuration) {
          this.variation = this.pickVariation();
          this.lastVariation = this.variation;
          this.phase = "enter";
          this.timer = 0;
          this.phaseDuration = this.enterDuration();
        }
        break;
      }
      case "enter": {
        this.weight = smoothstep01(this.timer / this.phaseDuration);
        if (this.timer >= this.phaseDuration) {
          this.weight = 1;
          this.phase = "hold";
          this.timer = 0;
          this.phaseDuration = this.randomHold();
        }
        break;
      }
      case "hold": {
        this.weight = 1;
        if (this.timer >= this.phaseDuration) {
          this.phase = "exit";
          this.timer = 0;
          this.phaseDuration = this.exitDuration();
        }
        break;
      }
      case "exit": {
        this.weight = 1 - smoothstep01(this.timer / this.phaseDuration);
        if (this.timer >= this.phaseDuration) {
          this.weight = 0;
          this.variation = null;
          this.phase = "idle";
          this.timer = 0;
          this.phaseDuration = this.randomCooldown();
        }
        break;
      }
    }

    if (!this.variation || this.weight <= 0) return {};

    const source = VARIATIONS[this.variation];
    const scaled: AmbientOffsets = {};
    (Object.keys(source) as AmbientBone[]).forEach((bone) => {
      const offset = source[bone];
      if (!offset) return;
      scaled[bone] = {
        x: offset.x * this.weight,
        y: offset.y * this.weight,
        z: offset.z * this.weight,
      };
    });
    return scaled;
  }

  getState(): AmbientIdleState {
    return {
      phase: this.phase,
      variation: this.variation,
      weight: this.weight,
      timeRemaining: Math.max(0, this.phaseDuration - this.timer),
    };
  }
}
