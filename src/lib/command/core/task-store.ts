/**
 * Durable task store for real Cognitive-Core tasks (Vertical Slice 3).
 *
 * The authoritative store is now the LILITH/Hermes backend (SQLite behind the
 * FastAPI `/os/tasks` API, reached through the same-origin write proxy at
 * `/api/lilith/tasks`). {@link RemoteTaskStore} is the production implementation;
 * the backend is the source of truth and always wins over the local mirror.
 *
 * The interface is async (a backend round-trip cannot be synchronous) and adds
 * optimistic-concurrency (`revision`) + idempotency (`operationId`) semantics.
 * A small localStorage cache is kept ONLY for startup responsiveness, degraded
 * display, and one-time migration of legacy browser-local history — it is
 * clearly secondary and never presented as durable persistence.
 *
 * {@link InMemoryTaskStore} is a faithful in-memory emulation of the backend
 * contract (revision, idempotent create/update, conflict, transition safety)
 * used by the deterministic self-tests and SSR — it never touches the network.
 * Demo/fixture tasks are never written here; only RealCommandCore persists.
 */
import type { CoreTaskRecord, CoreTaskStatus } from "./types";

export const TASK_SCHEMA_VERSION = 1;

/* ------------------------------------------------------------ persistence io */

export type PersistErrorKind =
  | "network"
  | "timeout"
  | "5xx"
  | "4xx"
  | "conflict"
  | "malformed";

export interface PersistOutcome {
  ok: boolean;
  /** True only when the write is durably confirmed by the authoritative store. */
  persisted: boolean;
  /** Authoritative revision after the write (or the current one on conflict). */
  revision?: number;
  /** For updates: false when the backend replayed an already-applied operation. */
  applied?: boolean;
  /** Present on a stale-revision conflict — the caller should adopt `current`. */
  conflict?: { current: CoreTaskRecord; revision: number };
  errorKind?: PersistErrorKind;
  error?: string;
}

export interface LoadResult {
  records: CoreTaskRecord[];
  /** "backend" = authoritative; "cache" = degraded local mirror (stale). */
  source: "backend" | "cache";
  stale: boolean;
}

export interface TaskStore {
  /** One-time init (legacy migration + cache warmup). Idempotent; safe to await repeatedly. */
  init?(): Promise<void>;
  create(record: CoreTaskRecord, operationId?: string): Promise<PersistOutcome>;
  update(
    record: CoreTaskRecord,
    expectedRevision: number,
    operationId?: string,
  ): Promise<PersistOutcome>;
  loadAll(): Promise<LoadResult>;
  get(taskId: string): Promise<CoreTaskRecord | undefined>;
  clear(): Promise<void>;
}

/* --------------------------------------------------------------- shared rules */

const TERMINAL: ReadonlySet<CoreTaskStatus> = new Set([
  "succeeded",
  "partial",
  "failed",
  "cancelled",
]);
const STATUSES: ReadonlySet<string> = new Set<CoreTaskStatus>([
  "created", "assembling_context", "planning", "capability_check", "running",
  "verifying", "cancel_requested", "succeeded", "partial", "failed",
  "cancelled", "blocked",
]);
const APPROVALS = new Set(["not_required", "required", "approved", "denied", "expired"]);
const TASK_ID_RE = /^[A-Za-z0-9._:-]{1,128}$/;

/** Reject terminal→active regressions unless it is an explicit new attempt. */
function transitionOk(
  oldStatus: CoreTaskStatus,
  oldAttempt: number,
  newStatus: CoreTaskStatus,
  newAttempt: number,
): boolean {
  if (TERMINAL.has(oldStatus) && !TERMINAL.has(newStatus)) return newAttempt > oldAttempt;
  return true;
}

/** Validate + normalize a candidate record; returns null if unusable. */
export function validateRecord(raw: unknown): CoreTaskRecord | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.taskId !== "string" || !TASK_ID_RE.test(r.taskId)) return null;
  if (typeof r.status !== "string" || !STATUSES.has(r.status)) return null;
  const sv = typeof r.schemaVersion === "number" ? r.schemaVersion : TASK_SCHEMA_VERSION;
  if (sv > TASK_SCHEMA_VERSION) return null; // unknown newer version fails safely
  if (typeof r.createdAt !== "number" || typeof r.updatedAt !== "number") return null;
  const appr = typeof r.approvalState === "string" ? r.approvalState : "not_required";
  if (!APPROVALS.has(appr)) return null;
  return { ...(raw as CoreTaskRecord), schemaVersion: sv };
}

function withMeta(record: CoreTaskRecord, revision?: number): CoreTaskRecord {
  const out: CoreTaskRecord = { ...record, schemaVersion: TASK_SCHEMA_VERSION };
  if (revision != null) out.revision = revision;
  return out;
}

