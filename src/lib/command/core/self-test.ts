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
import { getCapability } from "./capabilities";
import { evaluatePolicy, evaluateCapabilityPolicy, POLICY_CLASS_DEFAULTS, type PolicyClass } from "./policy";
import { planCareerFollowup, planCareerNote } from "./planner";
import { buildFollowupDraft, buildNote } from "./career-write";
import type { CareerApplication } from "./career-capabilities";
import {
  createTaskBackend,
  InMemoryTaskStore,
  RemoteTaskStore,
  type KV,
  type TaskStore,
} from "./task-store";
import type { CoreTaskRecord, CoreTransport, TransportResult } from "./types";

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

/* ---- Slice 4 write fixtures: an in-memory drafts backend + helpers ---- */

const WRITE_INTENT = "draft a follow-up for application #1";
const WRITE_APP = {
  id: 1, company: "NEXT", role: "Senior DevOps Engineer", stage: "discovered",
  source_account: "primary", confidence: 0.97, first_seen: RECENT, last_activity: RECENT,
  activities: 1, last_activity_summary: "…", recruiter: { name: "Alex Rivera", contact: "alex@x.com" },
};

interface DraftBackendOpts { failWritesTimes?: number; corruptReadback?: boolean; phantomTimeoutOnce?: boolean }

/** Faithful in-memory emulation of the /os/drafts store (idempotent create). */
function makeDraftBackend(apps: unknown, opts: DraftBackendOpts = {}) {
  const store = new Map<string, Record<string, unknown>>();
  const byKey = new Map<string, string>();
  let postCount = 0;
  let phantomUsed = false;
  const transport: CoreTransport = async (path, _signal, init) => {
    if (path.includes("/drafts")) {
      if (init?.method === "POST") {
        postCount += 1;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const b = (init.body ?? {}) as any;
        if (opts.failWritesTimes && postCount <= opts.failWritesTimes) return err(503, "temporary");
        const existing = byKey.get(b.idempotencyKey);
        if (existing) return ok({ draft: store.get(existing), created: false });
        const row = {
          draftId: b.draftId, status: "created", target: b.target, subject: b.subject, body: b.body,
          contentHash: `h.${String(b.subject).length}.${String(b.body).length}`,
          idempotencyKey: b.idempotencyKey, createdAt: 1000,
        };
        store.set(row.draftId, row);
        byKey.set(b.idempotencyKey, row.draftId);
        // Commit-then-timeout: the row IS stored but the caller sees a timeout —
        // an unknown commit state whose safe resolution is idempotent retry.
        if (opts.phantomTimeoutOnce && !phantomUsed) { phantomUsed = true; return err(0, "timeout"); }
        return ok({ draft: row, created: true });
      }
      const m = path.match(/\/drafts\/([^?]+)/);
      if (m) {
        const id = decodeURIComponent(m[1]);
        const row = store.get(id);
        if (!row) return err(404, "not found");
        const out = opts.corruptReadback ? { ...row, body: `${row.body} [TAMPERED]` } : row;
        return ok({ draft: out });
      }
      return ok({ drafts: [...store.values()], count: store.size }); // list / health
    }
    if (path.includes("applications")) return ok(apps);
    if (path.includes("pipeline")) return ok({});
    return ok([]);
  };
  return { transport, count: () => store.size, drafts: () => [...store.values()] };
}

