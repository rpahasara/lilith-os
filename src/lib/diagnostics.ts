/**
 * Frontend diagnostics policy.
 *
 * - Development diagnostics (rig dumps, expression lists, pose/spring/IK
 *   probes, command-core lifecycle traces) run only in development builds. Call
 *   sites are written as `if (DEV_DIAGNOSTICS) console.info(...)` with a
 *   module-local `DEV_DIAGNOSTICS = process.env.NODE_ENV !== "production"`, so
 *   the production bundle drops them entirely (Next inlines NODE_ENV and the
 *   minifier removes the dead branch; `npm run scan:bundle` checks this).
 * - Operational problems that matter in production (renderer failure, WebGL
 *   context loss) go through `reportProblem`: one short warning line built
 *   from fixed text plus an error's name and a truncated message. It never
 *   logs objects, stacks, request bodies, conversation text, owner data or
 *   memory context.
 */

export const DEV_DIAGNOSTICS = process.env.NODE_ENV !== "production";

const MAX_DETAIL = 160;

/** `Name: message`, single line, truncated. Never the object or its stack. */
export function describeError(error: unknown): string {
  if (error instanceof Error) {
    const text = `${error.name || "Error"}: ${error.message || ""}`.replace(/\s+/g, " ").trim();
    return text.length > MAX_DETAIL ? `${text.slice(0, MAX_DETAIL - 1)}…` : text;
  }
  return typeof error === "string" ? "non-Error thrown" : `non-Error (${typeof error})`;
}

/** Always-on, sanitized warning for an operational problem. */
export function reportProblem(
  scope: string,
  summary: string,
  error?: unknown,
  sink: (line: string) => void = (line) => console.warn(line),
): void {
  sink(error === undefined ? `[${scope}] ${summary}` : `[${scope}] ${summary} (${describeError(error)})`);
}
