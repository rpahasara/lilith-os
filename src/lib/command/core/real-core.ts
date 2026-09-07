/**
 * RealCommandCore — the single generic Cognitive Core engine.
 *
 * It implements the frozen {@link CommandCore} seam and owns everything that is
 * task-agnostic: task records, submit/run/cancel/retry, capability health
 * gating, one-step-at-a-time execution with bounded retry, genuine
 * AbortController cancellation, verification → terminal mapping, durable
 * BACKEND persistence, and structured logging. Each task type is a
 * {@link TaskPlaybook} (system health, career attention, …) that only supplies
 * its plan, per-step behaviour, and verifier — so new real tasks reuse this
 * engine wholesale.
 *
 * Persistence (Slice 3): the backend Task Store is authoritative. A real task
 * is created backend-side BEFORE meaningful execution begins (atomicity); a
 * running checkpoint and the terminal state are persisted with bounded retry
 * and optimistic-concurrency revisions. If persistence is unavailable the
 * read-only task may still run, but the result is honestly flagged as not
 * durably saved — a failure to save is never presented as "saved".
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
import {
  InMemoryTaskStore,
  RemoteTaskStore,
  TASK_SCHEMA_VERSION,
  type PersistOutcome,
  type TaskStore,
} from "./task-store";
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
  /** Backend revision of the persisted record (0 until first confirmed write). */
  revision: number;
  /** Whether the record was durably created backend-side. */
  created: boolean;
  /** True once any persistence write could not be durably confirmed. */
  persistenceDegraded: boolean;
}

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `task-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function cloneRecord(record: CoreTaskRecord): CoreTaskRecord {
  return {
    ...record,
    steps: record.steps.map((s) => ({ ...s })),
    evidence: record.evidence.map((e) => ({ ...e })),
  };
}

export class RealCommandCore implements CommandCore {
  readonly kind = "core" as const;

  private listeners = new Set<CommandEventListener>();
  private runs = new Map<string, Runtime>();

  constructor(
    private transport: CoreTransport = realTransport,
    private store: TaskStore = typeof window !== "undefined"
      ? new RemoteTaskStore()
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

  /**
   * Restore durable real-task history from the authoritative backend. Terminal
   * tasks render as their outcome; a task found in a NON-terminal state after a
   * restart (no live executor owns it) is classified as interrupted and shown
   * honestly with recovery metadata — never as a fabricated success/failure.
   */
  async restore(): Promise<CommandEvent[]> {
    const out: CommandEvent[] = [];
    try {
      await this.store.init?.();
    } catch {
      /* migration is best-effort; never block restore */
    }
    let records: CoreTaskRecord[] = [];
    try {
      records = (await this.store.loadAll()).records;
    } catch {
      return out;
    }
    for (const rec of records) {
      if (rec.source !== "core") continue;

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

      if (rec.outcome) {
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
        continue;
      }

      // Non-terminal after a restart → interrupted, not resumed. Honest recovery
      // classification mapped onto the frozen UI contract (failed + recovery
      // evidence): it did not complete, and no executor is driving it.
      out.push({
        type: "failed",
        taskId: rec.taskId,
        at: rec.updatedAt,
        error: "Interrupted before completion — the app restarted while this task was mid-run. It was not resumed; re-run to retry.",
        evidence: [
          ...rec.evidence,
          { kind: "observed_state", label: "Recovery", value: "interrupted — not resumed" },
        ],
      });
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
      schemaVersion: TASK_SCHEMA_VERSION,
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
      revision: 0, created: false, persistenceDegraded: false,
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
    if (!run.record.currentStepId) void this.finishCancelled(run);
  }

  private async finishCancelled(run: Runtime) {
    if (run.record.outcome) return;
    run.record.outcome = "cancelled";
    run.record.status = "cancelled";
    run.record.endedAt = Date.now();
    await this.persistUpdate(run, "terminal");
    this.logger.log("terminal", run.record.taskId, { outcome: "cancelled" });
    this.emit({ type: "cancelled", taskId: run.record.taskId, at: Date.now() });
  }

  /* ---------------------------------------------------------- persistence */

  /** Persist the initial record backend-side (atomicity gate). */
  private async persistCreate(run: Runtime) {
    run.record.updatedAt = Date.now();
    const opId = makeId();
    let outcome: PersistOutcome | undefined;
    try {
      outcome = await this.store.create(cloneRecord(run.record), opId);
    } catch {
      outcome = undefined;
    }
    if (outcome?.ok && outcome.persisted) {
      run.revision = outcome.revision ?? 1;
      run.record.revision = run.revision;
      run.created = true;
      this.logger.log("persist.create", run.record.taskId, { revision: run.revision });
    } else {
      run.persistenceDegraded = true;
      this.logger.log("persist.degraded", run.record.taskId, { phase: "create", kind: outcome?.errorKind, error: outcome?.error });
    }
  }

  /** Persist a lifecycle checkpoint with bounded retry + optimistic revision. */
  private async persistUpdate(run: Runtime, phase: string) {
    if (!run.created) {
      run.persistenceDegraded = true;
      return;
    }
    run.record.updatedAt = Date.now();
    run.record.revision = run.revision;
    const opId = makeId(); // one id for this logical update — reused across retries
    const maxAttempts = 3;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      let outcome: PersistOutcome | undefined;
      try {
        outcome = await this.store.update(cloneRecord(run.record), run.revision, opId);
      } catch {
        outcome = undefined;
      }
      if (outcome?.ok && outcome.persisted) {
        run.revision = outcome.revision ?? run.revision;
        run.record.revision = run.revision;
        this.logger.log("persist.update", run.record.taskId, { revision: run.revision, phase });
        return;
      }
      if (outcome?.errorKind === "conflict") {
        if (outcome.conflict) {
          run.revision = outcome.conflict.revision;
          run.record.revision = run.revision;
        }
        this.logger.log("persist.conflict", run.record.taskId, { phase, revision: run.revision });
        return;
      }
      const retryable =
        outcome === undefined ||
        outcome.errorKind === "network" ||
        outcome.errorKind === "timeout" ||
        outcome.errorKind === "5xx";
      if (!retryable || attempt === maxAttempts) break;
      this.logger.log("persist.retry", run.record.taskId, { phase, nextAttempt: attempt + 1 });
      await sleep(200 * attempt);
    }
    run.persistenceDegraded = true;
    this.logger.log("persist.degraded", run.record.taskId, { phase });
  }

  private persistenceEvidence(run: Runtime): CommandEvidence {
    return run.persistenceDegraded
      ? { kind: "observed_state", label: "Persistence", value: "unavailable — this run was not durably saved" }
      : { kind: "observed_state", label: "Persistence", value: "durable — saved to the LILITH task store" };
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

    // Atomicity: persist the task before any meaningful (backend) execution.
    run.record.status = "planning";
    await this.persistCreate(run);
    if (run.canceled) return this.finishCancelled(run);

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

    // Durable non-terminal checkpoint: a crash from here is recoverable.
    run.record.status = "running";
    await this.persistUpdate(run, "running");
    if (run.canceled) return this.finishCancelled(run);

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
      await this.persistUpdate(run, "terminal");
      this.logger.log("terminal", taskId, { outcome: "partial" });
      const ev = [...evidence, this.persistenceEvidence(run)];
      run.record.evidence = ev;
      this.emit({ type: "partial.result", taskId, at: Date.now(), result: { outcome: "partial", summary: verdict.summary, unresolved: verdict.unresolved }, evidence: ev });
      return;
    }

    run.record.outcome = "succeeded";
    run.record.status = "succeeded";
    run.record.endedAt = Date.now();
    await this.persistUpdate(run, "terminal");
    this.logger.log("terminal", taskId, { outcome: "succeeded" });
    const ev = [...evidence, this.persistenceEvidence(run)];
    run.record.evidence = ev;
    this.emit({ type: "result.available", taskId, at: Date.now(), result: { outcome: "succeeded", summary: verdict.summary, unresolved: verdict.unresolved.length ? verdict.unresolved : undefined }, evidence: ev });
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

  private async fail(run: Runtime, reason: string, recovery?: string, mode: "failed" | "capability_unsupported" = "failed") {
    if (run.record.outcome) return;
    run.record.failure = { reason, recovery };
    run.record.endedAt = Date.now();
    const baseEvidence: CommandEvidence[] = run.record.evidence.length
      ? run.record.evidence
      : recovery
        ? [{ kind: "observed_state", label: "Action taken", value: "None — safe to retry" }]
        : [];
    if (mode === "capability_unsupported") {
      run.record.outcome = "failed";
      run.record.status = "blocked";
      await this.persistUpdate(run, "terminal");
      this.logger.log("terminal", run.record.taskId, { outcome: "blocked" });
      this.emit({ type: "capability.unsupported", taskId: run.record.taskId, at: Date.now(), reason, evidence: [...baseEvidence, this.persistenceEvidence(run)] });
      return;
    }
    run.record.outcome = "failed";
    run.record.status = "failed";
    await this.persistUpdate(run, "terminal");
    this.logger.log("terminal", run.record.taskId, { outcome: "failed" });
    const evidence = [...baseEvidence, this.persistenceEvidence(run)];
    run.record.evidence = evidence;
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
