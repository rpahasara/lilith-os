/**
 * Capability Policy Engine — Vertical Slice 5.
 *
 * Slice 4 hard-wired the approval gate to a single capability flag
 * (`permission === "approval_required"`). This module generalises that into a
 * typed, class-based policy so EVERY capability is governed the same way and the
 * core no longer carries capability-specific approval assumptions.
 *
 * A capability declares a {@link PolicyClass}; the engine turns that (plus a few
 * per-capability facts like reversibility/idempotency) into a {@link PolicyDecision}
 * the executor obeys: whether approval is required, whether execution is allowed
 * at all (PROHIBITED can never run, regardless of what a planner emitted),
 * whether a read-back verification is mandatory, the approval TTL, and whether a
 * failed write may be silently retried.
 */
import type { Capability } from "./types";

/** The five governance classes every capability falls into. */
export type PolicyClass =
  | "READ"
  | "INTERNAL_WRITE"
  | "EXTERNAL_WRITE"
  | "DESTRUCTIVE"
  | "PROHIBITED";

export type RiskLevel = "none" | "low" | "medium" | "high" | "critical";
export type ApprovalMode = "none" | "explicit" | "elevated";
export type VerificationPolicy = "none" | "read_back_required";

/** The default governance for a class; a capability may tighten a few fields. */
export interface PolicyClassProfile {
  approvalMode: ApprovalMode;
  riskLevel: RiskLevel;
  verification: VerificationPolicy;
  /** How long a granted-but-unused approval stays valid; null when N/A. */
  approvalTtlMs: number | null;
  reversible: boolean;
  /** The approval card must show the exact content that will be written/sent. */
  requiresExactPreview: boolean;
  /** Surface an elevated warning in the approval card. */
  elevatedWarning: boolean;
  /** May a failed attempt be retried without re-confirmation? */
  allowSilentRetry: boolean;
  /** Execution is categorically refused. */
  prohibited: boolean;
}

/**
 * Per-class defaults (§5). A capability's own `reversible`/`idempotent`/overrides
 * refine these; the class is the floor.
 */
export const POLICY_CLASS_DEFAULTS: Record<PolicyClass, PolicyClassProfile> = {
  READ: {
    approvalMode: "none", riskLevel: "none", verification: "none",
    approvalTtlMs: null, reversible: true, requiresExactPreview: false,
    elevatedWarning: false, allowSilentRetry: true, prohibited: false,
  },
  INTERNAL_WRITE: {
    approvalMode: "explicit", riskLevel: "low", verification: "read_back_required",
    approvalTtlMs: 15 * 60 * 1000, reversible: true, requiresExactPreview: true,
    elevatedWarning: false, allowSilentRetry: true, prohibited: false,
  },
  EXTERNAL_WRITE: {
    approvalMode: "explicit", riskLevel: "medium", verification: "read_back_required",
    approvalTtlMs: 10 * 60 * 1000, reversible: false, requiresExactPreview: true,
    elevatedWarning: false, allowSilentRetry: false, prohibited: false,
  },
  DESTRUCTIVE: {
    approvalMode: "elevated", riskLevel: "high", verification: "read_back_required",
    approvalTtlMs: 5 * 60 * 1000, reversible: false, requiresExactPreview: true,
    elevatedWarning: true, allowSilentRetry: false, prohibited: false,
  },
  PROHIBITED: {
    approvalMode: "none", riskLevel: "critical", verification: "none",
    approvalTtlMs: null, reversible: false, requiresExactPreview: false,
    elevatedWarning: true, allowSilentRetry: false, prohibited: true,
  },
};

/** Optional per-capability policy overrides (a capability may only TIGHTEN). */
export interface CapabilityPolicyOverrides {
  riskLevel?: RiskLevel;
  verification?: VerificationPolicy;
  approvalTtlMs?: number;
  requiresExactPreview?: boolean;
  elevatedWarning?: boolean;
  /** Explicit opt-in that a write is safe to retry (must also be idempotent). */
  allowSilentRetry?: boolean;
}

/** The engine's verdict for one planned capability. */
export interface PolicyDecision {
  policyClass: PolicyClass;
  /** False only for PROHIBITED — execution must be refused. */
  allowed: boolean;
  prohibited: boolean;
  approvalRequired: boolean;
  approvalMode: ApprovalMode;
  /** Null when no approval is required. */
  approvalTtlMs: number | null;
  verificationRequired: boolean;
  requiresExactPreview: boolean;
  elevatedWarning: boolean;
  /** A failed attempt may be retried without re-confirmation. */
  allowSilentRetry: boolean;
  riskLevel: RiskLevel;
  reason: string;
}

/**
 * The Policy Engine. Pure and total: given a capability, decide how it must be
 * governed. This is the SINGLE place the core consults — capability code never
 * decides its own approval, and a planner cannot smuggle a PROHIBITED action
 * past it.
 */
export function evaluatePolicy(cap: {
  policyClass: PolicyClass;
  reversible?: boolean;
  idempotent?: boolean;
  policy?: CapabilityPolicyOverrides;
}): PolicyDecision {
  const cls = cap.policyClass;
  const base = POLICY_CLASS_DEFAULTS[cls];
  const o = cap.policy ?? {};

  const prohibited = base.prohibited;
  const approvalRequired = !prohibited && base.approvalMode !== "none";
  const reversible = cap.reversible ?? base.reversible;

  // A write may retry silently only when the class permits it AND the capability
  // is genuinely idempotent (a stable key prevents duplicates). Reads always may.
  const classAllowsRetry = o.allowSilentRetry ?? base.allowSilentRetry;
  const allowSilentRetry =
    cls === "READ" ? true : classAllowsRetry && cap.idempotent === true;

  return {
    policyClass: cls,
    allowed: !prohibited,
    prohibited,
    approvalRequired,
    approvalMode: base.approvalMode,
    approvalTtlMs: approvalRequired ? o.approvalTtlMs ?? base.approvalTtlMs : null,
    verificationRequired: (o.verification ?? base.verification) === "read_back_required",
    requiresExactPreview: o.requiresExactPreview ?? base.requiresExactPreview,
    elevatedWarning: o.elevatedWarning ?? base.elevatedWarning,
    allowSilentRetry,
    riskLevel: o.riskLevel ?? base.riskLevel,
    reason: prohibited
      ? "This action is prohibited by policy and cannot be executed."
      : approvalRequired
        ? `${cls} — explicit approval required before execution.`
        : `${cls} — no approval required.`,
  };
}

/** Convenience for the executor: evaluate a full Capability object. */
export function evaluateCapabilityPolicy(cap: Capability): PolicyDecision {
  return evaluatePolicy(cap);
}
