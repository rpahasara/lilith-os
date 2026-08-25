/**
 * Isolated demo adapter for the Memory module.
 *
 * Used ONLY when no live /memory backend is reachable (which, today, is always
 * — those endpoints don't exist yet). Every record here is SYNTHETIC sample
 * data authored for UX review. It is not, and must never be treated as, real
 * memory content: `MemoryData.isDemo` is set true so the UI labels it clearly.
 *
 * Deliberately contains NO real user profile content.
 */
import {
  CATEGORIES,
  type Entity,
  type MemoryCategory,
  type MemoryData,
  type MemoryOverview,
  type MemoryRecord,
  type ProvenanceKind,
  type Relationship,
} from "./types";

/* ---------------------------------------------------------------- entities */

const entities: Entity[] = [
  { id: "p_dana", type: "person", label: "Dana Whitfield", subtitle: "Technical Recruiter", memoryCount: 2 },
  { id: "p_marcus", type: "person", label: "Marcus Lee", subtitle: "Eng Recruiting", memoryCount: 1 },
  { id: "c_anthropic", type: "company", label: "Anthropic", subtitle: "AI lab", memoryCount: 3 },
  { id: "c_vercel", type: "company", label: "Vercel", subtitle: "Frontend cloud", memoryCount: 1 },
  { id: "c_figma", type: "company", label: "Figma", subtitle: "Design tools", memoryCount: 1 },
  { id: "proj_lilith", type: "project", label: "LILITH OS", subtitle: "Personal AI OS", memoryCount: 5 },
  { id: "proj_memv2", type: "project", label: "Memory v2", subtitle: "Durable memory", memoryCount: 2 },
  { id: "t_next", type: "technology", label: "Next.js 16", memoryCount: 1 },
  { id: "t_r3f", type: "technology", label: "React Three Fiber", memoryCount: 2 },
  { id: "t_k8s", type: "technology", label: "Kubernetes", memoryCount: 2 },
  { id: "pl_sg", type: "place", label: "Singapore", subtitle: "Timezone", memoryCount: 1 },
  { id: "co_lp", type: "concept", label: "Least privilege", subtitle: "Security principle", memoryCount: 2 },
];

const E: Record<string, Entity> = Object.fromEntries(entities.map((e) => [e.id, e]));
const ref = (id: string) => ({ id, type: E[id].type, label: E[id].label });

/* ----------------------------------------------------------------- records */

