/**
 * Meetings domain types — LILITH's meeting intelligence.
 *
 * Mirror the read-only backend:
 *   GET /meetings/overview
 *   GET /meetings/upcoming
 *   GET /meetings/context
 *   GET /meetings/followups
 *   GET /meetings/{id}/prep
 *
 * All meeting data originates from local state JSON that LILITH's background
 * meeting-prep chain + agenda snapshot produce; the API masks attendee emails,
 * omits raw descriptions, and never exposes tokens. The client normalises the
 * snake_case wire shapes to the camelCase types below. Live and demo data are
 * never mixed (client.ts falls back to the isolated demo adapter).
 */

/** Prep lifecycle — derived from real state, in order. */
export const PREP_STAGES = [
  "detected",
  "context_gathered",
  "delivered",
  "completed",
] as const;
export type PrepStatus = (typeof PREP_STAGES)[number] | "scheduled";

export const PREP_META: Record<
  PrepStatus,
  { label: string; accent: "violet" | "cyan" | "green" | "amber" | "faint" }
> = {
  scheduled: { label: "Scheduled", accent: "faint" },
  detected: { label: "Detected", accent: "cyan" },
  context_gathered: { label: "Context gathered", accent: "violet" },
  delivered: { label: "Prepared", accent: "green" },
  completed: { label: "Completed", accent: "faint" },
};

export interface Attendee {
  displayName?: string;
  emailMasked?: string;
  domain?: string;
}

export interface MeetingEvent {
  id: string;
  title: string;
  calendar?: string;
  start?: string; // ISO (local offset)
  end?: string; // ISO
  durationMinutes?: number | null;
  allDay: boolean;
  minutesUntil?: number | null;
  joinLink?: string | null;
  hasDescription: boolean;
  attendees: Attendee[];
  attendeeCount: number;
  prepStatus: PrepStatus;
  prepared: boolean;
  briefAvailable: boolean;
  contextAvailable: boolean;
}

export interface ContextMessage {
  account?: string;
  subject: string;
  from: string; // masked
  date?: string;
  relevanceScore?: number;
}

export interface Followup {
  id: string;
  title: string;
  source?: string;
  reason?: string;
  status: string; // waiting | resolved
  due?: string | null;
  dueKind: "date" | "window" | "none";
  dueConfidence?: string | null;
  createdAt?: string;
  updatedAt?: string;
  resolvedAt?: string | null;
  resolution?: string | null;
}

export interface MeetingContext {
  eventId?: string;
  generatedAt?: string;
  keywords: string[];
  messages: ContextMessage[];
  messageCount: number;
  followups: Followup[];
}

export interface PrepBrief {
  eventId: string;
  generatedAt?: string;
  brief: string;
  sourceCounts: { gmailMessages?: number; followups?: number };
}

export interface MeetingsOverview {
  generatedAt?: string;
  timezone?: string;
  counts: {
    upcomingTotal: number;
    todayTotal: number;
    prepared: number;
    followupsTotal: number;
    followupsPending: number;
    contextMessages: number;
  };
  next?: {
    id: string;
    title: string;
    start?: string;
    minutesUntil?: number | null;
    prepStatus: PrepStatus;
  } | null;
  /** timer health (real systemd metadata), passed through untyped. */
  prepTimer?: unknown;
  agendaSnapshot?: unknown;
}

/** A derived open window between meetings (never a fabricated score). */
export interface FocusWindow {
  start: string; // ISO
  end: string; // ISO
  minutes: number;
  /** true when this window contains "now". */
  current: boolean;
}

export interface MeetingsData {
  overview: MeetingsOverview;
  events: MeetingEvent[];
  context?: MeetingContext;
  followups: Followup[];
  isDemo: boolean;
  diagnostics?: import("@/lib/api").Diagnostics;
}
