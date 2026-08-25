/**
 * Automations API client.
 *
 * Reads live systemd/service state from the LILITH backend and normalises it to
 * the domain types. Falls back to the isolated demo adapter when unreachable.
 * Live and demo are never mixed — missing live pieces are derived from the live
 * units, not borrowed from demo.
 */
import { buildDemoAutomationsData } from "./demo";
import type {
  AutomationEvent,
  AutomationInsight,
  AutomationUnit,
  AutomationsData,
  RunOutcome,
  TriggerType,
  UnitKind,
  UnitStatus,
} from "./types";
import { fetchEndpoint, toDiagnostics, type EndpointResult } from "@/lib/api";

/**
 * Static descriptions for the known Lilith units. These are documentation-level
 * name + purpose only — NOT runtime data. Cadence/schedule and trigger timing
 * are deliberately omitted because the backend does not expose them; presenting
 * a specific cadence here would be fabrication. The trigger *type* is derived
 * from the unit kind (classification), and `schedule` comes only from the
 * backend when it is actually provided.
 */
const KNOWN: Record<string, { name: string; purpose: string }> = {
  "lilith-os-api.service": {
    name: "Core API",
    purpose: "Serves the Lilith OS API — the backbone every module talks to.",
  },
  "hermes-gateway.service": {
    name: "Model Gateway",
    purpose: "Routes and load-balances every LLM call across providers.",
  },
  "lilith-gmail-watcher.timer": {
    name: "Gmail Watcher",
    purpose: "Monitors your inbox for career, meeting, and follow-up signals.",
  },
  "lilith-career-watcher.timer": {
    name: "Career Watcher",
    purpose: "Scans job sources and keeps the career pipeline up to date.",
  },
  "lilith-meeting-prep.timer": {
    name: "Meeting Prep",
    purpose: "Briefs you before each meeting with context and talking points.",
  },
  "lilith-morning-brief.timer": {
    name: "Morning Brief",
    purpose: "Assembles your daily brief — schedule, priorities, and focus.",
  },
};

function classifyKind(unit: string): UnitKind {
  if (unit.includes("watcher")) return "watcher";
  if (unit.includes("agent")) return "agent";
  if (unit.endsWith(".service")) return "service";
  if (unit.endsWith(".timer")) return "timer";
  return "service";
}

function titleize(unit: string) {
  return unit
    .replace(/\.(service|timer|socket|target)$/, "")
    .replace(/^lilith-/, "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function normalizeResult(v: unknown): RunOutcome | undefined {
  const s = String(v ?? "").toLowerCase();
  if (s === "success" || s === "ok" || s === "succeeded") return "success";
  if (s === "failure" || s === "failed" || s === "error") return "failure";
  if (s === "skip" || s === "skipped") return "skip";
  return undefined;
}

function deriveStatus(r: any, kind: UnitKind): UnitStatus {
  const active = String(r.active_state ?? r.activeState ?? r.state ?? "").toLowerCase();
  const sub = String(r.sub_state ?? r.subState ?? "").toLowerCase();
  const result = String(r.result ?? r.last_result ?? "").toLowerCase();

  if (active === "failed" || result === "failure" || result === "failed") return "failed";
  if (sub === "running") return "running";
  if (active === "inactive" || active === "dead" || r.enabled === false) {
    return kind === "service" ? "inactive" : "waiting";
  }
  if (active === "active") {
    // a running .service is "running"; an armed timer/watcher is "active"/"waiting"
    if (kind === "service") return sub === "running" ? "running" : "active";
    return sub === "waiting" ? "waiting" : "active";
  }
  return "active";
}

function normalizeUnit(r: any): AutomationUnit {
  const unit = String(r.unit ?? r.name ?? r.id ?? "unknown");
  const kind = (r.kind as UnitKind) ?? classifyKind(unit);
  const known = KNOWN[unit];
  const history = Array.isArray(r.history)
    ? (r.history.map((h: any) =>
        ["success", "failure", "skip"].includes(h) ? h : "success",
      ) as RunOutcome[])
    : undefined;
  const rawFail = r.failures ?? r.n_failures ?? r.n_restarts;

  return {
    id: unit,
    unit,
    name: known?.name ?? r.display_name ?? titleize(unit),
    kind,
    status: deriveStatus(r, kind),
    purpose: known?.purpose ?? r.purpose ?? r.description ?? "—",
    // trigger *type* is a classification from the unit kind (not fabricated
    // data); a specific schedule string is used only if the backend sends one.
    trigger:
      (r.trigger as TriggerType) ??
      (kind === "service" ? "continuous" : kind === "watcher" ? "event" : "schedule"),
    schedule: r.schedule ?? undefined,
    lastRun:
      r.last_run ?? r.last_trigger ?? r.exec_main_start ?? r.last_trigger_at ?? undefined,
    nextRun: r.next_run ?? r.next_trigger ?? r.next_elapse ?? undefined,
    // backend exposes `result` on each unit ("success" | "failure")
    lastResult: normalizeResult(r.last_result ?? r.result),
    // only report a failure count when the backend actually exposes one
    failures: rawFail == null ? undefined : Number(rawFail),
    runsToday: r.runs_today ?? r.runs ?? undefined,
    history,
    enabled:
      typeof r.enabled === "boolean"
        ? r.enabled
        : String(r.load_state ?? "loaded").toLowerCase() === "loaded",
  };
}

function collectUnits(raw: any): any[] {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw?.units)) return raw.units;
  const services = raw?.services ?? [];
  const timers = raw?.timers ?? [];
  if (services.length || timers.length) return [...services, ...timers];
  return [];
}

