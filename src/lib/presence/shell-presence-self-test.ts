/**
 * Headless regression test for Lilith's presence mark in the shell: every
 * state comes from a source the client can verify, the avatar's expressive
 * engine is never used as evidence, a state without a source is never shown,
 * and the mark is accessible and still under reduced motion.
 *
 * Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ShellProviders } from "@/components/layout/app-shell";
import { TopBar } from "@/components/layout/top-bar";
import { PresenceAnnouncer, PresenceMark } from "@/components/presence/presence-mark";
import {
  PRESENCE_LABEL,
  PRESENCE_SOURCES,
  presenceAnnouncement,
  shellPresence,
  type ShellPresenceInputs,
  type ShellPresenceState,
} from "@/lib/presence/shell-presence";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const src = (...path: string[]) => readFileSync(join(process.cwd(), "src", ...path), "utf8");

const STATES: ShellPresenceState[] = [
  "checking", "available", "responding", "working", "attention", "speaking", "listening", "disconnected", "unavailable",
];
const IDLE: ShellPresenceInputs = { health: "live", sending: false, taskStatuses: [], voice: "idle", listening: false };

export function runShellPresenceSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `presence-mark: ${name}`, pass, detail: pass ? undefined : detail });

  /* each state from its source ---------------------------------------------------- */
  const cases: [string, Partial<ShellPresenceInputs>, ShellPresenceState][] = [
    ["available when the probe answered and nothing is happening", {}, "available"],
    ["connecting until the first probe finishes", { health: "checking" }, "checking"],
    ["responding while a turn is in flight", { sending: true }, "responding"],
    ["working while a task is queued", { taskStatuses: ["queued"] }, "working"],
    ["working while a task is planning", { taskStatuses: ["planning"] }, "working"],
    ["working while a task is running", { taskStatuses: ["running"] }, "working"],
    ["needs approval while a task waits for the owner", { taskStatuses: ["waiting_for_approval"] }, "attention"],
    ["a task still in review is not work", { taskStatuses: ["reviewing", "draft"] }, "available"],
    ["a blocked task is not work", { taskStatuses: ["blocked"] }, "available"],
    ["speaking only while audio is playing", { voice: "playing" }, "speaking"],
    ["loading audio is not speaking", { voice: "loading" }, "available"],
    ["paused audio is not speaking", { voice: "paused" }, "available"],
    ["listening only with real microphone capture", { listening: true }, "listening"],
    ["disconnected when the probe got no answer", { health: "unreachable" }, "disconnected"],
    ["unavailable when no backend is configured", { health: "unconfigured" }, "unavailable"],
  ];
  for (const [name, patch, expected] of cases) {
    const got = shellPresence({ ...IDLE, ...patch });
    check(name, got === expected, got);
  }

  /* priority ---------------------------------------------------------------------- */
  check("no backend outranks everything",
    shellPresence({ ...IDLE, health: "unconfigured", sending: true, voice: "playing", taskStatuses: ["running"] }) === "unavailable");
  check("speaking outranks responding, responding outranks working",
    shellPresence({ ...IDLE, voice: "playing", sending: true }) === "speaking" &&
      shellPresence({ ...IDLE, sending: true, taskStatuses: ["running"] }) === "responding");
  check("activity outranks a waiting approval; the approval returns when it ends",
    shellPresence({ ...IDLE, sending: true, taskStatuses: ["waiting_for_approval"] }) === "responding" &&
      shellPresence({ ...IDLE, taskStatuses: ["waiting_for_approval"] }) === "attention");
  check("direct evidence of activity outranks a stale probe",
    shellPresence({ ...IDLE, health: "unreachable", sending: true }) === "responding");
  check("a waiting approval outranks the connection state",
    shellPresence({ ...IDLE, health: "unreachable", taskStatuses: ["waiting_for_approval"] }) === "attention");

  /* honesty ----------------------------------------------------------------------- */
  check("every state names its source, or admits it has none",
    STATES.every((s) => s in PRESENCE_SOURCES) && STATES.filter((s) => PRESENCE_SOURCES[s] === null).join() === "listening");
  check("every state has a short label", STATES.every((s) => PRESENCE_LABEL[s].length > 3 && PRESENCE_LABEL[s].length < 22));
  const hook = src("components", "presence", "presence-mark.tsx");
  check("listening is hard-wired off: speech input does not exist", /listening: false,/.test(hook) && !/listening: (?!false)/.test(hook));
  check("the mark never reads the avatar's presence engine",
    !/usePresence\(|presence-engine|PresenceSignal|signal\./.test(hook) &&
      !/presence-engine|EVENT_MAP|PresenceSignal/.test(src("lib", "presence", "shell-presence.ts").replace(/\/\*[\s\S]*?\*\//g, "")));
  check("speaking comes from the audio player's own lifecycle", /lilithSpeech\.getSnapshot\(\)\.status/.test(hook));
  check("work comes from unfinished tasks in the command store", /tasks\.map\(\(t\) => t\.status\)\.filter\(\(s\) => !isTerminal\(s\)\)/.test(hook));
  check("the connection comes from the shared read-only probe", /useShellHealth\(\)/.test(hook));

  /* announcements ------------------------------------------------------------------ */
  check("losing Lilith is announced", /disconnected/.test(presenceAnnouncement("available", "disconnected")) &&
    /unavailable/.test(presenceAnnouncement("checking", "unavailable")));
  check("getting her back is announced", /available again/.test(presenceAnnouncement("disconnected", "available")));
  check("a request for approval is announced", /approval/.test(presenceAnnouncement("working", "attention")));
  check("routine activity is not narrated",
    presenceAnnouncement("available", "responding") === "" && presenceAnnouncement("responding", "available") === "" &&
      presenceAnnouncement("available", "working") === "" && presenceAnnouncement("checking", "available") === "" &&
      presenceAnnouncement("available", "available") === "");

  /* the mark ------------------------------------------------------------------------- */
  const css = src("app", "globals.css");
  for (const state of STATES) {
    const html = renderToStaticMarkup(createElement(PresenceMark, { state }));
    check(`the mark renders ${state} and is decorative`,
      html.includes(`data-presence="${state}"`) && /aria-hidden="true"/.test(html));
  }
  const styled = STATES.filter((s) => s !== "available" || true).filter((s) => !css.includes(`.presence-mark[data-presence="${s}"]`));
  check("every state has its own look in the stylesheet", styled.length === 0, styled.join(", "));
  const markCss = css.slice(css.indexOf(".presence-mark {"), css.indexOf("/* live status dot */"));
  check("the mark animates transform and opacity only",
    !/@keyframes presence-[a-z]+ \{[^@]*(width|height|top|left|margin|padding|filter|box-shadow)/.test(markCss));
  check("reduced motion stills the mark with the rest of the CSS",
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*animation-duration: 0\.001ms !important/.test(css));
  const announcer = renderToStaticMarkup(createElement(PresenceAnnouncer, { state: "available" }));
  check("the announcer is a polite status that starts silent",
    /role="status"/.test(announcer) && /aria-live="polite"/.test(announcer) && />\s*<\/span>$/.test(announcer));

  /* in the shell ----------------------------------------------------------------------- */
  const bar = renderToStaticMarkup(createElement(ShellProviders, null, createElement(TopBar)));
  check("the top bar shows the mark with its state in words",
    /class="presence-mark"/.test(bar) && /data-presence-state="checking"/.test(bar) && bar.includes(PRESENCE_LABEL.checking));
  check("the launcher describes Lilith's state to assistive technology", /aria-description="Lilith is connecting"/.test(bar));
  check("the mark is announced from exactly one place", (bar.match(/data-presence-announcer/g) ?? []).length === 1);
  check("the panel header carries the mark too", /<PresenceMark state=\{presence\} \/>/.test(src("components", "command", "global-command.tsx")));

  return out;
}