const byCreated = (a: CoreTaskRecord, b: CoreTaskRecord) => a.createdAt - b.createdAt;

/* ------------------------------------------------------------------ transport */

export interface TaskHttpResult {
  ok: boolean;
  status: number;
  data: unknown;
}
/** HTTP seam to the task proxy. Tests inject an in-memory backend emulation. */
export type TaskHttp = (
  method: "GET" | "POST" | "PATCH",
  path: string,
  body?: unknown,
) => Promise<TaskHttpResult>;

const TASKS_BASE = "/api/lilith/tasks";

export const fetchTaskHttp: TaskHttp = async (method, path, body) => {
  try {
    const res = await fetch(`${TASKS_BASE}${path}`, {
      method,
      headers: { "content-type": "application/json", accept: "application/json" },
      body: body != null ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { error: e instanceof Error ? e.message : "network" } };
  }
};

function classify(status: number): PersistErrorKind {
  if (status === 0) return "network";
  if (status === 408) return "timeout";
  if (status === 409) return "conflict";
  if (status >= 500) return "5xx";
  return "4xx";
}
function errMsg(r: TaskHttpResult): string {
  const d = r.data as { error?: string; detail?: unknown } | null;
  if (d && typeof d.error === "string") return d.error;
  if (d && typeof d.detail === "string") return d.detail;
  return `HTTP ${r.status}`;
}

/* ---------------------------------------------------------- local mirror (KV) */

export interface KV {
  get(key: string): string | null;
  set(key: string, value: string): void;
  remove(key: string): void;
}
export function localStorageKV(): KV | null {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    const ls = window.localStorage;
    return {
      get: (k) => {
        try {
          return ls.getItem(k);
        } catch {
          return null;
        }
      },
      set: (k, v) => {
        try {
          ls.setItem(k, v);
        } catch {
          /* quota / unavailable */
        }
      },
      remove: (k) => {
        try {
          ls.removeItem(k);
        } catch {
          /* ignore */
        }
      },
    };
  } catch {
    return null;
  }
}

const LEGACY_KEY = "lilith-os:core-tasks";
const CACHE_KEY = "lilith-os:core-tasks-cache:v1";
const MIGRATED_KEY = "lilith-os:core-tasks-migrated:v1";
const CACHE_MAX = 50;

export interface RemoteTaskStoreConfig {
  request?: TaskHttp;
  /** localStorage-like mirror; pass null to disable the local cache entirely. */
  kv?: KV | null;
  log?: (op: string, fields: Record<string, unknown>) => void;
}

export class RemoteTaskStore implements TaskStore {
  private request: TaskHttp;
  private kv: KV | null;
  private log: (op: string, fields: Record<string, unknown>) => void;
  private inited = false;
  private initPromise: Promise<void> | null = null;

  constructor(config: RemoteTaskStoreConfig = {}) {
    this.request = config.request ?? fetchTaskHttp;
    this.kv = config.kv === undefined ? localStorageKV() : config.kv;
    this.log = config.log ?? (() => {});
  }

  /* ---- authoritative writes ---- */

  async create(record: CoreTaskRecord, operationId?: string): Promise<PersistOutcome> {
    const r = await this.request("POST", "", { record: withMeta(record), operationId });
    if (r.ok) {
      const d = r.data as { task?: CoreTaskRecord; revision?: number; created?: boolean };
      const task = d?.task;
      const revision = d?.revision ?? task?.revision ?? 1;
      if (task) this.cachePut(task);
      return { ok: true, persisted: true, revision, applied: d?.created !== false };
    }
    return { ok: false, persisted: false, errorKind: classify(r.status), error: errMsg(r) };
  }

  async update(
    record: CoreTaskRecord,
    expectedRevision: number,
    operationId?: string,
  ): Promise<PersistOutcome> {
    const id = record.taskId;
    const r = await this.request("PATCH", `/${encodeURIComponent(id)}`, {
      record: withMeta(record),
      expectedRevision,
      operationId,
    });
    if (r.ok) {
      const d = r.data as { task?: CoreTaskRecord; revision?: number; applied?: boolean };
      if (d?.task) this.cachePut(d.task);
      return {
        ok: true,
        persisted: true,
        revision: d?.revision ?? d?.task?.revision,
        applied: d?.applied !== false,
      };
    }
    if (r.status === 409) {
      // FastAPI wraps a dict `detail`.
      const detail =
        (r.data as { detail?: { error?: string; current?: CoreTaskRecord; revision?: number } })
          ?.detail ?? (r.data as { error?: string; current?: CoreTaskRecord; revision?: number });
      if (detail?.error === "revision_conflict" && detail.current) {
        this.cachePut(detail.current);
        return {
          ok: false,
          persisted: false,
          errorKind: "conflict",
          revision: detail.revision,
          conflict: { current: detail.current, revision: detail.revision ?? 0 },
        };
      }
      return { ok: false, persisted: false, errorKind: "conflict", error: detail?.error ?? "conflict" };
    }
    return { ok: false, persisted: false, errorKind: classify(r.status), error: errMsg(r) };
  }

