/**
 * Isolated demo adapter for the Automations module.
 *
 * Used ONLY when the backend is unreachable in local dev. Times are computed
 * relative to now so the "last / next run" fields read realistically. Never
 * treated as, or written back to, production state (`isDemo` is set true).
 */
import type { AutomationUnit, AutomationsData, RunOutcome } from "./types";

const min = (n: number) => n * 60_000;
const hour = (n: number) => n * 3_600_000;

const ok = (n: number): RunOutcome[] => Array.from({ length: n }, () => "success");

export function buildDemoAutomationsData(): AutomationsData {
  const now = Date.now();
  const iso = (ms: number) => new Date(ms).toISOString();

  const units: AutomationUnit[] = [
    {
      id: "u_api",
      unit: "lilith-os-api.service",
      name: "Core API",
      kind: "service",
      status: "running",
      purpose: "Serves the Lilith OS API — the backbone every module talks to.",
      trigger: "continuous",
      lastRun: iso(now - hour(72)),
      lastResult: "success",
      failures: 0,
      runsToday: 1,
      history: ok(12),
      enabled: true,
    },
    {
      id: "u_hermes",
      unit: "hermes-gateway.service",
      name: "Model Gateway",
      kind: "service",
      status: "running",
      purpose: "Routes and load-balances every LLM call across providers.",
      trigger: "continuous",
      lastRun: iso(now - hour(72)),
      lastResult: "success",
      failures: 0,
      runsToday: 1,
      history: ok(12),
      enabled: true,
    },
    {
      id: "u_gmail",
      unit: "lilith-gmail-watcher.timer",
      name: "Gmail Watcher",
      kind: "watcher",
      status: "running",
      purpose: "Monitors your inbox for career, meeting, and follow-up signals.",
      trigger: "event",
      schedule: "Every 5 min",
      lastRun: iso(now - min(3)),
      nextRun: iso(now + min(2)),
      lastResult: "success",
      failures: 0,
      runsToday: 214,
      history: [...ok(9), "success", "success", "success"],
      enabled: true,
    },
    {
      id: "u_career",
      unit: "lilith-career-watcher.timer",
      name: "Career Watcher",
      kind: "watcher",
      status: "active",
      purpose: "Scans job sources and keeps the career pipeline up to date.",
      trigger: "schedule",
      schedule: "Every 30 min",
      lastRun: iso(now - min(18)),
      nextRun: iso(now + min(12)),
      lastResult: "success",
      failures: 0,
      runsToday: 34,
      history: [...ok(10), "success", "success"],
      enabled: true,
    },
    {
      id: "u_meeting",
      unit: "lilith-meeting-prep.timer",
      name: "Meeting Prep",
      kind: "timer",
      status: "failed",
      purpose: "Briefs you before each meeting with context and talking points.",
      trigger: "schedule",
      schedule: "15 min before events",
      lastRun: iso(now - min(42)),
      nextRun: iso(now + hour(2) + min(15)),
      lastResult: "failure",
      failures: 1,
      runsToday: 5,
      history: [...ok(8), "success", "success", "success", "failure"],
      enabled: true,
    },
    {
      id: "u_brief",
      unit: "lilith-morning-brief.timer",
      name: "Morning Brief",
      kind: "timer",
      status: "waiting",
      purpose: "Assembles your daily brief — schedule, priorities, and focus.",
      trigger: "schedule",
      schedule: "Daily 07:00",
      lastRun: iso(now - hour(4)),
      nextRun: iso(now + hour(20)),
      lastResult: "success",
      failures: 0,
      runsToday: 1,
      history: ok(12),
      enabled: true,
    },
    {
      id: "u_followup",
      unit: "lilith-followup-agent",
      name: "Follow-up Agent",
      kind: "agent",
      status: "running",
      purpose: "Drafts follow-ups when recruiter threads go quiet.",
      trigger: "event",
      lastRun: iso(now - min(26)),
      lastResult: "success",
      failures: 0,
      runsToday: 7,
      history: [...ok(9), "success", "success", "success"],
      enabled: true,
    },
  ];

  const running = units.filter((u) => u.status === "running").length;
  const active = units.filter((u) => u.status === "active").length;
  const waiting = units.filter((u) => u.status === "waiting").length;
  const failed = units.filter((u) => u.status === "failed").length;
  const score = Math.round(((units.length - failed) / units.length) * 100);

  return {
    isDemo: true,
    health: { score, total: units.length, running, active, waiting, failed },
    units,
    activity: [
      { id: "a1", time: iso(now - min(3)), unit: "Gmail Watcher", text: "Processed 3 new threads · 1 career signal", outcome: "success" },
      { id: "a2", time: iso(now - min(18)), unit: "Career Watcher", text: "Matched 1 new role (Retool · 91% fit)", outcome: "success" },
      { id: "a3", time: iso(now - min(26)), unit: "Follow-up Agent", text: "Drafted a follow-up for the Vercel thread", outcome: "success" },
      { id: "a4", time: iso(now - min(42)), unit: "Meeting Prep", text: "Run failed — SMTP timeout while sending brief", outcome: "failure" },
      { id: "a5", time: iso(now - hour(4)), unit: "Morning Brief", text: "Delivered your morning brief", outcome: "success" },
      { id: "a6", time: iso(now - hour(6)), unit: "Model Gateway", text: "Rotated to backup provider (14ms recovery)", outcome: "info" },
    ],
    insights: [
      {
        id: "i1",
        title: "Meeting Prep failed its last run",
        detail: "SMTP timeout at 42m ago. A retry is armed for the next event window; no meetings were missed.",
        tone: "risk",
      },
      {
        id: "i2",
        title: "Gmail Watcher is running hot",
        detail: "214 runs today — well above the daily median of ~150. Inbox volume is elevated.",
        tone: "info",
      },
      {
        id: "i3",
        title: "Core services healthy",
        detail: "API and Model Gateway have 100% uptime over the last 72h.",
        tone: "opportunity",
      },
    ],
  };
}
