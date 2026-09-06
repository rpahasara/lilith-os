/**
 * RealCommandCore — the single generic Cognitive Core engine.
 *
 * It implements the frozen {@link CommandCore} seam and owns everything that is
 * task-agnostic: task records, submit/run/cancel/retry, capability health
 * gating, one-step-at-a-time execution with bounded retry, genuine
 * AbortController cancellation, verification → terminal mapping, durable
 * persistence, and structured logging. Each task type is a {@link TaskPlaybook}
 * (system health, career attention, …) that only supplies its plan, per-step
 * behaviour, and verifier — so new real tasks reuse this engine wholesale.
 */
import type {
  CommandAction,
  CommandCore,
  CommandEvent,
  CommandEventListener,
} from "../events";
import type { CommandEvidence, CommandStep } from "../types";
import { getCapability } from "./capabilities";
import { consoleCoreLogger, type CoreLogger } from "./logger";
import { matchRealIntent, type RealIntent } from "./intents";
import { realTransport } from "./transport";
import { InMemoryTaskStore, LocalStorageTaskStore, type TaskStore } from "./task-store";
import { systemHealthPlaybook } from "./playbooks/system-health";
import { careerAttentionPlaybook } from "./playbooks/career-attention";
import type { PlaybookContext, TaskPlaybook } from "./playbook";
import type {
  Capability,
  CapabilityResult,
  CommandPlan,
  CoreTaskRecord,
  CoreTransport,
  ProvenanceRef,
} from "./types";

/** Task-type registry, keyed by RealIntent id. */
const PLAYBOOKS: Record<string, TaskPlaybook> = {
  [systemHealthPlaybook.id]: systemHealthPlaybook,
  [careerAttentionPlaybook.id]: careerAttentionPlaybook,
};

