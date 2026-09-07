/**
 * Policy conformance probe — Vertical Slice 5.
 *
 * A deliberately prohibited plan: it requires the PROHIBITED `mail.send_email`
 * capability. The Policy Engine must block it at capability-check, BEFORE any
 * step runs — proving that a plan cannot smuggle a prohibited action past the
 * gate regardless of planner output. Reachable only via an exact sentinel
 * phrase, never ordinary usage; `runStep` is unreachable by design.
 */
import type { PlaybookContext, StepResult, TaskPlaybook } from "../playbook";
import { planPolicyProbe } from "../planner";
import type { PlanStep } from "../types";

export const policyProbePlaybook: TaskPlaybook = {
  id: "policy.probe_prohibited",
  backboneCapabilityId: "mail.send_email",
  plan(taskId, intent) {
    return planPolicyProbe(taskId, intent);
  },
  async runStep(_step: PlanStep, _ctx: PlaybookContext): Promise<StepResult> {
    // Unreachable: the executor blocks the task at capability-check.
    return { outcome: "failed", fatal: { reason: "prohibited by policy" } };
  },
  verify() {
    return { verdict: "FAIL", summary: "Prohibited by policy.", evidence: [], unresolved: [] };
  },
};
