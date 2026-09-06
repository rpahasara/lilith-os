/**
 * Command lifecycle → presence semantic state (section 11 of the V1 brief).
 *
 * The Command System exposes *semantic* intent only. It never picks a scenario,
 * never hard-codes a physical pose or edge-peek, and never touches framing. The
 * Presence Director consumes this intent later and owns scenario choice.
 *
 * Two things are derived here:
 *   1. A {@link CommandPresenceIntent} in Director vocabulary (expression /
 *      attentionTarget / priority) — published for the Director to read.
 *   2. The `command.*` presence *event* to emit into the existing event bus,
 *      so the already-rendering Presence Engine reacts through its table-driven
 *      personality mapping (same mechanism as `conversation.*`).
 */

import type {
  NamedAttentionTarget,
  PresenceExpression,
  PresencePriority,
} from "@/lib/presence/presence-types";
import type { PresenceEventType } from "@/lib/presence/types";
import type { CommandStatus } from "./types";

export interface CommandPresenceIntent {
  /** Semantic expression request; the Director may honour or soften it. */
  expression: PresenceExpression;
  /** Where attention should be biased — never a scenario, just a target. */
  attentionTarget: NamedAttentionTarget;
  /** How insistent this state is; feeds the Director's interruption model. */
  priority: PresencePriority;
  /** True while the command surface is the user's active focus. */
  focused: boolean;
}

/** Director-facing semantic intent per command status. */
export function commandPresenceIntent(status: CommandStatus): CommandPresenceIntent {
  switch (status) {
    case "reviewing":
      return { expression: "attentive", attentionTarget: "command", priority: "normal", focused: true };
    case "queued":
    case "planning":
      return { expression: "attentive", attentionTarget: "command", priority: "normal", focused: true };
    case "running":
      return { expression: "attentive", attentionTarget: "command", priority: "notable", focused: true };
    case "waiting_for_approval":
      return { expression: "curious", attentionTarget: "command", priority: "notable", focused: true };
    case "blocked":
      return { expression: "curious", attentionTarget: "command", priority: "normal", focused: true };
    case "partial":
      return { expression: "attentive", attentionTarget: "command", priority: "notable", focused: false };
    case "failed":
      // The Director's expression vocabulary has no "concerned"; the presence
      // *event* still carries emotion:"concerned" via the event map. Bias to
      // attentive at high priority so the Director can escalate as it sees fit.
      return { expression: "attentive", attentionTarget: "command", priority: "urgent", focused: false };
    case "succeeded":
      return { expression: "soft-smile", attentionTarget: "command", priority: "normal", focused: false };
    case "cancelled":
      return { expression: "neutral", attentionTarget: "auto", priority: "passive", focused: false };
    case "draft":
    default:
      return { expression: "neutral", attentionTarget: "auto", priority: "passive", focused: false };
  }
}

/**
 * The `command.*` presence event to emit for a status transition, or null when
 * the transition should not disturb presence. Emitting an event (rather than
 * poking a signal) keeps personality in the presence mapping table and reuses
 * the interruption/cooldown model.
 */
export function commandPresenceEvent(status: CommandStatus): PresenceEventType | null {
  switch (status) {
    case "planning":
    case "queued":
      return "command.planning";
    case "running":
      return "command.running";
    case "waiting_for_approval":
      return "command.awaiting_approval";
    case "partial":
      return "command.partial";
    case "succeeded":
      return "command.succeeded";
    case "failed":
      return "command.failed";
    case "blocked":
      return "command.blocked";
    default:
      return null;
  }
}
