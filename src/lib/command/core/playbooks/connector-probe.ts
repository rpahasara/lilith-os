/**
 * Connector conformance probe — Vertical Slice 6.
 *
 * Requires a capability bound to an unsupported connector operation. The
 * executor's connector-discovery check must block it before any step runs,
 * proving unsupported capability→connector bindings fail safely. Reachable only
 * via an exact sentinel phrase.
 */
import type { PlaybookContext, StepResult, TaskPlaybook } from "../playbook";
import { planConnectorProbe } from "../planner";
import type { PlanStep } from "../types";

export const connectorProbePlaybook: TaskPlaybook = {
  id: "connector.probe_unsupported",
  backboneCapabilityId: "probe.unsupported_op",
  plan(taskId, intent) {
    return planConnectorProbe(taskId, intent);
  },
  async runStep(_step: PlanStep, _ctx: PlaybookContext): Promise<StepResult> {
    return { outcome: "failed", fatal: { reason: "unsupported connector operation" } };
  },
  verify() {
    return { verdict: "FAIL", summary: "Unsupported connector operation.", evidence: [], unresolved: [] };
  },
};
