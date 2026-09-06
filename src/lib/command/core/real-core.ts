/**
 * RealCommandCore — Cognitive Core V2, Vertical Slice 1.
 *
 * Implements the frozen {@link CommandCore} seam with REAL read-only backend
 * work: context assembly → plan → capability check → bounded step execution →
 * verification → evidence → durable result. It is the authoritative owner of
 * each task record (React only mirrors the emitted events), supports genuine
 * cancellation and bounded retry, and never promotes a non-verified or
 * post-cancellation result to success.
 */
import type {
  CommandAction,
  CommandCore,
  CommandEvent,
  CommandEventListener,
} from "../events";
import type { CommandEvidence, CommandStep } from "../types";
import {
  getCapability,
  isUnitUnhealthy,
  type OsOverview,
  type SystemStatus,
} from "./capabilities";
import { buildContextBundle } from "./context";
import { consoleCoreLogger, type CoreLogger } from "./logger";
import { matchRealIntent, type RealIntent } from "./intents";
import { planSystemHealth } from "./planner";
import { realTransport } from "./transport";
import { InMemoryTaskStore, LocalStorageTaskStore, type TaskStore } from "./task-store";
import { verifySystemHealth } from "./verifier";
import type {
  Capability,
  CapabilityResult,
  CommandPlan,
  ContextBundle,
  CoreTaskRecord,
  CoreTransport,
} from "./types";