const records: MemoryRecord[] = [
  {
    id: "m01",
    summary: "LILITH OS is a premium personal AI operating system.",
    content:
      "LILITH OS is a dark, premium personal AI operating system — a command center built with Next.js 16 (App Router), React 19, Tailwind v4, Framer Motion, and React Three Fiber. The visual language is deep-navy glassmorphism with violet (presence) and cyan (system/data) accents.",
    category: "projects",
    kind: "fact",
    entities: [ref("proj_lilith"), ref("t_next"), ref("t_r3f")],
    confidence: 99,
    importance: 96,
    pinned: true,
    tags: ["flagship", "architecture"],
    provenance: { kind: "project_data", sourceAccount: "lilith · repo", label: "Read from the project repository", at: "2026-08-25T09:00:00Z" },
    createdAt: "2026-08-25T09:00:00Z",
    updatedAt: "2026-08-25T09:00:00Z",
    lastAccessed: "2026-08-25T14:40:00Z",
    related: ["m02", "m14"],
  },
  {
    id: "m02",
    summary: "Memory v2 must be validated before adding new capabilities.",
    content:
      "The current focus is establishing structured, durable memory. Memory v2's structure should be completed and validated before adding planning, specialist workers, research, or automation capabilities.",
    category: "projects",
    kind: "fact",
    entities: [ref("proj_memv2"), ref("proj_lilith")],
    confidence: 90,
    importance: 89,
    pinned: true,
    tags: ["roadmap", "priority"],
    provenance: { kind: "manual", label: "Recorded as a project decision", at: "2026-08-24T20:30:00Z" },
    createdAt: "2026-08-24T20:30:00Z",
    updatedAt: "2026-08-25T08:10:00Z",
    lastAccessed: "2026-08-25T13:05:00Z",
    related: ["m01"],
  },
  {
    id: "m03",
    summary: "The presence orb is temporary — a live 3D avatar will replace it.",
    content:
      "The shader-driven presence orb at the center of the OS is a temporary stand-in. The intent is to eventually replace or augment it with a live 3D avatar, so the presence layer is kept behind an abstraction rather than hard-wired to an orb.",
    category: "projects",
    kind: "fact",
    entities: [ref("proj_lilith")],
    confidence: 86,
    importance: 60,
    tags: ["design", "presence"],
    provenance: { kind: "conversation", sourceAccount: "chat", label: "Stated in conversation", at: "2026-08-23T11:20:00Z" },
    createdAt: "2026-08-23T11:20:00Z",
    updatedAt: "2026-08-23T11:20:00Z",
    related: ["m01"],
  },
  {
    id: "m04",
    summary: "Dana Whitfield is a technical recruiter at Anthropic.",
    content:
      "Dana Whitfield is a technical recruiter at Anthropic. First contact arrived by email and she has been the point of contact for the Senior Product Engineer process.",
    category: "people",
    kind: "fact",
    entities: [ref("p_dana"), ref("c_anthropic")],
    confidence: 96,
    importance: 55,
    tags: ["recruiter", "contact"],
    provenance: { kind: "gmail", sourceAccount: "gmail · primary", label: "Extracted from a recruiter email", at: "2026-08-18T15:10:00Z" },
    createdAt: "2026-08-18T15:12:00Z",
    updatedAt: "2026-08-24T15:10:00Z",
    lastAccessed: "2026-08-24T15:10:00Z",
    related: ["m05", "m07"],
  },
  {
    id: "m05",
    summary: "Marcus Lee (Vercel) seems to prefer async updates over calls.",
    content:
      "Based on the cadence of replies during the Vercel process, Marcus Lee appears to prefer written async updates over scheduled calls. This is an inference and may be wrong.",
    category: "people",
    kind: "inference",
    entities: [ref("p_marcus"), ref("c_vercel")],
    confidence: 64,
    importance: 40,
    tags: ["communication"],
    provenance: { kind: "inferred", label: "Inferred from response patterns", at: "2026-08-23T10:00:00Z" },
    createdAt: "2026-08-23T10:00:00Z",
    updatedAt: "2026-08-23T10:00:00Z",
    related: ["m04"],
  },
  {
    id: "m06",
    summary: "Figma extended an offer — decision pending.",
    content:
      "Figma extended an offer for a Senior Frontend Engineer role. The decision is currently pending and time-sensitive relative to other active processes.",
    category: "career",
    kind: "fact",
    entities: [ref("c_figma")],
    confidence: 92,
    importance: 91,
    pinned: true,
    tags: ["offer", "time-sensitive"],
    provenance: { kind: "career_event", sourceAccount: "career · pipeline", label: "Career pipeline event", at: "2026-08-24T20:00:00Z" },
    createdAt: "2026-08-24T20:01:00Z",
    updatedAt: "2026-08-24T20:01:00Z",
    lastAccessed: "2026-08-25T09:30:00Z",
    related: ["m07"],
  },
  {
    id: "m07",
    summary: "Final interview panel with Anthropic is scheduled.",
    content:
      "A final interview panel with Anthropic is on the calendar. It falls close to the Figma offer deadline, which makes sequencing between the two important.",
    category: "career",
    kind: "fact",
    entities: [ref("c_anthropic")],
    confidence: 94,
    importance: 84,
    tags: ["interview", "scheduled"],
    provenance: { kind: "calendar", sourceAccount: "calendar · primary", label: "Read from a calendar event", at: "2026-08-24T15:10:00Z" },
    createdAt: "2026-08-24T15:11:00Z",
    updatedAt: "2026-08-24T15:11:00Z",
    related: ["m04", "m06"],
  },
  {
    id: "m08",
    summary: "Leaning toward remote-first roles in the current search.",
    content:
      "Across recent applications, remote and remote-first positions dominate. Lilith infers a preference for remote-first roles in the current search — a signal, not a stated rule.",
    category: "career",
    kind: "inference",
    entities: [],
    confidence: 61,
    importance: 45,
    tags: ["preference", "search"],
    provenance: { kind: "inferred", label: "Derived from application history", at: "2026-08-22T12:00:00Z" },
    createdAt: "2026-08-22T12:00:00Z",
    updatedAt: "2026-08-22T12:00:00Z",
    related: [],
  },
  {
    id: "m09",
    summary: "Works across Windows locally and Linux/cloud for deployments.",
    content:
      "Day-to-day development happens on Windows, while deployments and infrastructure target Linux and cloud environments — including Kubernetes.",
    category: "work",
    kind: "fact",
    entities: [ref("t_k8s")],
    confidence: 88,
    importance: 50,
    tags: ["environment", "tooling"],
    provenance: { kind: "conversation", sourceAccount: "chat", label: "Stated in conversation", at: "2026-08-20T09:15:00Z" },
    createdAt: "2026-08-20T09:15:00Z",
    updatedAt: "2026-08-20T09:15:00Z",
    related: ["m15"],
  },
  {
    id: "m10",
    summary: "Reviews infrastructure changes with a production-caution mindset.",
    content:
      "When infrastructure changes come up, the pattern is to prefer reversible steps, backups, and verification before touching production. Lilith treats this as a working style to respect.",
    category: "work",
    kind: "inference",
    entities: [ref("co_lp")],
    confidence: 72,
    importance: 58,
    tags: ["workflow", "caution"],
    provenance: { kind: "inferred", label: "Observed across sessions", at: "2026-08-21T16:40:00Z" },
    createdAt: "2026-08-21T16:40:00Z",
    updatedAt: "2026-08-24T10:00:00Z",
    related: ["m16"],
  },
  {
    id: "m11",
    summary: "Scheduling assumes a Singapore timezone.",
    content:
      "Meeting times and reminders should assume a Singapore timezone unless stated otherwise.",
    category: "personal",
    kind: "fact",
    entities: [ref("pl_sg")],
    confidence: 80,
    importance: 48,
    tags: ["timezone", "scheduling"],
    provenance: { kind: "calendar", sourceAccount: "calendar · primary", label: "Inferred from calendar events", at: "2026-08-19T08:00:00Z" },
    createdAt: "2026-08-19T08:00:00Z",
    updatedAt: "2026-08-19T08:00:00Z",
    related: [],
  },
  {
    id: "m12",
    summary: "Prefers concise, answer-first responses.",
    content:
      "Responses should lead with the answer and expand only when useful. Brevity and directness are valued over long preambles.",
    category: "preferences",
    kind: "fact",
    entities: [],
    confidence: 93,
    importance: 76,
    pinned: true,
    tags: ["communication", "style"],
    provenance: { kind: "manual", label: "Set as a standing preference", at: "2026-08-17T10:00:00Z" },
    createdAt: "2026-08-17T10:00:00Z",
    updatedAt: "2026-08-25T07:00:00Z",
    lastAccessed: "2026-08-25T14:00:00Z",
    related: ["m13"],
  },
  {
    id: "m13",
    summary: "Prefers dark, premium interfaces over generic dashboards.",
    content:
      "Strong preference for dark, premium, cinematic interfaces with restrained accents — and an explicit dislike of generic SaaS-dashboard aesthetics and empty 'coming soon' screens.",
    category: "preferences",
    kind: "fact",
    entities: [ref("proj_lilith")],
    confidence: 85,
    importance: 62,
    tags: ["design", "aesthetic"],
    provenance: { kind: "conversation", sourceAccount: "chat", label: "Stated repeatedly in conversation", at: "2026-08-22T19:30:00Z" },
    createdAt: "2026-08-22T19:30:00Z",
    updatedAt: "2026-08-24T18:00:00Z",
    related: ["m12", "m01"],
  },
  {
    id: "m14",
    summary: "R3F canvas can mis-size to 300×150 without a forced re-measure.",
    content:
      "A React Three Fiber <Canvas> can intermittently render at the default 300×150 instead of filling its container, because the internal ResizeObserver misses late layout shifts. The fix dispatches a window resize after mount and observes the container.",
    category: "knowledge",
    kind: "fact",
    entities: [ref("t_r3f"), ref("proj_lilith")],
    confidence: 97,
    importance: 54,
    tags: ["gotcha", "frontend"],
    provenance: { kind: "project_data", sourceAccount: "lilith · repo", label: "Learned while building the presence orb", at: "2026-08-25T10:18:00Z" },
    createdAt: "2026-08-25T10:18:00Z",
    updatedAt: "2026-08-25T10:18:00Z",
    related: ["m01"],
  },
  {
    id: "m15",
    summary: "Kubernetes workloads should set resource requests and limits.",
    content:
      "As a reliability practice, Kubernetes workloads should declare CPU/memory requests and limits so the scheduler can place them safely and noisy neighbours are contained.",
    category: "knowledge",
    kind: "fact",
    entities: [ref("t_k8s")],
    confidence: 90,
    importance: 44,
    tags: ["kubernetes", "reliability"],
    provenance: { kind: "manual", label: "Noted as a reference fact", at: "2026-08-16T14:00:00Z" },
    createdAt: "2026-08-16T14:00:00Z",
    updatedAt: "2026-08-16T14:00:00Z",
    related: ["m09"],
  },
  {
    id: "m16",
    summary: "Least privilege: grant only the minimum access required.",
    content:
      "Least privilege means granting the minimum access necessary for a task and no more — a core security principle to apply when provisioning credentials, roles, and integrations.",
    category: "knowledge",
    kind: "fact",
    entities: [ref("co_lp")],
    confidence: 99,
    importance: 66,
    tags: ["security", "principle"],
    provenance: { kind: "manual", label: "Noted as a reference fact", at: "2026-08-15T09:00:00Z" },
    createdAt: "2026-08-15T09:00:00Z",
    updatedAt: "2026-08-15T09:00:00Z",
    related: ["m10"],
  },
];

