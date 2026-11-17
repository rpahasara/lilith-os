/**
 * Platform status, read from the same `/system/status` response the shell
 * health probe already fetches every minute (see shell-health). No request of
 * its own, no polling of its own.
 *
 * The backend reports each unit with systemd's own words: `active`
 * (ActiveState), `sub` (SubState) and `result` (the last run's Result, taken
 * from the paired service for timers). This file reads exactly those fields and
 * nothing else; a unit the backend could not read is "unknown", never assumed.
 *
 * Only units listed here are shown, under readable names; anything else the
 * backend adds is counted, not named.
 */

export type PlatformRole = "platform" | "automation";
export type PlatformState = "running" | "scheduled" | "idle" | "failed" | "unknown";

export interface PlatformUnit {
  id: string;
  name: string;
  role: PlatformRole;
  kind: "service" | "timer";
  state: PlatformState;
  /** systemd's own sub-state word, for the tooltip ("running", "waiting", "dead"…). */
  detail: string | null;
  restarts: number | null;
  lastRun: string | null;
  nextRun: string | null;
}

export interface PlatformSnapshot {
  /** When the backend read the units (its own clock), if it said. */
  reportedAt: string | null;
  units: PlatformUnit[];
  /** Units the backend reported that are not listed here. */
  unlisted: number;
}

const KNOWN: Record<string, { name: string; role: PlatformRole }> = {
  "lilith-os-api.service": { name: "Core API", role: "platform" },
  "hermes-gateway.service": { name: "Conversation gateway", role: "platform" },
  "lilith-gmail-watcher.timer": { name: "Gmail watcher", role: "automation" },
  "lilith-career-watcher.timer": { name: "Career watcher", role: "automation" },
  "lilith-meeting-prep.timer": { name: "Meeting prep", role: "automation" },
  "lilith-morning-brief.timer": { name: "Morning brief", role: "automation" },
};

const word = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim().toLowerCase() : null);
const stamp = (v: unknown) => (typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v) ? v : null);
const count = (v: unknown) => (typeof v === "number" && Number.isInteger(v) && v >= 0 ? v : null);

/** One unit's state from systemd's words. Pure. */
export function unitState(kind: "service" | "timer", u: { available?: unknown; active?: unknown; sub?: unknown; result?: unknown }): PlatformState {
  if (u.available === false) return "unknown";
  const active = word(u.active), sub = word(u.sub), result = word(u.result);
  if (!active) return "unknown";
  if (active === "failed" || (result !== null && result !== "success")) return "failed";
  if (kind === "timer") return active === "active" ? "scheduled" : "idle";
  if (active === "activating" || active === "reloading") return "running";
  if (active === "active") return sub === "running" ? "running" : "idle";
  return "idle";
}

/** Platform units from a `/system/status` body; null when it is not one. */
export function platformFrom(data: unknown): PlatformSnapshot | null {
  if (typeof data !== "object" || data === null) return null;
  const body = data as { time_utc?: unknown; services?: unknown };
  if (!Array.isArray(body.services)) return null;
  const units: PlatformUnit[] = [];
  let unlisted = 0;
  for (const raw of body.services) {
    if (typeof raw !== "object" || raw === null) continue;
    const u = raw as Record<string, unknown>;
    const id = typeof u.unit === "string" ? u.unit : "";
    const known = KNOWN[id];
    if (!known) { unlisted += 1; continue; }
    const kind = id.endsWith(".timer") ? "timer" : "service";
    units.push({
      id,
      name: known.name,
      role: known.role,
      kind,
      state: unitState(kind, u),
      detail: word(kind === "timer" ? u.service_sub ?? u.sub : u.sub),
      restarts: count(u.n_restarts),
      lastRun: stamp(u.last_run),
      nextRun: stamp(u.next_run),
    });
  }
  return { reportedAt: stamp(body.time_utc), units, unlisted };
}

export const PLATFORM_STATE_LABEL: Record<PlatformState, string> = {
  running: "Running",
  scheduled: "Scheduled",
  idle: "Not running",
  failed: "Failed",
  unknown: "Unknown",
};

/** "4 automations · 3 scheduled · 1 failed" style counts, from what was reported. */
export function automationSummary(units: PlatformUnit[]) {
  const automations = units.filter((u) => u.role === "automation");
  const by = (s: PlatformState) => automations.filter((u) => u.state === s).length;
  return { total: automations.length, scheduled: by("scheduled"), running: by("running"), failed: by("failed"), idle: by("idle"), unknown: by("unknown") };
}
