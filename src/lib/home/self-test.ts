/**
 * Headless regression test: the Command Center's TODAY and NEXT cards must
 * never present fabricated, demo or stale information as the owner's live day.
 *
 * Covers the pure derivation (`deriveHomeMeetings`) and server-renders the real
 * cards for each state. Fakes only: no browser, no backend. Run by
 * `npm run test:core`.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { TodayCard } from "@/components/home/today-card";
import { NextCard } from "@/components/home/next-card";
import { brief, nextEvent, pipeline } from "@/lib/data";
import type { Followup, MeetingEvent, MeetingsData } from "@/lib/meetings/types";
import {
  STALE_AFTER_MS,
  countdownLabel,
  deriveHomeMeetings,
  safeJoinUrl,
  type HomeMeetingsView,
} from "./meetings-view";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const MIN = 60_000;
// 14:00 local on a fixed day, so "today"/"tomorrow" are deterministic.
const NOW = new Date(2026, 10, 11, 14, 0, 0).getTime();
const iso = (t: number) => new Date(t).toISOString();

function event(over: Partial<MeetingEvent> & { id: string }): MeetingEvent {
  return {
    title: `Meeting ${over.id}`,
    allDay: false,
    hasDescription: false,
    attendees: [],
    attendeeCount: 0,
    prepStatus: "scheduled",
    prepared: false,
    briefAvailable: false,
    contextAvailable: false,
    joinLink: null,
    ...over,
  };
}

function followup(over: Partial<Followup> & { id: string }): Followup {
  return { title: `Follow-up ${over.id}`, status: "waiting", dueKind: "date", ...over };
}

/** `generatedAt: null` = the backend sent no generation time. */
function data(over: Partial<MeetingsData> = {}, generatedAt: string | null = iso(NOW - 5 * MIN)): MeetingsData {
  return {
    isDemo: false,
    overview: {
      generatedAt: generatedAt ?? undefined,
      counts: { upcomingTotal: 0, todayTotal: 0, prepared: 0, followupsTotal: 0, followupsPending: 0, contextMessages: 0 },
      next: null,
    },
    events: [],
    followups: [],
    ...over,
  };
}

/**
 * Generic labels that real derived data legitimately renders. Their fabricated
 * values (e.g. "Recommended 2h") are still guarded below.
 */
const LEGITIMATE_LABELS = new Set(["Focus window open"]);

/** Every fact the old hard-coded cards showed (read from the demo module). */
const FABRICATED = [
  nextEvent.title,
  nextEvent.where,
  `in ${nextEvent.inMinutes}m`,
  `${nextEvent.people} attending`,
  `Focus ${pipeline.focusScore}`,
  ...brief.flatMap((b) => [b.text, b.meta]),
].filter((s) => !LEGITIMATE_LABELS.has(s));

function markup(view: HomeMeetingsView, now: number | null = NOW) {
  return {
    today: renderToStaticMarkup(createElement(TodayCard, { view, now })),
    next: renderToStaticMarkup(createElement(NextCard, { view })),
  };
}

function tagsOf(html: string, tag: "button" | "a"): string[] {
  return html.match(new RegExp(`<${tag}\\b[^>]*>`, "g")) ?? [];
}

