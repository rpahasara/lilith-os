/**
 * The pure presence reducer — no React, no timers, no I/O.
 *
 * It models two layers:
 *   - `steady`    the persistent signal Lilith rests in (idle, listening while
 *                 focused, thinking while a response is in flight)
 *   - `transient` a temporary reaction that overlays the steady signal for a
 *                 bounded time, then falls away ("hold / restore")
 *
 * Interruption is priority-based: a live transient is only replaced by one of
 * equal-or-greater importance. All time is passed in explicitly so the reducer
 * stays deterministic and unit-testable; the orchestrator owns the clock,
 * cooldowns, and typing-suppression.
 */

import type { EventMapping } from "./map-events";
import type { Importance, PresenceSignal } from "./types";
import { IDLE_SIGNAL, IMPORTANCE_RANK } from "./types";

export interface Transient {
  signal: PresenceSignal;
  /** Epoch ms after which the transient has expired. */
  until: number;
  importance: Importance;
}

export interface EngineState {
  steady: PresenceSignal;
  transient: Transient | null;
}

export function initialEngineState(): EngineState {
  return { steady: IDLE_SIGNAL, transient: null };
}

/** Merge a partial patch onto a base signal, stamping the driver's importance. */
export function mergeSignal(
  base: PresenceSignal,
  patch: Partial<PresenceSignal>,
  importance: Importance,
): PresenceSignal {
  return { ...base, ...patch, importance };
}

/** The signal a renderer should show right now. */
export function resolveSignal(state: EngineState, now: number): PresenceSignal {
  if (state.transient && state.transient.until > now) return state.transient.signal;
  return state.steady;
}

/**
 * Apply a (already cooldown-/suppression-filtered) mapping to the engine state.
 *
 * - `holdMs` present → a transient reaction; may also carry a `steadyPatch`
 *   that changes what Lilith restores to once the reaction fades.
 * - `holdMs` absent  → a persistent change to the steady signal.
 */
export function applyMapping(
  state: EngineState,
  mapping: EventMapping,
  now: number,
): EngineState {
  const incoming = IMPORTANCE_RANK[mapping.importance];
  const transientActive = !!state.transient && state.transient.until > now;

  if (mapping.holdMs != null) {
    // A live, higher-priority transient keeps the screen.
    if (
      transientActive &&
      IMPORTANCE_RANK[state.transient!.importance] > incoming
    ) {
      return state;
    }
    const nextSteady = mapping.steadyPatch
      ? mergeSignal(state.steady, mapping.steadyPatch, mapping.importance)
      : state.steady;
    const signal = mergeSignal(nextSteady, mapping.patch, mapping.importance);
    return {
      steady: nextSteady,
      transient: { signal, until: now + mapping.holdMs, importance: mapping.importance },
    };
  }

  // Persistent steady change.
  const steady = mergeSignal(state.steady, mapping.patch, mapping.importance);
  let transient = state.transient;
  if (
    transientActive &&
    incoming >= IMPORTANCE_RANK[state.transient!.importance]
  ) {
    // A steady change of equal-or-greater importance reveals the new steady.
    transient = null;
  }
  return { steady, transient };
}
