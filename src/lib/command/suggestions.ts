/**
 * Suggestion chips under the command input.
 *
 * A chip is a promise: it should only offer what Lilith can actually do. The
 * defaults each map to a real intent (see `core/intents.ts`, and the self-test
 * that holds them to it). The demo fixtures contribute theirs only when the
 * demo commands were explicitly enabled.
 */
export const REAL_SUGGESTIONS = ["System health", "Career summary"] as const;

export const DEMO_SUGGESTIONS = ["Summarise inbox", "Compare AWS cost", "Plan my day"] as const;

export function defaultSuggestions(
  demoCommands: string | undefined = process.env.NEXT_PUBLIC_LILITH_ENABLE_DEMO_COMMANDS,
): string[] {
  return demoCommands === "true"
    ? [...REAL_SUGGESTIONS, ...DEMO_SUGGESTIONS]
    : [...REAL_SUGGESTIONS];
}
