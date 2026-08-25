/**
 * Career domain types.
 *
 * These mirror the Lilith backend career API:
 *   GET /career/applications
 *   GET /career/pipeline
 *   GET /career/activity
 *   GET /os/overview
 *
 * Field names follow the backend's snake_case where they cross the wire and are
 * normalised to camelCase in the client. Adjust the raw shapes in client.ts if
 * the real payloads differ — the UI consumes only the normalised types below.
 */

/** Canonical application stages, in pipeline order. */
export const STAGES = [
  "discovered",
  "applied",
  "recruiter_contact",
  "screening",
  "assessment",
  "interview",
  "final_interview",
  "offer",
] as const;

/** Terminal stages, shown apart from the active funnel. */
export const TERMINAL_STAGES = ["rejected", "withdrawn", "closed"] as const;

export type Stage = (typeof STAGES)[number] | (typeof TERMINAL_STAGES)[number];

export interface Recruiter {
  /** may be absent when only an email/contact is known */
  name?: string;
  role?: string;
  contact?: string;
}

export interface NextAction {
  label: string;
  due?: string; // ISO date
}

export interface Application {
  id: string;
  company: string;
  role: string;
  stage: Stage;
  /** 0–100 model confidence in this opportunity. */
  confidence: number;
  /** Which connected account/source surfaced this. */
  sourceAccount: string;
  activityCount: number;
  lastActivity: string; // ISO datetime
  lastActivityLabel: string; // human summary
  location?: string;
  recruiter?: Recruiter;
  nextAction?: NextAction;
  /** true when Lilith detects a pending follow-up signal. */
  followUp?: boolean;
}

export interface PipelineStage {
  stage: Stage;
  count: number;
}

export interface ActivityEvent {
  id: string;
  time: string; // ISO datetime
  text: string;
  company?: string;
  kind: "stage" | "recruiter" | "insight" | "action" | "system";
}

export interface Insight {
  id: string;
  title: string;
  detail: string;
  tone: "opportunity" | "risk" | "info";
}

export interface CareerOverview {
  totalActive: number;
  offers: number;
  interviews: number;
  responseRate: number; // 0–100
  /** Weighted pipeline confidence. */
  pipelineHealth: number; // 0–100
}

/** Everything the Career screen needs, plus provenance. */
export interface CareerData {
  overview: CareerOverview;
  pipeline: PipelineStage[];
  applications: Application[];
  activity: ActivityEvent[];
  insights: Insight[];
  /** true when served from the isolated demo adapter (backend unavailable). */
  isDemo: boolean;
  /** connection + per-endpoint status, for verifying the live backend. */
  diagnostics?: import("@/lib/api").Diagnostics;
}

/** Human-facing labels + accent per stage. */
export const STAGE_META: Record<
  Stage,
  { label: string; accent: "violet" | "cyan" | "green" | "amber" | "rose" | "faint" }
> = {
  discovered: { label: "Discovered", accent: "faint" },
  applied: { label: "Applied", accent: "cyan" },
  recruiter_contact: { label: "Recruiter", accent: "cyan" },
  screening: { label: "Screening", accent: "violet" },
  assessment: { label: "Assessment", accent: "violet" },
  interview: { label: "Interview", accent: "violet" },
  final_interview: { label: "Final round", accent: "amber" },
  offer: { label: "Offer", accent: "green" },
  rejected: { label: "Rejected", accent: "rose" },
  withdrawn: { label: "Withdrawn", accent: "faint" },
  closed: { label: "Closed", accent: "faint" },
};
