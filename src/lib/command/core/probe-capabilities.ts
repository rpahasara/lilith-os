/**
 * Conformance probe capabilities — Vertical Slice 6.
 *
 * Registered but reachable only via sentinel phrasing. This one declares a
 * connector operation the connector does NOT support, so the executor's
 * discovery check must block it before any execution — proving unsupported
 * capability→connector bindings fail safely.
 */
import { executionId } from "./ids";
import { INTERNAL_CAREER_STORE_ID } from "./connectors";
import type { Capability } from "./types";

export const unsupportedOpProbeCapability: Capability = {
  id: "probe.unsupported_op",
  version: "0.0.0",
  title: "Unsupported connector operation (probe)",
  policyClass: "READ",
  classification: "read-only",
  connector: { id: INTERNAL_CAREER_STORE_ID, operation: "nonexistent_op" },
  timeoutMs: 1,
  retry: { maxAttempts: 1, retryOn: [] },
  sideEffects: "none",
  async checkHealth() {
    return { healthy: true };
  },
  execute() {
    const t = Date.now();
    return Promise.resolve({
      ok: false, data: null, status: 0, errorKind: "4xx" as const,
      error: "unreachable — blocked at connector discovery",
      executionId: executionId("probe"), source: "probe", startedAt: t, endedAt: t,
    });
  },
};

export const PROBE_CAPABILITIES: Capability[] = [unsupportedOpProbeCapability];
