/**
 * Deterministic self-test for the RealCommandCore.
 *
 * Drives the full lifecycle against an INJECTED fake transport (no network),
 * covering the required scenarios: success, cancellation, backend-unavailable,
 * malformed result, partial verification, retryable failure, and history
 * restoration. Exposed on `window.__lilithCore.selfTest()` in dev; also
 * importable by a runner. It exercises the real core code — it never fakes a
 * successful production result.
 */
import type { CommandEvent } from "../events";
import { silentCoreLogger } from "./logger";
import { RealCommandCore } from "./real-core";
import { InMemoryTaskStore, type TaskStore } from "./task-store";
import type { CoreTransport, TransportResult } from "./types";

const SYSTEM_INTENT = "system health summary";
const CAREER_INTENT = "what applications need attention";

function ok(data: unknown, status = 200): TransportResult {
  return { ok: true, status, data };
}
function err(status: number, error = `HTTP ${status}`): TransportResult {
  return { ok: false, status, data: null, error };
}

function healthyOverview() {
  return { lilith: { status: "online", os_version: "0.1.0" }, automations: { total: 2, healthy: 2, unhealthy: 0 }, career: { applications: 8 } };
}
function statusPayload(fail: boolean) {
  return {
    time_utc: new Date().toISOString(),
    services: [
      { unit: "a.service", type: "service", active: "active", sub: "running", result: "success", n_restarts: 0 },
      fail
        ? { unit: "b.timer", type: "timer", active: "active", sub: "waiting", result: "exit-code", n_restarts: 0, service_active: "failed" }
        : { unit: "b.timer", type: "timer", active: "active", sub: "waiting", result: "success", n_restarts: 0 },
    ],
  };
}

