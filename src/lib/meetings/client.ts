/**
 * Meetings API client.
 *
 * Fetches the read-only /meetings/* endpoints through the shared proxy/direct
 * layer and normalises to the domain types. Falls back to the isolated demo
 * adapter when the backend is unreachable. Live and demo data are never mixed:
 * `/meetings/overview` (or `/meetings/upcoming`) is the backbone — without it
 * the whole payload is demo.
 */
import { buildDemoMeetingsData } from "./demo";
import {
  PREP_STAGES,
  type Attendee,
  type ContextMessage,
  type Followup,
  type MeetingContext,
  type MeetingEvent,
  type MeetingsData,
  type MeetingsOverview,
  type PrepBrief,
  type PrepStatus,
} from "./types";
import { fetchEndpoint, toDiagnostics, type EndpointResult } from "@/lib/api";

const PREP_SET = new Set<string>([...PREP_STAGES, "scheduled"]);

function str(v: unknown, fb = ""): string {
  return v == null ? fb : String(v);
}
function numOrNull(v: unknown): number | null {
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? n : null;
}
function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
function asPrep(v: unknown): PrepStatus {
  return PREP_SET.has(v as string) ? (v as PrepStatus) : "scheduled";
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function normAttendee(a: any): Attendee {
  return {
    displayName: a.display_name ? str(a.display_name) : undefined,
    emailMasked: a.email_masked ? str(a.email_masked) : undefined,
    domain: a.domain ? str(a.domain) : undefined,
  };
}

function normEvent(e: any): MeetingEvent {
  return {
    id: str(e.id ?? e.event_id),
    title: str(e.title ?? "(Untitled event)"),
    calendar: e.calendar ? str(e.calendar) : undefined,
    start: e.start ? str(e.start) : undefined,
    end: e.end ? str(e.end) : undefined,
    durationMinutes: numOrNull(e.duration_minutes),
    allDay: Boolean(e.all_day),
    minutesUntil: numOrNull(e.minutes_until),
    joinLink: e.join_link ? str(e.join_link) : null,
    hasDescription: Boolean(e.has_description),
    attendees: arr(e.attendees).map(normAttendee),
    attendeeCount: numOrNull(e.attendee_count) ?? arr(e.attendees).length,
    prepStatus: asPrep(e.prep_status),
    prepared: Boolean(e.prepared),
    briefAvailable: Boolean(e.brief_available),
    contextAvailable: Boolean(e.context_available),
  };
}

function normFollowup(f: any): Followup {
  return {
    id: str(f.id),
    title: str(f.title),
    source: f.source ? str(f.source) : undefined,
    reason: f.reason ? str(f.reason) : undefined,
    status: str(f.status ?? "waiting"),
    due: f.due ? str(f.due) : null,
    dueKind: (["date", "window", "none"].includes(f.due_kind) ? f.due_kind : "none") as
      | "date"
      | "window"
      | "none",
    dueConfidence: f.due_confidence ? str(f.due_confidence) : null,
    createdAt: f.created_at ? str(f.created_at) : undefined,
    updatedAt: f.updated_at ? str(f.updated_at) : undefined,
    resolvedAt: f.resolved_at ? str(f.resolved_at) : null,
    resolution: f.resolution ? str(f.resolution) : null,
  };
}

function normMessage(m: any): ContextMessage {
  return {
    account: m.account ? str(m.account) : undefined,
    subject: str(m.subject),
    from: str(m.from),
    date: m.date ? str(m.date) : undefined,
    relevanceScore: numOrNull(m.relevance_score) ?? undefined,
  };
}

function normOverview(o: any): MeetingsOverview {
  const c = o?.counts ?? {};
  return {
    generatedAt: o?.generated_at ? str(o.generated_at) : undefined,
    timezone: o?.timezone ? str(o.timezone) : undefined,
    counts: {
      upcomingTotal: numOrNull(c.upcoming_total) ?? 0,
      todayTotal: numOrNull(c.today_total) ?? 0,
      prepared: numOrNull(c.prepared) ?? 0,
      followupsTotal: numOrNull(c.followups_total) ?? 0,
      followupsPending: numOrNull(c.followups_pending) ?? 0,
      contextMessages: numOrNull(c.context_messages) ?? 0,
    },
    next: o?.next
      ? {
          id: str(o.next.id),
          title: str(o.next.title),
          start: o.next.start ? str(o.next.start) : undefined,
          minutesUntil: numOrNull(o.next.minutes_until),
          prepStatus: asPrep(o.next.prep_status),
        }
      : null,
    prepTimer: o?.prep_timer,
    agendaSnapshot: o?.agenda_snapshot,
  };
}

function normContext(x: any): MeetingContext {
  return {
    eventId: x?.event_id ? str(x.event_id) : undefined,
    generatedAt: x?.generated_at ? str(x.generated_at) : undefined,
    keywords: arr(x?.keywords).map((k) => str(k)),
    messages: arr(x?.messages).map(normMessage),
    messageCount: numOrNull(x?.message_count) ?? arr(x?.messages).length,
    followups: arr(x?.followups).map(normFollowup),
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/** Fetch everything the Meetings screen needs. Never throws. */
export async function getMeetingsData(signal?: AbortSignal): Promise<MeetingsData> {
  const paths = [
    "/meetings/overview",
    "/meetings/upcoming",
    "/meetings/context",
    "/meetings/followups",
  ];
  const [ovRes, upRes, ctxRes, fuRes] = (await Promise.all(
    paths.map((p) => fetchEndpoint(p, signal)),
  )) as EndpointResult[];
  const results = [ovRes, upRes, ctxRes, fuRes];

  // Overview is the backbone. Without it we serve demo data.
  if (!ovRes.ok || ovRes.data == null) {
    const demo = buildDemoMeetingsData();
    demo.diagnostics = toDiagnostics("demo", results);
    return demo;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const up: any = upRes.ok ? upRes.data : {};
  const events = arr(up?.events).map(normEvent);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fu: any = fuRes.ok ? fuRes.data : {};
  const followups = arr(fu?.followups).map(normFollowup);

  const context = ctxRes.ok ? normContext(ctxRes.data) : undefined;

  return {
    isDemo: false,
    diagnostics: toDiagnostics("live", results),
    overview: normOverview(ovRes.data),
    events,
    context,
    followups,
  };
}

/** Lazily fetch a persisted LILITH prep brief for one event. */
export async function getMeetingBrief(
  eventId: string,
  signal?: AbortSignal,
): Promise<PrepBrief | null> {
  const res = await fetchEndpoint(`/meetings/${encodeURIComponent(eventId)}/prep`, signal);
  if (!res.ok || res.data == null) return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const d: any = res.data;
  return {
    eventId: str(d.event_id ?? eventId),
    generatedAt: d.generated_at ? str(d.generated_at) : undefined,
    brief: str(d.brief),
    sourceCounts: {
      gmailMessages: numOrNull(d.source_counts?.gmail_messages) ?? undefined,
      followups: numOrNull(d.source_counts?.followups) ?? undefined,
    },
  };
}
