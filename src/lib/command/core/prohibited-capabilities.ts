/**
 * Prohibited capabilities — Vertical Slice 5.
 *
 * These are registered but categorically refused by the Policy Engine
 * (policyClass "PROHIBITED"). Registering them — rather than merely leaving them
 * out — means the block is explicit and testable: if any future planner ever
 * emits a plan that requires one, the executor refuses it before execution,
 * regardless of approval. External email/calendar sends are out of scope for
 * this slice (§7/§12) and are encoded here as a hard guardrail.
 */
import { executionId } from "./ids";
import type { Capability, CapabilityResult } from "./types";

function refuse(id: string): CapabilityResult {
  const t = Date.now();
  return {
    ok: false, data: null, status: 0, errorKind: "4xx",
    error: "prohibited by policy — this action is refused",
    executionId: executionId(id), source: id, startedAt: t, endedAt: t,
  };
}

/** Sending email is prohibited (no Gmail sends in this system, by policy). */
export const mailSendProhibitedCapability: Capability = {
  id: "mail.send_email",
  version: "0.0.0",
  title: "Send email",
  policyClass: "PROHIBITED",
  classification: "write",
  timeoutMs: 1,
  retry: { maxAttempts: 1, retryOn: [] },
  sideEffects: "external_write",
  reversible: false,
  async checkHealth() {
    return { healthy: false, detail: "prohibited by policy" };
  },
  execute() {
    return Promise.resolve(refuse("mail.send_email"));
  },
};

export const PROHIBITED_CAPABILITIES: Capability[] = [mailSendProhibitedCapability];
