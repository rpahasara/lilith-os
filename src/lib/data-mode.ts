/**
 * Data mode — the one rule for what a workspace shows when it has nothing real.
 *
 *   live         the backend answered: show its data.
 *   unavailable  the backend did not answer: say so, and show nothing invented.
 *   demo         development only, and only by explicit opt-in: show the bundled
 *                sample data, marked as simulated on every page that uses it.
 *
 * Demo data is never a silent fallback. A workspace that cannot reach the
 * backend is `unavailable` unless `NEXT_PUBLIC_LILITH_DEMO_DATA=true` was set
 * for the development server. The Command Center goes further and never shows
 * demo data at all (see `lib/home/meetings-view.ts`).
 *
 * Two locks, not one. The flag is the opt-in; the build is the guard. A
 * production build (`next build`) never enables simulated content whatever the
 * flags say, so a stray env file or a host variable cannot put invented data
 * in front of real use. Both values are fixed when the app is built.
 */
import { toDiagnostics, type Diagnostics, type EndpointResult } from "@/lib/api";

/** Simulated content exists for the development server only. */
export function simulationAllowed(nodeEnv: string | undefined = process.env.NODE_ENV): boolean {
  return nodeEnv !== "production";
}

/** True only when sample data was explicitly asked for, outside a production build. */
export function demoDataEnabled(
  flag: string | undefined = process.env.NEXT_PUBLIC_LILITH_DEMO_DATA,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): boolean {
  return flag === "true" && simulationAllowed(nodeEnv);
}

/** True only when the scripted demo commands were explicitly asked for, outside a production build. */
export function demoCommandsEnabled(
  flag: string | undefined = process.env.NEXT_PUBLIC_LILITH_ENABLE_DEMO_COMMANDS,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): boolean {
  return flag === "true" && simulationAllowed(nodeEnv);
}

/** What a loader returns instead of data when the backend did not answer. */
export interface Unavailable {
  unavailable: true;
  diagnostics: Diagnostics;
}

/** The result of loading a workspace: its data, or an honest "unavailable". */
export type Loaded<T> = T | Unavailable;

export function unavailable(results: EndpointResult[]): Unavailable {
  return { unavailable: true, diagnostics: toDiagnostics("unavailable", results) };
}

export function isUnavailable<T>(value: Loaded<T>): value is Unavailable {
  return (value as Unavailable).unavailable === true;
}

/**
 * One line a person can act on, from the endpoint results. Mirrors the shell's
 * own vocabulary (see `lib/system/shell-health.ts`).
 */
export function unavailableReason(diagnostics: Diagnostics): string {
  const statuses = diagnostics.endpoints.map((e) => e.status);
  if (statuses.length && statuses.every((s) => s === 503)) {
    return "No backend is configured for this app.";
  }
  if (statuses.some((s) => s === 401 || s === 403)) {
    return "The backend refused the request.";
  }
  if (statuses.some((s) => s === 404)) {
    return "The backend does not provide this yet.";
  }
  return "The backend is not reachable right now.";
}
