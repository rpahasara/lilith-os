/**
 * Hsin Motion Orchestrator — Phase 1
 *
 * A tiny, pure controller that decides WHEN the existing motion systems are
 * allowed to run. It adds no animation and owns no offsets — it only grants or
 * denies permission and emits rare-motion triggers with cooldown/grace timing.
 * It holds no three.js references and never mutates the individual schedulers.
 *
 * Priority: Speaking > Rare > Ambient > Natural Idle > Canonical.
 *
 * Per frame the renderer calls `update(ctx)` with the observed facts (speaking,
 * rare active, ambient active, inspect active) — read from the existing
 * schedulers' getState() — and applies the returned decision:
 *   - ambientAllowed: whether the renderer may call ambientIdle.update() (whose
 *     OWN 25-45s cooldown remains the sole ambient cadence — no second cooldown).
 *   - rareTrigger/rareSide: fire the existing rare lookAsideTurn this frame.
 * Speaking is observed, not driven; the renderer's existing speech-priority
 * logic (rare fast-exit + ambient reset) is unchanged.
 *
 * Safety invariants (per approved plan):
 *  1. Same-frame rare ownership: on a rareTrigger frame, ambientAllowed is false
 *     and mode is "rare" in the SAME decision (never wait for next frame).
 *  2. Enable/disable reset: start() arms a fresh session; reset() clears all
 *     state so the committed manual behavior returns exactly.
 *  3. Rare cooldown is randomized exactly ONCE per completed rare cycle (on the
 *     rare falling edge while not speaking) — not at trigger time.
 */

export type OrchestratorMode =
  | "idle"
  | "ambient"
  | "rare"
  | "speaking"
  | "cooldown";

export type OrchestratorTurnSide = "left" | "right";

export interface OrchestratorContext {
  /** Seconds since last frame. */
  dt: number;
  /** Speaking layer active (speech owns the pose). */
  speaking: boolean;
  /** Rare motion currently non-idle. */
  rareActive: boolean;
  /** Ambient variation currently non-idle. */
  ambientActive: boolean;
  /** Expression/viseme inspect (or other calibration) active — lock out auto. */
  inspectActive: boolean;
}

export interface OrchestratorDecision {
  mode: OrchestratorMode;
  /** Whether the renderer may run the ambient scheduler this frame. */
  ambientAllowed: boolean;
  /** True for exactly one frame when a rare turn should be triggered. */
  rareTrigger: boolean;
  /** Side to pass to the rare scheduler on a trigger frame. */
  rareSide: OrchestratorTurnSide;
  /** Seconds of eligible calm remaining before rare becomes eligible. */
  nextRareIn: number;
  /** Seconds of grace lockout remaining. */
  graceRemaining: number;
  /** Human-readable last mode transition, e.g. "idle → ambient" (dev readout). */
  lastTransition: string;
}

/** Lightweight snapshot for the dev readout (no side effects). */
export interface OrchestratorReadout {
  mode: OrchestratorMode;
  nextRareIn: number;
  graceRemaining: number;
  ambientAllowed: boolean;
  lastTransition: string;
}

export interface OrchestratorConfig {
  /** Continuous idle before ambient is first permitted (seconds). */
  initialIdleGrace: number;
  /** Automatic rare cadence, counted only during eligible calm (seconds). */
  rareCooldownMin: number;
  rareCooldownMax: number;
  /** Grace lockout after an ambient variation completes (seconds). */
  graceAmbientMin: number;
  graceAmbientMax: number;
  /** Grace lockout after speech ends (seconds). */
  graceSpeechMin: number;
  graceSpeechMax: number;
  /** Grace lockout after a rare turn completes (seconds). */
  graceRareMin: number;
  graceRareMax: number;
  /** Deterministic RNG seed. */
  seed: number;
}

export const DEFAULT_ORCHESTRATOR_CONFIG: OrchestratorConfig = {
  initialIdleGrace: 1.5,
  rareCooldownMin: 90,
  rareCooldownMax: 180,
  graceAmbientMin: 2,
  graceAmbientMax: 4,
  graceSpeechMin: 2,
  graceSpeechMax: 4,
  graceRareMin: 5,
  graceRareMax: 8,
  seed: 24601,
};

/**
 * Dev-only FAST TEST cadence. Overrides ONLY the orchestrator's waiting/cadence
 * values (grace + rare cooldown + initial idle grace) so the exact same logic
 * can be validated without long waits. It changes no animation timing and no
 * motion data — the ambient scheduler's own accelerated cooldown is supplied
 * separately by the renderer (a second HsinAmbientIdle instance), not here.
 */
