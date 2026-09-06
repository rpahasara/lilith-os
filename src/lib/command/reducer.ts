/**
 * Pure reducer: folds a {@link CommandEvent} onto a {@link CommandTask}.
 *
 * React-free and side-effect-free so it can be reasoned about and tested in
 * isolation. The store in `@/components/command/command-provider` is the only
 * thing that drives it.
 */

import type { CommandEvent } from "./events";
import {
  isTerminal,
  type CommandApproval,
  type CommandStep,
  type CommandTask,
} from "./types";

/** A fresh task shell created on `task.created`. */
function createTask(
  e: Extract<CommandEvent, { type: "task.created" }>,
): CommandTask {
  return {
    taskId: e.taskId,
    userInput: e.userInput,
    normalizedIntent: e.normalizedIntent,
    title: e.title,
    status: "draft",
    kind: e.kind,
    source: e.source,
    createdAt: e.at,
    updatedAt: e.at,
    steps: [],
    currentStep: null,
    approval: { status: "not_required" },
    cancelability: false,
    resumability: false,
    cancelRequested: false,
    evidence: [],
    contextSummary: e.contextSummary,
  };
}

/** Cancelability is derived, not asserted by events: only live work can cancel. */
function deriveCancelability(status: CommandTask["status"]): boolean {
  return (
    status === "queued" ||
    status === "planning" ||
    status === "running" ||
    status === "waiting_for_approval"
  );
}

function withStep(
  steps: CommandStep[],
  stepId: string,
  patch: Partial<CommandStep>,
): CommandStep[] {
  return steps.map((s) => (s.id === stepId ? { ...s, ...patch } : s));
}

function indexOfStep(steps: CommandStep[], stepId: string): number | null {
  const i = steps.findIndex((s) => s.id === stepId);
  return i === -1 ? null : i;
}

/**
 * Apply one event to a task. Returns the same reference if the event does not
 * apply (unknown task id / stale terminal event), so callers can skip re-renders.
 */
export function applyCommandEvent(
  task: CommandTask | undefined,
  event: CommandEvent,
): CommandTask | undefined {
  if (event.type === "task.created") {
    return task ?? createTask(event);
  }
  if (!task) return task;

  // Ignore late lifecycle events once a task has terminated (a cancel/failure
  // race shouldn't resurrect it), but always allow evidence-bearing results.
  const next: CommandTask = { ...task, updatedAt: event.at };

  switch (event.type) {
    case "intent.proposed": {
      next.normalizedIntent = event.normalizedIntent;
      if (event.title) next.title = event.title;
      next.steps = event.steps;
      next.status = "reviewing";
      next.cancelability = false;
      next.resumability = false;
      break;
    }
    case "plan.available": {
      next.steps = event.steps;
      next.status = "queued";
      next.cancelability = true;
      break;
    }
    case "status": {
      if (isTerminal(task.status) && !isTerminal(event.status)) return task;
      next.status = event.status;
      if (event.error) next.error = event.error;
      next.cancelability = deriveCancelability(event.status);
      if (event.status === "blocked" || event.status === "failed") {
        next.resumability = true;
      }
      break;
    }
    case "step.started": {
      next.steps = withStep(task.steps, event.stepId, {
        status: "running",
        startedAt: event.at,
        detail: event.detail,
      });
      next.currentStep = indexOfStep(next.steps, event.stepId);
      if (task.status !== "running") next.status = "running";
      next.cancelability = true;
      break;
    }
    case "step.progress": {
      next.steps = withStep(task.steps, event.stepId, { detail: event.detail });
      break;
    }
    case "step.finished": {
      next.steps = withStep(task.steps, event.stepId, {
        status: event.outcome,
        endedAt: event.at,
        detail: event.detail,
      });
      break;
    }
    case "approval.requested": {
      next.approval = event.approval;
      next.status = "waiting_for_approval";
      next.cancelability = true;
      // Mark the current step as waiting.
      if (task.currentStep != null && task.steps[task.currentStep]) {
        next.steps = withStep(task.steps, task.steps[task.currentStep].id, {
          status: "waiting",
        });
      }
      break;
    }
    case "approval.resolved": {
      const approval: CommandApproval = {
        ...task.approval,
        status: event.approved ? "approved" : "denied",
      };
      next.approval = approval;
      if (event.approved) {
        next.status = "running";
        next.cancelability = true;
      } else {
        next.status = "cancelled";
        next.cancelability = false;
        next.resumability = true;
      }
      break;
    }
    case "partial.result": {
      next.result = event.result;
      next.status = "partial";
      next.cancelability = false;
      next.resumability = true;
      next.currentStep = null;
      if (event.evidence?.length) next.evidence = event.evidence;
      break;
    }
    case "result.available": {
      next.result = event.result;
      next.status = "succeeded";
      next.cancelability = false;
      next.resumability = false;
      next.currentStep = null;
      if (event.evidence?.length) next.evidence = event.evidence;
      break;
    }
    case "failed": {
      next.error = event.error;
      next.status = "failed";
      next.cancelability = false;
      next.resumability = true;
      next.currentStep = null;
      next.result = {
        outcome: "failed",
        summary: event.error,
      };
      if (event.evidence?.length) next.evidence = event.evidence;
      // Reflect the stall on the active step.
      if (task.currentStep != null && task.steps[task.currentStep]) {
        next.steps = withStep(task.steps, task.steps[task.currentStep].id, {
          status: "failed",
          endedAt: event.at,
        });
      }
      break;
    }
    case "cancelled": {
      next.status = "cancelled";
      next.cancelability = false;
      next.cancelRequested = false;
      next.resumability = true;
      next.currentStep = null;
      next.result = { outcome: "cancelled", summary: "Cancelled at your request." };
      break;
    }
    case "capability.unsupported": {
      next.status = "blocked";
      next.error = event.reason;
      next.cancelability = false;
      next.resumability = false;
      if (event.evidence?.length) next.evidence = event.evidence;
      break;
    }
  }

  return next;
}

/** Mark that a cancel has been requested (UI-optimistic; core confirms later). */
export function markCancelRequested(task: CommandTask): CommandTask {
  if (!task.cancelability || task.cancelRequested) return task;
  return { ...task, cancelRequested: true, updatedAt: Date.now() };
}
