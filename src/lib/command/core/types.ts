/**
 * Cognitive Core V2 — Vertical Slice 1 types.
 *
 * These are the CORE-side types: the authoritative task record, the context
 * bundle, the typed plan, the capability contract, and the verifier verdict.
 * They are intentionally separate from the UI presentation contract in
 * `../types` — the core owns truth; the UI mirrors events emitted from here.
 */

import type { CommandEvidence, CommandStep } from "../types";

/* --------------------------------------------------------------- transport */

/** A single read-only backend call result. Never throws. */
export interface TransportResult {
  ok: boolean;
  status: number;
  data: unknown;
  error?: string;
}

/**
 * The seam between the core and the real backend. The default implementation
 * wraps the same-origin read-only proxy (`@/lib/api`); tests inject a fake so
 * the whole lifecycle can be exercised deterministically.
 */
export type CoreTransport = (path: string, signal?: AbortSignal) => Promise<TransportResult>;

/* -------------------------------------------------------------- capability */

export type CapabilityClass = "read-only" | "write";
export type CapabilityPermission = "read" | "approval_required";

export interface CapabilityHealth {
  healthy: boolean;
  detail?: string;
}

export interface CapabilityRetryPolicy {
  maxAttempts: number;
  /** Error classes that may be retried. */
  retryOn: Array<"network" | "timeout" | "5xx">;
}

export interface CapabilityResult<T = unknown> {
  ok: boolean;
  data: T | null;
  status: number;
  /** Classified error kind, when !ok. */
  errorKind?: "network" | "timeout" | "5xx" | "4xx" | "malformed";
  error?: string;
  /** Opaque per-execution id for evidence/correlation. */
  executionId: string;
  /** The backend path actually called (provenance). */
  source: string;
  startedAt: number;
  endedAt: number;
}

export interface Capability<T = unknown> {
  id: string;
  version: string;
  /** Human summary. */
  title: string;
  permission: CapabilityPermission;
  classification: CapabilityClass;
  timeoutMs: number;
  retry: CapabilityRetryPolicy;
  /** Declared side effects — read-only capabilities have "none". */
  sideEffects: "none" | "external_write";
  /** Probe availability without doing the full work. */
  checkHealth(transport: CoreTransport, signal?: AbortSignal): Promise<CapabilityHealth>;
  /** Execute the capability; validates the response shape into `data`. */
  execute(transport: CoreTransport, signal?: AbortSignal): Promise<CapabilityResult<T>>;
}

/* ----------------------------------------------------------------- context */

export interface ProvenanceRef {
  capabilityId: string;
  executionId: string;
  source: string;
  fetchedAt: number;
}

export interface ContextBundle {
  taskId: string;
  userRequest: string;
  normalizedIntent: string;
  /** Domain scope for this task (e.g. "system"). */
  scope: string;
  /** ISO time the bundle was assembled. */
  assembledAt: string;
  /** Retrieved backend data keyed by capability id. */
  retrieved: Record<string, unknown>;
  /** Provenance for each retrieved datum. */
  provenance: ProvenanceRef[];
  /** Freshness: newest backend-reported timestamp seen, if any. */
  backendTime?: string;
}

/* -------------------------------------------------------------------- plan */

export interface PlanStep {
  id: string;
  label: string;
  /** Capability this step invokes, or null for an internal analysis step. */
  capabilityId: string | null;
  kind: "capability" | "analysis";
}

export interface CommandPlan {
  taskId: string;
  version: number;
  intent: string;
  steps: PlanStep[];
  capabilitiesRequired: string[];
  expectedResult: string;
}

/* ---------------------------------------------------------------- verifier */

export type Verdict = "PASS" | "PARTIAL" | "FAIL";

export interface VerifierResult {
  verdict: Verdict;
  summary: string;
  evidence: CommandEvidence[];
  unresolved: string[];
  recovery?: string;
}

/* ------------------------------------------------------------- task record */

export type CoreTaskStatus =
  | "created"
  | "assembling_context"
  | "planning"
  | "capability_check"
  | "running"
  | "verifying"
  | "cancel_requested"
  | "succeeded"
  | "partial"
  | "failed"
  | "cancelled"
  | "blocked";

export interface CoreStepRecord {
  id: string;
  label: string;
  status: CommandStep["status"];
  detail?: string;
  startedAt?: number;
  endedAt?: number;
  attempts: number;
  executionId?: string;
}

/** The durable, authoritative record of a real task. */
export interface CoreTaskRecord {
  taskId: string;
  /** Persisted schema version — every stored record carries this. */
  schemaVersion: number;
  /**
   * Optimistic-concurrency revision assigned by the backend Task Store: 1 on
   * create, +1 per confirmed update. Absent only before the first persist.
   */
  revision?: number;
  source: "core";
  rawIntent: string;
  normalizedIntent: string;
  title: string;
  scope: string;
  planVersion: number;
  plan: CommandPlan | null;
  status: CoreTaskStatus;
  currentStepId: string | null;
  steps: CoreStepRecord[];
  approvalState: "not_required" | "required" | "approved" | "denied" | "expired";
  attemptCount: number;
  cancelRequested: boolean;
  createdAt: number;
  updatedAt: number;
  startedAt?: number;
  endedAt?: number;
  evidence: CommandEvidence[];
  outcome?: "succeeded" | "partial" | "failed" | "cancelled";
  resultSummary?: string;
  unresolved?: string[];
  failure?: { reason: string; recovery?: string };
  /**
   * Recovery classification for a task found in a non-terminal state after a
   * restart with no live executor — set on restore, never a fake success.
   */
  recovery?: "interrupted";
}
