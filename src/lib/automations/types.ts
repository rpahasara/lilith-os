/**
 * Automations domain types — Lilith's autonomous operations.
 *
 * Backed by the LILITH backend:
 *   GET /system/status   — systemd service/timer health
 *   GET /os/overview     — aggregate automation state + insights
 *
 * Units are classified into four kinds so the UI can distinguish long-running
 * services from scheduled timers, event watchers, and background agents.
 */

export type UnitKind = "service" | "timer" | "watcher" | "agent";

export type UnitStatus =
  | "running" // actively doing work now
  | "active" // healthy + armed (e.g. a scheduled timer waiting to fire)
  | "waiting" // idle between scheduled runs
  | "failed" // last run/health check failed
  | "inactive"; // stopped / disabled

export type TriggerType = "continuous" | "schedule" | "event" | "manual";

export type RunOutcome = "success" | "failure" | "skip";

export interface AutomationUnit {
  id: string;
  /** raw systemd unit id, e.g. "lilith-gmail-watcher.timer" */
  unit: string;
  /** friendly display name */
  name: string;
  kind: UnitKind;
  status: UnitStatus;
  purpose: string;
  trigger: TriggerType;
  schedule?: string; // human cadence, e.g. "Every 5 min", "Daily 07:00"
  lastRun?: string; // ISO
  nextRun?: string; // ISO
  lastResult?: RunOutcome;
  /** recent failure count — undefined when the backend does not expose it */
  failures?: number;
  runsToday?: number;
  /** recent run outcomes, oldest→newest, for the sparkline */
  history?: RunOutcome[];
  enabled: boolean;
}

export interface AutomationHealth {
  score: number; // 0–100
  total: number;
  running: number;
  active: number;
  waiting: number;
  failed: number;
}

export interface AutomationEvent {
  id: string;
  time: string; // ISO
  unit: string; // display name
  text: string;
  outcome: RunOutcome | "info";
}

export interface AutomationInsight {
  id: string;
  title: string;
  detail: string;
  tone: "opportunity" | "risk" | "info";
}

export interface AutomationsData {
  health: AutomationHealth;
  units: AutomationUnit[];
  activity: AutomationEvent[];
  insights: AutomationInsight[];
  isDemo: boolean;
  diagnostics?: import("@/lib/api").Diagnostics;
}

export const KIND_META: Record<
  UnitKind,
  { label: string; accent: "violet" | "cyan" | "green" | "amber"; blurb: string }
> = {
  service: { label: "Service", accent: "cyan", blurb: "Always-on process" },
  timer: { label: "Timer", accent: "violet", blurb: "Scheduled job" },
  watcher: { label: "Watcher", accent: "green", blurb: "Event processor" },
  agent: { label: "Agent", accent: "amber", blurb: "Background agent" },
};

export const STATUS_META: Record<
  UnitStatus,
  { label: string; accent: "green" | "cyan" | "amber" | "rose" | "faint" }
> = {
  running: { label: "Running", accent: "green" },
  active: { label: "Active", accent: "cyan" },
  waiting: { label: "Waiting", accent: "faint" },
  failed: { label: "Failed", accent: "rose" },
  inactive: { label: "Inactive", accent: "faint" },
};
