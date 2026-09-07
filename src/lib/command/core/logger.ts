/**
 * Structured, taskId-correlated logging for the Cognitive Core.
 *
 * Never logs secrets, credentials, or full private payloads — only shapes,
 * counts, ids, and verdicts. Kept dependency-free so it works in the browser
 * and in the deterministic self-test.
 */

export type CoreLogEvent =
  | "task.created"
  | "context.assembled"
  | "plan.created"
  | "capability.selected"
  | "capability.health"
  | "step.started"
  | "capability.result"
  | "verify.verdict"
  | "retry"
  | "cancel"
  | "terminal"
  | "persist.create"
  | "persist.update"
  | "persist.retry"
  | "persist.conflict"
  | "persist.degraded";

export interface CoreLogger {
  log(event: CoreLogEvent, taskId: string, fields?: Record<string, unknown>): void;
}

/** Default console logger. Prefixes every line with the correlating taskId. */
export const consoleCoreLogger: CoreLogger = {
  log(event, taskId, fields) {
    // eslint-disable-next-line no-console
    console.info(`[core ${event}] task=${taskId}`, fields ?? {});
  },
};

/** No-op logger for tests that don't want output. */
export const silentCoreLogger: CoreLogger = { log() {} };
