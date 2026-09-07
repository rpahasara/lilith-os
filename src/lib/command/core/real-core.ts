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
import type { CommandApproval, CommandEvidence, CommandStep } from "../types";
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
import { careerFollowupPlaybook } from "./playbooks/career-followup";
import { careerNotePlaybook } from "./playbooks/career-note";
import { policyProbePlaybook } from "./playbooks/policy-probe";
import { evaluateCapabilityPolicy, type PolicyDecision } from "./policy";
import { fingerprintDraft, type DraftContent } from "./career-write";
import type { PlaybookContext, TaskPlaybook } from "./playbook";
import type {
  Capability,
  CapabilityResult,
  CommandPlan,
  CoreTaskRecord,
  CoreTransport,
  PlanStep,
  ProvenanceRef,
} from "./types";

/** Task-type registry, keyed by RealIntent id. */
const PLAYBOOKS: Record<string, TaskPlaybook> = {
  [systemHealthPlaybook.id]: systemHealthPlaybook,
  [careerAttentionPlaybook.id]: careerAttentionPlaybook,
  [careerFollowupPlaybook.id]: careerFollowupPlaybook,
  [careerNotePlaybook.id]: careerNotePlaybook,
  [policyProbePlaybook.id]: policyProbePlaybook,
};

/** Fallback approval window when a capability's policy declares none. */
const DEFAULT_APPROVAL_TTL_MS = 15 * 60 * 1000;

