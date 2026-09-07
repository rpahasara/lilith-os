/**
 * Working Memory — bounded, deterministic selection & reconstruction (Slice 7).
 *
 * This is REAL logic, not a placeholder: it operates purely over beliefs handed
 * to it, so it needs no backend and no durable state of its own. That is exactly
 * why Working Memory is defined as *reconstructible* — give it the same durable
 * beliefs + focus + capacity and it rebuilds the identical working set.
 *
 * Selection is deterministic and explainable (no LLM, no randomness): score by
 * focus relevance, epistemic authority, confidence, recency and lifecycle, then
 * take the top-`capacity` by (score desc, key asc) for a stable ordering.
 */

import type {
  Belief,
  BeliefEntityRef,
  LifecycleState,
  EpistemicState,
  WorkingFocus,
  WorkingSet,
} from "./types";

/** Default hard cap on how many beliefs may be cognitively active at once. */
export const DEFAULT_WORKING_CAPACITY = 12;

/** Confidence below this floor never enters the working set (treated UNKNOWN). */
export const ACTIVE_CONFIDENCE_FLOOR = 0.15;

/** Epistemic authority weight — VERIFIED outranks the rest (mirrors backend). */
const EPISTEMIC_WEIGHT: Record<EpistemicState, number> = {
  VERIFIED: 1.0,
  OBSERVED: 0.7,
  USER_ASSERTED: 0.7,
  INFERRED: 0.4,
};

/** Lifecycle weight — SUPERSEDED is excluded entirely; STALE is down-weighted. */
const LIFECYCLE_WEIGHT: Record<LifecycleState, number> = {
  ACTIVE: 1.0,
  CONFLICTED: 0.6, // kept, but flagged — the episode should see the conflict
  STALE: 0.4,
  SUPERSEDED: 0, // never active
};

function entityMatches(a: BeliefEntityRef, b: BeliefEntityRef): boolean {
  return a.entityType === b.entityType && a.entityId === b.entityId;
}

function focusRelevance(belief: Belief, focus?: WorkingFocus): number {
  if (!focus) return 0;
  let score = 0;
  if (focus.entities?.some((e) => entityMatches(e, belief.entity))) score += 1;
  if (focus.predicates?.includes(belief.predicate)) score += 0.5;
  return score;
}

/** Recency in [0,1] with a ~14-day half-life; undefined timestamps score 0. */
function recencyScore(iso?: string, now = Date.now()): number {
  if (!iso) return 0;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  const ageDays = Math.max(0, (now - t) / 86_400_000);
  return Math.pow(0.5, ageDays / 14);
}

export interface ScoredBelief {
  belief: Belief;
  score: number;
}

/**
 * Deterministically score a belief for working-memory admission. Higher is more
 * salient. Excluded beliefs (SUPERSEDED, or below the confidence floor) score 0.
 */
export function scoreBelief(
  belief: Belief,
  focus?: WorkingFocus,
  now = Date.now(),
): number {
  if (belief.lifecycleState === "SUPERSEDED") return 0;
  if (belief.confidence.value < ACTIVE_CONFIDENCE_FLOOR) return 0;

  const relevance = focusRelevance(belief, focus); // 0…1.5
  const authority = EPISTEMIC_WEIGHT[belief.epistemicState] ?? 0.4;
  const lifecycle = LIFECYCLE_WEIGHT[belief.lifecycleState] ?? 0.4;
  const recency = recencyScore(belief.updatedAt ?? belief.observedAt, now);
  const confidence = belief.confidence.value;

  // Weighted sum — relevance dominates so a focused episode stays on-topic,
  // then authority/confidence, with recency as a tie-breaker signal.
  return (
    3.0 * relevance +
    1.5 * authority +
    1.2 * confidence +
    0.8 * recency +
    0.5 * lifecycle
  );
}

/**
 * Select the bounded active subset of beliefs for a working set. Deterministic:
 * sort by (score desc, key asc), drop zero-scored, take at most `capacity`.
 */
export function selectActiveBeliefs(
  beliefs: Belief[],
  focus?: WorkingFocus,
  capacity: number = DEFAULT_WORKING_CAPACITY,
  now = Date.now(),
): ScoredBelief[] {
  const cap = Math.max(0, Math.floor(capacity));
  return beliefs
    .map((belief) => ({ belief, score: scoreBelief(belief, focus, now) }))
    .filter((s) => s.score > 0)
    .sort((a, b) =>
      b.score !== a.score
        ? b.score - a.score
        : a.belief.key.localeCompare(b.belief.key),
    )
    .slice(0, cap);
}

export interface BuildWorkingSetArgs {
  sessionId: string;
  taskId?: string;
  beliefs: Belief[];
  focus?: WorkingFocus;
  currentIntent?: string;
  currentGoalRef?: string;
  recentObservations?: string[];
  capacity?: number;
  now?: number;
}

/**
 * Build (or reconstruct) a bounded WorkingSet from durable beliefs. Pure and
 * idempotent for a fixed `now`: identical inputs yield an identical working set,
 * which is what makes Working Memory reconstructible after a reload rather than
 * a second source of durable truth.
 */
export function buildWorkingSet(args: BuildWorkingSetArgs): WorkingSet {
  const {
    sessionId,
    taskId,
    beliefs,
    focus,
    currentIntent,
    currentGoalRef,
    recentObservations = [],
    capacity = DEFAULT_WORKING_CAPACITY,
    now = Date.now(),
  } = args;

  const selected = selectActiveBeliefs(beliefs, focus, capacity, now);
  const activeBeliefIds = selected.map((s) => s.belief.key);

  // Distinct entities referenced by the active set, order-stable.
  const seen = new Set<string>();
  const activeEntities: BeliefEntityRef[] = [];
  for (const { belief } of selected) {
    const id = `${belief.entity.entityType}:${belief.entity.entityId}`;
    if (!seen.has(id)) {
      seen.add(id);
      activeEntities.push(belief.entity);
    }
  }

  const iso = new Date(now).toISOString();
  return {
    sessionId,
    taskId,
    focus,
    activeBeliefIds,
    activeEntities,
    currentIntent,
    currentGoalRef,
    recentObservations: recentObservations.slice(0, capacity),
    capacity: Math.max(0, Math.floor(capacity)),
    createdAt: iso,
    updatedAt: iso,
  };
}

/** True iff the working set honours its capacity bound (an invariant check). */
export function respectsCapacity(ws: WorkingSet): boolean {
  return ws.activeBeliefIds.length <= ws.capacity;
}
