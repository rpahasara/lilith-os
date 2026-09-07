/**
 * Real-intent matching for the Cognitive Core. Only intents the core can
 * actually fulfil against a live capability are matched here; everything else
 * falls through to the demo core or plain conversation.
 */

export type RealIntentId =
  | "system.health_summary"
  | "career.attention_summary"
  | "career.create_followup_draft"
  | "career.add_note"
  | "policy.probe_prohibited"
  | "connector.probe_unsupported";

export interface RealIntent {
  id: RealIntentId;
  title: string;
  normalized: string;
  scope: string;
  triggers: RegExp[];
}

export const REAL_INTENTS: RealIntent[] = [
  {
    // WRITE intent (Slice 4). Listed before the read-only attention intent so a
    // "draft/prepare a follow-up" phrasing is matched here, not as a summary.
    id: "career.create_followup_draft",
    title: "Draft an application follow-up",
    normalized: "Draft an unsent follow-up for a job application (requires approval)",
    scope: "career",
    triggers: [
      /(draft|prepare|write|compose|create).*(follow.?up|reply|response|message)/,
      /(follow.?up|reply).*(draft|for|to|on).*(application|job|role|recruiter|#?\d+)/,
      /draft.*(application|recruiter)/,
    ],
  },
  {
    // Second INTERNAL_WRITE (Slice 5) — save an internal note on an application.
    id: "career.add_note",
    title: "Add an application note",
    normalized: "Save an internal note on a job application (requires approval)",
    scope: "career",
    triggers: [
      /(add|save|log|make|leave|take|write|record)\s+a?\s*note/,
      /note\s+(on|to|for|about).*(application|job|role|recruiter|#?\d+)/,
    ],
  },
  {
    // Slice 5 policy conformance probe — sentinel only, never ordinary phrasing.
    id: "policy.probe_prohibited",
    title: "Policy probe (prohibited)",
    normalized: "Policy conformance probe — prohibited action",
    scope: "system",
    triggers: [/^__policy_probe__$/],
  },
  {
    // Slice 6 connector conformance probe — sentinel only.
    id: "connector.probe_unsupported",
    title: "Connector probe (unsupported op)",
    normalized: "Connector conformance probe — unsupported operation",
    scope: "system",
    triggers: [/^__connector_probe__$/],
  },
  {
    id: "system.health_summary",
    title: "System health summary",
    normalized: "Summarise the health of LILITH's backend services",
    scope: "system",
    triggers: [
      /system\s+(health|status)/,
      /(check|show|summar).*(service|system|automation).*(health|status)/,
      /are.*(services|systems).*(ok|healthy|up|running)/,
      /how.*(is|are).*(lilith|the system|services)/,
      /health\s+summary/,
    ],
  },
  {
    id: "career.attention_summary",
    title: "Career attention summary",
    normalized: "Summarise which job applications need attention",
    scope: "career",
    triggers: [
      /application.*(attention|follow.?up|need)/,
      /(need|needs).*(attention|follow.?up).*(application|job)/,
      /(career|pipeline|application|job.?search).*(summary|status|update)/,
      /what.*(happening|changed).*(application|job|career|search)/,
      /which.*application.*(follow|attention)/,
      /follow.?up.*candidate/,
      /what.*applications?.*need/,
    ],
  },
];

export function matchRealIntent(input: string): RealIntent | null {
  const text = input.toLowerCase().trim();
  for (const intent of REAL_INTENTS) {
    if (intent.triggers.some((re) => re.test(text))) return intent;
  }
  return null;
}