/** Reconstruct the frozen draft content from a persisted pendingWrite. */
function draftFromPending(pw: NonNullable<CoreTaskRecord["pendingWrite"]>): DraftContent {
  return {
    target: pw.target,
    subject: pw.subject ?? "",
    body: pw.body,
    idempotencyKey: pw.idempotencyKey,
    draftId: pw.draftId,
    fingerprint: pw.fingerprint,
  };
}

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
  /** The playbook context, reused across an approval suspend/resume. */
  ctx?: PlaybookContext;
  /** Step index to resume from once approval is granted. */
  resumeIndex?: number;
  /** True while the executor is suspended at an approval gate. */
  awaitingApproval?: boolean;
  /** Maintenance timer that expires an unused approval (§6). */
  expiryTimer?: ReturnType<typeof setTimeout>;
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
    for (const r of this.runs.values()) { r.abort.abort(); this.clearExpiry(r); }
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

      // Approval-gated recovery (Slice 4): a task persisted while waiting for —
      // or having just been granted — approval is NOT an interrupted run. Its
      // durable approval state deterministically decides what happens next.
      if (this.restoreApproval(rec, out)) continue;

      // Otherwise: non-terminal after a restart → interrupted, not resumed.
      // Honest recovery classification mapped onto the frozen UI contract
      // (failed + recovery evidence): it did not complete, and no executor is
      // driving it.
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

  /**
   * Rebuild an executable Runtime for a task restored mid-approval, and drive
   * the correct recovery:
   *  - approvalState "required"/"expired" → re-show the approval card and wait
   *    for an explicit decision; an expired window is surfaced, never auto-run.
   *  - approvalState "approved" but no terminal outcome → resume the ONE write.
   *    It is idempotent (stable key) and read-back verified, so it can never
   *    create a duplicate even if it had partially committed before the restart.
   * Returns true if it handled the record (caller should not mark interrupted).
   */
  private restoreApproval(rec: CoreTaskRecord, out: CommandEvent[]): boolean {
    const waiting = rec.status === "waiting_for_approval";
    const stillWaiting = waiting && (rec.approvalState === "required" || rec.approvalState === "expired");
    const approvedNotRun = rec.approvalState === "approved" && !rec.outcome;
    if (!stillWaiting && !approvedNotRun) return false;

    const intent = matchRealIntent(rec.rawIntent);
    const playbook = intent ? PLAYBOOKS[intent.id] : undefined;
    if (!intent || !playbook || !rec.plan) return false;

    const run: Runtime = {
      record: cloneRecord(rec),
      intent,
      playbook,
      plan: rec.plan,
      abort: new AbortController(),
      canceled: false,
      started: true,
      data: {},
      provenance: [],
      extraEvidence: [],
      revision: rec.revision ?? 0,
      created: rec.revision != null,
      persistenceDegraded: false,
      awaitingApproval: stillWaiting,
    };
    run.resumeIndex = this.writeStepIndex(run);
    this.runs.set(rec.taskId, run);

    if (approvedNotRun) {
      run.record.status = "running";
      // Defer to a macrotask so the provider folds task.created/plan.available
      // before the resumed run emits its own events.
      setTimeout(() => { void this.resumeAfterApproval(run); }, 0);
      return true;
    }

    // Still waiting. A window that has lapsed becomes an explicit expired state
    // (§6) — it cannot be silently approved; a valid window re-arms its timer.
    const now = Date.now();
    const expired = !!rec.approval?.expiresAt && now >= rec.approval.expiresAt;
    if (expired) {
      run.record.approvalState = "expired";
      void this.persistUpdate(run, "approval_expired");
      out.push({ type: "approval.requested", taskId: rec.taskId, at: rec.updatedAt, approval: this.approvalPayloadFor(rec, "expired") });
    } else {
      run.record.approvalState = "required";
      out.push({ type: "approval.requested", taskId: rec.taskId, at: rec.updatedAt, approval: this.approvalPayloadFor(rec, "required") });
      const remaining = (rec.approval?.expiresAt ?? now) - now;
      this.scheduleExpiry(run, remaining);
    }
    return true;
  }

  dispatch(action: CommandAction): void {
    switch (action.type) {
      case "submit": this.onSubmit(action.taskId, action.input); break;
      case "run": this.onRun(action.taskId); break;
      case "cancel": this.onCancel(action.taskId); break;
      case "retry":
      case "resume": this.onRetry(action.taskId); break;
      case "discard": this.runs.delete(action.taskId); break;
      case "approve": this.onApprove(action.taskId); break;
      case "deny": this.onDeny(action.taskId); break;
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

    const writes = plan.capabilitiesRequired.some((id) => getCapability(id)?.classification === "write");
    this.logger.log("task.created", taskId, { intent: intent.id, writes });
    this.emit({ type: "task.created", taskId, at: now, userInput: input, normalizedIntent: intent.normalized, title: intent.title, kind: "action", source: "core", contextSummary: writes ? "Live · will request approval before any change" : "Live read-only · no changes made" });
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
    // Cancelling while suspended at the approval gate (or before any step is
    // running) resolves to cancelled with ZERO side effect — no write occurs.
    if (run.awaitingApproval || !run.record.currentStepId) void this.finishCancelled(run);
  }

  private async finishCancelled(run: Runtime) {
    if (run.record.outcome) return;
    this.clearExpiry(run);
    run.awaitingApproval = false;
    run.record.outcome = "cancelled";
    run.record.status = "cancelled";
    run.record.endedAt = Date.now();
    await this.persistUpdate(run, "terminal");
    this.logger.log("terminal", run.record.taskId, { outcome: "cancelled" });
    this.emit({ type: "cancelled", taskId: run.record.taskId, at: Date.now() });
  }

  /* -------------------------------------------------------- approval gate */

  /** User granted approval — verify the freeze, then run the single write. */
  private async onApprove(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run) return;
    // Idempotent: a duplicate Approve after the first never runs a second write.
    if (run.record.approvalState === "approved") return;
    // Only a still-waiting (required) or expired approval is actionable; an
    // expired one re-requests below rather than executing.
    if (run.record.approvalState !== "required" && run.record.approvalState !== "expired") return;
    this.clearExpiry(run);

    const now = Date.now();
    // Expiry: an expired approval must NOT execute — re-request a fresh one.
    if (run.record.approval?.expiresAt && now > run.record.approval.expiresAt) {
      this.logger.log("approval.expired", taskId, {});
      this.reRequestApproval(run, "This approval had expired, so it was requested again.");
      return;
    }
    // Mutation freeze: the recomputed fingerprint must still match what was
    // approved. If the content changed, invalidate and request approval again.
    const pw = run.record.pendingWrite;
    const fp = pw
      ? fingerprintDraft({ capabilityId: pw.capabilityId, targetId: pw.target.id, subject: pw.subject ?? "", body: pw.body })
      : undefined;
    if (!pw || fp !== run.record.approval?.fingerprint) {
      this.logger.log("approval.fingerprint_mismatch", taskId, {});
      this.reRequestApproval(run, "The draft changed since it was shown, so approval was requested again.");
      return;
    }

    run.record.approvalState = "approved";
    run.record.approval = { ...run.record.approval, approvedAt: now };
    run.record.status = "running";
    run.awaitingApproval = false;
    await this.persistUpdate(run, "approval_approved");
    this.logger.log("approval.approved", taskId, {});
    this.emit({ type: "approval.resolved", taskId, at: now, approved: true });
    void this.resumeAfterApproval(run);
  }

  /** User denied — terminal cancelled, provably zero side effect. */
  private async onDeny(taskId: string) {
    const run = this.runs.get(taskId);
    if (!run) return;
    if (run.record.approvalState !== "required" && run.record.approvalState !== "expired") return;
    this.clearExpiry(run);
    const now = Date.now();
    run.record.approvalState = "denied";
    run.record.approval = { ...run.record.approval, deniedAt: now };
    run.awaitingApproval = false;
    run.record.outcome = "cancelled";
    run.record.status = "cancelled";
    run.record.endedAt = now;
    run.record.resultSummary = "Denied — no draft was created.";
    run.record.evidence = [
      ...run.record.evidence,
      { kind: "observed_state", label: "Action taken", value: "None — approval denied, nothing was written" },
    ];
    await this.persistUpdate(run, "terminal");
    this.logger.log("approval.denied", taskId, {});
    this.emit({ type: "approval.resolved", taskId, at: now, approved: false });
  }

  /** Suspend the executor at a write step and ask the user to approve. */
  private async requestApproval(run: Runtime, step: PlanStep, index: number, decision: PolicyDecision) {
    const data = run.data as { draft?: DraftContent };
    const draft = data.draft ?? (run.record.pendingWrite ? draftFromPending(run.record.pendingWrite) : undefined);
    if (!draft || !step.capabilityId) {
      return this.fail(run, "The draft to approve was not prepared.", "Re-run the request.");
    }
    // Freeze the exact action on the durable record.
    run.record.pendingWrite = {
      capabilityId: step.capabilityId,
      stepId: step.id,
      target: draft.target,
      subject: draft.subject,
      body: draft.body,
      idempotencyKey: draft.idempotencyKey,
      draftId: draft.draftId,
      fingerprint: draft.fingerprint,
    };
    const now = Date.now();
    const ttl = decision.approvalTtlMs ?? DEFAULT_APPROVAL_TTL_MS;
    run.record.approval = { requestedAt: now, expiresAt: now + ttl, fingerprint: draft.fingerprint };
    run.record.approvalState = "required";
    run.record.status = "waiting_for_approval";
    run.record.steps = run.record.steps.map((s) =>
      s.id === step.id ? { ...s, status: "waiting", startedAt: s.startedAt ?? now } : s,
    );
    run.record.currentStepId = step.id;
    run.resumeIndex = index;
    run.awaitingApproval = true;
    await this.persistUpdate(run, "approval_required");
    this.logger.log("approval.requested", run.record.taskId, { capId: step.capabilityId, policyClass: decision.policyClass });
    this.emit({ type: "approval.requested", taskId: run.record.taskId, at: now, approval: this.approvalPayloadFor(run.record, "required") });
    this.scheduleExpiry(run, ttl);
  }

  /**
   * Approval-expiry maintenance (§6): after the TTL, an unused waiting approval
   * transitions to an explicit expired state and the card is re-shown as stale —
   * it never stays silently valid. The timer is unref'd so it cannot keep a
   * process alive (harmless in the browser).
   */
  private scheduleExpiry(run: Runtime, ttl: number) {
    this.clearExpiry(run);
    if (!Number.isFinite(ttl) || ttl <= 0) return;
    const t = setTimeout(() => this.expireApproval(run.record.taskId), ttl);
    (t as { unref?: () => void }).unref?.();
    run.expiryTimer = t;
  }

  private clearExpiry(run: Runtime) {
    if (run.expiryTimer) { clearTimeout(run.expiryTimer); run.expiryTimer = undefined; }
  }

  /** Fired by the maintenance timer (or a manual sweep) when a wait times out. */
  private expireApproval(taskId: string, now = Date.now()) {
    const run = this.runs.get(taskId);
    if (!run || !run.awaitingApproval || run.record.approvalState !== "required") return;
    if (run.record.approval?.expiresAt && now < run.record.approval.expiresAt) return;
    this.clearExpiry(run);
    run.record.approvalState = "expired";
    this.logger.log("approval.expired", taskId, {});
    void this.persistUpdate(run, "approval_expired");
    // Re-show the card as expired; the user must re-approve, which re-requests.
    this.emit({ type: "approval.requested", taskId, at: now, approval: this.approvalPayloadFor(run.record, "expired") });
  }

  /** Force-expire any waiting approvals already past their TTL (restore-time sweep). */
  sweepExpiredApprovals(now = Date.now()): number {
    let n = 0;
    for (const run of this.runs.values()) {
      if (run.awaitingApproval && run.record.approvalState === "required" && run.record.approval?.expiresAt && now >= run.record.approval.expiresAt) {
        this.expireApproval(run.record.taskId, now);
        n += 1;
      }
    }
    return n;
  }

  /** Re-issue an approval request with a fresh window (expired / content drift). */
  private reRequestApproval(run: Runtime, note: string) {
    const now = Date.now();
    const fp = run.record.pendingWrite?.fingerprint;
    const cap = run.record.pendingWrite ? getCapability(run.record.pendingWrite.capabilityId) : undefined;
    const ttl = (cap ? evaluateCapabilityPolicy(cap).approvalTtlMs : null) ?? DEFAULT_APPROVAL_TTL_MS;
    run.record.approval = { requestedAt: now, expiresAt: now + ttl, fingerprint: fp };
    run.record.approvalState = "required";
    run.record.status = "waiting_for_approval";
    run.awaitingApproval = true;
    void this.persistUpdate(run, "approval_rerequested");
    this.emit({ type: "approval.resolved", taskId: run.record.taskId, at: now, approved: false });
    this.emit({ type: "approval.requested", taskId: run.record.taskId, at: now, approval: { ...this.approvalPayloadFor(run.record, "required"), reason: note } });
    this.scheduleExpiry(run, ttl);
  }

  /** Build the approval card payload from the frozen pendingWrite on a record. */
  private approvalPayloadFor(record: CoreTaskRecord, status: CommandApproval["status"]): CommandApproval {
    const pw = record.pendingWrite;
    const cap = pw ? getCapability(pw.capabilityId) : undefined;
    const decision = cap ? evaluateCapabilityPolicy(cap) : undefined;
    const targetLabel = pw?.target.label ?? (pw ? `application ${pw.target.id}` : "the target");
    const preview = pw ? `${pw.subject ? `Subject: ${pw.subject}\n\n` : ""}${pw.body}` : undefined;
    return {
      status,
      summary: `${cap?.title ?? "Confirm this action"} — ${targetLabel}`,
      reason: cap?.sideEffectLabel ?? "This action requires your approval.",
      action: cap?.title,
      target: targetLabel,
      contentPreview: preview,
      sideEffect: cap?.sideEffectLabel,
      reversible: cap?.reversible,
      capabilityId: pw?.capabilityId,
      expiresAt: record.approval?.expiresAt,
      elevatedWarning: decision?.elevatedWarning,
      riskLevel: decision?.riskLevel,
    };
  }

  /** Continue execution from the write step once approval is granted. */
  private async resumeAfterApproval(run: Runtime) {
    if (!run.ctx) run.ctx = this.buildCtx(run);
    const data = run.data as { draft?: DraftContent };
    if (!data.draft && run.record.pendingWrite) data.draft = draftFromPending(run.record.pendingWrite);
    run.started = true;
    const idx = run.resumeIndex ?? this.writeStepIndex(run);
    this.emit({ type: "status", taskId: run.record.taskId, at: Date.now(), status: "running" });
    await this.runSteps(run, idx);
  }

  private writeStepIndex(run: Runtime): number {
    const i = run.plan.steps.findIndex((s) => {
      const cap = s.capabilityId ? getCapability(s.capabilityId) : null;
      return !!cap && evaluateCapabilityPolicy(cap).approvalRequired;
    });
    return i < 0 ? 0 : i;
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

  private buildCtx(run: Runtime): PlaybookContext {
    const taskId = run.record.taskId;
    return {
      taskId,
      now: Date.now(),
      rawIntent: run.record.rawIntent,
      isCanceled: () => run.canceled,
      runCapability: (cap, stepId) => this.runCapability(run, cap, stepId),
      emitProgress: (stepId, detail) => this.emit({ type: "step.progress", taskId, at: Date.now(), stepId, detail }),
      data: run.data,
      provenance: run.provenance,
      evidence: run.extraEvidence,
    };
  }

  private async execute(run: Runtime) {
    const { taskId } = run.record;
    run.ctx = this.buildCtx(run);

    this.emit({ type: "status", taskId, at: Date.now(), status: "planning" });
    this.emit({ type: "plan.available", taskId, at: Date.now(), steps: recSteps(run.record) });

    // Atomicity: persist the task before any meaningful (backend) execution.
    run.record.status = "planning";
    await this.persistCreate(run);
    if (run.canceled) return this.finishCancelled(run);

    // Capability check — every required capability must exist AND be permitted
    // by policy. A PROHIBITED capability blocks the whole task before any step
    // runs, no matter what the planner emitted (§5).
    for (const capId of run.plan.capabilitiesRequired) {
      const cap = getCapability(capId);
      if (!cap) {
        this.logger.log("capability.selected", taskId, { capId, present: false });
        return this.fail(run, `Capability ${capId} is not available.`, undefined, "capability_unsupported");
      }
      const decision = evaluateCapabilityPolicy(cap);
      if (decision.prohibited) {
        this.logger.log("policy.blocked", taskId, { capId, policyClass: decision.policyClass });
        return this.fail(run, `The action "${cap.title}" is prohibited by policy and cannot be run.`, undefined, "capability_unsupported");
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

    await this.runSteps(run, 0);
  }

  /**
   * Run plan steps from `fromIndex`. A step whose capability is
   * `approval_required` (and not yet approved) SUSPENDS the executor at the
   * approval gate — no write happens until the user approves and execution
   * resumes here from the same index.
   */
  private async runSteps(run: Runtime, fromIndex: number) {
    const { taskId } = run.record;
    const ctx = run.ctx ?? (run.ctx = this.buildCtx(run));
    const steps = run.plan.steps;

    for (let i = fromIndex; i < steps.length; i++) {
      const step = steps[i];
      if (run.canceled) return this.finishCancelled(run);

      const cap = step.capabilityId ? getCapability(step.capabilityId) : null;
      if (cap) {
        const decision = evaluateCapabilityPolicy(cap);
        if (decision.prohibited) {
          return this.fail(run, `The action "${cap.title}" is prohibited by policy and cannot be run.`, undefined, "capability_unsupported");
        }
        if (decision.approvalRequired && run.record.approvalState !== "approved") {
          // Suspend at the gate. NOTHING has been written; only task state is saved.
          return this.requestApproval(run, step, i, decision);
        }
      }

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
    return this.finalize(run);
  }

  private async finalize(run: Runtime) {
    const { taskId } = run.record;
    const ctx = run.ctx ?? (run.ctx = this.buildCtx(run));

    run.record.status = "verifying";
    this.emit({ type: "status", taskId, at: Date.now(), status: "running" });
    const verdict = run.playbook.verify(ctx);
    this.logger.log("verify.verdict", taskId, { verdict: verdict.verdict, unresolved: verdict.unresolved.length });
    if (run.canceled) return this.finishCancelled(run);

    // Record the committed write on the audit trail (if any).
    const writeResult = (run.data as { writeResult?: { draft?: { draftId?: string; contentHash?: string; createdAt?: number } } }).writeResult;
    if (writeResult?.draft?.draftId) {
      run.record.writeResult = {
        draftId: writeResult.draft.draftId,
        operationId: run.record.pendingWrite?.idempotencyKey ?? writeResult.draft.draftId,
        createdAt: writeResult.draft.createdAt,
        contentHash: writeResult.draft.contentHash,
        verified: verdict.verdict,
      };
    }

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
    const retry = cap.retry;
    // Policy decides whether a failed attempt may be retried without re-confirm:
    // reads always may; a write only when it is idempotent (dedupe-safe).
    const canSilentRetry = evaluateCapabilityPolicy(cap).allowSilentRetry;
    let last: CapabilityResult | null = null;
    for (let attempt = 1; attempt <= retry.maxAttempts; attempt++) {
      if (run.canceled) break;
      this.bumpAttempt(run, stepId);
      last = await cap.execute(this.transport, run.abort.signal);
      this.logger.log("capability.result", taskId, { capId: cap.id, ok: last.ok, status: last.status, attempt, execId: last.executionId });
      if (last.ok) return last;
      const retryable = canSilentRetry && !!last.errorKind && (retry.retryOn as string[]).includes(last.errorKind) && attempt < retry.maxAttempts && !run.canceled;
      if (!retryable) break;
      this.logger.log("retry", taskId, { capId: cap.id, nextAttempt: attempt + 1 });
      this.emit({ type: "step.progress", taskId, at: Date.now(), stepId, detail: `retrying (attempt ${attempt + 1}/${retry.maxAttempts})` });
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