interface Runtime {
  record: CoreTaskRecord;
  intent: RealIntent;
  playbook: TaskPlaybook;
  plan: CommandPlan;
  abort: AbortController;
  canceled: boolean;
  started: boolean;
  data: Record<string, unknown>;
  provenance: ProvenanceRef[];
  extraEvidence: CommandEvidence[];
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
    const intent = matchRealIntent(input);
    return intent && PLAYBOOKS[intent.id] ? intent : null;
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
      if (rec.plan) out.push({ type: "plan.available", taskId: rec.taskId, at: rec.createdAt, steps: recSteps(rec) });
      const at = rec.endedAt ?? rec.updatedAt;
      if (rec.outcome === "succeeded") {
        out.push({ type: "result.available", taskId: rec.taskId, at, result: { outcome: "succeeded", summary: rec.resultSummary ?? "Done.", unresolved: rec.unresolved }, evidence: rec.evidence });
      } else if (rec.outcome === "partial") {
        out.push({ type: "partial.result", taskId: rec.taskId, at, result: { outcome: "partial", summary: rec.resultSummary ?? "Partial.", unresolved: rec.unresolved }, evidence: rec.evidence });
      } else if (rec.outcome === "failed") {
        out.push({ type: "failed", taskId: rec.taskId, at, error: rec.failure?.reason ?? "Failed.", evidence: rec.evidence });
      } else if (rec.outcome === "cancelled") {
        out.push({ type: "cancelled", taskId: rec.taskId, at });
      }
    }
    return out;
  }

  dispatch(action: CommandAction): void {
    switch (action.type) {
      case "submit": this.onSubmit(action.taskId, action.input); break;
      case "run": this.onRun(action.taskId); break;
      case "cancel": this.onCancel(action.taskId); break;
      case "retry":
      case "resume": this.onRetry(action.taskId); break;
      case "discard": this.runs.delete(action.taskId); break;
      case "approve":
      case "deny": break; // no approval gate in these read-only slices
    }
  }

  /* ------------------------------------------------------------- lifecycle */

  private onSubmit(taskId: string, input: string) {
    const intent = matchRealIntent(input);
    const playbook = intent ? PLAYBOOKS[intent.id] : undefined;
    if (!intent || !playbook) {
      this.emit({ type: "task.created", taskId, at: Date.now(), userInput: input, normalizedIntent: input, title: input.slice(0, 40), kind: "unsupported", source: "core" });
      this.emit({ type: "capability.unsupported", taskId, at: Date.now(), reason: "No real capability is wired for that request yet." });
      return;
    }

    const now = Date.now();
    const plan = playbook.plan(taskId, intent.normalized);
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
      record, intent, playbook, plan,
      abort: new AbortController(),
      canceled: false, started: false,
      data: {}, provenance: [], extraEvidence: [],
    });

    this.logger.log("task.created", taskId, { intent: intent.id });
    this.emit({ type: "task.created", taskId, at: now, userInput: input, normalizedIntent: intent.normalized, title: intent.title, kind: "action", source: "core", contextSummary: "Live read-only · no changes made" });
    this.logger.log("plan.created", taskId, { steps: plan.steps.length, version: plan.version });
    this.emit({ type: "intent.proposed", taskId, at: Date.now(), normalizedIntent: intent.normalized, title: intent.title, steps: recSteps(record) });
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
    run.data = {};
    run.provenance = [];
    run.extraEvidence = [];
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
    const ctx: PlaybookContext = {
      taskId,
      now: Date.now(),
      isCanceled: () => run.canceled,
      runCapability: (cap, stepId) => this.runCapability(run, cap, stepId),
      emitProgress: (stepId, detail) => this.emit({ type: "step.progress", taskId, at: Date.now(), stepId, detail }),
      data: run.data,
      provenance: run.provenance,
      evidence: run.extraEvidence,
    };

    this.emit({ type: "status", taskId, at: Date.now(), status: "planning" });
    this.emit({ type: "plan.available", taskId, at: Date.now(), steps: recSteps(run.record) });

    // Capability check — every required capability must exist.
    for (const capId of run.plan.capabilitiesRequired) {
      if (!getCapability(capId)) {
        this.logger.log("capability.selected", taskId, { capId, present: false });
        return this.fail(run, `Capability ${capId} is not available.`, undefined, "capability_unsupported");
      }
    }
    // Health-gate on the backbone capability.
    const backbone = getCapability(run.playbook.backboneCapabilityId)!;
    this.logger.log("capability.selected", taskId, { capId: backbone.id });
    if (run.canceled) return this.finishCancelled(run);
    const health = await backbone.checkHealth(this.transport, run.abort.signal);
    this.logger.log("capability.health", taskId, { capId: backbone.id, healthy: health.healthy });
    if (run.canceled) return this.finishCancelled(run);
    if (!health.healthy) {
      return this.fail(run, "The control backend is unreachable, so the task could not run.", "Retry when the backend is reachable.");
    }

    // Step-by-step execution via the playbook.
    for (const step of run.plan.steps) {
      if (run.canceled) return this.finishCancelled(run);
      this.setStep(run, step.id, { status: "running", startedAt: Date.now() });
      this.emit({ type: "step.started", taskId, at: Date.now(), stepId: step.id });
      this.logger.log("step.started", taskId, { stepId: step.id });

      const r = await run.playbook.runStep(step, ctx);
      if (run.canceled) return this.finishCancelled(run);

      if (r.fatal) {
        this.setStep(run, step.id, { status: "failed", endedAt: Date.now(), detail: r.detail });
        this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: "failed", detail: r.detail });
        return this.fail(run, r.fatal.reason, r.fatal.recovery);
      }
      this.setStep(run, step.id, { status: r.outcome, endedAt: Date.now(), detail: r.detail });
      this.emit({ type: "step.finished", taskId, at: Date.now(), stepId: step.id, outcome: r.outcome, detail: r.detail });
    }

    if (run.canceled) return this.finishCancelled(run);

    // Verify.
    run.record.status = "verifying";
    const verdict = run.playbook.verify(ctx);
    this.logger.log("verify.verdict", taskId, { verdict: verdict.verdict, unresolved: verdict.unresolved.length });
    if (run.canceled) return this.finishCancelled(run);

    const evidence = ctx.evidence.length ? [...ctx.evidence, ...verdict.evidence] : verdict.evidence;
    run.record.evidence = evidence;
    run.record.resultSummary = verdict.summary;
    run.record.unresolved = verdict.unresolved;

    if (verdict.verdict === "FAIL") return this.fail(run, verdict.summary, verdict.recovery);

    if (verdict.verdict === "PARTIAL") {
      run.record.outcome = "partial";
      run.record.status = "partial";
      run.record.endedAt = Date.now();
      this.persist(run.record);
      this.logger.log("terminal", taskId, { outcome: "partial" });
      this.emit({ type: "partial.result", taskId, at: Date.now(), result: { outcome: "partial", summary: verdict.summary, unresolved: verdict.unresolved }, evidence });
      return;
    }

    run.record.outcome = "succeeded";
    run.record.status = "succeeded";
    run.record.endedAt = Date.now();
    this.persist(run.record);
    this.logger.log("terminal", taskId, { outcome: "succeeded" });
    this.emit({ type: "result.available", taskId, at: Date.now(), result: { outcome: "succeeded", summary: verdict.summary, unresolved: verdict.unresolved.length ? verdict.unresolved : undefined }, evidence });
  }

  /** Execute one capability with bounded retry on retryable errors. */
  private async runCapability(run: Runtime, cap: Capability, stepId: string): Promise<CapabilityResult> {
    const { taskId } = run.record;
    const policy = cap.retry;
    let last: CapabilityResult | null = null;
    for (let attempt = 1; attempt <= policy.maxAttempts; attempt++) {
      if (run.canceled) break;
      this.bumpAttempt(run, stepId);
      last = await cap.execute(this.transport, run.abort.signal);
      this.logger.log("capability.result", taskId, { capId: cap.id, ok: last.ok, status: last.status, attempt, execId: last.executionId });
      if (last.ok) return last;
      const retryable = !!last.errorKind && (policy.retryOn as string[]).includes(last.errorKind) && attempt < policy.maxAttempts && !run.canceled;
      if (!retryable) break;
      this.logger.log("retry", taskId, { capId: cap.id, nextAttempt: attempt + 1 });
      this.emit({ type: "step.progress", taskId, at: Date.now(), stepId, detail: `retrying (attempt ${attempt + 1}/${policy.maxAttempts})` });
      await sleep(250);
    }
    return last!;
  }

  private fail(run: Runtime, reason: string, recovery?: string, mode: "failed" | "capability_unsupported" = "failed") {
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
    this.emit({ type: "failed", taskId: run.record.taskId, at: Date.now(), error: recovery ? `${reason} ${recovery}` : reason, evidence });
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
    run.record.steps = run.record.steps.map((s) => (s.id === stepId ? { ...s, attempts: s.attempts + 1 } : s));
  }
}

function recSteps(record: CoreTaskRecord): CommandStep[] {
  return record.steps.map((s) => ({
    id: s.id, label: s.label, status: s.status, detail: s.detail, startedAt: s.startedAt, endedAt: s.endedAt,
  }));
}