function normalizeActivity(raw: any): AutomationEvent[] {
  const list = Array.isArray(raw) ? raw : (raw?.events ?? raw?.entries ?? []);
  return list.slice(0, 12).map((r: any, i: number) => {
    // Audit/event rows (os_audit_log or career_events) carry action/entity, not
    // a prose message — compose a readable line from the real fields.
    let text = r.text ?? r.message ?? r.summary ?? "";
    if (!text && r.action) {
      const entity = r.entity_type
        ? ` · ${r.entity_type}${r.entity_id != null ? ` #${r.entity_id}` : ""}`
        : "";
      text = `${r.action}${entity}`;
    }
    return {
      id: String(r.id ?? i),
      time: String(r.time ?? r.timestamp ?? r.created_at ?? new Date(0).toISOString()),
      unit: String(r.unit ?? r.app ?? r.actor ?? r.source ?? r.service ?? "System"),
      text: String(text),
      outcome: (r.outcome ?? r.status ?? r.result ?? "info") as AutomationEvent["outcome"],
    };
  });
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function healthFrom(units: AutomationUnit[]) {
  const failed = units.filter((u) => u.status === "failed").length;
  return {
    total: units.length,
    running: units.filter((u) => u.status === "running").length,
    active: units.filter((u) => u.status === "active").length,
    waiting: units.filter((u) => u.status === "waiting").length,
    failed,
    score: units.length ? Math.round(((units.length - failed) / units.length) * 100) : 100,
  };
}

/** Surface degraded behaviour even when the backend sends no insights. */
function deriveInsights(units: AutomationUnit[]): AutomationInsight[] {
  const failed = units.filter((u) => u.status === "failed");
  if (failed.length === 0) {
    return [
      {
        id: "nominal",
        title: "All automations nominal",
        detail: "No failures across services, timers, watchers, or agents.",
        tone: "opportunity",
      },
    ];
  }
  return failed.map((u) => ({
    id: `fail-${u.id}`,
    title: `${u.name} failed its last run`,
    detail: `${u.unit} reported a failure. Check its logs — Lilith will retry on the next trigger.`,
    tone: "risk",
  }));
}

export async function getAutomationsData(
  signal?: AbortSignal,
): Promise<AutomationsData> {
  const paths = ["/system/status", "/os/overview", "/audit/recent"];
  const [statusRes, ovRes, auditRes] = (await Promise.all(
    paths.map((p) => fetchEndpoint(p, signal)),
  )) as EndpointResult[];
  const results = [statusRes, ovRes, auditRes];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ov: any = ovRes.ok ? (ovRes.data ?? {}) : {};

  // /system/status can be incomplete (it omits lilith-os-api.service), while
  // /os/overview.automations.services carries the full fleet. Merge both and
  // dedupe by unit name so every real unit is shown exactly once.
  const rawUnits = [
    ...collectUnits(statusRes.ok ? statusRes.data : null),
    ...(Array.isArray(ov?.automations?.services) ? ov.automations.services : []),
  ];
  const byUnit = new Map<string, any>();
  for (const r of rawUnits) {
    const key = String(r.unit ?? r.name ?? r.id ?? "");
    if (!key) continue;
    // keep the entry with the most fields (richer detail wins)
    const prev = byUnit.get(key);
    if (!prev || Object.keys(r).length > Object.keys(prev).length) byUnit.set(key, r);
  }
  const units = [...byUnit.values()].map(normalizeUnit);

  if (units.length === 0) {
    const demo = buildDemoAutomationsData();
    demo.diagnostics = toDiagnostics("demo", results);
    return demo;
  }
  const backendInsights = Array.isArray(ov.automation_insights)
    ? ov.automation_insights
    : Array.isArray(ov.insights)
      ? ov.insights
      : [];

  const activity = auditRes.ok
    ? normalizeActivity(auditRes.data)
    : normalizeActivity(ov?.recent_activity ?? []);

  // Derive running/active/waiting from real systemd sub-states; prefer the
  // backend's own total/healthy counts for the headline score when present.
  const health = healthFrom(units);
  const ovAuto = ov?.automations;
  if (ovAuto && typeof ovAuto.total === "number") {
    const total = ovAuto.total;
    const failed = Number(ovAuto.unhealthy ?? health.failed) || 0;
    health.total = total;
    health.failed = failed;
    health.score = total ? Math.round(((total - failed) / total) * 100) : 100;
  }

  return {
    isDemo: false,
    diagnostics: toDiagnostics("live", results),
    units,
    health,
    activity,
    insights:
      backendInsights.length > 0
        ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
          backendInsights.map((r: any, i: number) => ({
            id: String(r.id ?? i),
            title: String(r.title ?? r.headline ?? ""),
            detail: String(r.detail ?? r.body ?? ""),
            tone: (r.tone ?? "info") as AutomationInsight["tone"],
          }))
        : deriveInsights(units),
  };
}
