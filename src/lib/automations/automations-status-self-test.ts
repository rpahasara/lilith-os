/**
 * Headless regression test for the Automations unit-status mapping.
 *
 *   The backend reports each unit with systemd's own words — `available`,
 *   `active` (ActiveState), `sub` (SubState), `result` (the last run's Result,
 *   from the paired service for a timer) and `service_active` / `service_sub`
 *   for timers. Automations used to read `active_state` / `sub_state`, which the
 *   backend never sends, so every unit showed "Active" — including timers whose
 *   job failed on every run. It now reads the real fields and agrees with the
 *   System workspace (`unitState`), and its headline counts come from those
 *   states rather than from the overview's ActiveState-only `unhealthy` count.
 *
 * Every fixture is invented; the shapes follow services/core-api
 * `systemctl_state`. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { deriveStatus, getAutomationsData, healthFrom, normalizeResult, normalizeUnit } from "@/lib/automations/client";
import { STATUS_META, type UnitStatus } from "@/lib/automations/types";
import { unitState, type PlatformState } from "@/lib/system/platform";
import { UnitCard } from "@/components/automations/unit-card";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

/** Shaped like /system/status `services[]` (invented values). */
const UNITS = {
  gateway: { unit: "hermes-gateway.service", available: true, type: "service", active: "active", sub: "running", result: "success", n_restarts: 1, last_run: "2026-03-01T08:00:00+00:00", last_run_end: null, next_run: null, schedule: null },
  api: { unit: "lilith-os-api.service", available: true, type: "service", active: "active", sub: "running", result: "success", n_restarts: 0, last_run: "2026-03-01T08:00:01+00:00", last_run_end: null, next_run: null, schedule: null },
  // a healthy watcher timer: armed, last run succeeded
  mail: { unit: "lilith-gmail-watcher.timer", available: true, type: "timer", active: "active", sub: "waiting", result: "success", n_restarts: 0, last_run: "2026-03-04T09:50:00+00:00", last_run_end: "2026-03-04T09:50:03+00:00", next_run: "2026-03-04T10:00:00+00:00", schedule: "*:0/10", service_active: "inactive", service_sub: "dead" },
  // the defect: an armed timer whose job exits non-zero on every run
  career: { unit: "lilith-career-watcher.timer", available: true, type: "timer", active: "active", sub: "waiting", result: "exit-code", n_restarts: 0, last_run: "2026-03-04T09:45:00+00:00", last_run_end: "2026-03-04T09:45:01+00:00", next_run: "2026-03-04T10:00:00+00:00", schedule: "*:0/15", service_active: "failed", service_sub: "failed" },
  prep: { unit: "lilith-meeting-prep.timer", available: true, type: "timer", active: "active", sub: "waiting", result: "exit-code", n_restarts: 0, last_run: "2026-03-04T09:45:00+00:00", last_run_end: "2026-03-04T09:45:01+00:00", next_run: "2026-03-04T10:00:00+00:00", schedule: "*:0/15", service_active: "failed", service_sub: "failed" },
  brief: { unit: "lilith-morning-brief.timer", available: true, type: "timer", active: "active", sub: "waiting", result: "success", n_restarts: 0, last_run: "2026-03-04T02:30:00+00:00", last_run_end: "2026-03-04T02:31:00+00:00", next_run: "2026-03-05T02:30:00+00:00", schedule: "*-*-* 08:00:00 Asia/Colombo", service_active: "inactive", service_sub: "dead" },
};

const STATUS_BODY = { time_utc: "2026-03-04T10:00:00+00:00", services: Object.values(UNITS) };
/** /os/overview as the backend builds it: `unhealthy` counts ActiveState only, so it is 0 here. */
const OVERVIEW_BODY = {
  lilith: { status: "online", os_version: "0.1.0", time_utc: "2026-03-04T10:00:00+00:00" },
  automations: { total: 6, healthy: 6, unhealthy: 0, services: Object.values(UNITS) },
  recent_activity: [],
};

/** What the System workspace says for the same unit. */
const SYSTEM_EQUIVALENT: Record<UnitStatus, PlatformState[]> = {
  running: ["running"],
  active: ["idle"],
  waiting: ["scheduled"],
  failed: ["failed"],
  inactive: ["idle"],
  unknown: ["unknown"],
};

async function withBackend<T>(fn: () => Promise<T>): Promise<T> {
  const real = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input instanceof Request ? input.url : input);
    const body = url.includes("system/status") ? STATUS_BODY : url.includes("os/overview") ? OVERVIEW_BODY : url.includes("audit/recent") ? { events: [] } : null;
    return body ? new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } }) : new Response("{}", { status: 404 });
  }) as typeof fetch;
  try {
    return await fn();
  } finally {
    globalThis.fetch = real;
  }
}

