/**
 * Headless regression test for the global command surface: Lilith is reachable
 * from every page through the one conversation and the one command store, the
 * Command Center keeps its own full surface, and every state the surface shows
 * is derived from something measured.
 *
 * Pure rules are called directly; the launcher is server-rendered inside the
 * real provider stack; structural guarantees are read from source.
 * Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ShellProviders } from "@/components/layout/app-shell";
import { TopBar } from "@/components/layout/top-bar";
import {
  GLOBAL_INPUT_ID,
  GLOBAL_PANEL_ID,
  HERO_INPUT_ID,
  SURFACE_LINE,
  activationFor,
  canSend,
  hasUnseenReply,
  isCommandCenter,
  isCommandShortcut,
  latestReplyId,
  surfaceFor,
  surfaceState,
  type SurfaceInputs,
  type SurfaceState,
} from "@/lib/command/global-surface";
import type { ConversationMessage } from "@/lib/conversation/types";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const src = (...path: string[]) => readFileSync(join(process.cwd(), "src", ...path), "utf8");
const count = (text: string, pattern: RegExp) => (text.match(pattern) ?? []).length;

function topBarAt(pathname: string): string {
  const g = globalThis as { __lilithTestPathname?: string };
  const before = g.__lilithTestPathname;
  g.__lilithTestPathname = pathname;
  try {
    return renderToStaticMarkup(createElement(ShellProviders, null, createElement(TopBar)));
  } finally {
    g.__lilithTestPathname = before;
  }
}

const msg = (id: string, role: "user" | "lilith"): ConversationMessage => ({ id, role, text: id, ts: "2026-11-16T00:00:00Z" });
const READY: SurfaceInputs = { hydrated: true, sending: false, error: null, stopped: false, health: "live" };

export function runGlobalSurfaceSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `global-command: ${name}`, pass, detail: pass ? undefined : detail });

  /* where it applies ------------------------------------------------------------ */
  check("only \"/\" is the Command Center", isCommandCenter("/") && !isCommandCenter("/career") && !isCommandCenter("/memory/atlas"));
  check("a turn carries the page it was launched from",
    surfaceFor("/") === "home" && surfaceFor("/career") === "career" && surfaceFor("/memory/atlas") === "memory" &&
      surfaceFor("/Weird%20Path") === "shell");

  /* the shortcut ------------------------------------------------------------------ */
  check("Ctrl+Space is the shortcut",
    isCommandShortcut({ ctrlKey: true, code: "Space" }));
  check("no other chord is claimed",
    !isCommandShortcut({ ctrlKey: false, code: "Space" }) && !isCommandShortcut({ ctrlKey: true, code: "KeyK" }) &&
      !isCommandShortcut({ ctrlKey: true, code: "Space", shiftKey: true }) &&
      !isCommandShortcut({ ctrlKey: true, code: "Space", altKey: true }) &&
      !isCommandShortcut({ ctrlKey: true, code: "Space", metaKey: true }));

  /* activation -------------------------------------------------------------------- */
  check("on the Command Center, activating focuses the hero input: no second surface",
    activationFor("/", false) === "focus-hero" && activationFor("/", true) === "focus-hero");
  check("elsewhere it opens the panel, then focuses it",
    activationFor("/career", false) === "open-panel" && activationFor("/career", true) === "focus-panel");
  check("the two inputs and the panel have distinct ids",
    new Set([HERO_INPUT_ID, GLOBAL_INPUT_ID, GLOBAL_PANEL_ID]).size === 3);

  /* states ------------------------------------------------------------------------- */
  const cases: [string, Partial<SurfaceInputs>, SurfaceState][] = [
    ["ready when the backend answers and nothing is pending", {}, "ready"],
    ["loading until the stored conversation is read", { hydrated: false }, "loading"],
    ["responding while a turn is in flight", { sending: true }, "responding"],
    ["responding outranks a stale unreachable probe", { sending: true, health: "unreachable" }, "responding"],
    ["error after a failed turn", { error: "conversation backend unreachable" }, "error"],
    ["stopped after Stop", { stopped: true }, "stopped"],
    ["unavailable when no backend is configured", { health: "unconfigured" }, "unavailable"],
    ["unavailable outranks an old error", { health: "unconfigured", error: "x" }, "unavailable"],
    ["disconnected when the probe got no answer", { health: "unreachable" }, "disconnected"],
    ["a failed turn outranks the probe", { health: "unreachable", error: "x" }, "error"],
    ["still ready while the first probe is running", { health: "checking" }, "ready"],
  ];
  for (const [name, patch, expected] of cases) {
    const got = surfaceState({ ...READY, ...patch });
    check(`state: ${name}`, got === expected, got);
  }
  check("every state has its own plain line",
    new Set(Object.values(SURFACE_LINE)).size === Object.keys(SURFACE_LINE).length &&
      Object.values(SURFACE_LINE).every((line) => line.length > 5));

  check("sending is refused while a turn is in flight, before hydration, and with no backend",
    canSend(READY) && !canSend({ ...READY, sending: true }) && !canSend({ ...READY, hydrated: false }) &&
      !canSend({ ...READY, health: "unconfigured" }));
  check("an unreachable probe does not block sending: the turn itself reports failure",
    canSend({ ...READY, health: "unreachable" }) && canSend({ ...READY, error: "x" }));

  /* unseen replies -------------------------------------------------------------------- */
  const convo = [msg("u1", "user"), msg("l1", "lilith"), msg("u2", "user")];
  check("the latest reply is the newest message from Lilith",
    latestReplyId(convo) === "l1" && latestReplyId([msg("u1", "user")]) === null && latestReplyId([]) === null);
  check("restored history is never marked as new", !hasUnseenReply(convo, undefined, false) && !hasUnseenReply(convo, "l1", false));
  check("a reply that arrives while the surface is closed is marked",
    hasUnseenReply([...convo, msg("l2", "lilith")], "l1", false));
  check("nothing is marked while the conversation is on screen",
    !hasUnseenReply([...convo, msg("l2", "lilith")], "l1", true));

  /* the launcher ------------------------------------------------------------------------ */
  const away = topBarAt("/career");
  const launcher = /<button[^>]*data-global-command-launcher=""[^>]*>/.exec(away)?.[0] ?? "";
  check("the top bar has a working launcher, not a disabled placeholder",
    launcher !== "" && !/\sdisabled=""/.test(launcher) && !/data-unavailable/.test(away) && /Ask Lilith/.test(away));
  check("away from the Command Center it is a dialog trigger with its shortcut",
    /aria-haspopup="dialog"/.test(launcher) && /aria-expanded="false"/.test(launcher) &&
      launcher.includes(`aria-controls="${GLOBAL_PANEL_ID}"`) && /aria-keyshortcuts="Control\+Space"/.test(launcher), launcher);
  check("narrow screens get the same action as one control", count(away, /aria-label="Ask Lilith"/g) === 2);
  const home = topBarAt("/");
  const homeLauncher = /<button[^>]*data-global-command-launcher=""[^>]*>/.exec(home)?.[0] ?? "";
  check("on the Command Center it does not claim to open a dialog", homeLauncher !== "" && !/aria-haspopup/.test(homeLauncher));
  check("no new-reply mark is shown before anything arrives", !/Lilith replied/.test(away));
  check("replies are announced away from the Command Center, which announces its own",
    /data-conversation-announcer/.test(away) && !/data-conversation-announcer/.test(home));

  /* one conversation, one command store ---------------------------------------------------- */
  const shell = src("components", "layout", "app-shell.tsx");
  check("the shell mounts exactly one conversation and one command store",
    count(shell, /<ConversationProvider>/g) === 1 && count(shell, /<CommandProvider>/g) === 1 &&
      count(shell, /<GlobalCommandPanel \/>/g) === 1);
  const surface = src("components", "command", "global-command.tsx");
  check("the global surface creates no conversation or command state of its own",
    !/<ConversationProvider|<CommandProvider|TurnRunner|sendConversation|\bfetch\s*\(|localStorage/.test(surface));
  check("it sends through the shared command store, with the launching page as context",
    /const \{ submit,[^}]*\} = useCommand\(\);/.test(surface) && /submit\(text, \{ context: \{ surface: surfaceFor\(pathname\) \} \}\)/.test(surface));
  check("it reuses the shared transcript, command console and input",
    /<ConversationView /.test(surface) && /<CommandConsole /.test(surface) && /<CommandInput/.test(surface));
  check("it offers no suggestions of its own", !/suggestions=/.test(surface));
  check("it does not drive the avatar's presence engine", !/usePresence|emit\(/.test(surface));

  /* the panel ---------------------------------------------------------------------------------- */
  check("the panel is a labelled modal dialog with a live state line",
    /role="dialog"/.test(surface) && /aria-modal="true"/.test(surface) && /aria-label="Lilith"/.test(surface) &&
      /role="status"\s+aria-live="polite"\s+data-surface-line=""/.test(surface));
  check("the panel traps Tab, closes on Escape and returns focus",
    /event\.key !== "Tab"/.test(surface) && /event\.key === "Escape"/.test(surface) && /launcherRef\.current\)\?\.focus\(\)/.test(surface));
  check("Escape is left to the input while it is recalling history", /if \(event\.defaultPrevented\) return;/.test(surface));
  check("the panel never opens over the Command Center", /if \(onHome\) setOpen\(false\);/.test(surface));
  check("the panel states the connection, and a recording, when they apply",
    /data-surface-notice="unavailable"/.test(surface) && /data-surface-notice="disconnected"/.test(surface) &&
      /data-surface-notice="recording"/.test(surface));
  check("the Command Center stays one step away", /href="\/"/.test(surface) && /Command Center/.test(surface));

  const input = src("components", "presence", "command-input.tsx");
  check("the hero input keeps its id and its own Ctrl+Space",
    input.includes("id = HERO_INPUT_ID") && /e\.ctrlKey && e\.code === "Space"/.test(input));

  return out;
}
