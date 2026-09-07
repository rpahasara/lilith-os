/**
 * World Model read client (Slice 7 Phase A).
 *
 * Read-only access to the backend belief store via the same-origin proxy. It
 * calls the REAL endpoints (`/os/world`, `/os/world/{key}`) so it goes live the
 * moment the backend ships them (Slice 7 Phase B). Until then every call returns
 * an explicit `available: false` result with an honest reason.
 *
 * HONESTY INVARIANT: there is intentionally no demo/fallback belief data. A
 * World Model that shows invented beliefs would misrepresent what LILITH
 * actually believes. "Unavailable" is a first-class, rendered state — never
 * papered over with placeholders.
 */

import { fetchEndpoint, toDiagnostics, type EndpointResult } from "@/lib/api";
import type {
  Belief,
  WorldMeta,
  WorldReadResult,
  WorldUnavailableReason,
} from "./types";

/* ------------------------------------------------------------- wire shapes */

/** snake_case wire shape returned by GET /os/world (see backend spec). */
interface WireBelief {
  key: string;
  entity_type: string;
  entity_id: string;
  predicate: string;
  value: unknown;
  lifecycle_state: Belief["lifecycleState"];
  epistemic_state: Belief["epistemicState"];
  confidence: { value: number; tier: Belief["confidence"]["tier"]; basis: string };
  provenance: Array<{
    source_class: string;
    source_id?: string;
    source_type?: string;
    correlation_id?: string;
    observed_at?: string;
    freshness?: string;
    confidence?: number;
    origin_ref?: string;
    note?: string;
  }>;
  observed_at?: string;
  created_at: string;
  updated_at: string;
  expires_at?: string;
  revision: number;
  supersedes?: string[];
  contradicted_by?: string[];
}

interface WireWorldResponse {
  beliefs: WireBelief[];
  meta?: {
    total: number;
    by_lifecycle?: Record<string, number>;
    by_epistemic?: Record<string, number>;
    conflicted?: number;
    stale?: number;
    last_reconciled_at?: string;
  };
}

/* -------------------------------------------------------------- normalise */

function normBelief(w: WireBelief): Belief {
  return {
    key: w.key,
    entity: { entityType: w.entity_type, entityId: w.entity_id },
    predicate: w.predicate,
    value: w.value,
    lifecycleState: w.lifecycle_state,
    epistemicState: w.epistemic_state,
    confidence: {
      value: w.confidence.value,
      tier: w.confidence.tier,
      basis: w.confidence.basis,
    },
    provenance: (w.provenance ?? []).map((p) => ({
      sourceClass: p.source_class as Belief["provenance"][number]["sourceClass"],
      sourceId: p.source_id,
      sourceType: p.source_type,
      correlationId: p.correlation_id,
      observedAt: p.observed_at,
      freshness: p.freshness as Belief["provenance"][number]["freshness"],
      confidence: p.confidence,
      originRef: p.origin_ref,
      note: p.note,
    })),
    observedAt: w.observed_at,
    createdAt: w.created_at,
    updatedAt: w.updated_at,
    expiresAt: w.expires_at,
    revision: w.revision,
    supersedes: w.supersedes,
    contradictedBy: w.contradicted_by,
  };
}

function normMeta(m: WireWorldResponse["meta"]): WorldMeta | undefined {
  if (!m) return undefined;
  return {
    total: m.total,
    byLifecycle: (m.by_lifecycle ?? {}) as WorldMeta["byLifecycle"],
    byEpistemic: (m.by_epistemic ?? {}) as WorldMeta["byEpistemic"],
    conflicted: m.conflicted ?? 0,
    stale: m.stale ?? 0,
    lastReconciledAt: m.last_reconciled_at,
  };
}

/** Map a non-ok endpoint result to an honest unavailable reason + detail. */
function unavailable(
  result: EndpointResult<unknown>,
): { reason: WorldUnavailableReason; detail: string } {
  switch (result.status) {
    case 503:
      return {
        reason: "backend-not-configured",
        detail: "LILITH_API_URL is not set — no backend tunnel is configured.",
      };
    case 404:
      return {
        reason: "endpoint-not-live",
        detail:
          "The /os/world belief store is not implemented yet (Slice 7 Phase B).",
      };
    case 502:
    case 0:
      return {
        reason: "backend-unreachable",
        detail: "The backend tunnel/VM is unreachable.",
      };
    default:
      return {
        reason: "error",
        detail: result.error ?? `Unexpected status ${result.status}.`,
      };
  }
}

/* ---------------------------------------------------------------- queries */

export interface WorldQuery {
  /** filter by entity type, e.g. "career.application". */
  entityType?: string;
  entityId?: string;
  /** include SUPERSEDED beliefs (default: false). */
  includeSuperseded?: boolean;
  limit?: number;
}

function toSearch(q: WorldQuery): string {
  const p = new URLSearchParams();
  if (q.entityType) p.set("entity_type", q.entityType);
  if (q.entityId) p.set("entity_id", q.entityId);
  if (q.includeSuperseded) p.set("include_superseded", "1");
  if (q.limit != null) p.set("limit", String(q.limit));
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Read the current belief set. Never throws; never fabricates beliefs. */
export async function fetchWorld(
  query: WorldQuery = {},
  signal?: AbortSignal,
): Promise<WorldReadResult> {
  const path = `/os/world${toSearch(query)}`;
  const res = await fetchEndpoint<WireWorldResponse>(path, signal);
  const diagnostics = toDiagnostics(res.ok ? "live" : "demo", [res]);

  if (!res.ok || !res.data) {
    const u = unavailable(res);
    return { available: false, reason: u.reason, detail: u.detail, diagnostics };
  }

  return {
    available: true,
    beliefs: (res.data.beliefs ?? []).map(normBelief),
    meta: normMeta(res.data.meta),
    diagnostics,
  };
}

/** Read a single belief by canonical key. */
export async function fetchBelief(
  key: string,
  signal?: AbortSignal,
): Promise<WorldReadResult> {
  const path = `/os/world/${encodeURIComponent(key)}`;
  const res = await fetchEndpoint<WireBelief>(path, signal);
  const diagnostics = toDiagnostics(res.ok ? "live" : "demo", [res]);

  if (!res.ok || !res.data) {
    const u = unavailable(res);
    return { available: false, reason: u.reason, detail: u.detail, diagnostics };
  }
  return { available: true, beliefs: [normBelief(res.data)], diagnostics };
}
