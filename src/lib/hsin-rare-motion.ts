/**
 * Hsin Rare Larger Motion — Phase 1 POC
 *
 * A small, isolated scheduler for ONE rare, larger-scale motion: a controlled
 * look-aside body turn (~35-36deg world head-facing turn), NOT a 360 spin. Like
 * the ambient and speaking modules it is intentionally pure — it holds no
 * three.js references and only emits bounded per-bone Euler offsets (degrees)
 * for the six torso/neck/head bones. The renderer post-multiplies these onto the
 * normalized bones via the existing `addMicroMotion` seam, so the motion is
 * purely additive and always returns to exactly the canonical front-facing
 * neutral. Arms/hands/fingers ride the torso hierarchy rigidly (never authored
 * here); hips carry the legs rigidly with only a tiny yaw so the stance stays
 * visually planted (no leg/foot animation).
 *
 * Lifecycle: idle -> enter -> hold -> exit -> idle. Enter/exit are smoothstep;
 * hold is full-weight for a randomized-but-bounded window. The exit can be
 * shortened via beginExit() when Speaking Motion takes priority mid-turn, so
 * Hsin returns promptly (but smoothly) to neutral as speech takes over.
 *
 * Scope (Phase 1): one variation (lookAsideTurn), left/right, torso/neck/head
 * only, no arms/hands/legs, no springs, no IK, no automatic firing.
 */

export type RareMotionBone =
  | "hips"
  | "spine"
  | "chest"
  | "upperChest"
  | "neck"
  | "head";

export type RareBoneOffset = { x: number; y: number; z: number };

export type RareMotionOffsets = Partial<Record<RareMotionBone, RareBoneOffset>>;

export type RareMotionPhase = "idle" | "enter" | "hold" | "exit";

export type RareVariationName = "lookAsideTurn";

export type RareTurnSide = "left" | "right";

export interface RareMotionConfig {
  /** Smoothstep ramp-in duration (seconds). */
  enterDuration: number;
  /** Full-weight hold window (seconds, randomized). */
  holdMin: number;
  holdMax: number;
  /** Smoothstep ramp-out duration for a normally-completed turn (seconds). */
  exitDuration: number;
  /** Faster ramp-out used when Speaking Motion interrupts an active turn (s). */
  interruptExitDuration: number;
  /** Deterministic RNG seed (reproducible session for debugging). */
  seed: number;
}

export const DEFAULT_RARE_MOTION_CONFIG: RareMotionConfig = {
  enterDuration: 2.4,
  holdMin: 2,
  holdMax: 4,
  exitDuration: 2.6,
  // Speech-priority exit: prompt but not a snap (0.8-1.2s range -> 1.0s).
  interruptExitDuration: 1.0,
  seed: 9001,
};

/**
 * Full-weight (weight = 1) authored offsets, in degrees (local XYZ =
 * pitch/yaw/roll), for a RIGHT-side look-aside turn. The yaw is distributed up
 * the chain so world yaw accumulates (head furthest, hips least) — local
 * gradient head > neck > upperChest > chest > spine > hips — summing to a
 * ~35.7deg world head turn. Head/neck lead the turn clearly while the mid-torso
 * (spine/chest/upperChest) stays calmer, so the upper body does not rotate as
 * one block. Hips carry only a tiny yaw + roll so the stance stays planted.
 * Secondary axes (chest/upperChest roll, head pitch/tilt, hip weight-
 * compensation roll) stay <= ~1deg for an organic, elegant shape.
 *
 * A LEFT turn reuses this exact structure with yaw and roll mirrored (pitch,
 * being symmetric, is unchanged) — see sidedOffsets().
 */
