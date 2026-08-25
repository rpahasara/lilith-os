/**
 * Isolated demo adapter for the Meetings module.
 *
 * Used ONLY when the backend is unreachable. Every record is SYNTHETIC sample
 * data for UX review (times are relative to now so the timeline reads live).
 * Never treated as, or written back to, production state (`isDemo` is true).
 * Contains no real calendar/Gmail content.
 */
import type {
  Followup,
  MeetingContext,
  MeetingEvent,
  MeetingsData,
  PrepBrief,
} from "./types";

const min = (n: number) => n * 60_000;
const iso = (ms: number) => new Date(ms).toISOString();

function buildEvents(now: number): MeetingEvent[] {
  return [
    {
      id: "dm_standup",
      title: "Team Standup",
      calendar: "Work",
      start: iso(now - min(180)),
      end: iso(now - min(165)),
      durationMinutes: 15,
      allDay: false,
      minutesUntil: -180,
      joinLink: "https://meet.google.com/demo-standup",
      hasDescription: false,
      attendees: [
        { displayName: "Priya N.", emailMasked: "p***a@acme.dev", domain: "acme.dev" },
        { displayName: "Tom A.", emailMasked: "t***m@acme.dev", domain: "acme.dev" },
      ],
      attendeeCount: 4,
      prepStatus: "completed",
      prepared: true,
      briefAvailable: false,
      contextAvailable: false,
    },
    {
      id: "dm_interview",
      title: "Interview — Senior DevOps Engineer",
      calendar: "Primary",
      start: iso(now + min(24)),
      end: iso(now + min(84)),
      durationMinutes: 60,
      allDay: false,
      minutesUntil: 24,
      joinLink: "https://meet.google.com/demo-interview",
      hasDescription: true,
      attendees: [
        { displayName: "Dana Whitfield", emailMasked: "d***a@hatchyard.io", domain: "hatchyard.io" },
        { displayName: "Recruiting Team", emailMasked: "t***m@hatchyard.io", domain: "hatchyard.io" },
      ],
      attendeeCount: 2,
      prepStatus: "delivered",
      prepared: true,
      briefAvailable: true,
      contextAvailable: true,
    },
    {
      id: "dm_oneonone",
      title: "1:1 with Manager",
      calendar: "Work",
      start: iso(now + min(180)),
      end: iso(now + min(210)),
      durationMinutes: 30,
      allDay: false,
      minutesUntil: 180,
      joinLink: null,
      hasDescription: false,
      attendees: [{ displayName: "Marcus Lee", emailMasked: "m***e@acme.dev", domain: "acme.dev" }],
      attendeeCount: 2,
      prepStatus: "detected",
      prepared: false,
      briefAvailable: false,
      contextAvailable: false,
    },
    {
      id: "dm_arch",
      title: "Architecture Review — Memory v2",
      calendar: "Work",
      start: iso(now + min(1500)),
      end: iso(now + min(1560)),
      durationMinutes: 60,
      allDay: false,
      minutesUntil: 1500,
      joinLink: "https://meet.google.com/demo-arch",
      hasDescription: true,
      attendees: [
        { displayName: "Priya N.", emailMasked: "p***a@acme.dev", domain: "acme.dev" },
        { displayName: "Elena R.", emailMasked: "e***a@acme.dev", domain: "acme.dev" },
      ],
      attendeeCount: 3,
      prepStatus: "scheduled",
      prepared: false,
      briefAvailable: false,
      contextAvailable: false,
    },
  ];
}

const followups: Followup[] = [
  {
    id: "dfu_1",
    title: "Send portfolio + system-design notes to recruiter",
    source: "gmail",
    reason: "Recruiter asked for a portfolio ahead of the DevOps interview.",
    status: "waiting",
    due: new Date(Date.now() + min(60 * 20)).toISOString().slice(0, 10),
    dueKind: "date",
    dueConfidence: "high",
  },
  {
    id: "dfu_2",
    title: "Follow up on Architecture Review agenda",
    source: "gmail",
    reason: "Confirm scope for the Memory v2 review.",
    status: "resolved",
    due: null,
    dueKind: "none",
    resolution: "Agenda confirmed with the team.",
  },
];

const context: MeetingContext = {
  eventId: "dm_interview",
  generatedAt: new Date().toISOString(),
  keywords: ["devops", "kubernetes", "interview", "hatchyard", "azure", "terraform"],
  messages: [
    { account: "primary", subject: "Interview confirmation — Senior DevOps Engineer", from: "Dana Whitfield <d***a@hatchyard.io>", date: new Date(Date.now() - min(1440)).toUTCString(), relevanceScore: 8 },
    { account: "primary", subject: "Re: Application — DevOps role", from: "d***a@hatchyard.io", date: new Date(Date.now() - min(4320)).toUTCString(), relevanceScore: 5 },
    { account: "primary", subject: "Your application was received", from: "n***y@hatchyard.io", date: new Date(Date.now() - min(7200)).toUTCString(), relevanceScore: 3 },
  ],
  messageCount: 3,
  followups: [followups[0]],
};

const DEMO_BRIEFS: Record<string, PrepBrief> = {
  dm_interview: {
    eventId: "dm_interview",
    generatedAt: new Date(Date.now() - min(9)).toISOString(),
    sourceCounts: { gmailMessages: 3, followups: 1 },
    brief: [
      "This is a first-round interview for a Senior DevOps Engineer role at Hatchyard, arranged by Dana Whitfield (recruiter).",
      "",
      "Likely focus: Kubernetes, CI/CD, IaC (Terraform), and cloud reliability — matched from the recruiter thread and your application.",
      "",
      "Prepare:",
      "• A crisp 2-minute summary of a production incident you resolved (SRE angle).",
      "• One IaC example you can whiteboard end-to-end.",
      "• Questions on team structure, on-call, and how they measure reliability.",
      "",
      "Outstanding: send your portfolio + system-design notes (follow-up due soon).",
    ].join("\n"),
  },
};

export function demoBriefFor(eventId: string): PrepBrief | null {
  return DEMO_BRIEFS[eventId] ?? null;
}

export function buildDemoMeetingsData(): MeetingsData {
  const now = Date.now();
  const events = buildEvents(now);
  const upcoming = events.filter((e) => (e.minutesUntil ?? -1) >= 0);
  const next = upcoming[0];

  return {
    isDemo: true,
    overview: {
      generatedAt: new Date().toISOString(),
      timezone: "Asia/Colombo",
      counts: {
        upcomingTotal: upcoming.length,
        todayTotal: events.filter((e) => Math.abs(e.minutesUntil ?? 9999) < 720).length,
        prepared: events.filter((e) => e.prepared).length,
        followupsTotal: followups.length,
        followupsPending: followups.filter((f) => f.status === "waiting").length,
        contextMessages: context.messageCount,
      },
      next: next
        ? {
            id: next.id,
            title: next.title,
            start: next.start,
            minutesUntil: next.minutesUntil,
            prepStatus: next.prepStatus,
          }
        : null,
      prepTimer: { available: true, active: "active", result: "success" },
      agendaSnapshot: { available: true, active: "active", result: "success" },
    },
    events,
    context,
    followups,
  };
}