  /* ---- reads (backend wins; cache only when unreachable) ---- */

  async loadAll(): Promise<LoadResult> {
    const r = await this.request("GET", "?limit=50");
    if (r.ok) {
      const tasks = ((r.data as { tasks?: CoreTaskRecord[] })?.tasks ?? []).filter(Boolean);
      this.cacheReplace(tasks);
      return { records: [...tasks].sort(byCreated), source: "backend", stale: false };
    }
    const cached = this.cacheRead();
    return { records: cached, source: "cache", stale: true };
  }

  async get(taskId: string): Promise<CoreTaskRecord | undefined> {
    const r = await this.request("GET", `/${encodeURIComponent(taskId)}`);
    if (r.ok) {
      const t = (r.data as { task?: CoreTaskRecord })?.task;
      if (t) this.cachePut(t);
      return t;
    }
    return this.cacheRead().find((t) => t.taskId === taskId);
  }

  async clear(): Promise<void> {
    // Only the local mirror is cleared here — backend history is durable and
    // never destroyed from the client (there is no delete capability).
    this.kv?.remove(CACHE_KEY);
  }

  /* ---- one-time legacy migration ---- */

  init(): Promise<void> {
    if (this.inited) return this.initPromise ?? Promise.resolve();
    this.inited = true;
    this.initPromise = this.doInit();
    return this.initPromise;
  }

  private async doInit(): Promise<void> {
    if (!this.kv) return;
    if (this.kv.get(MIGRATED_KEY)) return; // already migrated
    const rawLegacy = this.kv.get(LEGACY_KEY);
    if (!rawLegacy) {
      this.kv.set(MIGRATED_KEY, String(Date.now()));
      return;
    }
    let legacy: unknown;
    try {
      legacy = JSON.parse(rawLegacy);
    } catch {
      legacy = null;
    }
    if (!Array.isArray(legacy)) {
      this.log("migrate.skip", { reason: "not-array" });
      this.kv.set(MIGRATED_KEY, String(Date.now()));
      return;
    }
    let migrated = 0;
    let skipped = 0;
    for (const raw of legacy) {
      const rec = validateRecord(raw);
      // Only real core history migrates — demo/simulated + malformed never do.
      if (!rec || rec.source !== "core") {
        skipped++;
        continue;
      }
      const out = await this.create(rec, `migrate:${rec.taskId}`); // idempotent by taskId
      if (!out.ok) {
        // Backend unreachable mid-migration: abort and retry on a later load.
        // The migrated flag is NOT set, so nothing is lost; create is idempotent.
        this.log("migrate.abort", { migrated, skipped, reason: out.errorKind });
        return;
      }
      migrated++;
    }
    this.log("migrate.done", { migrated, skipped });
    // Downgrade legacy storage: fold into the secondary cache, drop the old key.
    this.kv.remove(LEGACY_KEY);
    this.kv.set(MIGRATED_KEY, String(Date.now()));
  }

  /* ---- secondary cache helpers ---- */

  private cacheRead(): CoreTaskRecord[] {
    if (!this.kv) return [];
    const raw = this.kv.get(CACHE_KEY);
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as CoreTaskRecord[]).sort(byCreated) : [];
    } catch {
      return [];
    }
  }
  private cacheWrite(list: CoreTaskRecord[]) {
    if (!this.kv) return;
    const trimmed = [...list].sort((a, b) => a.updatedAt - b.updatedAt).slice(-CACHE_MAX);
    this.kv.set(CACHE_KEY, JSON.stringify(trimmed));
  }
  private cachePut(task: CoreTaskRecord) {
    if (!this.kv) return;
    const map = new Map(this.cacheRead().map((t) => [t.taskId, t]));
    map.set(task.taskId, task);
    this.cacheWrite([...map.values()]);
  }
  private cacheReplace(tasks: CoreTaskRecord[]) {
    if (!this.kv) return;
    this.cacheWrite(tasks);
  }
}

/* ------------------------------------------------------- in-memory emulation */

/**
 * Faithful in-memory emulation of the backend `/os/tasks` contract: monotonic
 * revision, idempotent create (by taskId) and update (by operationId), stale-
 * revision 409 conflicts, and terminal→active transition rejection. Backs the
 * deterministic self-tests and the SSR default. Optional failure injection
 * lets tests exercise degraded + bounded-retry behaviour.
 */
