/**
 * World Model + Working Memory — typed contracts (Slice 7).
 *
 * Three separate abstractions that MUST NOT be collapsed:
 *   World Model     — "what does LILITH currently believe is true?"  (durable, checkpointable)
 *   Working Memory  — "what is cognitively active right now?"        (ephemeral, reconstructible)
 *   Long-Term Memory— "what was recorded/learned historically?"      (see src/lib/memory)
 *
 * These are the UI/client contract for the READ side of the World Model. The
 * authoritative, durable belief store, controlled ingestion, and reconciliation
 * live on the backend (Slice 7 Phase B) — see
 * docs/architecture/slice-7-world-model-backend-spec.md. The frontend never
 * mutates beliefs and never fabricates them: when the backend is not live the
 * client reports an explicit unavailable state (see client.ts). There is NO
 * demo belief adapter — a World Model with invented beliefs would be a lie.
 *
 * Wire shapes (snake_case) are normalised to the camelCase types below by
 * client.ts, matching the existing memory-domain convention.
 */

/* --------------------------------------------------------------- phase gate */

/**
 * Slice 7 ships in two phases. Phase A (this repo) = contracts, client, proxy
 * allow-list, pure Working-Memory selection, Context Builder shim. Phase B
 * (backend/VM) = the durable belief store, ingestion, reconciliation, /os/world.
 */
export const WORLD_MODEL_PHASE = "A" as const;

/* ------------------------------------------------------------ epistemic axis */

/**
 * How LILITH came to hold a belief — the epistemic status. Orthogonal to the
 * lifecycle axis below. VERIFIED may ONLY originate from the Verification path
 * (never asserted by a connector or inferred by the model).
 */
export type EpistemicState =
  | "OBSERVED" // seen via a live connector / real observation
  | "USER_ASSERTED" // the user stated it directly
  | "INFERRED" // derived by reasoning — may be wrong, never outranks evidence
  | "VERIFIED"; // independently proven by the Verification layer

/**
 * UNKNOWN is not stored as a belief — it is the honest ABSENCE of one, or a
 * belief whose confidence is below the usable floor. Represented explicitly so
 * "no current data" never silently becomes "nothing happened".
 */
export type KnownState = EpistemicState | "UNKNOWN";

/* ------------------------------------------------------------ lifecycle axis */

/** The reconciliation lifecycle of a belief within the store. */
export type LifecycleState =
  | "ACTIVE" // current best-estimate truth
  | "SUPERSEDED" // replaced by newer/stronger evidence (retained, not deleted)
  | "CONFLICTED" // trusted evidence disagrees and rules can't safely resolve
  | "STALE"; // past its freshness/TTL — still known, but explicitly old

/* ------------------------------------------------------------ provenance */

/** The class of source that produced an observation/assertion. */
export type BeliefSourceClass =
  | "USER"
  | "LIVE_CONNECTOR"
  | "TASK_RESULT"
  | "VERIFICATION"
  | "MEMORY"
  | "INFERENCE"
  | "SYSTEM";

/**
 * Traceable provenance for a single piece of evidence behind a belief. Stores
 * refs/summaries, never hidden chain-of-thought and never duplicated private
 * payloads (prefer originRef + a short summary; hash large content).
 */
export interface BeliefProvenance {
  sourceClass: BeliefSourceClass;
  /** stable id of the producing source (connector id, task id, session, …). */
  sourceId?: string;
  /** finer-grained source type, e.g. "career.application", "gmail". */
  sourceType?: string;
  /** correlation id linking this evidence to the cognitive trace. */
  correlationId?: string;
  /** ISO time the underlying signal was observed (not when stored). */
  observedAt?: string;
  /** relative freshness bucket at read time, when the backend computes it. */
  freshness?: "fresh" | "recent" | "aging" | "stale";
  /** 0–1 confidence contributed by THIS evidence (see confidence model). */
  confidence?: number;
  /** opaque reference back to the origin record (no private payload inline). */
  originRef?: string;
  /** short human "why" — safe summary, not full content. */
  note?: string;
}

/* ------------------------------------------------------------ confidence */

/**
 * Confidence is explainable, never arbitrary LLM precision. The backend derives
 * the numeric value from explicit source/reconciliation rules and also exposes
 * a coarse typed tier for display. See the backend spec's confidence model.
 */
export type ConfidenceTier = "high" | "medium" | "low" | "unknown";

export interface Confidence {
  /** bounded 0–1, derived from explicit rules (not a free-form model number). */
  value: number;
  tier: ConfidenceTier;
  /** short machine-readable reason code, e.g. "verified", "single_observation". */
  basis: string;
}

/* ------------------------------------------------------------ the Belief */

/** Reference to the entity a belief concerns. */
export interface BeliefEntityRef {
  entityType: string; // e.g. "career.application"
  entityId: string; // e.g. "17"
}

/**
 * A single reconciled belief. Canonical identity is
 * `<entityType>:<entityId>:<predicate>` (see beliefKey) — semantically
 * identical facts reconcile into one belief with revisions, never duplicates.
 */
export interface Belief {
  /** canonical key: `${entityType}:${entityId}:${predicate}`. */
  key: string;
  entity: BeliefEntityRef;
  predicate: string; // e.g. "status"
  value: unknown; // the believed value

