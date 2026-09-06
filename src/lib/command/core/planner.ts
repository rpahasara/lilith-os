/**
 * Planner V1 — bounded, deterministic. For the system-health slice it emits a
 * small finite plan. No recursive/uncontrolled planning, no hidden retries.
 * A plan change is an explicit new version.
 */
import type { CommandPlan, PlanStep } from "./types";

const SYSTEM_HEALTH_STEPS: PlanStep[] = [
  { id: "s1", label: "Reach control backend", capabilityId: "os.get_overview", kind: "capability" },
  { id: "s2", label: "Retrieve service inventory", capabilityId: "system.get_status", kind: "capability" },
  { id: "s3", label: "Cross-check service health", capabilityId: null, kind: "analysis" },
  { id: "s4", label: "Prepare summary", capabilityId: null, kind: "analysis" },
];

export function planSystemHealth(taskId: string, intent: string, version = 1): CommandPlan {
  return {
    taskId,
    version,
    intent,
    steps: SYSTEM_HEALTH_STEPS.map((s) => ({ ...s })),
    capabilitiesRequired: ["os.get_overview", "system.get_status"],
    expectedResult: "A verified summary of systemd service health with per-unit evidence.",
  };
}
