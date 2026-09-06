/**
 * Context Builder V1 — the smallest bundle the first task needs.
 *
 * It captures the request, the time, the domain scope, and reserves slots for
 * retrieved backend data + provenance (filled by the executor as capabilities
 * return). No speculative memory reads, no personal-memory writes.
 */
import type { RealIntent } from "./intents";
import type { ContextBundle } from "./types";

export function buildContextBundle(
  taskId: string,
  userRequest: string,
  intent: RealIntent,
): ContextBundle {
  return {
    taskId,
    userRequest,
    normalizedIntent: intent.normalized,
    scope: intent.scope,
    assembledAt: new Date().toISOString(),
    retrieved: {},
    provenance: [],
  };
}
