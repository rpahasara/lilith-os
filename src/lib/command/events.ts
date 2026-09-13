/**
 * The UI ↔ Cognitive Core contract.
 *
 * This is the seam the future Cognitive Core V2 will implement. The UI never
 * talks to an executor directly — it sends {@link CommandAction}s into a
 * {@link CommandCore} and renders whatever {@link CommandEvent}s come back. In
 * V1 a demo adapter implements this interface from scripted fixtures; swapping
 * in the real brain later is a one-file change and touches no UI.
 *
 * Events carry meaning and results only — never tokens, raw backend payloads,
 * or PII beyond what the user typed.
 */

import type {
  CommandApproval,
  CommandEvidence,
  CommandKind,
  CommandResult,
  CommandSource,
  CommandStep,
  CommandStatus,
} from "./types";

/* ----------------------------------------------------------------- UI → Core */

/** Context the UI attaches to a new command (kept small + non-sensitive). */
export interface CommandContext {
  /** Where the user launched from, e.g. "home", "career". */
  surface?: string;
  /** Short non-sensitive summary the core may use for retrieval. */
  summary?: string;
}

export type CommandAction =
  | { type: "submit"; taskId: string; input: string; context?: CommandContext }
  | { type: "approve"; taskId: string }
  | { type: "deny"; taskId: string }
  | { type: "cancel"; taskId: string }
  | { type: "resume"; taskId: string }
  | { type: "retry"; taskId: string }
  /** Accept a reviewed intent and begin execution. */
  | { type: "run"; taskId: string }
  /** Drop a task that is still in review (user chose "Cancel" pre-run). */
  | { type: "discard"; taskId: string };

/* ----------------------------------------------------------------- Core → UI */

/**
 * Lifecycle events the core emits. The pure reducer in `./reducer` folds these
 * onto a {@link import("./types").CommandTask}.
 */
export type CommandEvent =
  | {
      type: "task.created";
      taskId: string;
      at: number;
      userInput: string;
      normalizedIntent: string;
      title: string;
      kind: CommandKind;
      source: CommandSource;
      contextSummary?: string;
    }
  /** An intent + proposed plan is ready for the user to review before running. */
  | {
      type: "intent.proposed";
      taskId: string;
      at: number;
      normalizedIntent: string;
      title?: string;
      steps: CommandStep[];
    }
  /** The plan is accepted / finalised and the task is queued to run. */
  | { type: "plan.available"; taskId: string; at: number; steps: CommandStep[] }
  /** Generic status transition (planning, queued, running, blocked…). */
  | { type: "status"; taskId: string; at: number; status: CommandStatus; error?: string }
  | { type: "step.started"; taskId: string; at: number; stepId: string; detail?: string }
  | { type: "step.progress"; taskId: string; at: number; stepId: string; detail: string }
  | {
      type: "step.finished";
      taskId: string;
      at: number;
      stepId: string;
      outcome: "succeeded" | "failed" | "skipped";
      detail?: string;
    }
  /** A sensitive step needs explicit approval before it can proceed. */
  | { type: "approval.requested"; taskId: string; at: number; approval: CommandApproval }
  | { type: "approval.resolved"; taskId: string; at: number; approved: boolean }
  /** A partial result — some work done, some unresolved. Never reads as success. */
  | {
      type: "partial.result";
      taskId: string;
      at: number;
      result: CommandResult;
      evidence?: CommandEvidence[];
    }
  | {
      type: "result.available";
      taskId: string;
      at: number;
      result: CommandResult;
      evidence?: CommandEvidence[];
    }
  | { type: "failed"; taskId: string; at: number; error: string; evidence?: CommandEvidence[] }
  | { type: "cancelled"; taskId: string; at: number }
  /** Recognised intent with no capability behind it yet. */
  | {
      type: "capability.unsupported";
      taskId: string;
      at: number;
      reason: string;
      evidence?: CommandEvidence[];
    };

export type CommandEventListener = (event: CommandEvent) => void;

/**
 * The pluggable command backend. The Cognitive Core will implement this; the
 * demo adapter implements it for V1. The UI depends only on this interface.
 */
export interface CommandCore {
  /** Whether this core executes for real, or produces labelled preview state. */
  readonly kind: CommandSource;
  /** Subscribe to lifecycle events. Returns an unsubscribe fn. */
  subscribe(listener: CommandEventListener): () => void;
  /** Dispatch a UI intent into the core. */
  dispatch(action: CommandAction): void;
  /** Release timers / resources. */
  dispose?(): void;
}