/* ----------------------------------------------------------- relationships */

const relationships: Relationship[] = [
  { id: "r1", from: "p_dana", to: "c_anthropic", kind: "works at" },
  { id: "r2", from: "p_marcus", to: "c_vercel", kind: "works at" },
  { id: "r3", from: "proj_memv2", to: "proj_lilith", kind: "part of" },
  { id: "r4", from: "proj_lilith", to: "t_next", kind: "built with" },
  { id: "r5", from: "proj_lilith", to: "t_r3f", kind: "built with" },
  { id: "r6", from: "co_lp", to: "t_k8s", kind: "applies to" },
];

/* -------------------------------------------------------------- aggregate */

function buildOverview(recs: MemoryRecord[]): MemoryOverview {
  const now = Date.parse("2026-08-25T15:00:00Z");
  const weekAgo = now - 7 * 24 * 3600 * 1000;

  const byCategory = Object.fromEntries(CATEGORIES.map((c) => [c, 0])) as Record<
    MemoryCategory,
    number
  >;
  const bySource: Partial<Record<ProvenanceKind, number>> = {};
  let confSum = 0;
  let confN = 0;
  let recentlyLearned = 0;
  let pinned = 0;

  for (const r of recs) {
    byCategory[r.category] += 1;
    bySource[r.provenance.kind] = (bySource[r.provenance.kind] ?? 0) + 1;
    if (typeof r.confidence === "number") {
      confSum += r.confidence;
      confN += 1;
    }
    if (r.pinned) pinned += 1;
    if (r.createdAt && Date.parse(r.createdAt) >= weekAgo) recentlyLearned += 1;
  }

  return {
    total: recs.length,
    recentlyLearned,
    pinned,
    categories: CATEGORIES.filter((c) => byCategory[c] > 0).length,
    entities: entities.length,
    avgConfidence: confN ? Math.round(confSum / confN) : 0,
    byCategory,
    bySource,
    recentActivity: [
      { id: "a1", at: "2026-08-25T10:18:00Z", text: "Learned an R3F canvas sizing gotcha while building the orb", category: "knowledge", kind: "learned" },
      { id: "a2", at: "2026-08-25T09:00:00Z", text: "Refreshed the LILITH OS architecture memory", category: "projects", kind: "updated" },
      { id: "a3", at: "2026-08-24T20:01:00Z", text: "Recorded a pending Figma offer", category: "career", kind: "learned" },
      { id: "a4", at: "2026-08-24T15:11:00Z", text: "Noted a scheduled Anthropic final panel", category: "career", kind: "learned" },
      { id: "a5", at: "2026-08-24T18:00:00Z", text: "Reinforced the dark-premium interface preference", category: "preferences", kind: "reinforced" },
    ],
  };
}

export function buildDemoMemoryData(): MemoryData {
  return {
    isDemo: true,
    records,
    entities,
    relationships,
    overview: buildOverview(records),
  };
}
