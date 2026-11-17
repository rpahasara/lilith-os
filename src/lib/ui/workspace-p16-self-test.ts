/**
 * Headless regression test for P1-6 (workspace simplification): the five-tile
 * rows stay gone from Career, Meetings and Automations, the figures only they
 * showed are kept where they moved, the insights panel and the event timeline
 * each have one implementation, Career's two overlapping rail panels are one
 * "Next steps" list, and the Meetings brief sits directly under its meeting.
 *
 * Fixtures are invented. Server-renders real components where it can; reads
 * source where the thing under test is a file convention. Run by
 * `npm run test:core`.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FleetOverview } from "@/components/automations/fleet-overview";
import { matching } from "@/components/automations/systems-grid";
import { NextSteps } from "@/components/career/next-steps";
import { PipelineOverview } from "@/components/career/pipeline-overview";
import { EventTimeline } from "@/components/ui/event-timeline";
import { LilithInsights } from "@/components/ui/lilith-insights";
import { nextSteps } from "@/lib/career/next-steps";
import type { AutomationUnit } from "@/lib/automations/types";
import type { Application } from "@/lib/career/types";
import { CheckCircle2 } from "lucide-react";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const src = (...path: string[]) => readFileSync(join(root, "src", ...path), "utf8");

function filesUnder(...path: string[]): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(entry.name) && !/self-test\.ts$/.test(entry.name)) out.push(full);
    }
  };
  walk(join(root, "src", ...path));
  return out;
}

const DAY = 86_400_000;
const T0 = Date.parse("2026-11-17T12:00:00Z");
const iso = (days: number) => new Date(T0 + days * DAY).toISOString();

function app(id: string, over: Partial<Application> = {}): Application {
  return {
    id,
    company: `Company ${id}`,
    role: "Engineer",
    stage: "applied",
    confidence: 50,
    lastActivity: iso(-1),
    lastActivityLabel: "Applied",
    activityCount: 1,
    sourceAccount: "test",
    ...over,
  } as Application;
}

function unit(id: string, over: Partial<AutomationUnit>): AutomationUnit {
  return { id, name: id, unit: `${id}.service`, kind: "service", status: "running", enabled: true, trigger: "continuous", purpose: "test", ...over } as AutomationUnit;
}

export function runWorkspaceP16SelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `p1-6: ${name}`, pass, detail: pass ? undefined : detail });

  /* the tile rows are gone ---------------------------------------------------- */
  for (const [page, header] of [["career", "career-header"], ["meetings", "meetings-header"], ["automations", "automations-header"]]) {
    const text = src("components", page, `${header}.tsx`);
    check(`${page} header has no metric tiles`, !/MetricTile/.test(text));
    check(`${page} loading skeleton has no tile row`, !/lg:grid-cols-5/.test(src("components", page, `${page}-skeleton.tsx`)));
  }

  /* what only the tiles showed is kept ---------------------------------------- */
  const pipeline = renderToStaticMarkup(
    createElement(PipelineOverview, {
      pipeline: [{ stage: "applied", count: 3 }, { stage: "interview", count: 2 }],
      overview: { totalActive: 5, interviews: 2, offers: 0, responseRate: 41, pipelineHealth: 67 },
    }),
  );
  const text = (html: string) => html.replace(/<!-- -->/g, "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
  check("career response rate and pipeline health move onto the pipeline",
    /5 ?in flight/.test(text(pipeline)) && /response 41 ?%/.test(text(pipeline)) && /health 67 ?\/100/.test(text(pipeline)), text(pipeline).slice(0, 200));

  const fleet = renderToStaticMarkup(createElement(FleetOverview, { health: { score: 86, total: 7, running: 4, active: 1, waiting: 1, failed: 1 } }));
  check("automations health and status counts move onto the fleet panel",
    /86 ?%/.test(text(fleet)) && /Running 4 Active 1 Scheduled 1 Failed 1/.test(text(fleet)) && /7 ?units/.test(text(fleet)), text(fleet).slice(0, 200));

  const units = [
    unit("a", { kind: "service" }),
    unit("b", { kind: "watcher", status: "failed" }),
    unit("c", { kind: "timer", enabled: false, status: "inactive" }),
    unit("d", { kind: "agent" }),
  ];
  check("each filter tab counts exactly what it shows",
    matching(units, "all").length === 4 && matching(units, "failed").length === 1 &&
      matching(units, "paused").length === 1 && matching(units, "watcher").length === 1);

  const schedule = src("components", "meetings", "timeline-today.tsx");
  check("meetings schedule says how many are prepared", /prepared/.test(schedule) && /e\.prepared/.test(schedule));

  /* one implementation each ---------------------------------------------------- */
  const definesInsights = filesUnder("components").filter((f) => /title="Lilith insights"/.test(readFileSync(f, "utf8")));
  check("one Lilith insights component", definesInsights.length === 1 && /lilith-insights\.tsx$/.test(definesInsights[0]), definesInsights.join(", "));
  check("the copied insights panels are gone",
    !existsSync(join(root, "src/components/career/insights-panel.tsx")) && !existsSync(join(root, "src/components/automations/ops-insights.tsx")));
  check("both timelines use the shared one",
    /EventTimeline/.test(src("components", "career", "activity-timeline.tsx")) &&
      /EventTimeline/.test(src("components", "automations", "execution-timeline.tsx")) &&
      !/motion\.ol/.test(src("components", "career", "activity-timeline.tsx")) &&
      !/motion\.ol/.test(src("components", "automations", "execution-timeline.tsx")));

  const insights = renderToStaticMarkup(createElement(LilithInsights, { insights: [{ id: "1", title: "Invented insight", detail: "Detail", tone: "risk" }] }));
  check("the shared insights panel renders its items", insights.includes("Invented insight") && insights.includes("Lilith insights"));
  check("the shared insights panel says so when it has nothing",
    renderToStaticMarkup(createElement(LilithInsights, { insights: [] })).includes("Nothing to point out"));
  check("the shared timeline renders and has an honest empty state",
    renderToStaticMarkup(createElement(EventTimeline, { title: "T", empty: "Nothing yet.", items: [{ id: "x", icon: CheckCircle2, color: "text-green", text: "Ran", meta: "now" }] })).includes("Ran") &&
      renderToStaticMarkup(createElement(EventTimeline, { title: "T", empty: "Nothing yet.", items: [] })).includes("Nothing yet."));

  /* Career: one "Next steps" list ------------------------------------------------ */
  const apps = [
    app("late", { nextAction: { label: "Send portfolio", due: iso(5) } }),
    app("soon", { nextAction: { label: "Reply to recruiter", due: iso(1) } }),
    app("prep", { stage: "interview" }),
    app("prep-dated", { stage: "final_interview", nextAction: { label: "Final round", due: iso(2) } }),
    app("idle"),
  ];
  const steps = nextSteps(apps);
  check("next steps include stated actions and interview-stage applications, once each",
    steps.map((s) => s.application.id).join() === "soon,prep-dated,late,prep");
  check("applications with nothing to do are left out", !steps.some((s) => s.application.id === "idle"));
  check("next steps are capped", nextSteps(Array.from({ length: 20 }, (_, i) => app(`a${i}`, { stage: "interview" }))).length === 6);
  check("the two overlapping rail panels are one",
    !existsSync(join(root, "src/components/career/next-actions.tsx")) && !existsSync(join(root, "src/components/career/interview-prep.tsx")));
  const stepsHtml = renderToStaticMarkup(createElement(NextSteps, { applications: apps, onSelect: () => {} }));
  check("each step opens its application (a real control, not a dead card)",
    (stepsHtml.match(/<button/g) ?? []).length === 4 && !/data-unavailable/.test(stepsHtml));

  /* Meetings: the brief sits under its meeting ----------------------------------- */
  const meetings = src("app", "meetings", "page.tsx");
  const order = ["<NextMeeting", "<MeetingIntelligence", "<TimelineToday"].map((tag) => meetings.indexOf(tag));
  check("meetings: next meeting, then its brief, then the schedule", order.every((i) => i > 0) && order[0] < order[1] && order[1] < order[2], order.join());
  check("choosing a meeting in the schedule brings its brief into view, respecting reduced motion",
    /scrollIntoView/.test(meetings) && /prefers-reduced-motion/.test(meetings));

  return out;
}
