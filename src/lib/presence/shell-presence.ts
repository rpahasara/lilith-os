/**
 * Lilith's presence in the shell — the small mark shown on every page.
 *
 * It is a readout, not a performance. Each state comes from one source the
 * client can verify, listed in {@link PRESENCE_SOURCES}. It never reads the
 * avatar's presence engine: that engine drives an expressive character and
 * includes timed, canned beats (for example a short "speaking" pose when no
 * audio plays), which are right for the avatar and would be a false report
 * here. Where there is no source for a state, the state is not shown.
 *
 * The Command Center's avatar remains the full representation of Lilith; this
 * mark is its small companion.
 */
import type { CommandStatus } from "@/lib/command/types";
import type { ShellHealthState } from "@/lib/system/shell-health";
import type { SpeechStatus } from "@/lib/voice/types";

export type ShellPresenceState =
  | "checking"
  | "available"
  | "responding"
  | "working"
  | "attention"
  | "speaking"
  | "listening"
  | "disconnected"
  | "unavailable";

/** Where each state comes from. `null` means there is no source yet. */
export const PRESENCE_SOURCES: Record<ShellPresenceState, string | null> = {
  checking: "the first backend probe has not finished",
  available: "the read-only backend probe answered (repeated every minute)",
  responding: "a conversation turn sent from this browser is waiting for its reply",
  working: "a command task is queued, planning or running in the command store",
  attention: "a command task is waiting for the owner's approval",
  speaking: "the audio player is playing a reply aloud",
  // Speech input is not built: there is no microphone capture to report.
  listening: null,
  disconnected: "the backend probe got no answer",
  unavailable: "the proxy reports that no backend is configured",
};

export const PRESENCE_LABEL: Record<ShellPresenceState, string> = {
  checking: "Connecting",
  available: "Available",
  responding: "Responding",
  working: "Working",
  attention: "Needs your approval",
  speaking: "Speaking",
  listening: "Listening",
  disconnected: "Disconnected",
  unavailable: "Unavailable",
};

export interface ShellPresenceInputs {
  health: ShellHealthState;
  /** A conversation turn is in flight. */
  sending: boolean;
  /** Status of every command task that has not finished. */
  taskStatuses: readonly CommandStatus[];
  /** The audio player's own lifecycle. */
  voice: SpeechStatus;
  /** Real microphone capture. Always false today: speech input does not exist. */
  listening: boolean;
}

const RUNNING: readonly CommandStatus[] = ["queued", "planning", "running"];

/**
 * One state at a time, most specific first.
 *
 *  1. No backend configured: nothing else can be true.
 *  2. What Lilith is doing right now, from direct evidence: listening,
 *     speaking, responding, working.
 *  3. Something is waiting on the owner.
 *  4. What the last probe said about the connection.
 *
 * Direct evidence of activity outranks the probe, which can be a minute old.
 */
export function shellPresence(i: ShellPresenceInputs): ShellPresenceState {
  if (i.health === "unconfigured") return "unavailable";
  if (i.listening) return "listening";
  if (i.voice === "playing") return "speaking";
  if (i.sending) return "responding";
  if (i.taskStatuses.some((s) => RUNNING.includes(s))) return "working";
  if (i.taskStatuses.includes("waiting_for_approval")) return "attention";
  if (i.health === "unreachable") return "disconnected";
  if (i.health === "checking") return "checking";
  return "available";
}

/**
 * What a screen reader is told when the state changes. Only changes that
 * matter to someone who cannot see the mark: losing Lilith, getting her back,
 * and being asked for a decision. Routine activity is not narrated (replies
 * are already announced once by the conversation).
 */
export function presenceAnnouncement(prev: ShellPresenceState | null, next: ShellPresenceState): string {
  if (prev === next) return "";
  if (next === "disconnected") return "Lilith is disconnected.";
  if (next === "unavailable") return "Lilith is unavailable: no backend is configured.";
  if (next === "attention") return "Lilith needs your approval for a command.";
  if (next === "available" && (prev === "disconnected" || prev === "unavailable")) return "Lilith is available again.";
  return "";
}
