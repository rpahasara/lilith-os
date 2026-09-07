/**
 * Minimal capability registry for Vertical Slice 1 (system health summary).
 *
 * Two real, read-only capabilities. Each declares its contract, probes its own
 * health, and validates the backend response shape — a 200 alone is never
 * treated as success (the executor + verifier enforce this).
 */
import type {
  Capability,
  CapabilityResult,
  CoreTransport,
  TransportResult,
} from "./types";
import { executionId } from "./ids";
import { CAREER_CAPABILITIES } from "./career-capabilities";
import { CAREER_WRITE_CAPABILITIES } from "./career-write";
import { PROHIBITED_CAPABILITIES } from "./prohibited-capabilities";

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
  validate: (data: unknown) => T | null,
  signal: AbortSignal | undefined,
  execPrefix: string,
): Promise<CapabilityResult<T>> {
  const startedAt = Date.now();
  const eid = executionId(execPrefix);
  const res = await transport(path, signal);
  const endedAt = Date.now();
  if (!res.ok) {
    return {
      ok: false,
      data: null,
      status: res.status,
      errorKind: classify(res),
      error: res.error ?? `HTTP ${res.status}`,
      executionId: eid,
      source: path,
      startedAt,
      endedAt,
    };
  }
  const validated = validate(res.data);
  if (validated == null) {
    return {
      ok: false,
      data: null,
      status: res.status,
      errorKind: "malformed",
      error: "response did not match the expected shape",
      executionId: eid,
      source: path,
      startedAt,
      endedAt,
    };
  }
  return {
    ok: true,
    data: validated,
    status: res.status,
    executionId: eid,
    source: path,
    startedAt,
    endedAt,
  };
}

/* ------------------------------------------------------- os.get_overview */

export interface OsOverview {
  lilithStatus: string;
  osVersion?: string;
  automations: { total: number; healthy: number; unhealthy: number };
  careerApplications?: number;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function validateOverview(data: any): OsOverview | null {
  if (!data || typeof data !== "object" || !data.lilith) return null;
  const a = data.automations ?? {};
  return {
    lilithStatus: String(data.lilith.status ?? "unknown"),
    osVersion: data.lilith.os_version ? String(data.lilith.os_version) : undefined,
    automations: {
      total: Number(a.total ?? 0),
      healthy: Number(a.healthy ?? 0),
      unhealthy: Number(a.unhealthy ?? 0),
    },
    careerApplications: data.career?.applications != null ? Number(data.career.applications) : undefined,
  };
}

export const osOverviewCapability: Capability<OsOverview> = {
  id: "os.get_overview",
  version: "1.0.0",
  title: "LILITH OS overview",
  policyClass: "READ",
  classification: "read-only",
  timeoutMs: 10_000,
  retry: { maxAttempts: 2, retryOn: ["network", "timeout", "5xx"] },
  sideEffects: "none",
  async checkHealth(transport, signal) {
    const res = await transport("/os/overview", signal);
    return res.ok && !!(res.data as { lilith?: unknown })?.lilith
      ? { healthy: true }
      : { healthy: false, detail: res.error ?? `HTTP ${res.status}` };
  },
  execute(transport, signal) {
    return call(transport, "/os/overview", validateOverview, signal, "os-ov");
  },
};

/* ------------------------------------------------------ system.get_status */

export interface SystemUnit {
  unit: string;
  type: string;
  active: string;
  sub: string;
  result: string;
  restarts: number;
  serviceActive?: string;
  serviceSub?: string;
  lastRun?: string;
  nextRun?: string;
  schedule?: string;
}

export interface SystemStatus {
  timeUtc?: string;
  units: SystemUnit[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function validateStatus(data: any): SystemStatus | null {
  const rawUnits = Array.isArray(data?.services)
    ? data.services
    : Array.isArray(data)
      ? data
      : null;
  if (!rawUnits) return null;
  const units: SystemUnit[] = rawUnits
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((u: any) => u && typeof u.unit === "string")
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((u: any) => ({
      unit: String(u.unit),
      type: String(u.type ?? "unit"),
      active: String(u.active ?? "unknown"),
      sub: String(u.sub ?? ""),
      result: String(u.result ?? ""),
      restarts: Number(u.n_restarts ?? 0),
      serviceActive: u.service_active ? String(u.service_active) : undefined,
      serviceSub: u.service_sub ? String(u.service_sub) : undefined,
      lastRun: u.last_run ? String(u.last_run) : undefined,
      nextRun: u.next_run ? String(u.next_run) : undefined,
      schedule: u.schedule ? String(u.schedule) : undefined,
    }));
  if (units.length === 0) return null;
  return { timeUtc: data?.time_utc ? String(data.time_utc) : undefined, units };
}

export const systemStatusCapability: Capability<SystemStatus> = {
  id: "system.get_status",
  version: "1.0.0",
  title: "System & automation status",
  policyClass: "READ",
  classification: "read-only",
  timeoutMs: 10_000,
  retry: { maxAttempts: 2, retryOn: ["network", "timeout", "5xx"] },
  sideEffects: "none",
  async checkHealth(transport, signal) {
    const res = await transport("/system/status", signal);
    return res.ok ? { healthy: true } : { healthy: false, detail: res.error ?? `HTTP ${res.status}` };
  },
  execute(transport, signal) {
    return call(transport, "/system/status", validateStatus, signal, "sys-st");
  },
};

/* ---------------------------------------------------------------- registry */

export const CAPABILITY_REGISTRY: Record<string, Capability> = {
  [osOverviewCapability.id]: osOverviewCapability as Capability,
  [systemStatusCapability.id]: systemStatusCapability as Capability,
  ...Object.fromEntries(CAREER_CAPABILITIES.map((c) => [c.id, c])),
  ...Object.fromEntries(CAREER_WRITE_CAPABILITIES.map((c) => [c.id, c])),
  ...Object.fromEntries(PROHIBITED_CAPABILITIES.map((c) => [c.id, c])),
};

export function getCapability(id: string): Capability | undefined {
  return CAPABILITY_REGISTRY[id];
}

/** A unit is unhealthy if its service failed or it exited with a bad result. */
export function isUnitUnhealthy(u: SystemUnit): boolean {
  if (u.serviceActive === "failed") return true;
  if (u.active === "failed") return true;
  if (u.result && u.result !== "success" && u.result !== "") return true;
  return false;
}