const LOOK_ASIDE_RIGHT: RareMotionOffsets = {
  hips: { x: 0, y: -1.2, z: 0.4 },
  spine: { x: 0, y: -3.5, z: 0 },
  chest: { x: 0, y: -5.0, z: 0.4 },
  upperChest: { x: 0, y: -6.5, z: 0.7 },
  neck: { x: 0, y: -9.0, z: 0 },
  head: { x: 0.5, y: -10.5, z: -0.8 },
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

export interface RareMotionState {
  phase: RareMotionPhase;
  variation: RareVariationName | null;
  side: RareTurnSide;
  weight: number;
}

export class HsinRareMotion {
  private readonly config: RareMotionConfig;
  private rng: () => number;

  private phase: RareMotionPhase = "idle";
  private timer = 0;
  private phaseDuration = 0;
  private weight = 0;
  private side: RareTurnSide = "right";
  /** Weight at the moment an exit began, so the ramp-out is smooth from any
   *  starting weight (e.g. an interrupt mid-enter). */
  private exitStartWeight = 1;

  constructor(config: Partial<RareMotionConfig> = {}) {
    this.config = { ...DEFAULT_RARE_MOTION_CONFIG, ...config };
    this.rng = makeRng(this.config.seed);
  }

  /** Return to neutral immediately and disarm (used when the layer is disabled). */
  reset(): void {
    this.phase = "idle";
    this.timer = 0;
    this.weight = 0;
  }

  /** Begin a look-aside turn to the given side (default right). Ignored if a
   *  turn is already in flight (single motion at a time). */
  trigger(side: RareTurnSide = "right"): void {
    if (this.phase !== "idle") return;
    this.side = side;
    this.phase = "enter";
    this.timer = 0;
    this.phaseDuration = this.config.enterDuration;
  }

  /**
   * Priority interrupt (Speaking Motion took the pose): ramp out promptly but
   * smoothly from the current weight. No-op when idle; when already exiting, it
   * only speeds the ramp up, never slows it.
   */
  beginExit(): void {
    if (this.phase === "idle") return;
    const remaining = this.phaseDuration - this.timer;
    if (this.phase === "exit" && remaining <= this.config.interruptExitDuration) {
      return;
    }
    this.exitStartWeight = this.weight;
    this.phase = "exit";
    this.timer = 0;
    this.phaseDuration = this.config.interruptExitDuration;
  }

  private randRange(min: number, max: number): number {
    return min + this.rng() * (max - min);
  }

  /** Resolve the sided full-weight targets (mirror yaw + roll for left). */
  private sidedOffsets(): RareMotionOffsets {
    if (this.side === "right") return LOOK_ASIDE_RIGHT;
    const mirrored: RareMotionOffsets = {};
    (Object.keys(LOOK_ASIDE_RIGHT) as RareMotionBone[]).forEach((bone) => {
      const o = LOOK_ASIDE_RIGHT[bone];
      if (!o) return;
      mirrored[bone] = { x: o.x, y: -o.y, z: -o.z };
    });
    return mirrored;
  }

  /**
   * Advance the scheduler by `dt` seconds and return the bounded offsets
   * (degrees) to apply this frame. Empty while idle.
   */
  update(dt: number): RareMotionOffsets {
    switch (this.phase) {
      case "idle": {
        this.weight = 0;
        return {};
      }
      case "enter": {
        this.timer += dt;
        this.weight = smoothstep01(this.timer / this.phaseDuration);
        if (this.timer >= this.phaseDuration) {
          this.weight = 1;
          this.phase = "hold";
          this.timer = 0;
          this.phaseDuration = this.randRange(
            this.config.holdMin,
            this.config.holdMax,
          );
        }
        break;
      }
      case "hold": {
        this.timer += dt;
        this.weight = 1;
        if (this.timer >= this.phaseDuration) {
          this.exitStartWeight = 1;
          this.phase = "exit";
          this.timer = 0;
          this.phaseDuration = this.config.exitDuration;
        }
        break;
      }
      case "exit": {
        this.timer += dt;
        this.weight =
          this.exitStartWeight * (1 - smoothstep01(this.timer / this.phaseDuration));
        if (this.timer >= this.phaseDuration) {
          this.weight = 0;
          this.phase = "idle";
          this.timer = 0;
          return {};
        }
        break;
      }
    }

    if (this.weight <= 0) return {};
    const source = this.sidedOffsets();
    const scaled: RareMotionOffsets = {};
    (Object.keys(source) as RareMotionBone[]).forEach((bone) => {
      const o = source[bone];
      if (!o) return;
      scaled[bone] = {
        x: o.x * this.weight,
        y: o.y * this.weight,
        z: o.z * this.weight,
      };
    });
    return scaled;
  }

  getState(): RareMotionState {
    return {
      phase: this.phase,
      variation: this.phase === "idle" ? null : "lookAsideTurn",
      side: this.side,
      weight: this.weight,
    };
  }
}
