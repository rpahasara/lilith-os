/** Dependency-free id helpers (kept out of transport so pure modules stay
 *  free of any `@/lib/api` import and remain unit-testable in isolation). */

function rid(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().slice(0, 12)
    : Math.random().toString(36).slice(2, 14);
}

/** Opaque per-execution id for capability results / evidence correlation. */
export function executionId(prefix: string): string {
  return `${prefix}-${rid()}`;
}
