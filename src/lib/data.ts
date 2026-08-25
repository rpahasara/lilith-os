import type { LucideIcon } from "lucide-react";
import {
  Sparkles,
  CalendarClock,
  Workflow,
  Brain,
  Search,
  FileText,
  Plug,
  Command,
} from "lucide-react";

/* -------------------------------------------------------------- user */
export const user = {
  name: "Ravindu",
  handle: "ravindu.pahasara",
  plan: "Founder",
};

/* -------------------------------------------------------------- quick actions */
export interface QuickAction {
  label: string;
  hint: string;
  icon: LucideIcon;
  accent: "violet" | "cyan";
}

export const quickActions: QuickAction[] = [
  { label: "New command", hint: "Ask anything", icon: Command, accent: "violet" },
  { label: "Deep research", hint: "Multi-source", icon: Search, accent: "cyan" },
  { label: "Draft", hint: "Write with me", icon: FileText, accent: "violet" },
  { label: "Automate", hint: "Build a flow", icon: Workflow, accent: "cyan" },
];

/* -------------------------------------------------------------- pipeline */
export const pipeline = {
  focusScore: 87,
  stages: [
    { label: "Captured", value: 24, accent: "violet" as const },
    { label: "In motion", value: 12, accent: "cyan" as const },
    { label: "Review", value: 5, accent: "violet" as const },
    { label: "Done", value: 2, accent: "cyan" as const },
  ],
};

/* -------------------------------------------------------------- next event */
export const nextEvent = {
  title: "Product Strategy Sync",
  where: "Deep Focus Room",
  start: "10:30",
  end: "11:30",
  inMinutes: 45,
  people: 4,
};

/* -------------------------------------------------------------- memory */
export interface MemoryShard {
  label: string;
  value: number;
  accent: "violet" | "cyan";
}

export const memory = {
  total: 2847,
  fresh: 18,
  shards: [
    { label: "Work", value: 45, accent: "cyan" },
    { label: "People", value: 20, accent: "violet" },
    { label: "Projects", value: 20, accent: "cyan" },
    { label: "Personal", value: 15, accent: "violet" },
  ] as MemoryShard[],
};

/* -------------------------------------------------------------- automations */
export const automations = {
  healthy: 98,
  running: 24,
  idle: 3,
  failed: 0,
  items: [
    { name: "Inbox triage", status: "running" as const },
    { name: "Meeting prep", status: "running" as const },
    { name: "Daily digest", status: "running" as const },
    { name: "Follow-up nudges", status: "idle" as const },
  ],
};

/* -------------------------------------------------------------- activity */
export interface ActivityItem {
  time: string;
  text: string;
  icon: LucideIcon;
  accent: "violet" | "cyan";
}

export const activity: ActivityItem[] = [
  { time: "2m", text: "Summarised 14 unread threads into a brief", icon: Sparkles, accent: "violet" },
  { time: "18m", text: "Scheduled Product Strategy Sync", icon: CalendarClock, accent: "cyan" },
  { time: "1h", text: "Learned 6 new facts about Project Nova", icon: Brain, accent: "violet" },
  { time: "3h", text: "Connected Linear workspace", icon: Plug, accent: "cyan" },
];

/* -------------------------------------------------------------- brief */
export const brief = [
  { text: "3 meetings today", meta: "2 high priority", accent: "cyan" as const },
  { text: "Project Nova review due", meta: "Tomorrow, 5:00 PM", accent: "violet" as const },
  { text: "Focus window open", meta: "Recommended 2h", accent: "cyan" as const },
];

/* -------------------------------------------------------------- system vitals */
export const vitals = [
  { label: "Context", value: "Private", bars: [4, 5, 4, 5, 5] },
  { label: "Sync", value: "Live", bars: [5, 5, 4, 5, 5] },
  { label: "Latency", value: "48ms", bars: [5, 4, 5, 4, 5] },
];
