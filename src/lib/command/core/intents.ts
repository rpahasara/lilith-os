/**
 * Real-intent matching for the Cognitive Core. Only intents the core can
 * actually fulfil against a live capability are matched here; everything else
 * falls through to the demo core or plain conversation.
 */

export type RealIntentId = "system.health_summary";

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
];

export function matchRealIntent(input: string): RealIntent | null {
  const text = input.toLowerCase().trim();
  for (const intent of REAL_INTENTS) {
    if (intent.triggers.some((re) => re.test(text))) return intent;
  }
  return null;
}
