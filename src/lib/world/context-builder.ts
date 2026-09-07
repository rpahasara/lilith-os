/**
 * Context Builder (Slice 7 Phase A).
 *
 * Assembles a typed CognitiveContext for reasoning/planning from the sources
 * available *now*: the current input, an optional active task/goal, World Model
 * beliefs, and recent observations. It runs the real bounded Working-Memory
 * selection over whatever beliefs it is given.
 *
 * Honesty: the builder records the availability of each source. When the World
 * Model backend is not live it does NOT invent beliefs — it produces a valid
 * (empty-active) context tagged with the unavailable reason, so downstream can
 * distinguish "LILITH knows nothing relevant" from "the belief store is down".
 *
 * This is a shim in one sense only: the belief *input* is thin until Phase B
 * ships /os/world. The assembly, selection and honesty logic are real.
 */

import type {
  Belief,
  CognitiveContext,
  WorkingFocus,
  WorldReadResult,
} from "./types";
import { buildWorkingSet, DEFAULT_WORKING_CAPACITY } from "./working-memory";

export interface BuildContextArgs {
  sessionId: string;
  correlationId: string;
  taskId?: string;
  focus?: WorkingFocus;
  currentIntent?: string;
  currentGoalRef?: string;
  /** result of a World Model read (available or not — both handled honestly). */
  world: WorldReadResult;
  /** recent observation keys/refs, newest first (optional). */
  recentObservations?: string[];
  capacity?: number;
  now?: number;
}

/**
 * Build a CognitiveContext. Never throws; never fabricates beliefs. If `world`
 * is unavailable the returned context has an empty active set and its
 * `sources.worldModel` carries the honest reason.
 */
export function buildCognitiveContext(args: BuildContextArgs): CognitiveContext {
  const {
    sessionId,
    correlationId,
    taskId,
    focus,
    currentIntent,
    currentGoalRef,
    world,
    recentObservations = [],
    capacity = DEFAULT_WORKING_CAPACITY,
    now = Date.now(),
  } = args;

  const beliefs: Belief[] = world.available ? world.beliefs : [];

  const workingSet = buildWorkingSet({
    sessionId,
    taskId,
    beliefs,
    focus,
    currentIntent,
    currentGoalRef,
    recentObservations,
    capacity,
    now,
  });

  // Resolve the selected keys back to full beliefs, preserving selection order.
  const byKey = new Map(beliefs.map((b) => [b.key, b]));
  const activeBeliefs = workingSet.activeBeliefIds
    .map((k) => byKey.get(k))
    .filter((b): b is Belief => b != null);

  return {
    sessionId,
    taskId,
    focus,
    workingSet,
    activeBeliefs,
    currentIntent,
    sources: {
      worldModel: world.available ? "available" : world.reason,
      // Long-Term Memory read endpoints are likewise not live yet.
      longTermMemory: "endpoint-not-live",
    },
    correlationId,
    builtAt: new Date(now).toISOString(),
  };
}