/* ---- career fixtures (raw backend shape) ---- */
const OLD = "2026-08-20 10:00:00"; // ~2+ weeks before the test clock → idle_stale
const RECENT = "2026-09-05 10:00:00"; // ~1 day before → not idle
function careerApp(id: number, o: { stage?: string; last?: string } = {}) {
  const last = o.last ?? OLD;
  return {
    id, company: `Co${id}`, role: `Role ${id}`, stage: o.stage ?? "applied",
    source_account: "primary", confidence: 0.95, first_seen: last, last_activity: last,
    activities: 1, last_activity_summary: "…", recruiter: { name: "R", contact: "r@x.com" },
  };
}
function careerAct(id: number, appId: number | null, o: { type?: string; at?: string } = {}) {
  return { id, application_id: appId, activity_type: o.type ?? "applied", title: `t${id}`, occurred_at: o.at ?? OLD, confidence: 0.95, company: "Co", role: "Role" };
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function careerRoute(apps: any, pipe: any, acts: any): CoreTransport {
  return async (p) => (p.includes("applications") ? ok(apps) : p.includes("pipeline") ? ok(pipe) : ok(acts));
}

const TERMINALS = new Set(["result.available", "partial.result", "failed", "cancelled", "capability.unsupported"]);

function makeCore(transport: CoreTransport, store?: TaskStore) {
  return new RealCommandCore(transport, store ?? new InMemoryTaskStore(), silentCoreLogger);
}

async function drive(
  core: RealCommandCore,
  intent: string,
  opts: { cancelAfterMs?: number; timeoutMs?: number } = {},
): Promise<{ events: CommandEvent[]; terminal?: CommandEvent }> {
  const events: CommandEvent[] = [];
  const taskId = `selftest-${Math.random().toString(36).slice(2, 8)}`;
  const unsub = core.subscribe((e) => events.push(e));
  core.dispatch({ type: "submit", taskId, input: intent });
  core.dispatch({ type: "run", taskId });
  if (opts.cancelAfterMs != null) {
    setTimeout(() => core.dispatch({ type: "cancel", taskId }), opts.cancelAfterMs);
  }
  const deadline = Date.now() + (opts.timeoutMs ?? 4000);
  let terminal: CommandEvent | undefined;
  while (Date.now() < deadline) {
    terminal = events.find((e) => TERMINALS.has(e.type));
    if (terminal) break;
    await new Promise((r) => setTimeout(r, 20));
  }
  // Give a short grace window to catch any (bug) late terminal after cancel.
  await new Promise((r) => setTimeout(r, 60));
  unsub();
  return { events, terminal };
}

export interface SelfTestResult {
  name: string;
  pass: boolean;
  detail: string;
}

export async function runCoreSelfTest(): Promise<SelfTestResult[]> {
  const results: SelfTestResult[] = [];
  const record = (name: string, pass: boolean, detail: string) => results.push({ name, pass, detail });

  // A. normal success
  {
    const t: CoreTransport = async (p) => (p.includes("overview") ? ok(healthyOverview()) : ok(statusPayload(false)));
    const { terminal } = await drive(makeCore(t), SYSTEM_INTENT);
    record("A success", terminal?.type === "result.available", terminal?.type ?? "no terminal");
  }

  // B. cancellation (all calls delayed so cancel lands mid-flight)
  {
    const t: CoreTransport = async (p, signal) => {
      await new Promise((r) => setTimeout(r, 300));
      if (signal?.aborted) return err(0, "aborted");
      return p.includes("overview") ? ok(healthyOverview()) : ok(statusPayload(false));
    };
    const { events, terminal } = await drive(makeCore(t), SYSTEM_INTENT, { cancelAfterMs: 150, timeoutMs: 5000 });
    const noLateSuccess = !events.some((e) => e.type === "result.available");
    record("B cancellation", terminal?.type === "cancelled" && noLateSuccess, `${terminal?.type}; lateSuccess=${!noLateSuccess}`);
  }

  // C. backend unavailable
  {
    const t: CoreTransport = async () => err(502, "backend unreachable");
    const { terminal } = await drive(makeCore(t), SYSTEM_INTENT);
    const failed = terminal?.type === "failed";
    record("C backend down", failed, terminal?.type ?? "none");
  }

  // D. malformed result (health 200 ok, execute returns garbage)
  {
    const t: CoreTransport = async (p) => (p.includes("overview") ? ok(healthyOverview()) : ok({ nope: true }));
    const { terminal } = await drive(makeCore(t), SYSTEM_INTENT);
    const failedMalformed = terminal?.type === "failed" && /malformed/i.test((terminal as { error?: string }).error ?? "");
    record("D malformed", failedMalformed, terminal?.type === "failed" ? (terminal as { error?: string }).error ?? "" : (terminal?.type ?? "none"));
  }

  // E. partial (overview down, status ok)
  {
    const t: CoreTransport = async (p) => (p.includes("overview") ? err(502) : ok(statusPayload(false)));
    const { terminal } = await drive(makeCore(t), SYSTEM_INTENT);
    record("E partial", terminal?.type === "partial.result", terminal?.type ?? "none");
  }

  // F. retryable failure then success
  {
    let statusCalls = 0;
    const t: CoreTransport = async (p) => {
      if (p.includes("overview")) return ok(healthyOverview());
      statusCalls += 1;
      // call 1 = health probe (ok), call 2 = execute attempt 1 (503), call 3 = retry (ok)
      if (statusCalls === 2) return err(503, "temporary");
      return ok(statusPayload(false));
    };
    const { events, terminal } = await drive(makeCore(t), SYSTEM_INTENT);
    const retried = events.some((e) => e.type === "step.progress" && /retry/i.test((e as { detail?: string }).detail ?? ""));
    record("F retry→success", terminal?.type === "result.available" && retried, `${terminal?.type}; retried=${retried}`);
  }

  // G. reload / history restoration
  {
    const store = new InMemoryTaskStore();
    const t: CoreTransport = async (p) => (p.includes("overview") ? ok(healthyOverview()) : ok(statusPayload(false)));
    await drive(makeCore(t, store), SYSTEM_INTENT);
    const core2 = makeCore(async () => err(502), store); // core2 never calls backend
    const restored = core2.restore();
    const hasSucceeded = restored.some((e) => e.type === "result.available");
    const hasCreated = restored.some((e) => e.type === "task.created" && e.source === "core");
    record("G history restore", hasSucceeded && hasCreated, `events=${restored.length}`);
  }

  /* =============================== career slice =========================== */
  const APPS3 = [careerApp(1, { stage: "discovered", last: RECENT }), careerApp(2), careerApp(3)];
  const ACTS3 = [careerAct(11, 1, { type: "discovered", at: RECENT }), careerAct(12, 2), careerAct(13, 3)];
  const PIPE3 = { applied: 2, discovered: 1 };

  // Career A. complete success (attention items present)
  {
    const { terminal } = await drive(makeCore(careerRoute(APPS3, PIPE3, ACTS3)), CAREER_INTENT);
    record("Career A complete", terminal?.type === "result.available", terminal?.type ?? "none");
  }

  // Career B. zero applications
  {
    const { terminal } = await drive(makeCore(careerRoute([], {}, [])), CAREER_INTENT);
    record("Career B zero apps", terminal?.type === "result.available", terminal?.type ?? "none");
  }

  // Career E. unresolved activity linkage → PARTIAL
  {
    const acts = [...ACTS3, careerAct(99, 999)];
    const { terminal } = await drive(makeCore(careerRoute(APPS3, PIPE3, acts)), CAREER_INTENT);
    record("Career E unresolved link", terminal?.type === "partial.result", terminal?.type ?? "none");
  }

  // Career F. pipeline/application discrepancy → PASS with discrepancy evidence
  {
    const { terminal } = await drive(makeCore(careerRoute(APPS3, { applied: 5, discovered: 1 }, ACTS3)), CAREER_INTENT);
    const ev = (terminal as { evidence?: { label: string }[] }).evidence ?? [];
    const flagged = ev.some((e) => e.label === "pipeline_mismatch");
    record("Career F discrepancy", terminal?.type === "result.available" && flagged, `${terminal?.type}; flagged=${flagged}`);
  }

  // Career G. activity endpoint unavailable → PARTIAL
  {
    const t: CoreTransport = async (p) => (p.includes("applications") ? ok(APPS3) : p.includes("pipeline") ? ok(PIPE3) : err(502));
    const { terminal } = await drive(makeCore(t), CAREER_INTENT);
    record("Career G activity down", terminal?.type === "partial.result", terminal?.type ?? "none");
  }

  // Career H. malformed applications → FAIL
  {
    const t: CoreTransport = async (p) => (p.includes("applications") ? ok({ nope: true }) : p.includes("pipeline") ? ok(PIPE3) : ok(ACTS3));
    const { terminal } = await drive(makeCore(t), CAREER_INTENT);
    record("Career H malformed", terminal?.type === "failed", terminal?.type ?? "none");
  }

  // Career I. cancellation mid multi-endpoint retrieval
  {
    const t: CoreTransport = async (p, signal) => {
      await new Promise((r) => setTimeout(r, 250));
      if (signal?.aborted) return err(0, "aborted");
      return p.includes("applications") ? ok(APPS3) : p.includes("pipeline") ? ok(PIPE3) : ok(ACTS3);
    };
    const { events, terminal } = await drive(makeCore(t), CAREER_INTENT, { cancelAfterMs: 150, timeoutMs: 6000 });
    const noLate = !events.some((e) => e.type === "result.available");
    record("Career I cancellation", terminal?.type === "cancelled" && noLate, `${terminal?.type}; lateSuccess=${!noLate}`);
  }

  // Career J. retryable failure on applications then success
  {
    let appCalls = 0;
    const t: CoreTransport = async (p) => {
      if (p.includes("applications")) {
        appCalls += 1;
        if (appCalls === 2) return err(503, "temporary"); // 1=health, 2=exec attempt1, 3=retry
        return ok(APPS3);
      }
      return p.includes("pipeline") ? ok(PIPE3) : ok(ACTS3);
    };
    const { events, terminal } = await drive(makeCore(t), CAREER_INTENT);
    const retried = events.some((e) => e.type === "step.progress" && /retry/i.test((e as { detail?: string }).detail ?? ""));
    record("Career J retry→success", terminal?.type === "result.available" && retried, `${terminal?.type}; retried=${retried}`);
  }

  // Career K. persisted reload restore
  {
    const store = new InMemoryTaskStore();
    await drive(makeCore(careerRoute(APPS3, PIPE3, ACTS3), store), CAREER_INTENT);
    const core2 = makeCore(async () => err(502), store);
    const restored = core2.restore();
    const okRestore = restored.some((e) => e.type === "result.available") && restored.some((e) => e.type === "task.created" && e.source === "core");
    record("Career K reload restore", okRestore, `events=${restored.length}`);
  }

  return results;
}