export async function runAutomationsStatusSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `automations-status: ${name}`, pass, detail: pass ? undefined : detail });

  /* the mapping, unit by unit ----------------------------------------------- */
  check("a timer whose last run exited non-zero is Failed (it showed Active)",
    deriveStatus(UNITS.career) === "failed" && deriveStatus(UNITS.prep) === "failed",
    `${deriveStatus(UNITS.career)} / ${deriveStatus(UNITS.prep)}`);
  check("an armed timer whose last run succeeded is Scheduled",
    deriveStatus(UNITS.mail) === "waiting" && deriveStatus(UNITS.brief) === "waiting" && STATUS_META.waiting.label === "Scheduled",
    `${deriveStatus(UNITS.mail)} / ${STATUS_META.waiting.label}`);
  check("a running service is Running",
    deriveStatus(UNITS.gateway) === "running" && deriveStatus(UNITS.api) === "running");
  check("a timer whose job is running now is Running",
    deriveStatus({ ...UNITS.mail, service_active: "activating", service_sub: "start" }) === "running");
  check("a timer that failed earlier and is running again still shows the failed last run",
    deriveStatus({ ...UNITS.career, service_active: "activating", service_sub: "start" }) === "failed");
  check("other systemd failure results are failures too",
    ["signal", "timeout", "core-dump", "oom-kill", "start-limit-hit", "watchdog"].every((r) => deriveStatus({ ...UNITS.mail, result: r }) === "failed"));
  check("a failed ActiveState is Failed even with no result",
    deriveStatus({ ...UNITS.api, active: "failed", sub: "failed", result: null }) === "failed");
  check("a service that is up but not running is Active; a stopped one Inactive",
    deriveStatus({ ...UNITS.api, sub: "exited" }) === "active" && deriveStatus({ ...UNITS.api, active: "inactive", sub: "dead" }) === "inactive");
  check("a disarmed timer is Inactive",
    deriveStatus({ ...UNITS.mail, active: "inactive", sub: "dead" }) === "inactive");
  check("a unit the backend could not read is Unknown, never assumed healthy",
    deriveStatus({ unit: UNITS.career.unit, available: false, type: "timer" }) === "unknown" &&
      deriveStatus({ unit: "lilith-os-api.service", available: true }) === "unknown" &&
      STATUS_META.unknown.label === "Unknown");
  check("a watcher is read as a timer from its unit name, not its display kind",
    normalizeUnit(UNITS.career).kind === "watcher" && normalizeUnit(UNITS.career).status === "failed" &&
      normalizeUnit(UNITS.mail).status === "waiting");
  check("Automations agrees with the System workspace for every unit",
    [...Object.values(UNITS), { ...UNITS.mail, service_active: "activating", service_sub: "start" }, { ...UNITS.api, active: "inactive", sub: "dead" }, { unit: "lilith-meeting-prep.timer", available: false, type: "timer" }]
      .every((u) => SYSTEM_EQUIVALENT[deriveStatus(u)].includes(unitState(u.unit.endsWith(".timer") ? "timer" : "service", u)) ||
        // System has no "running" for a timer: it shows a running timer as Scheduled
        (deriveStatus(u) === "running" && u.unit.endsWith(".timer") && unitState("timer", u) === "scheduled")));

  /* last result and failure count ------------------------------------------- */
  check("the last result reads systemd's Result word",
    normalizeResult("success") === "success" && normalizeResult("exit-code") === "failure" &&
      normalizeResult("timeout") === "failure" && normalizeResult(null) === undefined && normalizeResult("") === undefined &&
      normalizeUnit(UNITS.career).lastResult === "failure" && normalizeUnit(UNITS.mail).lastResult === "success");
  check("the restart counter is not shown as a failure count",
    normalizeUnit(UNITS.career).failures === undefined && normalizeUnit({ ...UNITS.career, failures: 3 }).failures === 3);

  /* the screen, end to end ----------------------------------------------------- */
  const loaded = await withBackend(() => getAutomationsData(undefined, false));
  const data = "units" in loaded ? loaded : null;
  check("the fleet loads live from the stand-in backend", Boolean(data && !data.isDemo && data.units.length === 6),
    JSON.stringify(loaded).slice(0, 200));
  if (data) {
    const by = (u: string) => data.units.find((x) => x.unit === u)?.status;
    check("the two failing automations are Failed on the screen",
      by(UNITS.career.unit) === "failed" && by(UNITS.prep.unit) === "failed" && by(UNITS.mail.unit) === "waiting" && by(UNITS.gateway.unit) === "running");
    check("the headline counts come from the unit states, not the overview's ActiveState count",
      data.health.failed === 2 && data.health.running === 2 && data.health.waiting === 2 && data.health.total === 6 && data.health.score === 67,
      JSON.stringify(data.health));
    check("the insights name the failed automations",
      data.insights.some((i) => i.tone === "risk" && i.title.startsWith("Career Watcher")) &&
        data.insights.some((i) => i.tone === "risk" && i.title.startsWith("Meeting Prep")) &&
        !data.insights.some((i) => i.id === "nominal"));
    const health = healthFrom(data.units);
    check("health is the same whether or not the overview answers", JSON.stringify(health) === JSON.stringify(data.health));

    const career = data.units.find((x) => x.unit === UNITS.career.unit)!;
    const html = renderToStaticMarkup(createElement(UnitCard, { unit: career, onSelect: () => {} }));
    check("the card for a failing automation says Failed, and no failure count it does not know",
      html.includes(">Failed<") && !html.includes(">Active<") && !/Failures[\s\S]{0,200}None/.test(html), html.slice(0, 300));
  }

  /* the source ------------------------------------------------------------------ */
  const src = readFileSync(join(process.cwd(), "src", "lib", "automations", "client.ts"), "utf8");
  check("the client reads the backend's `active` / `sub` / `result` fields",
    /r\?\.active\b/.test(src) && /r\?\.sub\b/.test(src) && /r\?\.result\b/.test(src) && /service_active/.test(src));
  check("the overview's `unhealthy` count no longer overrides the failed count",
    !/ovAuto\.unhealthy|\.unhealthy\s*\?\?/.test(src));
  check("the restart counter is no longer read as failures", !/n_failures \?\? r\.n_restarts/.test(src));

  return out;
}
