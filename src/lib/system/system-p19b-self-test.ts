/**
 * Headless regression test for P1-9 PR B (the measured System workspace).
 *
 *   Platform status comes from the backend's own systemd words in the SAME
 *   /system/status response the shell probe already fetches: no request of its
 *   own, no polling of its own, unknown units counted but not named.
 *   The avatar line is what the presence stage actually drew and measured;
 *   before it has rendered in this tab, System says so.
 *   Preferences use the existing contracts (presence preference, the one voice
 *   switch); motion follows the device and has no in-app override.
 *   The old statements are gone: no fixed statuses, no dead controls.
 *
 * Every fixture is invented. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { automationSummary, platformFrom, unitState } from "@/lib/system/platform";
import { deriveShellHealth, probeShellHealth } from "@/lib/system/shell-health";
import { presenceRenderReport } from "@/lib/presence/renderer-report";
import { ShellProviders } from "@/components/layout/app-shell";
import { SystemWorkspace, presenceLine } from "@/components/system/system-workspace";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const read = (...path: string[]) => readFileSync(join(root, ...path), "utf8");

/** Shaped exactly like services/core-api /system/status (invented values). */
const STATUS = {
  time_utc: "2026-03-04T10:00:00+00:00",
  services: [
    { unit: "hermes-gateway.service", available: true, type: "service", active: "active", sub: "running", result: "success", n_restarts: 2, last_run: "2026-03-01T08:00:00+00:00", last_run_end: null, next_run: null, schedule: null },
    { unit: "lilith-gmail-watcher.timer", available: true, type: "timer", active: "active", sub: "waiting", result: "success", n_restarts: 0, last_run: "2026-03-04T09:45:00+00:00", next_run: "2026-03-04T10:00:00+00:00", schedule: "*:0/15", service_active: "inactive", service_sub: "dead" },
    { unit: "lilith-meeting-prep.timer", available: true, type: "timer", active: "active", sub: "waiting", result: "exit-code", n_restarts: 0, last_run: "2026-03-04T09:00:00+00:00", next_run: null },
    { unit: "lilith-morning-brief.timer", available: false, type: "timer" },
    { unit: "lilith-career-watcher.timer", available: true, type: "timer", active: "inactive", sub: "dead", result: "success" },
    { unit: "lilith-os-api.service", available: true, type: "service", active: "active", sub: "running", result: "success", n_restarts: 0, last_run: "2026-03-02T08:00:00+00:00" },
    { unit: "invented-secret-internal.service", available: true, type: "service", active: "active", sub: "running", result: "success" },
  ],
};

