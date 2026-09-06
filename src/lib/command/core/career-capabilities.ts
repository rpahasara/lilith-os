/**
 * Career read-only capabilities for Vertical Slice 2. Same contract as Slice 1;
 * each validates the real backend shape (a 200 is never trusted blindly).
 */
import type { Capability, CapabilityResult, CoreTransport, TransportResult } from "./types";
import { executionId } from "./ids";

function classify(res: TransportResult): "network" | "timeout" | "5xx" | "4xx" | undefined {
  if (res.ok) return undefined;
  if (res.status === 0) return /timeout|abort/i.test(res.error ?? "") ? "timeout" : "network";
  if (res.status >= 500) return "5xx";
  if (res.status >= 400) return "4xx";
  return "network";
}

async function call<T>(
  transport: CoreTransport,
  path: string,
  validate: (d: unknown) => T | null,
  signal: AbortSignal | undefined,
  prefix: string,
): Promise<CapabilityResult<T>> {
  const startedAt = Date.now();
  const eid = executionId(prefix);
  const res = await transport(path, signal);
  const endedAt = Date.now();
  if (!res.ok) {
    return { ok: false, data: null, status: res.status, errorKind: classify(res), error: res.error ?? `HTTP ${res.status}`, executionId: eid, source: path, startedAt, endedAt };
  }
  const v = validate(res.data);
  if (v == null) {
    return { ok: false, data: null, status: res.status, errorKind: "malformed", error: "response did not match the expected shape", executionId: eid, source: path, startedAt, endedAt };
  }
  return { ok: true, data: v, status: res.status, executionId: eid, source: path, startedAt, endedAt };
}

/* ------------------------------------------------------------------- types */

export interface CareerApplication {
  id: number;
  company: string;
  role: string;
  stage: string;
  sourceAccount: string;
  confidence: number; // 0..1
  firstSeen?: string;
  lastActivity?: string;
  activities: number;
  lastActivitySummary?: string;
  recruiter?: { name?: string; contact?: string };
}

export interface CareerActivity {
  id: number;
  applicationId: number | null;
  activityType: string;
  title: string;
  occurredAt?: string;
  company?: string;
  role?: string;
}

export type CareerPipeline = Record<string, number>;

/* -------------------------------------------------------------- validators */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toNum(v: any): number | null {
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function validateApplications(data: any): CareerApplication[] | null {
  const rows = Array.isArray(data) ? data : Array.isArray(data?.applications) ? data.applications : null;
  if (!rows) return null;
  const out: CareerApplication[] = [];
  for (const r of rows) {
    const id = toNum(r?.id ?? r?.application_id);
    if (id == null) return null; // malformed record → whole payload invalid
    out.push({
      id,
      company: String(r.company ?? "Unknown"),
      role: String(r.role ?? "Role"),
      stage: String(r.stage ?? r.status ?? "discovered"),
      sourceAccount: String(r.source_account ?? r.source ?? "—"),
      confidence: toNum(r.confidence ?? r.score) ?? 0,
      firstSeen: r.first_seen ? String(r.first_seen) : undefined,
      lastActivity: r.last_activity ? String(r.last_activity) : undefined,
      activities: toNum(r.activities) ?? 0,
      lastActivitySummary: r.last_activity_summary ? String(r.last_activity_summary) : undefined,
      recruiter: r.recruiter
        ? { name: r.recruiter.name ? String(r.recruiter.name) : undefined, contact: r.recruiter.contact ? String(r.recruiter.contact) : undefined }
        : undefined,
    });
  }
  return out;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function validatePipeline(data: any): CareerPipeline | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const out: CareerPipeline = {};
  for (const [k, v] of Object.entries(data)) {
    const n = toNum(v);
    if (n != null) out[k] = n;
  }
  return out;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function validateActivity(data: any): CareerActivity[] | null {
  const rows = Array.isArray(data) ? data : Array.isArray(data?.events) ? data.events : null;
  if (!rows) return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return rows.map((r: any, i: number) => ({
    id: toNum(r?.id) ?? i,
    applicationId: toNum(r?.application_id ?? r?.applicationId),
    activityType: String(r?.activity_type ?? r?.type ?? "activity"),
    title: String(r?.title ?? r?.text ?? ""),
    occurredAt: r?.occurred_at ? String(r.occurred_at) : r?.time ? String(r.time) : undefined,
    company: r?.company ? String(r.company) : undefined,
    role: r?.role ? String(r.role) : undefined,
  }));
}

/* ----------------------------------------------------------- capabilities */

const RETRY = { maxAttempts: 2, retryOn: ["network", "timeout", "5xx"] as Array<"network" | "timeout" | "5xx"> };

export const careerListApplicationsCapability: Capability<CareerApplication[]> = {
  id: "career.list_applications",
  version: "1.0.0",
  title: "List job applications",
  permission: "read",
  classification: "read-only",
  timeoutMs: 10_000,
  retry: RETRY,
  sideEffects: "none",
  async checkHealth(transport, signal) {
    const res = await transport("/career/applications", signal);
    return res.ok ? { healthy: true } : { healthy: false, detail: res.error ?? `HTTP ${res.status}` };
  },
  execute(transport, signal) {
    return call(transport, "/career/applications", validateApplications, signal, "car-app");
  },
};

export const careerGetPipelineCapability: Capability<CareerPipeline> = {
  id: "career.get_pipeline",
  version: "1.0.0",
  title: "Career pipeline snapshot",
  permission: "read",
  classification: "read-only",
  timeoutMs: 10_000,
  retry: RETRY,
  sideEffects: "none",
  async checkHealth(transport, signal) {
    const res = await transport("/career/pipeline", signal);
    return res.ok ? { healthy: true } : { healthy: false, detail: res.error ?? `HTTP ${res.status}` };
  },
  execute(transport, signal) {
    return call(transport, "/career/pipeline", validatePipeline, signal, "car-pipe");
  },
};

export const careerGetActivityCapability: Capability<CareerActivity[]> = {
  id: "career.get_activity",
  version: "1.0.0",
  title: "Recent career activity",
  permission: "read",
  classification: "read-only",
  timeoutMs: 10_000,
  retry: RETRY,
  sideEffects: "none",
  async checkHealth(transport, signal) {
    const res = await transport("/career/activity", signal);
    return res.ok ? { healthy: true } : { healthy: false, detail: res.error ?? `HTTP ${res.status}` };
  },
  execute(transport, signal) {
    return call(transport, "/career/activity", validateActivity, signal, "car-act");
  },
};

export const CAREER_CAPABILITIES: Capability[] = [
  careerListApplicationsCapability as Capability,
  careerGetPipelineCapability as Capability,
  careerGetActivityCapability as Capability,
];
