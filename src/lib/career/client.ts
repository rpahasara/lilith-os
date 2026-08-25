/**
 * Career API client.
 *
 * Fetches live data from the LILITH backend (via the shared proxy/direct layer
 * in `@/lib/api`) and normalises it to the domain types. When the backend is
 * unreachable it falls back to the isolated demo adapter. Live and demo data
 * are never mixed: if only some live endpoints respond, missing pieces are
 * DERIVED from the live applications, not borrowed from demo.
 */
import { buildDemoCareerData } from "./demo";
import {
  STAGES,
  TERMINAL_STAGES,
  type Application,
  type CareerData,
  type Stage,
  type ActivityEvent,
  type Insight,
  type PipelineStage,
} from "./types";
import { fetchEndpoint, toDiagnostics, type EndpointResult } from "@/lib/api";

const ALL_STAGES: string[] = [...STAGES, ...TERMINAL_STAGES];

function asStage(v: unknown): Stage {
  return typeof v === "string" && ALL_STAGES.includes(v)
    ? (v as Stage)
    : "discovered";
}

function num(v: unknown, fallback = 0): number {
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? n : fallback;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Contact linked to an application. The backend sends {name, contact} where
 * name may be null (email-only). This is raw CRM contact data, NOT a guaranteed
 * human recruiter — presented as-is, never reinterpreted.
 */
function normalizeRecruiter(raw: any) {
  if (!raw) return undefined;
  const rec = typeof raw === "string" ? { name: raw } : raw;
  const name = rec.name ? String(rec.name) : undefined;
  const contact = rec.contact ? String(rec.contact) : undefined;
  if (!name && !contact) return undefined;
  return {
    name,
    role: rec.role ? String(rec.role) : undefined,
    contact,
  };
}

function normalizeApplication(r: any): Application {
  const rawConfidence = num(r.confidence ?? r.score, 0);
  return {
    id: String(r.id ?? r.application_id ?? Math.random().toString(36).slice(2)),
    company: String(r.company ?? r.company_name ?? "Unknown"),
    role: String(r.role ?? r.title ?? r.position ?? "Role"),
    stage: asStage(r.stage ?? r.status),
    // accept confidence as either 0–1 or 0–100
    confidence: Math.round(rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence),
    sourceAccount: String(r.source_account ?? r.source ?? r.account ?? "—"),
    activityCount: num(r.activity_count ?? r.activities ?? r.events, 0),
    lastActivity: String(
      r.last_activity ?? r.last_activity_at ?? r.updated_at ?? new Date(0).toISOString(),
    ),
    lastActivityLabel: String(
      r.last_activity_label ?? r.last_activity_summary ?? r.summary ?? "—",
    ),
    location: r.location ? String(r.location) : undefined,
    recruiter: normalizeRecruiter(r.recruiter),
    nextAction: r.next_action
      ? {
          label: String(r.next_action.label ?? r.next_action),
          due: r.next_action.due ? String(r.next_action.due) : undefined,
        }
      : undefined,
    followUp: Boolean(r.follow_up ?? r.needs_follow_up),
  };
}

/**
 * Build a stage→count map from the /career/pipeline payload, which may arrive
 * as an array [{stage,count}] OR an object map {applied: 6}. Unknown shapes
 * yield an empty map so the caller can derive from applications instead.
 */
function pipelineCountsFrom(rows: any): Map<Stage, number> {
  const m = new Map<Stage, number>();
  const add = (stage: unknown, count: unknown) => {
    if (typeof stage === "string" && ALL_STAGES.includes(stage)) {
      m.set(stage as Stage, num(count, 0));
    }
  };
  if (Array.isArray(rows)) {
    for (const r of rows) add(r.stage ?? r.name, r.count ?? r.total);
  } else if (rows && typeof rows === "object") {
    const obj = rows.stages && typeof rows.stages === "object" ? rows.stages : rows;
    if (Array.isArray(obj)) {
      for (const r of obj) add(r.stage ?? r.name, r.count ?? r.total);
    } else {
      for (const [k, v] of Object.entries(obj)) {
        if (typeof v === "number" || (typeof v === "string" && !isNaN(Number(v)))) {
          add(k, v);
        }
      }
    }
  }
  return m;
}

/** Always emit the full ordered stage scaffold so the funnel renders every column. */
function toFullPipeline(counts: Map<Stage, number>): PipelineStage[] {
  return STAGES.map((stage) => ({ stage, count: counts.get(stage) ?? 0 }));
}

function normalizeActivity(rows: any): ActivityEvent[] {
  const list = Array.isArray(rows) ? rows : (rows?.events ?? []);
  return list.map((r: any, i: number) => ({
    id: String(r.id ?? i),
    time: String(r.time ?? r.timestamp ?? r.created_at ?? new Date(0).toISOString()),
    text: String(r.text ?? r.message ?? r.summary ?? ""),
    company: r.company ? String(r.company) : undefined,
    kind: (r.kind ?? r.type ?? "system") as ActivityEvent["kind"],
  }));
}

function normalizeInsights(rows: any): Insight[] {
  const list = Array.isArray(rows)
    ? rows
    : (rows?.insights ?? rows?.career_insights ?? []);
  return list.map((r: any, i: number) => ({
    id: String(r.id ?? i),
    title: String(r.title ?? r.headline ?? ""),
    detail: String(r.detail ?? r.body ?? ""),
    tone: (r.tone ?? "info") as Insight["tone"],
  }));
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/** Count stages directly from applications (fallback when pipeline is absent). */
function countsFromApps(apps: Application[]): Map<Stage, number> {
  const m = new Map<Stage, number>();
  for (const a of apps) {
    if ((STAGES as readonly string[]).includes(a.stage)) {
      m.set(a.stage, (m.get(a.stage) ?? 0) + 1);
    }
  }
  return m;
}

/**
 * The /career/applications rows carry no activity summary, but /career/activity
 * does. Build a map of applicationId → latest activity title/time so we can fill
 * lastActivityLabel with real backend data (never invented).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function latestActivityByApp(rawActivity: any): Map<string, { title: string; at: string }> {
  const list = Array.isArray(rawActivity)
    ? rawActivity
    : (rawActivity?.events ?? []);
  const map = new Map<string, { title: string; at: string }>();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  for (const r of list as any[]) {
    const appId = String(r.application_id ?? r.applicationId ?? "");
    if (!appId) continue;
    const at = String(r.occurred_at ?? r.time ?? r.timestamp ?? "");
    const title = String(r.title ?? r.text ?? r.message ?? "");
    const prev = map.get(appId);
    if (!prev || new Date(at).getTime() > new Date(prev.at).getTime()) {
      map.set(appId, { title, at });
    }
  }
  return map;
}

/**
 * Fetch everything the Career screen needs. Never throws — resolves to usable
 * data, falling back to the demo adapter when the backend is absent.
 */
export async function getCareerData(signal?: AbortSignal): Promise<CareerData> {
  const paths = [
    "/career/applications",
    "/career/pipeline",
    "/career/activity",
    "/os/overview",
  ];

  const [appsRes, pipeRes, actRes, ovRes] = (await Promise.all(
    paths.map((p) => fetchEndpoint(p, signal)),
  )) as EndpointResult[];

  const results = [appsRes, pipeRes, actRes, ovRes];

  // Applications are the backbone. Without them we serve demo data.
  if (!appsRes.ok || appsRes.data == null) {
    const demo = buildDemoCareerData();
    demo.diagnostics = toDiagnostics("demo", results);
    return demo;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawApps: any = appsRes.data;
  const applications: Application[] = (rawApps.applications ?? rawApps ?? []).map(
    normalizeApplication,
  );

  // Enrich each application's last-activity label from the real activity feed.
  const activityByApp = actRes.ok ? latestActivityByApp(actRes.data) : new Map();
  for (const app of applications) {
    if (app.lastActivityLabel === "—") {
      const hit = activityByApp.get(app.id);
      if (hit?.title) app.lastActivityLabel = hit.title;
    }
  }

  const active = applications.filter(
    (a: Application) => !(TERMINAL_STAGES as readonly string[]).includes(a.stage),
  );

  // Pipeline: prefer the backend endpoint (array OR {stage:count} map); fall
  // back to counting applications. Always emit the full stage scaffold.
  let counts = pipeRes.ok ? pipelineCountsFrom(pipeRes.data) : new Map<Stage, number>();
  if (counts.size === 0) counts = countsFromApps(applications);
  const pipeline = toFullPipeline(counts);

  const activity = actRes.ok ? normalizeActivity(actRes.data) : [];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ov: any = ovRes.ok ? (ovRes.data ?? {}) : {};

  return {
    isDemo: false,
    diagnostics: toDiagnostics("live", results),
    applications,
    pipeline,
    activity,
    insights: normalizeInsights(ov),
    overview: {
      totalActive: num(ov.active ?? ov.total_active, active.length),
      offers: num(
        ov.offers,
        applications.filter((a: Application) => a.stage === "offer").length,
      ),
      interviews: num(
        ov.interviews,
        applications.filter((a: Application) =>
          ["interview", "final_interview"].includes(a.stage),
        ).length,
      ),
      responseRate: num(ov.response_rate ?? ov.responseRate, 0),
      pipelineHealth: num(
        ov.pipeline_health ?? ov.pipelineHealth,
        Math.round(
          active.reduce((s: number, a: Application) => s + a.confidence, 0) /
            Math.max(active.length, 1),
        ),
      ),
    },
  };
}