export async function runSystemP19bSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `p1-9b: ${name}`, pass, detail: pass ? undefined : detail });

  /* platform ------------------------------------------------------------------------ */
  const p = platformFrom(STATUS);
  const by = (id: string) => p?.units.find((u) => u.id === id);
  check("units are read from systemd's own words (active / sub / result)",
    by("hermes-gateway.service")?.state === "running" && by("lilith-os-api.service")?.state === "running" &&
      by("lilith-gmail-watcher.timer")?.state === "scheduled" && by("lilith-meeting-prep.timer")?.state === "failed" &&
      by("lilith-morning-brief.timer")?.state === "unknown" && by("lilith-career-watcher.timer")?.state === "idle",
    JSON.stringify(p?.units.map((u) => [u.id, u.state])));
  check("an unreadable unit is unknown, never assumed", unitState("service", { available: false, active: "active", sub: "running" }) === "unknown" && unitState("timer", {}) === "unknown");
  check("readable names, platform vs automation", by("lilith-os-api.service")?.name === "Core API" && by("hermes-gateway.service")?.name === "Conversation gateway" &&
    by("hermes-gateway.service")?.role === "platform" && by("lilith-gmail-watcher.timer")?.role === "automation");
  check("units not listed are counted, not named", p?.unlisted === 1 && !JSON.stringify(p).includes("invented-secret"));
  check("restarts and run times are carried only when reported", by("hermes-gateway.service")?.restarts === 2 && by("lilith-morning-brief.timer")?.restarts === null && by("lilith-gmail-watcher.timer")?.nextRun === "2026-03-04T10:00:00+00:00");
  const auto = automationSummary(p?.units ?? []);
  check("automation summary counts what was reported", auto.total === 4 && auto.scheduled === 1 && auto.failed === 1 && auto.unknown === 1 && auto.idle === 1, JSON.stringify(auto));
  check("a body that is not a status report gives no platform", platformFrom(null) === null && platformFrom({}) === null && platformFrom({ services: "x" }) === null);

  /* the same probe, no extra request ---------------------------------------------------- */
  const live = deriveShellHealth({ ok: true, status: 200, data: STATUS }, 42);
  const down = deriveShellHealth({ ok: false, status: 502, data: STATUS }, 42);
  check("platform rides on the shell probe's own response", live.platform?.units.length === 6 && down.platform === null);
  let calls = 0;
  const probed = await probeShellHealth(async (path) => { calls += 1; return { path, ok: true, status: 200, data: STATUS }; }, () => 0);
  check("one probe is one request, platform included", calls === 1 && probed.platform !== null);
  const ws = read("src", "components", "system", "system-workspace.tsx");
  check("System starts no polling and no request of its own",
    !/setInterval|fetchEndpoint|fetch\(|probeShellHealth/.test(ws) && /useShellHealth\(\)/.test(ws) && /refresh\(\)/.test(ws));

  /* renderer report --------------------------------------------------------------------- */
  presenceRenderReport.reset();
  check("before the stage renders, nothing is claimed", presenceLine(presenceRenderReport.get()).text === "Not measured yet in this tab");
  presenceRenderReport.setFps(60);
  check("a frame rate without a live renderer is ignored", presenceRenderReport.get() === null);
  presenceRenderReport.setRendered("avatar", "live");
  presenceRenderReport.setFps(58.6);
  check("live avatar with its measured frame rate", presenceLine(presenceRenderReport.get()).text === "Avatar, live · 59 fps");
  presenceRenderReport.setRendered("static", "performance");
  check("a performance fallback says so and drops the frame rate", presenceRenderReport.get()?.fps === null && /frame rate stayed too low/.test(presenceLine(presenceRenderReport.get()).text));
  presenceRenderReport.setRendered("static", "reduced-motion");
  check("reduced motion is named as the reason", /reduced motion/.test(presenceLine(presenceRenderReport.get()).text));
  presenceRenderReport.reset();
  const stage = read("src", "components", "presence", "presence-stage.tsx");
  check("the stage reports every branch it draws",
    ["preference-off", "reduced-motion", "no-webgl", "performance", "error", "live"].every((r) => stage.includes(`"${r}"`)) && /onFailure=\{\(\) => setFailed\(true\)\}/.test(stage));
  check("the performance guard still degrades on the same rule", /fps < 20/.test(stage) && /lowStreak\.current >= 2/.test(stage) && /windowStart < measureAfter/.test(stage));
  check("the error boundary tells the stage", /this\.props\.onFailure\?\.\(\)/.test(read("src", "components", "presence", "presence-fallback.tsx")));

  /* preferences ------------------------------------------------------------------------- */
  const caps = read("src", "lib", "presence", "capabilities.ts");
  check("presence preference uses the existing key and tells this tab",
    /PRESENCE_PREF_KEY = "lilith-os:presence-pref"/.test(caps) && /dispatchEvent\(new CustomEvent<PresencePreference>\(PRESENCE_PREF_EVENT/.test(caps) && /PRESENCE_PREF_EVENT, onLocal/.test(caps));
  check("the dev renderer override is ignored in production builds", /NODE_ENV === "production"\) return null/.test(caps));
  const toggle = read("src", "components", "conversation", "voice-toggle.tsx");
  check("one voice switch implementation, used by the Command Center and System",
    /export function setVoiceReplies/.test(toggle) && /setVoiceReplies\(!on\)/.test(toggle) && /setVoiceReplies\(!speak\)/.test(ws));
  check("no in-app reduced-motion override", !/setReducedMotion|reducedMotion: (true|false)|MotionConfig/.test(ws));
  check("About reads the build's version, not a literal", /NEXT_PUBLIC_LILITH_VERSION/.test(ws) && !/"0\.1\.0"/.test(ws) && /NEXT_PUBLIC_LILITH_VERSION: appVersion/.test(read("next.config.ts")));

  /* the page ---------------------------------------------------------------------------- */
  const html = renderToStaticMarkup(createElement(ShellProviders, null, createElement(SystemWorkspace)));
  check("five sections: Connection, Platform, This device, Preferences, About",
    ["connection", "platform", "device", "preferences", "about"].every((c) => html.includes(`data-system-card="${c}"`)));
  check("no fixed statuses or dead controls from the old page",
    !/Client active|See module|>Manage<|Least privilege|Runtime metrics|Advanced diagnostics|Per workspace|In Command|>Enabled</.test(html));
  check("first render claims nothing it has not measured",
    /Not measured yet in this tab/.test(html) && /data-connection-state="checking"/.test(html) && /Shown once the backend answers/.test(html) && !/\bfps\b/.test(html));
  check("presence is a real radio group with three options",
    /role="radiogroup"/.test(html) && (html.match(/role="radio"/g) ?? []).length === 3 && (html.match(/aria-checked="true"/g) ?? []).length >= 1);
  check("speak replies is a real switch", /role="switch"/.test(html));
  check("motion is shown, not settable", /Follows your device/.test(html));

  return out;
}