  lifecycleState: LifecycleState;
  epistemicState: EpistemicState;
  confidence: Confidence;

  /** ordered evidence chain — newest first. */
  provenance: BeliefProvenance[];

  observedAt?: string; // ISO — when the underlying fact was observed
  createdAt: string; // ISO — first time this belief key appeared
  updatedAt: string; // ISO — last reconciliation
  expiresAt?: string; // ISO — freshness horizon, when applicable

  /** monotonic revision, bumped on every reconciliation that changes state. */
  revision: number;

  /** keys this belief superseded, and keys/ids it currently conflicts with. */
  supersedes?: string[];
  contradictedBy?: string[];
}

/* ------------------------------------------------ meta-cognition trace (read) */

/**
 * Read projection of a belief-mutation trace event. Observable decision
 * metadata — NEVER hidden LLM chain-of-thought. Emitted by the backend on every
 * belief mutation; surfaced read-only here for the inspector.
 */
export interface BeliefTraceEvent {
  id: string;
  correlationId: string;
  beliefKey: string;
  at: string; // ISO
  prevLifecycle?: LifecycleState;
  newLifecycle: LifecycleState;
  prevEpistemic?: EpistemicState;
  newEpistemic: EpistemicState;
  confidence: Confidence;
  provenance: BeliefProvenance;
  /** deterministic reconciliation reason code, e.g. "verified_outranks_inferred". */
  reconciliationReason: string;
  supersededKeys?: string[];
  conflictKeys?: string[];
}

/* ------------------------------------------------------------ read results */

/** Reason the World Model read surface is unavailable — honest, never faked. */
export type WorldUnavailableReason =
  | "backend-not-configured" // LILITH_API_URL unset (503)
  | "backend-unreachable" // tunnel/VM down (502/0)
  | "endpoint-not-live" // /os/world not shipped yet — Slice 7 Phase B (404)
  | "error"; // other non-ok

/**
 * Result of a World Model read. When `available` is false there are NO beliefs
 * — the caller must render an explicit unavailable state, never placeholder
 * beliefs. This is the core honesty invariant of Phase A.
 */
export type WorldReadResult =
  | {
      available: true;
      beliefs: Belief[];
      /** server-reported store metadata, when present. */
      meta?: WorldMeta;
      diagnostics?: import("@/lib/api").Diagnostics;
    }
  | {
      available: false;
      reason: WorldUnavailableReason;
      /** human-facing explanation for the inspector's empty state. */
      detail: string;
      diagnostics?: import("@/lib/api").Diagnostics;
    };

export interface WorldMeta {
  total: number;
  byLifecycle: Partial<Record<LifecycleState, number>>;
  byEpistemic: Partial<Record<EpistemicState, number>>;
  conflicted: number;
  stale: number;
  /** ISO time of the most recent reconciliation across the store. */
  lastReconciledAt?: string;
}

/* ------------------------------------------------- working memory / context */

/**
 * The bounded, ephemeral working set for one cognitive episode. Reconstructible
 * from durable beliefs — never a durable truth store of its own. Only minimal
 * reconstruction metadata (session/task/focus) is ever persisted.
 */
export interface WorkingSet {
  sessionId: string;
  taskId?: string;

  /** what attention is currently centred on. */
  focus?: WorkingFocus;
  /** keys of beliefs selected into the active set (bounded by capacity). */
  activeBeliefIds: string[];
  /** entities referenced by the active beliefs. */
  activeEntities: BeliefEntityRef[];
  currentIntent?: string;
  currentGoalRef?: string;

  /** short-lived recent observations (keys or refs), newest first. */
  recentObservations: string[];

  /** hard upper bound on activeBeliefIds — bounded selection is enforced. */
  capacity: number;
  createdAt: string; // ISO
  updatedAt: string; // ISO
}

export interface WorkingFocus {
  /** entities the episode is about. */
  entities: BeliefEntityRef[];
  /** predicates of interest, when narrowed (e.g. ["status"]). */
  predicates?: string[];
  /** free-text label for display/trace only. */
  label?: string;
}

/**
 * Structured context handed to reasoning/planning. Carries the working set plus
 * the honest availability of each source, so downstream never mistakes an
 * unavailable backend for "no facts exist".
 */
export interface CognitiveContext {
  sessionId: string;
  taskId?: string;
  focus?: WorkingFocus;
  workingSet: WorkingSet;
  /** the beliefs actually selected into the working set (resolved). */
  activeBeliefs: Belief[];
  currentIntent?: string;
  /** availability of each contributing source — never silently empty. */
  sources: {
    worldModel: "available" | WorldUnavailableReason;
    longTermMemory: "available" | "endpoint-not-live";
  };
  /** correlation id threading this context through the cognitive trace. */
  correlationId: string;
  builtAt: string; // ISO
}

/* -------------------------------------------------------------------- keys */

/** Canonical belief identity. Keep in lockstep with the backend spec. */
export function beliefKey(
  entityType: string,
  entityId: string,
  predicate: string,
): string {
  return `${entityType}:${entityId}:${predicate}`;
}
