/**
 * Real-intent matching for the Cognitive Core. Only intents the core can
 * actually fulfil against a live capability are matched here; everything else
 * falls through to the demo core or plain conversation.
 */

export type RealIntentId = "system.health_summary" | "career.attention_summary";

export interface RealIntent {
  id: RealIntentId;
  title: string;
  normalized: string;
  scope: string;
  triggers: RegExp[];
}

export const REAL_INTENTS: RealIntent[] = [
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
