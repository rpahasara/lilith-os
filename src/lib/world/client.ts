/**
 * World Model read client.
 *
 * Read-only access to the backend belief store (`/os/world`, `/os/world/{key}`)
 * through the same-origin proxy. Nothing here can change a belief.
 *
 * HONESTY INVARIANT: there is intentionally no demo/fallback belief data. A
 * World Model that shows invented beliefs would misrepresent what LILITH
 * actually believes. "Unavailable" is a first-class, rendered state — never
 * papered over with placeholders.
 *
 * VISIBILITY: the browser only ever sees what the belief list shows by default.
 *   - Owner-context beliefs (`entity_type = "owner"`) are never requested and,
 *     if one arrives anyway, are dropped (the proxy enforces the same rule).
 *   - Superseded beliefs are not part of the current picture and are dropped.
 *   - The store-wide `meta` counts include both of the above, so they are not
 *     passed on: every number the UI shows is counted from what it displays.
 *   - Provenance keeps only what is safe to show: the class and type of source,
 *     when it was observed, its confidence, and a readable origin for known
 *     sources. Source ids, correlation ids, origin refs and free-text notes
 *     (which can hold account names) are not kept.
 */

import { fetchEndpoint, toDiagnostics, type EndpointResult } from "@/lib/api";
import type { Belief, BeliefProvenance, WorldReadResult, WorldUnavailableReason } from "./types";

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
}

/* -------------------------------------------------------------- normalise */

/**
 * Readable names for the evidence sources the backend is known to use. A
 * source id that is not listed is not shown at all (it could be anything).
 */
export const KNOWN_ORIGINS: Record<string, string> = {
  "career-store": "Career pipeline record",
  "career-events": "Career activity event",
};

/** Only the provenance fields that are safe to put on screen. */
export function safeProvenance(p: WireBelief["provenance"][number]): BeliefProvenance {
  return {
    sourceClass: p.source_class as BeliefProvenance["sourceClass"],
    sourceType: p.source_type,
    observedAt: p.observed_at,
    freshness: p.freshness as BeliefProvenance["freshness"],
    confidence: typeof p.confidence === "number" ? p.confidence : undefined,
    origin: p.source_id ? KNOWN_ORIGINS[p.source_id] : undefined,
  };
}

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
    provenance: (w.provenance ?? []).map(safeProvenance),
    observedAt: w.observed_at,
    createdAt: w.created_at,
    updatedAt: w.updated_at,
    expiresAt: w.expires_at,
    revision: w.revision,
    supersedes: w.supersedes,
    contradictedBy: w.contradicted_by,
  };
}

/** The listing rule: owner context and superseded beliefs are not shown. */
export function isVisibleBelief(b: Pick<Belief, "entity" | "lifecycleState">): boolean {
  return b.entity.entityType.trim().toLowerCase() !== "owner" && b.lifecycleState !== "SUPERSEDED";
}

/** Map a non-ok endpoint result to an honest unavailable reason + detail. */
export function unavailable(
  result: EndpointResult<unknown>,
): { reason: WorldUnavailableReason; detail: string } {
  switch (result.status) {
    case 503:
      return {
        reason: "backend-not-configured",
        detail: "This deployment is not set up to read the belief store.",
      };
    case 401:
    case 403:
      return {
        reason: "not-authorized",
        detail: "The belief store refused the read.",
      };
    case 404:
      return {
        reason: "endpoint-not-live",
        detail: "The belief store did not answer at this address.",
      };
    case 502:
    case 0:
      return {
        reason: "backend-unreachable",
        detail: "The backend could not be reached.",
      };
    default:
      return {
        reason: "error",
        detail: `The belief store answered with an unexpected status (${result.status}).`,
      };
  }
}

/* ---------------------------------------------------------------- queries */

export interface WorldQuery {
  /** filter by entity type, e.g. "career.application". Never "owner". */
  entityType?: string;
  entityId?: string;
  limit?: number;
}

/** The backend's default and maximum page for one read. */
export const WORLD_LIST_LIMIT = 200;

function toSearch(q: WorldQuery): string {
  const p = new URLSearchParams();
  if (q.entityType && q.entityType.trim().toLowerCase() !== "owner") p.set("entity_type", q.entityType);
  if (q.entityId) p.set("entity_id", q.entityId);
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
  const diagnostics = toDiagnostics(res.ok ? "live" : "unavailable", [res]);

  if (!res.ok || !res.data) {
    const u = unavailable(res);
    return { available: false, reason: u.reason, detail: u.detail, diagnostics };
  }

  return {
    available: true,
    beliefs: (res.data.beliefs ?? []).map(normBelief).filter(isVisibleBelief),
    diagnostics,
  };
}

/**
 * Read a single belief by canonical key, under the same visibility as the list:
 * a key that is owner context or superseded reads exactly like an unknown one.
 */
export async function fetchBelief(
  key: string,
  signal?: AbortSignal,
): Promise<WorldReadResult> {
  const path = `/os/world/${encodeURIComponent(key)}`;
  const res = await fetchEndpoint<WireBelief>(path, signal);
  const diagnostics = toDiagnostics(res.ok ? "live" : "unavailable", [res]);

  const belief = res.ok && res.data ? normBelief(res.data) : null;
  if (!belief || !isVisibleBelief(belief)) {
    const u = unavailable(belief ? { ...res, ok: false, status: 404 } : res);
    return { available: false, reason: u.reason, detail: u.detail, diagnostics };
  }
  return { available: true, beliefs: [belief], diagnostics };
}