export function runHomeSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `home: ${name}`, pass, detail: pass ? undefined : detail });

  /* ------------------------------------------------ derivation: sources */
  check("no data while loading is loading", deriveHomeMeetings(null, true, NOW).kind === "loading");
  check("no data after loading is unavailable", deriveHomeMeetings(null, false, NOW).kind === "unavailable");
  const demo = deriveHomeMeetings(
    data({ isDemo: true, events: [event({ id: "d", start: iso(NOW + 30 * MIN), end: iso(NOW + 60 * MIN) })] }),
    false, NOW);
  check("demo meetings never reach Home (unavailable instead)", demo.kind === "unavailable", JSON.stringify(demo));

  /* ------------------------------------------------ derivation: countdown */
  const snapshot = deriveHomeMeetings(
    data({ events: [event({ id: "a", start: iso(NOW + 120 * MIN), end: iso(NOW + 150 * MIN), minutesUntil: 45 })] }),
    false, NOW);
  const nextA = snapshot.kind === "live" ? snapshot.next : null;
  check("countdown is recomputed from start, ignoring the stored minutes_until",
    !!nextA && nextA.minutesUntil === 120 && countdownLabel(nextA) === "in 2h", JSON.stringify(nextA));

  const later = deriveHomeMeetings(
    data({ events: [event({ id: "a", start: iso(NOW + 120 * MIN), end: iso(NOW + 150 * MIN) })] }),
    false, NOW + 10 * MIN);
  check("countdown advances with the clock (never frozen)",
    later.kind === "live" && later.next?.minutesUntil === 110);

  const mixed = deriveHomeMeetings(data({
    events: [
      event({ id: "past", start: iso(NOW - 90 * MIN), end: iso(NOW - 60 * MIN) }),
      event({ id: "no-end", start: iso(NOW - 10 * MIN) }),
      event({ id: "allday", allDay: true, start: iso(NOW - 60 * MIN) }),
      event({ id: "running", start: iso(NOW - 15 * MIN), end: iso(NOW + 15 * MIN) }),
      event({ id: "soon", start: iso(NOW + 30 * MIN), end: iso(NOW + 60 * MIN) }),
    ],
  }), false, NOW);
  const running = mixed.kind === "live" ? mixed.next : null;
  check("past, endless-past and all-day events are not shown as next; running is 'Now'",
    running?.id === "running" && running.inProgress && countdownLabel(running) === "Now", JSON.stringify(running));

  /* ------------------------------------------------ derivation: freshness */
  const fresh = deriveHomeMeetings(data({}, iso(NOW - 10 * MIN)), false, NOW);
  const stale = deriveHomeMeetings(data({}, iso(NOW - STALE_AFTER_MS - MIN)), false, NOW);
  const unknown = deriveHomeMeetings(data({}, null), false, NOW);
  check("a recent agenda is not stale", fresh.kind === "live" && !fresh.stale);
  check("an old agenda is flagged stale", stale.kind === "live" && stale.stale);
  check("an agenda with no generation time is flagged stale", unknown.kind === "live" && unknown.stale);

  /* ------------------------------------------------ derivation: today/followups/focus */
  const day = deriveHomeMeetings(data({
    events: [
      event({ id: "m1", start: iso(NOW - 120 * MIN), end: iso(NOW - 90 * MIN) }),
      event({ id: "m2", start: iso(NOW + 60 * MIN), end: iso(NOW + 90 * MIN) }),
      event({ id: "tomorrow", start: iso(NOW + 24 * 60 * MIN), end: iso(NOW + 24 * 60 * MIN + 30 * MIN) }),
    ],
    followups: [
      followup({ id: "resolved", status: "resolved", due: iso(NOW + MIN) }),
      followup({ id: "window", dueKind: "window", due: iso(NOW + 2 * MIN) }),
      followup({ id: "later", title: "Later one", due: iso(NOW + 3 * 24 * 60 * MIN) }),
      followup({ id: "soonest", title: "Soonest one", due: iso(NOW + 24 * 60 * MIN) }),
    ],
  }), false, NOW);
  check("today counts only today's meetings, remaining by end time",
    day.kind === "live" && day.today.total === 2 && day.today.remaining === 1, JSON.stringify(day.kind === "live" && day.today));
  check("next follow-up is the earliest open dated one",
    day.kind === "live" && day.nextDue?.title === "Soonest one", JSON.stringify(day.kind === "live" && day.nextDue));
  check("focus is a real gap (current window until the next meeting)",
    day.kind === "live" && !!day.focus && day.focus.current && day.focus.minutes === 60,
    JSON.stringify(day.kind === "live" && day.focus));
  check("no score of any kind is derived", !/score/i.test(JSON.stringify(day)));

  /* ------------------------------------------------ join links */
  check("join link: https accepted", safeJoinUrl("https://meet.example.com/abc") === "https://meet.example.com/abc");
  check("join link: javascript/http/garbage rejected",
    safeJoinUrl("javascript:alert(1)") === null && safeJoinUrl("http://meet.example.com/x") === null &&
    safeJoinUrl("not a url") === null && safeJoinUrl(null) === null);

  /* ------------------------------------------------ rendered cards */
  const liveWithLink = deriveHomeMeetings(data({
    events: [event({ id: "x", title: "Real sync", start: iso(NOW + 30 * MIN), end: iso(NOW + 60 * MIN),
      joinLink: "https://meet.example.com/real", attendeeCount: 3, calendar: "Work" })],
  }), false, NOW);
  const liveNoLink = deriveHomeMeetings(data({
    events: [event({ id: "y", title: "No link sync", start: iso(NOW + 30 * MIN), end: iso(NOW + 60 * MIN),
      joinLink: "javascript:alert(1)" })],
  }), false, NOW);
  const liveEmpty = deriveHomeMeetings(data(), false, NOW);

  const states: Record<string, ReturnType<typeof markup>> = {
    loading: markup({ kind: "loading" }, null),
    unavailable: markup({ kind: "unavailable" }),
    "live empty": markup(liveEmpty),
    "live with link": markup(liveWithLink),
    "live without link": markup(liveNoLink),
  };

  for (const [state, html] of Object.entries(states)) {
    const both = html.today + html.next;
    const leaked = FABRICATED.filter((s) => both.includes(s));
    check(`${state}: no hard-coded sample content`, leaked.length === 0, `leaked: ${leaked.join(" | ")}`);
    const enabled = tagsOf(both, "button").filter((b) => !/\sdisabled=""/.test(b));
    check(`${state}: no enabled button without a real action`, enabled.length === 0, enabled.join(" "));
  }

  for (const state of ["loading", "unavailable", "live empty"]) {
    const n = states[state].next;
    check(`${state}: NEXT offers no actions`, tagsOf(n, "button").length === 0 && tagsOf(n, "a").length === 0, n);
  }
  check("unavailable: both cards say so explicitly",
    /Agenda unavailable/.test(states.unavailable.today) && /Meetings unavailable/.test(states.unavailable.next));
  check("loading: both cards are marked busy",
    /aria-busy="true"/.test(states.loading.today) && /aria-busy="true"/.test(states.loading.next));

  const withLink = states["live with link"].next;
  const joinA = tagsOf(withLink, "a").find((a) => /data-home-action="join"/.test(a)) ?? "";
  check("live with link: Join opens the meeting's own https URL safely",
    /href="https:\/\/meet\.example\.com\/real"/.test(joinA) && /target="_blank"/.test(joinA) &&
    /rel="noopener noreferrer"/.test(joinA), joinA);
  check("live with link: real title, countdown and attendee count shown",
    /Real sync/.test(withLink) && /in 30m/.test(withLink) && /3 attendees/.test(withLink));

  for (const state of ["live with link", "live without link"]) {
    const prep = tagsOf(states[state].next, "button").find((b) => /data-home-action="prep"/.test(b)) ?? "";
    check(`${state}: Prep with Lilith is disabled with a reason`, /\sdisabled=""/.test(prep) && /\stitle="/.test(prep), prep);
  }
  const noLink = states["live without link"].next;
  const joinB = tagsOf(noLink, "button").find((b) => /data-home-action="join"/.test(b)) ?? "";
  check("live without (safe) link: Join is disabled, no unsafe href",
    /\sdisabled=""/.test(joinB) && !/javascript:/.test(noLink), joinB);

  check("stale agenda: TODAY says 'as of'",
    /as of /.test(markup(stale).today) && !/as of /.test(markup(fresh).today));

  /* ------------------------------------------------ source guard */
  const root = process.cwd();
  const sources = ["src/app/page.tsx", "src/components/home/today-card.tsx", "src/components/home/next-card.tsx"];
  const importing = sources.filter((p) => /from\s+["']@\/lib\/data["']/.test(readFileSync(join(root, p), "utf8")));
  check("Command Center home cards do not import the hard-coded demo module",
    importing.length === 0, importing.join(", "));

  return out;
}
