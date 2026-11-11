/**
 * Home (Command Center) view of the owner's day: what TODAY and NEXT show.
 *
 * Derived ONLY from the live, read-only meetings client (`/meetings/*` via the
 * same-origin proxy). Rules that keep the home screen truthful:
 *  - Demo data never reaches Home. When the meetings client falls back to its
 *    demo adapter (`isDemo`), Home shows an "unavailable" state instead of
 *    synthetic meetings. The Meetings workspace keeps its labelled demo.
 *  - Countdowns are recomputed from each event's start time against the
 *    current clock. The backend's `minutes_until` is a snapshot taken when
 *    the agenda was generated, so it goes stale and is never displayed.
 *  - Snapshot age is surfaced: an agenda older than STALE_AFTER_MS is flagged
 *    so the cards can say "as of …" rather than imply it is current.
 *  - No fabricated scores: a focus window is a real gap between meetings
 *    (`computeFocusWindows`), never a number.
 *  - A join link is offered only when it is a well-formed https URL.
 */
import { computeFocusWindows } from "@/lib/meetings/focus";
import type { Followup, MeetingEvent, MeetingsData } from "@/lib/meetings/types";

/** The meeting-prep chain refreshes every 15 min; 2 h means it has stopped. */
export const STALE_AFTER_MS = 2 * 3600_000;

export interface HomeNextMeeting {
  id: string;
  title: string;
  startMs: number;
  endMs: number | null;
  /** true when the meeting has started and not yet ended. */
  inProgress: boolean;
  /** Whole minutes until start (0 when in progress), from the live clock. */
  minutesUntil: number;
  calendar?: string;
  attendeeCount: number;
  /** Validated https join URL, or null. */
  joinUrl: string | null;
}

export interface HomeDueFollowup {
  title: string;
  dueMs: number;
}

export interface HomeFocusWindow {
  startMs: number;
  endMs: number;
  minutes: number;
  current: boolean;
}

export type HomeMeetingsView =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | {
      kind: "live";
      /** ISO time the backend generated the agenda, when known. */
      asOf: string | null;
      stale: boolean;
      today: { total: number; remaining: number };
      nextDue: HomeDueFollowup | null;
      focus: HomeFocusWindow | null;
      next: HomeNextMeeting | null;
    };

function ms(iso?: string | null): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isFinite(t) ? t : null;
}

function endMsOf(e: MeetingEvent): number | null {
  const end = ms(e.end);
  if (end != null) return end;
  const start = ms(e.start);
  if (start != null && e.durationMinutes) return start + e.durationMinutes * 60_000;
  return null;
}

function sameLocalDay(a: number, b: number): boolean {
  const x = new Date(a);
  const y = new Date(b);
  return (
    x.getFullYear() === y.getFullYear() &&
    x.getMonth() === y.getMonth() &&
    x.getDate() === y.getDate()
  );
}

/** Only https URLs are offered as a join action (no javascript:, http:, etc.). */
export function safeJoinUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    return u.protocol === "https:" ? u.toString() : null;
  } catch {
    return null;
  }
}

function nextMeeting(events: MeetingEvent[], now: number): HomeNextMeeting | null {
  const candidates = events
    .filter((e) => !e.allDay)
    .map((e) => ({ e, start: ms(e.start), end: endMsOf(e) }))
    .filter((x): x is { e: MeetingEvent; start: number; end: number | null } => x.start != null)
    // Upcoming, or started and still running. A start in the past with no
    // known end is treated as over: we cannot claim it is in progress.
    .filter((x) => x.start > now || (x.end != null && x.end > now))
    .sort((a, b) => a.start - b.start);
  const first = candidates[0];
  if (!first) return null;
  const inProgress = first.start <= now;
  return {
    id: first.e.id,
    title: first.e.title,
    startMs: first.start,
    endMs: first.end,
    inProgress,
    minutesUntil: inProgress ? 0 : Math.ceil((first.start - now) / 60_000),
    calendar: first.e.calendar,
    attendeeCount: Math.max(0, first.e.attendeeCount || 0),
    joinUrl: safeJoinUrl(first.e.joinLink),
  };
}

function nextDueFollowup(followups: Followup[]): HomeDueFollowup | null {
  const due = followups
    .filter((f) => f.status !== "resolved" && f.dueKind === "date")
    .map((f) => ({ title: f.title, dueMs: ms(f.due) }))
    .filter((f): f is HomeDueFollowup => f.dueMs != null && !!f.title)
    .sort((a, b) => a.dueMs - b.dueMs);
  return due[0] ?? null;
}

export function deriveHomeMeetings(
  data: MeetingsData | null,
  loading: boolean,
  now: number,
): HomeMeetingsView {
  if (!data) return loading ? { kind: "loading" } : { kind: "unavailable" };
  if (data.isDemo) return { kind: "unavailable" };

  const events = data.events ?? [];
  const todays = events.filter((e) => {
    const s = ms(e.start);
    return s != null && sameLocalDay(s, now);
  });
  const remaining = todays.filter((e) => {
    const end = endMsOf(e) ?? ms(e.start);
    return end != null && end > now;
  }).length;

  const window = computeFocusWindows(events, now)[0];
  const focus: HomeFocusWindow | null = window
    ? {
        startMs: new Date(window.start).getTime(),
        endMs: new Date(window.end).getTime(),
        minutes: window.minutes,
        current: window.current,
      }
    : null;

  const asOf = data.overview?.generatedAt ?? null;
  const asOfMs = ms(asOf);
  return {
    kind: "live",
    asOf,
    // Unknown generation time counts as stale: we cannot vouch for freshness.
    stale: asOfMs == null || now - asOfMs > STALE_AFTER_MS,
    today: { total: todays.length, remaining },
    nextDue: nextDueFollowup(data.followups ?? []),
    focus,
    next: nextMeeting(events, now),
  };
}

/** "in 5m", "in 2h 05m", "Now". */
export function countdownLabel(m: HomeNextMeeting): string {
  if (m.inProgress) return "Now";
  if (m.minutesUntil < 60) return `in ${m.minutesUntil}m`;
  const h = Math.floor(m.minutesUntil / 60);
  const rest = m.minutesUntil % 60;
  return rest ? `in ${h}h ${String(rest).padStart(2, "0")}m` : `in ${h}h`;
}

/** "45m", "1h 30m", "2h". */
export function durationLabel(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${h}h ${rest}m` : `${h}h`;
}

/** "today", "tomorrow", "overdue", or a short date. */
export function dueLabel(dueMs: number, now: number): string {
  if (sameLocalDay(dueMs, now)) return dueMs < now ? "due earlier today" : "due today";
  if (dueMs < now) return "overdue";
  if (sameLocalDay(dueMs, now + 24 * 3600_000)) return "due tomorrow";
  return `due ${new Date(dueMs).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}
