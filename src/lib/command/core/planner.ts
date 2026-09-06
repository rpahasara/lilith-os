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

const CAREER_ATTENTION_STEPS: PlanStep[] = [
  { id: "s1", label: "Retrieve applications", capabilityId: "career.list_applications", kind: "capability" },
  { id: "s2", label: "Retrieve pipeline", capabilityId: "career.get_pipeline", kind: "capability" },
  { id: "s3", label: "Retrieve recent activity", capabilityId: "career.get_activity", kind: "capability" },
  { id: "s4", label: "Link records", capabilityId: null, kind: "analysis" },
  { id: "s5", label: "Derive attention candidates", capabilityId: null, kind: "analysis" },
  { id: "s6", label: "Verify & summarise", capabilityId: null, kind: "analysis" },
];

export function planCareerAttention(taskId: string, intent: string, version = 1): CommandPlan {
  return {
    taskId,
    version,
    intent,
    steps: CAREER_ATTENTION_STEPS.map((s) => ({ ...s })),
    capabilitiesRequired: ["career.list_applications", "career.get_pipeline", "career.get_activity"],
    expectedResult: "A verified, evidence-backed summary of which applications need attention.",
  };
}
