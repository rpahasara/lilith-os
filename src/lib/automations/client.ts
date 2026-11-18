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
import { demoDataEnabled, unavailable, type Loaded } from "@/lib/data-mode";

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
const word = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim().toLowerCase() : null);

/**
 * A run's outcome from systemd's `Result` word. systemd says "success" for a
 * clean run and names the failure otherwise ("exit-code", "signal", "timeout",
 * "core-dump", "oom-kill", "start-limit-hit"…), so any other word is a failure.
 */
export function normalizeResult(v: unknown): RunOutcome | undefined {
  const s = word(v);
  if (s === null) return undefined;
  if (s === "success" || s === "ok" || s === "succeeded") return "success";
  if (s === "skip" || s === "skipped") return "skip";
  return "failure";
}

/**
 * A unit's status from the fields the backend actually sends for it
 * (services/core-api `systemctl_state`): `available`, `active` (ActiveState),
 * `sub` (SubState), `result` (the last run's Result — for a timer, its paired
 * service's) and, for timers, `service_active` / `service_sub`. The same reading
 * as the System workspace (`unitState` in lib/system/platform):
 *
 *   - not readable, or no ActiveState  → unknown (never assumed healthy);
 *   - ActiveState failed, or a last run that did not succeed → failed;
 *   - a timer whose service is starting or running now → running;
 *     an armed timer → waiting (shown as "Scheduled"); otherwise inactive;
 *   - a service starting or running → running; other active → active;
 *     otherwise inactive.
 *
 * Whether a unit is a timer comes from its unit name (or the backend's `type`),
 * not from its display kind: a watcher is a timer too.
 */
export function deriveStatus(r: any): UnitStatus {
  if (r?.available === false) return "unknown";
  const active = word(r?.active ?? r?.active_state ?? r?.activeState);
  const sub = word(r?.sub ?? r?.sub_state ?? r?.subState);
  if (active === null) return "unknown";
  const outcome = normalizeResult(r?.result ?? r?.last_result);
  if (active === "failed" || outcome === "failure") return "failed";

  const timer = String(r?.unit ?? r?.name ?? "").endsWith(".timer") || word(r?.type) === "timer";
  if (timer) {
    const job = word(r?.service_active), jobSub = word(r?.service_sub);
    if (job === "activating" || job === "reloading" || jobSub === "running" || jobSub === "start") return "running";
    return active === "active" ? "waiting" : "inactive";
  }
  if (active === "activating" || active === "reloading" || sub === "running") return "running";
  if (active === "active") return "active";
  return "inactive";
}

export function normalizeUnit(r: any): AutomationUnit {
  const unit = String(r.unit ?? r.name ?? r.id ?? "unknown");
  const kind = (r.kind as UnitKind) ?? classifyKind(unit);
  const known = KNOWN[unit];
  const history = Array.isArray(r.history)
    ? (r.history.map((h: any) =>
        ["success", "failure", "skip"].includes(h) ? h : "success",
      ) as RunOutcome[])
    : undefined;
  // A failure count only when the backend sends one. `n_restarts` is systemd's
  // restart counter (always 0 for a oneshot job that fails every run), not a
  // failure count, so it is not shown as one.
  const rawFail = r.failures ?? r.n_failures;

  return {
    id: unit,
    unit,
    name: known?.name ?? r.display_name ?? titleize(unit),
    kind,
    status: deriveStatus(r),
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
    // systemd's Result word for the last run ("success", "exit-code", …)
    lastResult: normalizeResult(r.last_result ?? r.result),
    // only report a failure count when the backend actually exposes one
    failures: rawFail == null || !Number.isFinite(Number(rawFail)) ? undefined : Number(rawFail),
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

export function healthFrom(units: AutomationUnit[]) {
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

/**
 * Fetch everything the Automations screen needs. Never throws. When neither
 * source of units answers it resolves to `unavailable` — or to the sample
 * data, if `demo`. A backend that answers with no units is live and empty.
 */
export async function getAutomationsData(
  signal?: AbortSignal,
  demo: boolean = demoDataEnabled(),
): Promise<Loaded<AutomationsData>> {
  const paths = ["/system/status", "/os/overview", "/audit/recent"];
  const [statusRes, ovRes, auditRes] = (await Promise.all(
    paths.map((p) => fetchEndpoint(p, signal)),
  )) as EndpointResult[];
  const results = [statusRes, ovRes, auditRes];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ov: any = ovRes.ok ? (ovRes.data ?? {}) : {};

  // /system/status and /os/overview.automations.services both carry the unit
  // list (the same per-unit fields). Merge both and dedupe by unit name so each
  // real unit is shown exactly once, even when only one of them answers.
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

  if (units.length === 0 && !statusRes.ok && !ovRes.ok) {
    if (!demo) return unavailable(results);
    const sample = buildDemoAutomationsData();
    sample.diagnostics = toDiagnostics("demo", results);
    return sample;
  }
  const backendInsights = Array.isArray(ov.automation_insights)
    ? ov.automation_insights
    : Array.isArray(ov.insights)
      ? ov.insights
      : [];

  const activity = auditRes.ok
    ? normalizeActivity(auditRes.data)
    : normalizeActivity(ov?.recent_activity ?? []);

  // Counts come from the units' own states. The backend's overview
  // `automations.unhealthy` counts only units whose ActiveState is not
  // "active" — an armed timer stays "active" while every run of its job fails —
  // so it is not used to override the failed count or the score.
  const health = healthFrom(units);

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
