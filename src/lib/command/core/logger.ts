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
  | "policy.blocked"
  | "connector.health"
  | "connector.unsupported"
  | "approval.requested"
  | "approval.approved"
  | "approval.denied"
  | "approval.expired"
  | "approval.fingerprint_mismatch"
  | "terminal"
  | "persist.create"
  | "persist.update"
  | "persist.retry"
  | "persist.conflict"
  | "persist.degraded";

export interface CoreLogger {
  log(event: CoreLogEvent, taskId: string, fields?: Record<string, unknown>): void;
}

/** Lifecycle events that indicate a real problem worth surfacing in production. */
const PRODUCTION_EVENTS: ReadonlySet<CoreLogEvent> = new Set(["persist.degraded"]);

/**
 * Console logger. In development it traces every event with its fields,
 * prefixed by the correlating taskId. In production it is quiet: only problem
 * events, as one line with the event and taskId and NO fields (fields can carry
 * backend error text).
 */
export function createConsoleCoreLogger(
  development: boolean,
  sink: { info: (...a: unknown[]) => void; warn: (...a: unknown[]) => void } = console,
): CoreLogger {
  return {
    log(event, taskId, fields) {
      if (development) {
        sink.info(`[core ${event}] task=${taskId}`, fields ?? {});
      } else if (PRODUCTION_EVENTS.has(event)) {
        sink.warn(`[core ${event}] task=${taskId}`);
      }
    },
  };
}

/** Default logger: full traces in development, problem-only in production. */
export const consoleCoreLogger: CoreLogger = createConsoleCoreLogger(process.env.NODE_ENV !== "production");

/** No-op logger for tests that don't want output. */
export const silentCoreLogger: CoreLogger = { log() {} };
