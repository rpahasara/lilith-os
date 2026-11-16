/**
 * The global command surface — the rules behind "Lilith is reachable from every
 * page". Pure functions, so the behaviour is covered headlessly.
 *
 * There is exactly one conversation and one command store (both live in the
 * shell, above the routed pages). This surface is a second *window* onto them,
 * never a second copy: it sends through the same `submit`, shows the same
 * transcript, and continues the same backend session.
 *
 * On the Command Center the full experience (avatar, voice, the hero input)
 * already is that window, so the global surface steps aside there: the top-bar
 * field and Ctrl+Space focus the hero input instead of opening a panel.
 */
import type { ConversationMessage } from "@/lib/conversation/types";
import type { ShellHealthState } from "@/lib/system/shell-health";

export const COMMAND_CENTER_PATH = "/";
/** The hero input on the Command Center. */
export const HERO_INPUT_ID = "lilith-command-input";
/** The input inside the global panel. */
export const GLOBAL_INPUT_ID = "lilith-global-command-input";
export const GLOBAL_PANEL_ID = "lilith-global-command-panel";

export function isCommandCenter(pathname: string): boolean {
  return pathname === COMMAND_CENTER_PATH;
}

/**
 * Where a turn was launched from; passed to the command core as context.
 *
 * This is page origin only: a coarse label such as "career". It is not object
 * context. Which memory, application or meeting is open or selected is never
 * derived here, and nothing should present this label as Lilith understanding
 * what is on the page. Object-level context needs its own authorized
 * interface and is out of scope for this surface.
 */
export function surfaceFor(pathname: string): string {
  if (isCommandCenter(pathname)) return "home";
  const first = pathname.split("/").filter(Boolean)[0];
  return first && /^[a-z0-9-]+$/.test(first) ? first : "shell";
}

/** Ctrl+Space, and nothing else: no Meta, Alt or Shift variants are claimed. */
export function isCommandShortcut(e: {
  ctrlKey: boolean;
  code: string;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
}): boolean {
  return e.ctrlKey && e.code === "Space" && !e.metaKey && !e.altKey && !e.shiftKey;
}

/** What activating the surface (click or shortcut) should do. */
export type Activation = "focus-hero" | "open-panel" | "focus-panel";

export function activationFor(pathname: string, panelOpen: boolean): Activation {
  if (isCommandCenter(pathname)) return "focus-hero";
  return panelOpen ? "focus-panel" : "open-panel";
}

/**
 * The one line that says what is going on. Every value is derived from
 * something measured or stored: the transcript's hydration, the in-flight
 * turn, its error, a Stop, and the backend probe. Nothing is inferred.
 */
export type SurfaceState =
  | "loading" // the stored conversation has not been read yet
  | "responding" // a turn is in flight
  | "error" // the last turn failed
  | "stopped" // the owner stopped waiting
  | "unavailable" // no backend is configured: Lilith cannot answer here
  | "disconnected" // a backend is configured but did not answer the probe
  | "ready";

export interface SurfaceInputs {
  hydrated: boolean;
  sending: boolean;
  error: string | null;
  stopped: boolean;
  health: ShellHealthState;
}

export function surfaceState(i: SurfaceInputs): SurfaceState {
  if (!i.hydrated) return "loading";
  if (i.sending) return "responding";
  if (i.health === "unconfigured") return "unavailable";
  if (i.error) return "error";
  if (i.stopped) return "stopped";
  if (i.health === "unreachable") return "disconnected";
  return "ready";
}

export const SURFACE_LINE: Record<SurfaceState, string> = {
  loading: "Restoring the conversation…",
  responding: "Replying…",
  error: "The last message did not get through",
  stopped: "Stopped waiting",
  unavailable: "Unavailable — no backend is configured",
  disconnected: "The backend is not reachable right now",
  ready: "Ask, or give a command",
};

/**
 * Sending is refused only when there is certainly nowhere to send to, or a turn
 * is already in flight. An unreachable probe does not block it: the probe is up
 * to a minute old, and the turn itself will say if it fails.
 */
export function canSend(i: SurfaceInputs): boolean {
  return i.hydrated && !i.sending && i.health !== "unconfigured";
}

/** Id of the newest reply from Lilith, or null. */
export function latestReplyId(messages: ConversationMessage[]): string | null {
  for (let k = messages.length - 1; k >= 0; k--) {
    if (messages[k].role === "lilith") return messages[k].id;
  }
  return null;
}

/**
 * True when a reply has arrived that the owner has not been shown: the surface
 * is closed, they are not on the Command Center, and the newest reply is not
 * the one last seen. Restored history is seen by definition (the caller seeds
 * `seenId` with it once the transcript is hydrated).
 */
export function hasUnseenReply(
  messages: ConversationMessage[],
  seenId: string | null | undefined,
  visible: boolean,
): boolean {
  if (visible || seenId === undefined) return false;
  const latest = latestReplyId(messages);
  return latest !== null && latest !== seenId;
}
