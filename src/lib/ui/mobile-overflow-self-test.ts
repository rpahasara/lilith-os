/**
 * Headless regression test for the two mobile overflow fixes:
 *
 *   Career — the workspace grid's single column below xl is minmax(0, 1fr), the
 *   tracker card is a size container, and a row wraps its title, company and
 *   contact when narrow (truncating only from @md up, as approved), with the
 *   filters wrapping instead of scrolling.
 *
 *   Command Center — the stage-anchored avatar viewports cap at the hero's
 *   width (100cqw) below xl only; peeks are untouched and the desktop pixel caps
 *   are unchanged.
 *
 * Server-renders real components with invented data; reads source for layout
 * classes. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ApplicationRow } from "@/components/career/application-row";
import { ApplicationTracker } from "@/components/career/application-tracker";
import { createPresenceProfiles, STAGE_FIT } from "@/lib/presence/presence-profiles";
import type { Application } from "@/lib/career/types";
import type { PresenceFraming } from "@/lib/presence/presence-types";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const read = (...path: string[]) => readFileSync(join(root, ...path), "utf8");

// Invented: long enough to have overflowed a phone before the fix.
const APP: Application = {
  id: "app_invented_1",
  company: "Example Systems International",
  role: "Senior Platform Reliability Engineer - Distributed Operations (Remote, Europe Hours)",
  stage: "applied",
  confidence: 88,
  sourceAccount: "invented · inbox",
  activityCount: 3,
  lastActivity: new Date(Date.now() - 2 * 86400000).toISOString(),
  lastActivityLabel: "Invented acknowledgement for the platform reliability engineering application",
  location: "Remote",
  recruiter: { contact: "a.very.long.invented.contact.address@example.invalid" },
  nextAction: { label: "Send the invented follow-up" },
  followUp: true,
};

const classOf = (html: string, tag: string, text: string) => {
  const i = html.indexOf(text);
  const open = html.lastIndexOf(`<${tag}`, i);
  return /class="([^"]*)"/.exec(html.slice(open, i))?.[1] ?? "";
};

export function runMobileOverflowSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `mobile-overflow: ${name}`, pass, detail: pass ? undefined : detail });

  /* career ---------------------------------------------------------------------- */
  const page = read("src", "app", "career", "page.tsx");
  check("the career grid's one column below xl cannot grow past the page",
    /className="grid grid-cols-1 gap-4 xl:grid-cols-\[1fr_360px\]"/.test(page));

  const tracker = renderToStaticMarkup(createElement(ApplicationTracker, { applications: [APP], onSelect: () => {} }));
  check("the tracker card is a size container", /class="[^"]*@container[^"]*"/.test(tracker));
  const tabs = classOf(tracker, "div", ">Needs attention<");
  check("filters wrap when narrow and keep the approved pill from @md",
    /\bflex-wrap\b/.test(tabs) && /@md:flex-nowrap/.test(tabs) && /@md:rounded-full/.test(tabs), tabs);
  check("every filter is still offered", ["Active", "Needs attention", "Offers", "All"].every((f) => tracker.includes(`>${f}<`)));

  const row = renderToStaticMarkup(createElement(ApplicationRow, { app: APP, onSelect: () => {} }));
  const title = classOf(row, "h3", APP.role);
  check("a narrow row wraps the title; it truncates from @md as before",
    /\[overflow-wrap:anywhere\]/.test(title) && /@md:truncate/.test(title) && !/(^|\s)truncate(\s|$)/.test(title), title);
  const company = classOf(row, "p", APP.company);
  check("the company line wraps when narrow too", /\[overflow-wrap:anywhere\]/.test(company) && /@md:truncate/.test(company), company);
  const contact = classOf(row, "p", APP.recruiter!.contact!);
  check("a long contact wraps when narrow instead of being cut off",
    /\[overflow-wrap:anywhere\]/.test(contact) && /@md:truncate/.test(contact), contact);
  check("nothing in the row is dropped",
    [APP.role, APP.company, APP.location!, APP.lastActivityLabel, APP.sourceAccount, "3 events", APP.recruiter!.contact!, APP.nextAction!.label, "Follow-up signal"]
      .every((t) => row.includes(t)));
  check("the row keeps its button semantics", /^<button type="button"[^>]*aria-pressed/.test(row) || /<button[^>]*type="button"/.test(row));
  const metaGrid = /class="(mt-3 grid [^"]*)"/.exec(row)?.[1] ?? "";
  check("details drop to one column on the narrowest cards and keep 4 from @md",
    /(^|\s)grid-cols-1(\s|$)/.test(metaGrid) && /@min-\[13rem\]:grid-cols-2/.test(metaGrid) && /@md:grid-cols-4/.test(metaGrid), metaGrid);
  const header = /class="(contents [^"]*)"/.exec(row)?.[1] ?? "";
  check("narrow: the header joins the row grid; @md: the approved flex header",
    /(^|\s)contents(\s|$)/.test(header) && /@md:flex/.test(header) && /@md:justify-between/.test(header) && /@md:items-start/.test(header), header);
  const badges = classOf(row, "div", "Follow-up signal");
  check("from @md the badges keep the header's top alignment", /@md:self-auto/.test(badges), badges);
  const mark = classOf(row, "div", ">E<");
  check("from @md the company mark is the approved 44px tile spanning the row",
    /@md:h-11/.test(mark) && /@md:w-11/.test(mark) && /@md:row-span-2/.test(mark), mark);

  /* command center ---------------------------------------------------------------- */
  const framing: PresenceFraming = { scale: 1, offsetX: 0, offsetY: 0, cameraDistance: 3, fov: 30, targetY: 1 };
  const profiles = createPresenceProfiles(framing);
  check("the dashboard avatar keeps its 780px cap and also fits the column",
    profiles["dashboard-close"].viewport.maxWidth === `min(780px, ${STAGE_FIT})` && STAGE_FIT === "100cqw");
  check("the scenic avatar keeps its 760px cap and also fits the column",
    profiles["scenic-full-body"].viewport.maxWidth === `min(760px, ${STAGE_FIT})`);
  check("the overshoot that gives her hair room is unchanged",
    profiles["dashboard-close"].viewport.width === "170%" && profiles["scenic-full-body"].viewport.width === "156%");
  check("edge peeks are untouched (fixed size, no column cap)",
    (["peek-left", "peek-right", "peek-top"] as const).every((s) => profiles[s].viewport.maxWidth === undefined));
  const hero = read("src", "components", "presence", "presence-hero.tsx");
  check("the hero is the size container below xl only (desktop framing unchanged)",
    /className="relative flex h-full flex-col items-center justify-between pb-1 pt-2 max-xl:@container"/.test(hero));
  const stage = read("src", "components", "presence", "presence-stage.tsx");
  check("the frame-rate fallback still swaps the avatar for the static bloom",
    /fps < 20/.test(stage) && /lowStreak\.current >= 2/.test(stage) && /!webgl \|\| degraded\) \{\s*content = <StaticPresence \/>/.test(stage));

  return out;
}