export const FAST_TEST_ORCHESTRATOR_CONFIG: OrchestratorConfig = {
  ...DEFAULT_ORCHESTRATOR_CONFIG,
  initialIdleGrace: 0.9,
  rareCooldownMin: 10,
  rareCooldownMax: 15,
  graceAmbientMin: 1.5,
  graceAmbientMax: 2,
  graceSpeechMin: 1.5,
  graceSpeechMax: 2,
  graceRareMin: 2,
  graceRareMax: 3,
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

export class HsinMotionOrchestrator {
  private readonly config: OrchestratorConfig;
  private readonly fastConfig: OrchestratorConfig;
  private fast = false;
  /**
   * Whether automatic rare triggering is permitted. Default false: the rare
   * cooldown is still tracked (readout stays meaningful) but the orchestrator
   * never emits an automatic rareTrigger. Manual/dev rare triggering is
   * unaffected (it goes through the renderer, not this flag).
   */
  private allowRareAuto = false;
  private rng: () => number;

  private mode: OrchestratorMode = "idle";
  private graceTimer = 0;
  private rareCooldown = 0;
  private idleAccum = 0;
  private rarePending = false;
  private lastRareSide: OrchestratorTurnSide | null = null;

  private prevSpeaking = false;
  private prevRareActive = false;
  private prevAmbientActive = false;

  private prevMode: OrchestratorMode = "idle";
  private lastTransition = "";

  constructor(config: Partial<OrchestratorConfig> = {}) {
    this.config = { ...DEFAULT_ORCHESTRATOR_CONFIG, ...config };
    this.fastConfig = { ...FAST_TEST_ORCHESTRATOR_CONFIG, ...config };
    this.rng = makeRng(this.config.seed);
  }

  /** The active cadence config (fast-test overrides only timing/cadence). */
  private cfg(): OrchestratorConfig {
    return this.fast ? this.fastConfig : this.config;
  }

  /**
   * Dev-only: toggle FAST TEST cadence. On a real change it re-arms the rare
   * cooldown to the active range and clears grace/idle accumulation so the new
   * cadence takes effect promptly and predictably (a deliberate testing action,
   * not a completion path — so it does not double-randomize a rare cycle).
   */
  setFast(on: boolean): void {
    if (on === this.fast) return;
    this.fast = on;
    this.rareCooldown = this.randomRareCooldown();
    this.graceTimer = 0;
    this.idleAccum = 0;
    this.rarePending = false;
  }

  /**
   * Enable/disable automatic rare triggering. When switched on with the cooldown
   * already elapsed, re-arm it so rare does not fire instantly on the toggle.
   */
  setAllowRareAuto(on: boolean): void {
    if (on === this.allowRareAuto) return;
    this.allowRareAuto = on;
    if (on && this.rareCooldown <= 0) this.rareCooldown = this.randomRareCooldown();
  }

  private randRange(min: number, max: number): number {
    return min + this.rng() * (max - min);
  }

  private randomRareCooldown(): number {
    return this.randRange(this.cfg().rareCooldownMin, this.cfg().rareCooldownMax);
  }

  /**
   * Arm a fresh orchestration session (called when the dev toggle turns ON).
   * Fresh rare cooldown 90-180s guarantees no immediate rare after enabling.
   */
  start(): void {
    this.mode = "idle";
    this.graceTimer = 0;
    this.rareCooldown = this.randomRareCooldown();
    this.idleAccum = 0;
    this.rarePending = false;
    this.lastRareSide = null;
    this.prevSpeaking = false;
    this.prevRareActive = false;
    this.prevAmbientActive = false;
    this.prevMode = "idle";
    this.lastTransition = "";
  }

  /**
   * Clear all state (called when the dev toggle turns OFF). Leaves no stale
   * grace/cooldown/edge state so committed manual behavior returns exactly.
   */
  reset(): void {
    this.mode = "idle";
    this.graceTimer = 0;
    this.rareCooldown = 0;
    this.idleAccum = 0;
    this.rarePending = false;
    this.prevSpeaking = false;
    this.prevRareActive = false;
    this.prevAmbientActive = false;
    this.prevMode = "idle";
    this.lastTransition = "";
  }

  /** Pick a random side, avoiding an immediate repeat of the previous side. */
  private pickRareSide(): OrchestratorTurnSide {
    let side: OrchestratorTurnSide = this.rng() < 0.5 ? "left" : "right";
    if (side === this.lastRareSide) side = side === "left" ? "right" : "left";
    return side;
  }

  update(ctx: OrchestratorContext): OrchestratorDecision {
    const { dt, speaking, rareActive, ambientActive, inspectActive } = ctx;

    // --- Completion edges (falling) -------------------------------------
    const speechEnded = this.prevSpeaking && !speaking;
    const rareEnded = this.prevRareActive && !rareActive;
    const ambientEnded = this.prevAmbientActive && !ambientActive;

    // Rare finished: clear ownership always; randomize its next cooldown ONCE
    // here, but only for a natural completion (not a speech interrupt — speech
    // end restarts the cooldown instead, so it's never randomized twice).
    if (rareEnded) {
      this.rarePending = false;
      if (!speaking) {
        this.rareCooldown = this.randomRareCooldown();
        this.graceTimer = Math.max(
          this.graceTimer,
          this.randRange(this.cfg().graceRareMin, this.cfg().graceRareMax),
        );
      }
    }
    if (speechEnded) {
      this.graceTimer = Math.max(
        this.graceTimer,
        this.randRange(this.cfg().graceSpeechMin, this.cfg().graceSpeechMax),
      );
      // Fresh rare cooldown after speech (single randomize for this event).
      this.rareCooldown = this.randomRareCooldown();
      this.rarePending = false;
    }
    if (ambientEnded) {
      this.graceTimer = Math.max(
        this.graceTimer,
        this.randRange(this.cfg().graceAmbientMin, this.cfg().graceAmbientMax),
      );
    }

    // --- Mode decision (priority order) ---------------------------------
    let ambientAllowed = false;
    let rareTrigger = false;
    let rareSide: OrchestratorTurnSide = this.lastRareSide ?? "right";

    if (speaking) {
      // Speaking always wins; cancel any pending auto-rare. Timers hold.
      this.mode = "speaking";
      this.idleAccum = 0;
      this.rarePending = false;
    } else if (inspectActive) {
      // Inspect/calibration locks automatic orchestration out entirely.
      this.mode = "idle";
      this.idleAccum = 0;
    } else {
      // Not speaking, not inspecting: grace counts down here.
      if (this.graceTimer > 0) this.graceTimer = Math.max(0, this.graceTimer - dt);

      if (rareActive || this.rarePending) {
        // Rare owns the pose (active, or triggered and awaiting activation).
        this.mode = "rare";
        this.idleAccum = 0;
      } else if (ambientActive) {
        // Let an in-flight ambient variation finish; cooldown paused.
        this.mode = "ambient";
        this.idleAccum = 0;
        ambientAllowed = true;
      } else if (this.graceTimer > 0) {
        // Breathing room after a motion: both ambient and rare blocked.
        this.mode = "cooldown";
        this.idleAccum = 0;
      } else {
        // Truly idle and eligible: ambient permitted after a short grace; the
        // rare cooldown counts down ONLY here (eligible calm time).
        this.mode = "idle";
        this.idleAccum += dt;
        ambientAllowed = this.idleAccum >= this.cfg().initialIdleGrace;
        this.rareCooldown = Math.max(0, this.rareCooldown - dt);
        if (this.rareCooldown <= 0 && this.allowRareAuto) {
          // Fire one rare trigger and take same-frame ownership: block ambient
          // now, mode is rare now. Cooldown is NOT randomized here — that
          // happens once on the rare completion edge. Gated by allowRareAuto:
          // while off, the cooldown simply rests at 0 and never fires.
          rareTrigger = true;
          rareSide = this.pickRareSide();
          this.lastRareSide = rareSide;
          this.rarePending = true;
          this.mode = "rare";
          ambientAllowed = false;
        }
      }
    }

    // --- Record edges for next frame ------------------------------------
    this.prevSpeaking = speaking;
    this.prevRareActive = rareActive;
    this.prevAmbientActive = ambientActive;

    if (this.mode !== this.prevMode) {
      this.lastTransition = `${this.prevMode} → ${this.mode}`;
      this.prevMode = this.mode;
    }

    return {
      mode: this.mode,
      ambientAllowed,
      rareTrigger,
      rareSide,
      nextRareIn: this.rareCooldown,
      graceRemaining: this.graceTimer,
      lastTransition: this.lastTransition,
    };
  }

  getState(): OrchestratorReadout {
    return {
      mode: this.mode,
      nextRareIn: this.rareCooldown,
      graceRemaining: this.graceTimer,
      ambientAllowed: false,
      lastTransition: this.lastTransition,
    };
  }
}
