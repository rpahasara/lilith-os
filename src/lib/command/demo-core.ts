/**
 * DemoCommandCore — the V1 implementation of the {@link CommandCore} seam.
 *
 * It plays explicit fixture timelines (see `./fixtures`) so the whole command
 * UX can be exercised and reviewed without a real executor. Everything it
 * produces is `source: "demo"` and is labelled in the UI as a preview — it
 * never claims real external execution.
 *
 * When the Cognitive Core V2 lands it implements the same interface and this
 * file is retired. No UI change is required for the swap.
 */

import type {
  CommandAction,
  CommandCore,
  CommandEvent,
  CommandEventListener,
} from "./events";
import {
  matchFixture,
  planToSteps,
  type CommandFixture,
  type ScriptBeat,
} from "./fixtures";
import type { CommandSource } from "./types";

interface RunState {
  fixture: CommandFixture;
  index: number;
  timer: ReturnType<typeof setTimeout> | null;
  /** Paused at an approval gate, waiting for approve/deny. */
  awaitingApproval: boolean;
  /** True once the timeline has been kicked off (guards double-run). */
  started: boolean;
  done: boolean;
}

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `task-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export class DemoCommandCore implements CommandCore {
  readonly kind: CommandSource = "demo";

  private listeners = new Set<CommandEventListener>();
  private runs = new Map<string, RunState>();

  subscribe(listener: CommandEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(event: CommandEvent) {
    for (const l of this.listeners) l(event);
  }

  dispatch(action: CommandAction): void {
    switch (action.type) {
      case "submit":
        this.onSubmit(action.taskId, action.input);
        break;
      case "run":
        this.onRun(action.taskId);
        break;
      case "approve":
        this.onApprove(action.taskId, true);
        break;
      case "deny":
        this.onApprove(action.taskId, false);
        break;
      case "cancel":
        this.onCancel(action.taskId);
        break;
      case "retry":
      case "resume":
        this.onRetry(action.taskId);
        break;
      case "discard":
        this.clearRun(action.taskId);
        break;
    }
  }

  dispose(): void {
    for (const r of this.runs.values()) if (r.timer) clearTimeout(r.timer);
    this.runs.clear();
    this.listeners.clear();
  }

  /* --------------------------------------------------------------- handlers */

  private onSubmit(taskId: string, input: string) {
    const fx = matchFixture(input);
    const now = Date.now();

    if (!fx) {
      // Not a command the demo core recognises. It reports this honestly rather
      // than pretending; the provider routes plain chat to the real backend, so
      // this path is only reached when something is explicitly run as a command.
      this.emit({
        type: "task.created",
        taskId,
        at: now,
        userInput: input,
        normalizedIntent: input,
        title: input.length > 40 ? `${input.slice(0, 40)}…` : input,
        kind: "unsupported",
        source: "demo",
      });
      this.emit({
        type: "capability.unsupported",
        taskId,
        at: Date.now(),
        reason:
          "I understand the request, but I don't have a capability wired for it yet.",
      });
      return;
    }

    this.emit({
      type: "task.created",
      taskId,
      at: now,
      userInput: input,
      normalizedIntent: fx.normalizedIntent,
      title: fx.title,
      kind: fx.kind,
      source: "demo",
      contextSummary: fx.contextSummary,
    });

    if (fx.kind === "unsupported" && fx.unsupported) {
      this.emit({
        type: "capability.unsupported",
        taskId,
        at: Date.now(),
        reason: fx.unsupported.reason,
        evidence: fx.unsupported.evidence,
      });
      return;
    }

    // Actionable command → propose intent + plan for review before running.
    this.emit({
      type: "intent.proposed",
      taskId,
      at: Date.now(),
      normalizedIntent: fx.normalizedIntent,
      title: fx.title,
      steps: planToSteps(fx.plan),
    });
    this.runs.set(taskId, {
      fixture: fx,
      index: 0,
      timer: null,
      awaitingApproval: false,
      started: false,
      done: false,
    });
  }

  private onRun(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run) return;
    // Idempotent: ignore a duplicate Run (e.g. an impatient double-click before
    // the review surface transitions) so we never spawn two racing timelines.
    if (run.started) return;
    if (run.timer) clearTimeout(run.timer);
    run.index = 0;
    run.awaitingApproval = false;
    run.done = false;
    run.started = true;
    this.emit({
      type: "plan.available",
      taskId,
      at: Date.now(),
      steps: planToSteps(run.fixture.plan),
    });
    this.emit({ type: "status", taskId, at: Date.now(), status: "planning" });
    this.schedule(taskId);
  }

  private onRetry(taskId: string) {
    // Demo retry/resume replays the fixture from the plan. Real cancellation +
    // resume semantics arrive with the Cognitive Core.
    const run = this.runs.get(taskId);
    if (!run) return;
    if (run.timer) clearTimeout(run.timer);
    run.started = false;
    this.onRun(taskId);
  }

  private onApprove(taskId: string, approved: boolean) {
    const run = this.runs.get(taskId);
    if (!run || !run.awaitingApproval) return;
    run.awaitingApproval = false;
    this.emit({ type: "approval.resolved", taskId, at: Date.now(), approved });
    if (!approved) {
      // Reducer maps a denied approval to a cancelled task.
      this.clearRun(taskId);
      return;
    }
    this.emit({ type: "status", taskId, at: Date.now(), status: "running" });
    this.schedule(taskId);
  }

  private onCancel(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run) return;
    if (run.timer) clearTimeout(run.timer);
    run.done = true;
    this.emit({ type: "cancelled", taskId, at: Date.now() });
    this.runs.delete(taskId);
  }

  private clearRun(taskId: string) {
    const run = this.runs.get(taskId);
    if (run?.timer) clearTimeout(run.timer);
    this.runs.delete(taskId);
  }

  /* ---------------------------------------------------------- scheduler ---- */

  private schedule(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run || run.done) return;

    if (run.index >= run.fixture.script.length) {
      this.runs.delete(taskId);
      return;
    }

    const beat: ScriptBeat = run.fixture.script[run.index];
    run.timer = setTimeout(() => {
      const current = this.runs.get(taskId);
      if (!current || current.done) return;
      const event = beat.build({ taskId, at: Date.now() });
      this.emit(event);
      current.index += 1;

      // Pause at an approval gate until approve/deny arrives.
      if (event.type === "approval.requested") {
        current.awaitingApproval = true;
        current.timer = null;
        return;
      }
      this.schedule(taskId);
    }, beat.delay);
  }
}