function collect(core: RealCommandCore) {
  const events: CommandEvent[] = [];
  const unsub = core.subscribe((e) => events.push(e));
  return { events, unsub };
}
async function waitFor(
  events: CommandEvent[],
  pred: (e: CommandEvent) => boolean,
  ms = 4000,
): Promise<CommandEvent | undefined> {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    const e = events.find(pred);
    if (e) return e;
    await new Promise((r) => setTimeout(r, 15));
  }
  return undefined;
}
const isTerminalEvt = (e: CommandEvent) => TERMINALS.has(e.type);

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
    const restored = await core2.restore();
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
    const restored = await core2.restore();
    const okRestore = restored.some((e) => e.type === "result.available") && restored.some((e) => e.type === "task.created" && e.source === "core");
    record("Career K reload restore", okRestore, `events=${restored.length}`);
  }

  /* ====================== Slice 3: durable persistence ==================== */

  const okT: CoreTransport = async (p) =>
    p.includes("overview") ? ok(healthyOverview()) : ok(statusPayload(false));

  // A valid minimal CoreTaskRecord for store-level assertions.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function baseRec(id: string, over: Record<string, any> = {}): CoreTaskRecord {
    return {
      taskId: id, schemaVersion: 1, source: "core", rawIntent: "x",
      normalizedIntent: "x", title: "T", scope: "system", planVersion: 1,
      plan: null, status: "created", currentStepId: null, steps: [],
      approvalState: "not_required", attemptCount: 0, cancelRequested: false,
      createdAt: 1000, updatedAt: 1000, evidence: [], ...over,
    } as CoreTaskRecord;
  }
  function memKV(init: Record<string, string> = {}): KV {
    const m = new Map(Object.entries(init));
    return {
      get: (k) => (m.has(k) ? (m.get(k) as string) : null),
      set: (k, v) => { m.set(k, v); },
      remove: (k) => { m.delete(k); },
    };
  }

  // A. create task (integration → durable)
  {
    const be = createTaskBackend();
    await drive(makeCore(okT, new InMemoryTaskStore(be)), SYSTEM_INTENT);
    const snap = be.snapshot();
    record("P-A create+persist", snap.length === 1 && snap[0].outcome === "succeeded" && snap[0].revision === 3, `n=${snap.length} rev=${snap[0]?.revision}`);
  }

  // B. retrieve task
  {
    const be = createTaskBackend();
    const store = new InMemoryTaskStore(be);
    const { events } = await drive(makeCore(okT, store), SYSTEM_INTENT);
    const id = (events.find((e) => e.type === "task.created") as { taskId: string }).taskId;
    const got = await store.get(id);
    record("P-B retrieve", !!got && got.taskId === id && got.outcome === "succeeded", got ? "ok" : "missing");
  }

  // C. update → revision monotonic
  {
    const s = new InMemoryTaskStore();
    const c = await s.create(baseRec("upd-1"), "o1");
    const u = await s.update(baseRec("upd-1", { status: "running" }), c.revision!, "o2");
    record("P-C update revision", c.revision === 1 && u.ok && u.revision === 2, `c=${c.revision} u=${u.revision}`);
  }

  // D. list history (+ filter)
  {
    const s = new InMemoryTaskStore();
    await s.create(baseRec("h1"), "a");
    await s.create(baseRec("h2", { scope: "career" }), "b");
    const all = await s.loadAll();
    record("P-D list history", all.source === "backend" && all.records.length === 2, `n=${all.records.length}`);
  }

  // E. persistence across store restart (new store, same durable backend)
  {
    const be = createTaskBackend();
    await new InMemoryTaskStore(be).create(baseRec("r1"), "a");
    const all = await new InMemoryTaskStore(be).loadAll();
    record("P-E survives restart", all.records.some((r) => r.taskId === "r1"), `n=${all.records.length}`);
  }

  // F. duplicate create / idempotency
  {
    const be = createTaskBackend();
    const s = new InMemoryTaskStore(be);
    const c1 = await s.create(baseRec("d1"), "o1");
    const c2 = await s.create(baseRec("d1"), "o1");
    record("P-F create idempotent", be.count() === 1 && c1.revision === 1 && c2.applied === false, `count=${be.count()}`);
  }

  // G. stale revision conflict
  {
    const s = new InMemoryTaskStore();
    await s.create(baseRec("c1"), "o1");
    await s.update(baseRec("c1", { status: "running" }), 1, "o2");
    const stale = await s.update(baseRec("c1", { status: "verifying" }), 1, "o3");
    record("P-G stale conflict", !stale.ok && stale.errorKind === "conflict" && stale.conflict?.revision === 2, `${stale.errorKind} rev=${stale.conflict?.revision}`);
  }

  // H. repeated operation does not duplicate evidence
  {
    const s = new InMemoryTaskStore();
    await s.create(baseRec("i1"), "o1");
    const oneEv = [{ kind: "observed_state" as const, label: "x", value: "1" }];
    const u1 = await s.update(baseRec("i1", { status: "running", evidence: oneEv }), 1, "opX");
    const u2 = await s.update(baseRec("i1", { status: "running", evidence: oneEv }), 1, "opX");
    const got = await s.get("i1");
    record("P-H op replay no dup", u1.revision === 2 && u2.applied === false && u2.revision === 2 && got?.evidence?.length === 1, `applied=${u2.applied} ev=${got?.evidence?.length}`);
  }

  // I. invalid transition rejected
  {
    const s = new InMemoryTaskStore();
    await s.create(baseRec("t1"), "o1");
    await s.update(baseRec("t1", { status: "succeeded", outcome: "succeeded", endedAt: 2000 }), 1, "o2");
    const bad = await s.update(baseRec("t1", { status: "running" }), 2, "o3");
    record("P-I illegal transition", !bad.ok && bad.errorKind === "conflict" && /illegal/.test(bad.error ?? ""), `${bad.errorKind} ${bad.error}`);
  }

  // J. legacy localStorage migration
  {
    const be = createTaskBackend();
    const kv = memKV({ "lilith-os:core-tasks": JSON.stringify([baseRec("leg1"), baseRec("leg2", { scope: "career" })]) });
    const s = new RemoteTaskStore({ request: be.http, kv });
    await s.init();
    const all = await s.loadAll();
    const flag = kv.get("lilith-os:core-tasks-migrated:v1");
    const legacyGone = kv.get("lilith-os:core-tasks") === null;
    record("P-J legacy migration", all.records.length === 2 && !!flag && legacyGone, `n=${all.records.length} flag=${!!flag} gone=${legacyGone}`);
  }

  // K. demo task NOT migrated
  {
    const be = createTaskBackend();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const demo: any = { ...baseRec("demo1"), source: "demo" };
    const kv = memKV({ "lilith-os:core-tasks": JSON.stringify([baseRec("real1"), demo]) });
    await new RemoteTaskStore({ request: be.http, kv }).init();
    const snap = be.snapshot();
    record("P-K demo not migrated", snap.length === 1 && snap[0].taskId === "real1", `n=${snap.length}`);
  }

  // L. malformed legacy task skipped
  {
    const be = createTaskBackend();
    const kv = memKV({ "lilith-os:core-tasks": JSON.stringify([baseRec("good1"), { taskId: "" }, { nonsense: true }, "not-an-object"]) });
    await new RemoteTaskStore({ request: be.http, kv }).init();
    record("P-L malformed skipped", be.count() === 1 && be.snapshot()[0].taskId === "good1", `n=${be.count()}`);
  }

  // M. backend unavailable → runs read-only but honestly flagged, nothing faked
  {
    const be = createTaskBackend();
    be.setMode({ offline: true });
    const { terminal } = await drive(makeCore(okT, new InMemoryTaskStore(be)), SYSTEM_INTENT);
    const ev = (terminal as { evidence?: { label: string; value?: string }[] }).evidence ?? [];
    const persist = ev.find((e) => e.label === "Persistence");
    const honest = terminal?.type === "result.available" && !!persist && /unavailable/i.test(persist.value ?? "") && be.count() === 0;
    record("P-M backend unavailable honest", honest, `${terminal?.type} persist="${persist?.value}" n=${be.count()}`);
  }

  // N. transient persistence failure + bounded retry recovers
  {
    const be = createTaskBackend();
    be.setMode({ failUpdates: 2 });
    const { terminal } = await drive(makeCore(okT, new InMemoryTaskStore(be)), SYSTEM_INTENT);
    const ev = (terminal as { evidence?: { label: string; value?: string }[] }).evidence ?? [];
    const persist = ev.find((e) => e.label === "Persistence");
    const snap = be.snapshot();
    record("P-N transient retry recovers", !!persist && /durable/i.test(persist.value ?? "") && snap[0]?.outcome === "succeeded", `persist="${persist?.value}" rev=${snap[0]?.revision}`);
  }

  // O. non-terminal task restored as interrupted (recovery classification)
  {
    const be = createTaskBackend();
    be.seed(baseRec("intr-1", {
      status: "running",
      plan: { taskId: "intr-1", version: 1, intent: "x", steps: [{ id: "s1", label: "Step", capabilityId: null, kind: "analysis" }], capabilitiesRequired: [], expectedResult: "x" },
    }), 2);
    const events = await makeCore(async () => err(502), new InMemoryTaskStore(be)).restore();
    const failed = events.find((e) => e.type === "failed" && e.taskId === "intr-1") as { error?: string; evidence?: { label: string; value?: string }[] } | undefined;
    const rec = failed?.evidence?.some((e) => e.label === "Recovery" && /interrupted/i.test(e.value ?? ""));
    const created = events.some((e) => e.type === "task.created" && e.taskId === "intr-1");
    const notSuccess = !events.some((e) => e.type === "result.available" && e.taskId === "intr-1");
    record("P-O interrupted recovery", created && !!failed && !!rec && notSuccess && /interrupted/i.test(failed?.error ?? ""), `failed=${!!failed} rec=${!!rec}`);
  }

  // P. clear localStorage → restore entirely from backend
  {
    const be = createTaskBackend();
    await new InMemoryTaskStore(be).create(baseRec("persisted-1", { status: "succeeded", outcome: "succeeded", resultSummary: "ok", endedAt: 2000 }), "o1");
    const kv = memKV({}); // simulates cleared localStorage
    const events = await makeCore(async () => err(502), new RemoteTaskStore({ request: be.http, kv })).restore();
    const restored = events.some((e) => e.type === "result.available" && e.taskId === "persisted-1") && events.some((e) => e.type === "task.created" && e.taskId === "persisted-1");
    record("P-P restore without localStorage", restored, `events=${events.length}`);
  }

  /* ============ Slice 4: approval-gated write (draft follow-up) ============ */

  const writePlan = (id: string) => planCareerFollowup(id, "x");
  const draftFor = (id: string) => buildFollowupDraft(WRITE_APP as unknown as CareerApplication, id, "s3");
  const pendingFor = (id: string) => {
    const d = draftFor(id);
    return {
      capabilityId: "career.create_followup_draft", stepId: "s3", target: d.target,
      subject: d.subject, body: d.body, idempotencyKey: d.idempotencyKey, draftId: d.draftId, fingerprint: d.fingerprint,
    };
  };

  // W-A / W-B — approval requested BEFORE any write; zero side effect at the gate.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-ab", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-ab" });
    const appr = await waitFor(events, (e) => e.type === "approval.requested");
    const noWriteFinished = !events.some((e) => e.type === "step.finished" && (e as { stepId?: string }).stepId === "s3");
    record("W-A approval before write", !!appr && noWriteFinished, `appr=${!!appr}`);
    record("W-B no side effect pre-approval", be.count() === 0, `drafts=${be.count()}`);
    unsub();
  }

  // W-C / W-K — approve → exactly one real mutation, read-back verified PASS.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-c", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-c" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "approve", taskId: "w-c" });
    const term = await waitFor(events, isTerminalEvt);
    const evid = (term as { evidence?: { kind: string }[] }).evidence ?? [];
    const hasId = evid.some((e) => e.kind === "external_id");
    record("W-C approve→one write", term?.type === "result.available" && be.count() === 1, `${term?.type} drafts=${be.count()}`);
    record("W-K write + read-back PASS", term?.type === "result.available" && hasId, `evid=${hasId}`);
    unsub();
  }

  // W-D — deny → zero mutation, terminal cancelled.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-d", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-d" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "deny", taskId: "w-d" });
    const resolved = await waitFor(events, (e) => e.type === "approval.resolved");
    record("W-D deny→zero mutation", (resolved as { approved?: boolean })?.approved === false && be.count() === 0, `drafts=${be.count()}`);
    unsub();
  }

  // W-E — cancel while waiting → zero mutation, terminal cancelled.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-e", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-e" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "cancel", taskId: "w-e" });
    const term = await waitFor(events, isTerminalEvt);
    record("W-E cancel before approval→zero", term?.type === "cancelled" && be.count() === 0, `${term?.type} drafts=${be.count()}`);
    unsub();
  }

  // W-F / W-G — reload while waiting stays waiting; approve after reload runs once.
  {
    const taskBe = createTaskBackend();
    const be = makeDraftBackend([WRITE_APP]);
    const coreA = makeCore(be.transport, new InMemoryTaskStore(taskBe));
    const cA = collect(coreA);
    coreA.dispatch({ type: "submit", taskId: "w-fg", input: WRITE_INTENT });
    coreA.dispatch({ type: "run", taskId: "w-fg" });
    await waitFor(cA.events, (e) => e.type === "approval.requested");
    cA.unsub();

    const coreB = makeCore(be.transport, new InMemoryTaskStore(taskBe));
    const cB = collect(coreB);
    const restored = await coreB.restore();
    const stillWaiting =
      restored.some((e) => e.type === "approval.requested" && e.taskId === "w-fg") &&
      !restored.some((e) => e.type === "failed" && e.taskId === "w-fg");
    record("W-F reload while waiting", stillWaiting && be.count() === 0, `waiting=${stillWaiting} drafts=${be.count()}`);

    coreB.dispatch({ type: "approve", taskId: "w-fg" });
    const term = await waitFor(cB.events, isTerminalEvt, 5000);
    record("W-G approve after reload→once", term?.type === "result.available" && be.count() === 1, `${term?.type} drafts=${be.count()}`);
    cB.unsub();
  }

  // W-H — duplicate approve → no duplicate write.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-h", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-h" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "approve", taskId: "w-h" });
    core.dispatch({ type: "approve", taskId: "w-h" }); // duplicate, same tick
    const term = await waitFor(events, isTerminalEvt);
    record("W-H duplicate approve no dup", term?.type === "result.available" && be.count() === 1, `drafts=${be.count()}`);
    unsub();
  }

  // W-I — retryable write failure + idempotent retry recovers with one row.
  {
    const be = makeDraftBackend([WRITE_APP], { failWritesTimes: 1 });
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-i", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-i" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "approve", taskId: "w-i" });
    const term = await waitFor(events, isTerminalEvt);
    const retried = events.some((e) => e.type === "step.progress" && /retry/i.test((e as { detail?: string }).detail ?? ""));
    record("W-I write timeout + idempotent retry", term?.type === "result.available" && be.count() === 1 && retried, `${term?.type} drafts=${be.count()} retried=${retried}`);
    unsub();
  }

  // W-J — unknown commit state (committed-but-unacknowledged) → idempotent retry, no duplicate.
  {
    const be = makeDraftBackend([WRITE_APP], { phantomTimeoutOnce: true });
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-j", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-j" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "approve", taskId: "w-j" });
    const term = await waitFor(events, isTerminalEvt);
    record("W-J unknown commit → verify-before-retry", term?.type === "result.available" && be.count() === 1, `${term?.type} drafts=${be.count()}`);
    unsub();
  }

  // W-L — write succeeds but read-back content differs → honest FAIL (not success).
  {
    const be = makeDraftBackend([WRITE_APP], { corruptReadback: true });
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "w-l", input: WRITE_INTENT });
    core.dispatch({ type: "run", taskId: "w-l" });
    await waitFor(events, (e) => e.type === "approval.requested");
    core.dispatch({ type: "approve", taskId: "w-l" });
    const term = await waitFor(events, isTerminalEvt);
    record("W-L write ok + verify FAIL honest", term?.type === "failed" && be.count() === 1, `${term?.type} drafts=${be.count()}`);
    unsub();
  }

  // W-M — stale approval fingerprint on restore → re-approval required, no write.
  {
    const taskBe = createTaskBackend();
    const be = makeDraftBackend([WRITE_APP]);
    const bogus = { ...pendingFor("w-m"), fingerprint: "BOGUS", subject: "S", body: "B" };
    taskBe.seed(baseRec("w-m", {
      status: "waiting_for_approval", approvalState: "required", rawIntent: WRITE_INTENT, scope: "career",
      plan: writePlan("w-m"), pendingWrite: bogus,
      approval: { requestedAt: 1000, expiresAt: Date.now() + 60_000, fingerprint: "BOGUS" },
    }), 2);
    const core = makeCore(be.transport, new InMemoryTaskStore(taskBe));
    const { events, unsub } = collect(core);
    await core.restore();
    core.dispatch({ type: "approve", taskId: "w-m" });
    const reReq = await waitFor(events, (e) => e.type === "approval.requested");
    record("W-M stale fingerprint → reapproval", !!reReq && be.count() === 0, `reReq=${!!reReq} drafts=${be.count()}`);
    unsub();
  }

  // W-N — approved-but-not-executed recovery → resumes once, idempotent.
  {
    const taskBe = createTaskBackend();
    const be = makeDraftBackend([WRITE_APP]);
    taskBe.seed(baseRec("w-n", {
      status: "waiting_for_approval", approvalState: "approved", rawIntent: WRITE_INTENT, scope: "career",
      plan: writePlan("w-n"), pendingWrite: pendingFor("w-n"),
      approval: { requestedAt: 1000, approvedAt: 1500, fingerprint: draftFor("w-n").fingerprint },
    }), 2);
    const core = makeCore(be.transport, new InMemoryTaskStore(taskBe));
    const { events, unsub } = collect(core);
    await core.restore();
    const term = await waitFor(events, isTerminalEvt, 5000);
    record("W-N approved-not-executed recovery", term?.type === "result.available" && be.count() === 1, `${term?.type} drafts=${be.count()}`);
    unsub();
  }

  // W-O — post-write reload restores the audit evidence (offline core).
  {
    const taskBe = createTaskBackend();
    const be = makeDraftBackend([WRITE_APP]);
    const coreA = makeCore(be.transport, new InMemoryTaskStore(taskBe));
    const cA = collect(coreA);
    coreA.dispatch({ type: "submit", taskId: "w-o", input: WRITE_INTENT });
    coreA.dispatch({ type: "run", taskId: "w-o" });
    await waitFor(cA.events, (e) => e.type === "approval.requested");
    coreA.dispatch({ type: "approve", taskId: "w-o" });
    await waitFor(cA.events, isTerminalEvt, 5000);
    cA.unsub();

    const coreB = makeCore(async () => err(502), new InMemoryTaskStore(taskBe));
    const restored = await coreB.restore();
    const res = restored.find((e) => e.type === "result.available" && e.taskId === "w-o") as { evidence?: { kind: string }[] } | undefined;
    const hasEvidence = (res?.evidence ?? []).some((e) => e.kind === "external_id");
    record("W-O post-write reload audit", !!res && hasEvidence, `res=${!!res} evid=${hasEvidence}`);
  }

  // W-P — demo tasks never reach the live write capability.
  {
    const routed = RealCommandCore.matches(WRITE_INTENT) !== null;
    const cap = getCapability("career.create_followup_draft");
    const gated = !!cap && evaluateCapabilityPolicy(cap).approvalRequired && cap.classification === "write";
    record("W-P demo never calls live write", routed && gated, `routed=${routed} gated=${gated}`);
  }

  /* ================= Slice 5: capability policy / integration fabric ======= */

  // PE — policy engine class behaviour (§4/§5). Pure, exhaustive over the classes.
  {
    const probe = (cls: PolicyClass, over: { idempotent?: boolean; reversible?: boolean } = {}) =>
      evaluatePolicy({ policyClass: cls, idempotent: over.idempotent, reversible: over.reversible });
    const read = probe("READ");
    const intw = probe("INTERNAL_WRITE", { idempotent: true });
    const extw = probe("EXTERNAL_WRITE", { idempotent: true });
    const dest = probe("DESTRUCTIVE", { idempotent: true });
    const proh = probe("PROHIBITED");
    record("PE-A read bypasses approval", read.allowed && !read.approvalRequired && !read.verificationRequired, `${JSON.stringify(read.approvalRequired)}`);
    record("PE-B internal write gated+verified", intw.allowed && intw.approvalRequired && intw.verificationRequired && intw.requiresExactPreview, "");
    record("PE-C external write gated+preview+verified", extw.approvalRequired && extw.verificationRequired && extw.requiresExactPreview, "");
    record("PE-D destructive elevated+no-silent-retry", dest.approvalRequired && dest.elevatedWarning && dest.allowSilentRetry === false, `silent=${dest.allowSilentRetry}`);
    record("PE-E prohibited never allowed", proh.prohibited && !proh.allowed && !proh.approvalRequired, `allowed=${proh.allowed}`);
    // Non-idempotent write must not be silently retried even if class allows it.
    const nonIdem = evaluatePolicy({ policyClass: "INTERNAL_WRITE", idempotent: false });
    record("PE-F non-idempotent write no silent retry", nonIdem.allowSilentRetry === false, `silent=${nonIdem.allowSilentRetry}`);
    // Class defaults table matches §5 expectations.
    const d = POLICY_CLASS_DEFAULTS;
    const tableOk = d.READ.approvalMode === "none" && d.INTERNAL_WRITE.approvalMode === "explicit" &&
      d.EXTERNAL_WRITE.requiresExactPreview && d.DESTRUCTIVE.elevatedWarning && d.PROHIBITED.prohibited;
    record("PE-G class table matches spec", tableOk, "");
  }

  // PB — prohibited capability is blocked by the core, end-to-end, zero execution.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "pb-1", input: "__policy_probe__" });
    core.dispatch({ type: "run", taskId: "pb-1" });
    const term = await waitFor(events, isTerminalEvt);
    const blocked = term?.type === "capability.unsupported" || (term?.type === "failed");
    const noApproval = !events.some((e) => e.type === "approval.requested" && e.taskId === "pb-1");
    record("PB prohibited blocked (no execution)", blocked && noApproval && be.count() === 0, `${term?.type} approval=${!noApproval} drafts=${be.count()}`);
    unsub();
  }

  // PC — READ intent bypasses approval entirely (policy, not capability flag).
  {
    const t: CoreTransport = async (p) => (p.includes("overview") ? ok(healthyOverview()) : ok(statusPayload(false)));
    const { events, terminal } = await drive(makeCore(t), SYSTEM_INTENT);
    const noApproval = !events.some((e) => e.type === "approval.requested");
    record("PC read bypasses approval (e2e)", terminal?.type === "result.available" && noApproval, `${terminal?.type} approval=${!noApproval}`);
  }

  // ND — the SECOND internal write (add_note) works end-to-end through the same gate.
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "nd-1", input: "add a note to application #1: called the recruiter, awaiting reply" });
    core.dispatch({ type: "run", taskId: "nd-1" });
    const appr = await waitFor(events, (e) => e.type === "approval.requested");
    const preApprove = be.count();
    core.dispatch({ type: "approve", taskId: "nd-1" });
    const term = await waitFor(events, isTerminalEvt);
    record("ND add_note gated write e2e", !!appr && preApprove === 0 && term?.type === "result.available" && be.count() === 1, `appr=${!!appr} pre=${preApprove} ${term?.type} n=${be.count()}`);
    unsub();
  }

  // NX — expired approval on restore cannot execute; approve re-requests (no write).
  {
    const taskBe = createTaskBackend();
    const be = makeDraftBackend([WRITE_APP]);
    const noteDraft = buildNote(WRITE_APP as unknown as CareerApplication, "call back", "nx-1", "s3");
    const pw = { capabilityId: "career.add_note", stepId: "s3", target: noteDraft.target, subject: "", body: noteDraft.body, idempotencyKey: noteDraft.idempotencyKey, draftId: noteDraft.draftId, fingerprint: noteDraft.fingerprint };
    taskBe.seed(baseRec("nx-1", {
      status: "waiting_for_approval", approvalState: "required", rawIntent: "add a note to application #1: call back", scope: "career",
      plan: planCareerNote("nx-1", "x"), pendingWrite: pw,
      approval: { requestedAt: 1000, expiresAt: Date.now() - 1000, fingerprint: noteDraft.fingerprint }, // already expired
    }), 2);
    const core = makeCore(be.transport, new InMemoryTaskStore(taskBe));
    const { events, unsub } = collect(core);
    const restored = await core.restore();
    const shownExpired = restored.some((e) => e.type === "approval.requested" && e.taskId === "nx-1" && (e as { approval?: { status?: string } }).approval?.status === "expired");
    core.dispatch({ type: "approve", taskId: "nx-1" });
    const reReq = await waitFor(events, (e) => e.type === "approval.requested");
    record("NX expired approval cannot execute", shownExpired && !!reReq && be.count() === 0, `expired=${shownExpired} reReq=${!!reReq} n=${be.count()}`);
    unsub();
  }

  // NS — sweepExpiredApprovals transitions a live waiting task to expired (§6).
  {
    const be = makeDraftBackend([WRITE_APP]);
    const core = makeCore(be.transport);
    const { events, unsub } = collect(core);
    core.dispatch({ type: "submit", taskId: "ns-1", input: "add a note to application #1: ping" });
    core.dispatch({ type: "run", taskId: "ns-1" });
    await waitFor(events, (e) => e.type === "approval.requested");
    const swept = core.sweepExpiredApprovals(Date.now() + 60 * 60 * 1000); // pretend an hour passed
    const expiredCard = events.some((e) => e.type === "approval.requested" && (e as { approval?: { status?: string } }).approval?.status === "expired");
    record("NS expiry sweep marks expired", swept === 1 && expiredCard && be.count() === 0, `swept=${swept} card=${expiredCard} n=${be.count()}`);
    unsub();
  }

  return results;
}