export interface TaskBackend {
  http: TaskHttp;
  /** Inject a row as if written by another client (for restart / conflict tests). */
  seed(record: CoreTaskRecord, revision?: number, operationId?: string): void;
  /** Bump a task's revision out from under a client (to force a stale conflict). */
  bump(taskId: string): void;
  setMode(mode: { offline?: boolean; failCreates?: number; failUpdates?: number }): void;
  count(): number;
  snapshot(): CoreTaskRecord[];
}

interface Row {
  rec: CoreTaskRecord;
  revision: number;
  lastOp?: string;
}

export function createTaskBackend(): TaskBackend {
  const rows = new Map<string, Row>();
  const mode = { offline: false, failCreates: 0, failUpdates: 0 };

  const store = (rec: CoreTaskRecord, revision: number, lastOp?: string) => {
    rows.set(rec.taskId, { rec: withMeta(rec, revision), revision, lastOp });
  };
  const out = (row: Row) => ({ task: withMeta(row.rec, row.revision), revision: row.revision });

  const http: TaskHttp = async (method, path, body) => {
    if (mode.offline) return { ok: false, status: 0, data: { error: "offline" } };
    const b = (body ?? {}) as { record?: CoreTaskRecord; expectedRevision?: number; operationId?: string };

    // POST "" — create
    if (method === "POST") {
      if (mode.failCreates > 0) {
        mode.failCreates--;
        return { ok: false, status: 503, data: { error: "transient" } };
      }
      const rec = validateRecord(b.record);
      if (!rec) return { ok: false, status: 422, data: { detail: "invalid record" } };
      const existing = rows.get(rec.taskId);
      if (existing) return { ok: true, status: 200, data: { ...out(existing), created: false } };
      store(rec, 1, b.operationId);
      return { ok: true, status: 200, data: { ...out(rows.get(rec.taskId)!), created: true } };
    }

    // GET
    if (method === "GET") {
      if (path === "" || path.startsWith("?")) {
        const list = [...rows.values()].map((r) => withMeta(r.rec, r.revision)).sort((a, b) => b.createdAt - a.createdAt);
        return { ok: true, status: 200, data: { tasks: list, count: list.length } };
      }
      const id = decodeURIComponent(path.replace(/^\//, ""));
      const row = rows.get(id);
      if (!row) return { ok: false, status: 404, data: { detail: "not found" } };
      return { ok: true, status: 200, data: out(row) };
    }

    // PATCH "/{id}" — update
    if (method === "PATCH") {
      const id = decodeURIComponent(path.replace(/^\//, ""));
      const row = rows.get(id);
      if (!row) return { ok: false, status: 404, data: { detail: "not found" } };
      if (b.operationId && row.lastOp === b.operationId) {
        return { ok: true, status: 200, data: { ...out(row), applied: false } };
      }
      if (mode.failUpdates > 0) {
        mode.failUpdates--;
        return { ok: false, status: 503, data: { error: "transient" } };
      }
      const rec = validateRecord(b.record);
      if (!rec) return { ok: false, status: 422, data: { detail: "invalid record" } };
      if (b.expectedRevision != null && b.expectedRevision !== row.revision) {
        return {
          ok: false,
          status: 409,
          data: { detail: { error: "revision_conflict", current: out(row).task, revision: row.revision } },
        };
      }
      const oldAttempt = row.rec.attemptCount ?? 0;
      const newAttempt = rec.attemptCount ?? 0;
      if (!transitionOk(row.rec.status, oldAttempt, rec.status, newAttempt)) {
        return { ok: false, status: 409, data: { detail: { error: "illegal_transition", from: row.rec.status, to: rec.status } } };
      }
      const nextRev = row.revision + 1;
      store(rec, nextRev, b.operationId ?? row.lastOp);
      return { ok: true, status: 200, data: { ...out(rows.get(id)!), applied: true } };
    }
    return { ok: false, status: 405, data: { detail: "method not allowed" } };
  };

  return {
    http,
    seed: (rec, revision = 1, operationId) => store(rec, revision, operationId),
    bump: (taskId) => {
      const row = rows.get(taskId);
      if (row) row.revision += 1;
    },
    setMode: (m) => Object.assign(mode, m),
    count: () => rows.size,
    snapshot: () => [...rows.values()].map((r) => withMeta(r.rec, r.revision)),
  };
}

/** In-memory store (fresh backend, no local cache) for tests / SSR. */
export class InMemoryTaskStore extends RemoteTaskStore {
  readonly backend: TaskBackend;
  constructor(backend: TaskBackend = createTaskBackend()) {
    super({ request: backend.http, kv: null });
    this.backend = backend;
  }
}
