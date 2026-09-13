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

// Slice 4: the first approval-gated WRITE plan. Context + draft are prepared
// BEFORE the approval gate (s3); the mutation only runs after approval, then a
// read-back step verifies exactly what was written.
const CAREER_FOLLOWUP_STEPS: PlanStep[] = [
  { id: "s1", label: "Retrieve application context", capabilityId: "career.list_applications", kind: "capability" },
  { id: "s2", label: "Draft the follow-up", capabilityId: null, kind: "analysis" },
  { id: "s3", label: "Create draft (requires approval)", capabilityId: "career.create_followup_draft", kind: "capability" },
  { id: "s4", label: "Read back & verify draft", capabilityId: "career.get_draft", kind: "capability" },
];

export function planCareerFollowup(taskId: string, intent: string, version = 1): CommandPlan {
  return {
    taskId,
    version,
    intent,
    steps: CAREER_FOLLOWUP_STEPS.map((s) => ({ ...s })),
    capabilitiesRequired: ["career.list_applications", "career.create_followup_draft", "career.get_draft"],
    expectedResult: "An unsent follow-up draft created for the chosen application, verified by read-back.",
  };
}

// Slice 5: second INTERNAL_WRITE plan — save an internal note. Same shape as the
// follow-up (context -> freeze -> gated write -> read-back) but a different
// capability, proving the policy/gate is generic.
const CAREER_NOTE_STEPS: PlanStep[] = [
  { id: "s1", label: "Retrieve application context", capabilityId: "career.list_applications", kind: "capability" },
  { id: "s2", label: "Compose the note", capabilityId: null, kind: "analysis" },
  { id: "s3", label: "Save note (requires approval)", capabilityId: "career.add_note", kind: "capability" },
  { id: "s4", label: "Read back & verify note", capabilityId: "career.get_draft", kind: "capability" },
];

export function planCareerNote(taskId: string, intent: string, version = 1): CommandPlan {
  return {
    taskId,
    version,
    intent,
    steps: CAREER_NOTE_STEPS.map((s) => ({ ...s })),
    capabilitiesRequired: ["career.list_applications", "career.add_note", "career.get_draft"],
    expectedResult: "An internal note saved on the chosen application, verified by read-back.",
  };
}

// Slice 5 conformance probe: a plan that requires a PROHIBITED capability. It
// exists only to prove the Policy Engine blocks such a plan before execution —
// it is never reachable from ordinary user phrasing.
export function planPolicyProbe(taskId: string, intent: string, version = 1): CommandPlan {
  return {
    taskId,
    version,
    intent,
    steps: [{ id: "s1", label: "Attempt prohibited action", capabilityId: "mail.send_email", kind: "capability" }],
    capabilitiesRequired: ["mail.send_email"],
    expectedResult: "Blocked — this action is prohibited by policy.",
  };
}

// Slice 6 connector conformance probe: requires a capability whose connector
// operation is unsupported. Blocked at connector discovery before execution.
export function planConnectorProbe(taskId: string, intent: string, version = 1): CommandPlan {
  return {
    taskId,
    version,
    intent,
    steps: [{ id: "s1", label: "Attempt unsupported connector op", capabilityId: "probe.unsupported_op", kind: "capability" }],
    capabilitiesRequired: ["probe.unsupported_op"],
    expectedResult: "Blocked — the connector does not support this operation.",
  };
}