interface Runtime {
  record: CoreTaskRecord;
  intent: RealIntent;
  plan: CommandPlan;
  context: ContextBundle;
  abort: AbortController;
  canceled: boolean;
  started: boolean;
  overview: OsOverview | null;
  status: SystemStatus | null;
  statusExecId?: string;
}

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `task-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class RealCommandCore implements CommandCore {
  readonly kind = "core" as const;

  private listeners = new Set<CommandEventListener>();
  private runs = new Map<string, Runtime>();

  constructor(
    private transport: CoreTransport = realTransport,
    private store: TaskStore = typeof window !== "undefined"
      ? new LocalStorageTaskStore()
      : new InMemoryTaskStore(),
    private logger: CoreLogger = consoleCoreLogger,
  ) {}

  /** Which inputs this core can fulfil for real. */
  static matches(input: string): RealIntent | null {
    return matchRealIntent(input);
  }

  subscribe(listener: CommandEventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(e: CommandEvent) {
    for (const l of this.listeners) l(e);
  }

  dispose(): void {
    for (const r of this.runs.values()) r.abort.abort();
    this.runs.clear();
    this.listeners.clear();
  }

  /** Restore durable real-task history as terminal CommandTasks for the UI. */
  restore(): CommandEvent[] {
    // Return synthesized events the provider can fold to rebuild history.
    const out: CommandEvent[] = [];
    for (const rec of this.store.loadAll()) {
      if (!rec.outcome) continue;
      out.push({
        type: "task.created",
        taskId: rec.taskId,
        at: rec.createdAt,
        userInput: rec.rawIntent,
        normalizedIntent: rec.normalizedIntent,
        title: rec.title,
        kind: "action",
        source: "core",
        contextSummary: rec.scope,
      });
      if (rec.plan) {
        out.push({ type: "plan.available", taskId: rec.taskId, at: rec.createdAt, steps: recSteps(rec) });
      }
      if (rec.outcome === "succeeded") {
        out.push({
          type: "result.available",
          taskId: rec.taskId,
          at: rec.endedAt ?? rec.updatedAt,
          result: { outcome: "succeeded", summary: rec.resultSummary ?? "Done.", unresolved: rec.unresolved },
          evidence: rec.evidence,
        });
      } else if (rec.outcome === "partial") {
        out.push({
          type: "partial.result",
          taskId: rec.taskId,
          at: rec.endedAt ?? rec.updatedAt,
          result: { outcome: "partial", summary: rec.resultSummary ?? "Partial.", unresolved: rec.unresolved },
          evidence: rec.evidence,
        });
      } else if (rec.outcome === "failed") {
        out.push({
          type: "failed",
          taskId: rec.taskId,
          at: rec.endedAt ?? rec.updatedAt,
          error: rec.failure?.reason ?? "Failed.",
          evidence: rec.evidence,
        });
      } else if (rec.outcome === "cancelled") {
        out.push({ type: "cancelled", taskId: rec.taskId, at: rec.endedAt ?? rec.updatedAt });
      }
    }
    return out;
  }

  dispatch(action: CommandAction): void {
    switch (action.type) {
      case "submit":
        this.onSubmit(action.taskId, action.input);
        break;
      case "run":
        this.onRun(action.taskId);
        break;
      case "cancel":
        this.onCancel(action.taskId);
        break;
      case "retry":
      case "resume":
        this.onRetry(action.taskId);
        break;
      case "discard":
        this.runs.delete(action.taskId);
        break;
      // No approval gate in this read-only slice.
      case "approve":
      case "deny":
        break;
    }
  }

  /* ------------------------------------------------------------- lifecycle */

  private onSubmit(taskId: string, input: string) {
    const intent = matchRealIntent(input);
    if (!intent) {
      // Provider only routes real intents here; guard anyway.
      this.emit({
        type: "task.created",
        taskId,
        at: Date.now(),
        userInput: input,
        normalizedIntent: input,
        title: input.slice(0, 40),
        kind: "unsupported",
        source: "core",
      });
      this.emit({
        type: "capability.unsupported",
        taskId,
        at: Date.now(),
        reason: "No real capability is wired for that request yet.",
      });
      return;
    }

    const now = Date.now();
    const plan = planSystemHealth(taskId, intent.normalized);
    const context = buildContextBundle(taskId, input, intent);
    const record: CoreTaskRecord = {
      taskId,
      source: "core",
      rawIntent: input,
      normalizedIntent: intent.normalized,
      title: intent.title,
      scope: intent.scope,
      planVersion: plan.version,
      plan,
      status: "created",
      currentStepId: null,
      steps: plan.steps.map((s) => ({ id: s.id, label: s.label, status: "pending", attempts: 0 })),
      approvalState: "not_required",
      attemptCount: 0,
      cancelRequested: false,
      createdAt: now,
      updatedAt: now,
      evidence: [],
    };

    this.runs.set(taskId, {
      record,
      intent,
      plan,
      context,
      abort: new AbortController(),
      canceled: false,
      started: false,
      overview: null,
      status: null,
    });

    this.logger.log("task.created", taskId, { intent: intent.id });
    this.emit({
      type: "task.created",
      taskId,
      at: now,
      userInput: input,
      normalizedIntent: intent.normalized,
      title: intent.title,
      kind: "action",
      source: "core",
      contextSummary: "Live read-only · no changes made",
    });
    this.logger.log("plan.created", taskId, { steps: plan.steps.length, version: plan.version });
    this.emit({
      type: "intent.proposed",
      taskId,
      at: Date.now(),
      normalizedIntent: intent.normalized,
      title: intent.title,
      steps: recSteps(record),
    });
  }

  private onRun(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run || run.started) return;
    run.started = true;
    run.abort = new AbortController();
    run.canceled = false;
    void this.execute(run);
  }

  private onRetry(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run) return;
    run.abort.abort();
    run.record.attemptCount += 1;
    run.record.steps = run.plan.steps.map((s) => ({ id: s.id, label: s.label, status: "pending", attempts: 0 }));
    run.record.outcome = undefined;
    run.record.failure = undefined;
    run.record.evidence = [];
    run.overview = null;
    run.status = null;
    run.started = false;
    this.emit({ type: "plan.available", taskId, at: Date.now(), steps: recSteps(run.record) });
    this.onRun(taskId);
  }

  private onCancel(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run) return;
    run.canceled = true;
    run.record.cancelRequested = true;
    run.abort.abort();
    this.logger.log("cancel", taskId, {});
    // The execute loop will observe `canceled` and emit the terminal cancelled
    // event after the current step settles. If nothing is running yet, finish now.
    if (!run.record.currentStepId) this.finishCancelled(run);
  }

  private finishCancelled(run: Runtime) {
    if (run.record.outcome) return;
    run.record.outcome = "cancelled";
    run.record.status = "cancelled";
    run.record.endedAt = Date.now();
    this.persist(run.record);
    this.logger.log("terminal", run.record.taskId, { outcome: "cancelled" });
    this.emit({ type: "cancelled", taskId: run.record.taskId, at: Date.now() });
  }

  private persist(record: CoreTaskRecord) {
    record.updatedAt = Date.now();
    this.store.save({ ...record, steps: record.steps.map((s) => ({ ...s })) });
  }

  /* -------------------------------------------------------------- executor */

  private async execute(run: Runtime) {
    const { taskId } = run.record;

    this.emit({ type: "status", taskId, at: Date.now(), status: "planning" });
    this.emit({ type: "plan.available", taskId, at: Date.now(), steps: recSteps(run.record) });

    // Capability check — the capability must exist and be healthy before work.
    this.emit({ type: "status", taskId, at: Date.now(), status: "planning" });
    for (const capId of run.plan.capabilitiesRequired) {
      const cap = getCapability(capId);
      if (!cap) {
        this.logger.log("capability.selected", taskId, { capId, present: false });
        return this.fail(run, `Capability ${capId} is not available.`, undefined, "capability_unsupported");
      }
    }
    // Health-gate on the backbone capability.
    const backbone = getCapability("system.get_status")!;
    this.logger.log("capability.selected", taskId, { capId: backbone.id });
    if (run.canceled) return this.finishCancelled(run);
    const health = await backbone.checkHealth(this.transport, run.abort.signal);
    this.logger.log("capability.health", taskId, { capId: backbone.id, healthy: health.healthy });
    if (run.canceled) return this.finishCancelled(run);
    if (!health.healthy) {
      return this.fail(
        run,
        "The control backend is unreachable, so system status could not be read.",
        "Retry when the backend tunnel is active.",
      );
    }

    // Step-by-step execution.
    for (const step of run.plan.steps) {
      if (run.canceled) return this.finishCancelled(run);

      this.setStep(run, step.id, { status: "running", startedAt: Date.now() });
      this.emit({ type: "step.started", taskId, at: Date.now(), stepId: step.id });
      this.logger.log("step.started", taskId, { stepId: step.id });

      if (step.kind === "capability" && step.capabilityId) {
        const cap = getCapability(step.capabilityId)!;
        const result = await this.runCapability(run, cap, step.id);
        if (run.canceled) return this.finishCancelled(run);

        if (step.capabilityId === "os.get_overview") {
          if (result.ok) {
            run.overview = result.data as OsOverview;
            run.context.retrieved["os.get_overview"] = run.overview;
            run.context.provenance.push({
              capabilityId: cap.id,
              executionId: result.executionId,
              source: result.source,
              fetchedAt: result.endedAt,
            });
            this.setStep(run, step.id, {
              status: "succeeded",
              endedAt: Date.now(),
              detail: `LILITH ${run.overview.lilithStatus}`,
              executionId: result.executionId,
            });
            this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: "succeeded", detail: `LILITH ${run.overview.lilithStatus}` });
          } else {
            // Overview is context, not the backbone — degrade to a warning and
            // continue; the verifier downgrades the final verdict to PARTIAL.
            this.setStep(run, step.id, { status: "skipped", endedAt: Date.now(), detail: "overview unavailable" });
            this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: "skipped", detail: "overview unavailable" });
          }
        } else if (step.capabilityId === "system.get_status") {
          if (!result.ok) {
            this.setStep(run, step.id, { status: "failed", endedAt: Date.now(), detail: result.error });
            this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: "failed", detail: result.error });
            return this.fail(
              run,
              result.errorKind === "malformed"
                ? "The backend returned a malformed system status response."
                : "Could not retrieve system status from the control backend.",
              "Retry when the backend is healthy.",
            );
          }
          run.status = result.data as SystemStatus;
          run.statusExecId = result.executionId;
          run.context.retrieved["system.get_status"] = run.status;
          run.context.backendTime = run.status.timeUtc;
          run.context.provenance.push({
            capabilityId: cap.id,
            executionId: result.executionId,
            source: result.source,
            fetchedAt: result.endedAt,
          });
          const detail = `${run.status.units.length} units`;
          this.setStep(run, step.id, { status: "succeeded", endedAt: Date.now(), detail, executionId: result.executionId });
          this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: "succeeded", detail });
        }
      } else {
        // Internal analysis step over already-retrieved data.
        let detail = "";
        if (step.id === "s3" && run.status) {
          const unhealthy = run.status.units.filter(isUnitUnhealthy).length;
          detail = unhealthy === 0 ? "all healthy" : `${unhealthy} need attention`;
        }
        if (run.canceled) return this.finishCancelled(run);
        this.setStep(run, step.id, { status: "succeeded", endedAt: Date.now(), detail: detail || undefined });
        this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: "succeeded", detail: detail || undefined });
      }
    }

    if (run.canceled) return this.finishCancelled(run);

    // Verify.
    run.record.status = "verifying";
    const verdict = verifySystemHealth({
      status: run.status,
      overview: run.overview,
      statusExecutionId: run.statusExecId,
    });
    this.logger.log("verify.verdict", taskId, { verdict: verdict.verdict, unresolved: verdict.unresolved.length });

    if (run.canceled) return this.finishCancelled(run);

    run.record.evidence = verdict.evidence;
    run.record.resultSummary = verdict.summary;
    run.record.unresolved = verdict.unresolved;

    if (verdict.verdict === "FAIL") {
      return this.fail(run, verdict.summary, verdict.recovery);
    }
    if (verdict.verdict === "PARTIAL") {
      run.record.outcome = "partial";
      run.record.status = "partial";
      run.record.endedAt = Date.now();
      this.persist(run.record);
      this.logger.log("terminal", taskId, { outcome: "partial" });
      this.emit({
        type: "partial.result",
        taskId,
        at: Date.now(),
        result: { outcome: "partial", summary: verdict.summary, unresolved: verdict.unresolved },
        evidence: verdict.evidence,
      });
      return;
    }
    // PASS
    run.record.outcome = "succeeded";
    run.record.status = "succeeded";
    run.record.endedAt = Date.now();
    this.persist(run.record);
    this.logger.log("terminal", taskId, { outcome: "succeeded" });
    this.emit({
      type: "result.available",
      taskId,
      at: Date.now(),
      result: {
        outcome: "succeeded",
        summary: verdict.summary,
        unresolved: verdict.unresolved.length ? verdict.unresolved : undefined,
      },
      evidence: verdict.evidence,
    });
  }

  /** Execute one capability with bounded retry on retryable errors. */
  private async runCapability(
    run: Runtime,
    cap: Capability,
    stepId: string,
  ): Promise<CapabilityResult> {
    const { taskId } = run.record;
    const policy = cap.retry;
    let last: CapabilityResult | null = null;
    for (let attempt = 1; attempt <= policy.maxAttempts; attempt++) {
      if (run.canceled) break;
      this.bumpAttempt(run, stepId);
      last = await cap.execute(this.transport, run.abort.signal);
      this.logger.log("capability.result", taskId, {
        capId: cap.id,
        ok: last.ok,
        status: last.status,
        attempt,
        execId: last.executionId,
      });
      if (last.ok) return last;
      const retryable =
        !!last.errorKind &&
        (policy.retryOn as string[]).includes(last.errorKind) &&
        attempt < policy.maxAttempts &&
        !run.canceled;
      if (!retryable) break;
      this.logger.log("retry", taskId, { capId: cap.id, nextAttempt: attempt + 1 });
      this.emit({
        type: "step.progress",
        taskId,
        at: Date.now(),
        stepId,
        detail: `retrying (attempt ${attempt + 1}/${policy.maxAttempts})`,
      });
      await sleep(250);
    }
    return last!;
  }

  private fail(
    run: Runtime,
    reason: string,
    recovery?: string,
    mode: "failed" | "capability_unsupported" = "failed",
  ) {
    if (run.record.outcome) return;
    run.record.failure = { reason, recovery };
    run.record.endedAt = Date.now();
    const evidence: CommandEvidence[] = run.record.evidence.length
      ? run.record.evidence
      : recovery
        ? [{ kind: "observed_state", label: "Action taken", value: "None — safe to retry" }]
        : [];
    if (mode === "capability_unsupported") {
      run.record.outcome = "failed";
      run.record.status = "blocked";
      this.persist(run.record);
      this.logger.log("terminal", run.record.taskId, { outcome: "blocked" });
      this.emit({ type: "capability.unsupported", taskId: run.record.taskId, at: Date.now(), reason });
      return;
    }
    run.record.outcome = "failed";
    run.record.status = "failed";
    this.persist(run.record);
    this.logger.log("terminal", run.record.taskId, { outcome: "failed" });
    this.emit({
      type: "failed",
      taskId: run.record.taskId,
      at: Date.now(),
      error: recovery ? `${reason} ${recovery}` : reason,
      evidence,
    });
  }

  private setStep(run: Runtime, stepId: string, patch: Partial<CoreTaskRecord["steps"][number]>) {
    run.record.currentStepId = patch.status === "running" ? stepId : run.record.currentStepId;
    run.record.steps = run.record.steps.map((s) => (s.id === stepId ? { ...s, ...patch } : s));
    if (patch.status && patch.status !== "running") {
      const stillRunning = run.record.steps.some((s) => s.status === "running");
      if (!stillRunning) run.record.currentStepId = null;
    }
  }

  private bumpAttempt(run: Runtime, stepId: string) {
    run.record.steps = run.record.steps.map((s) =>
      s.id === stepId ? { ...s, attempts: s.attempts + 1 } : s,
    );
  }
}

/* --------------------------------------------------------------- helpers */

function recSteps(record: CoreTaskRecord): CommandStep[] {
  return record.steps.map((s) => ({
    id: s.id,
    label: s.label,
    status: s.status,
    detail: s.detail,
    startedAt: s.startedAt,
    endedAt: s.endedAt,
  }));
}
