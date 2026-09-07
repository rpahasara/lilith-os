/**
 * Task playbook abstraction.
 *
 * The RealCommandCore is the single generic engine (submit/run/cancel/retry/
 * step-execution/persistence/logging/terminal emission). Each *task type* is a
 * {@link TaskPlaybook} that only describes what is task-specific: its plan, how
 * to run each step, and how to verify. This is what lets Slice 2 (career) reuse
 * the entire Slice 1 machinery instead of duplicating it.
 */
import type { CommandEvidence } from "../types";
import type {
  Capability,
  CapabilityResult,
  CommandPlan,
  PlanStep,
  ProvenanceRef,
  VerifierResult,
} from "./types";

/** Outcome of running a single plan step. */
export interface StepResult {
  outcome: "succeeded" | "failed" | "skipped";
  detail?: string;
  /** When set, the whole task fails with this reason (backbone step failure). */
  fatal?: { reason: string; recovery?: string };
}

/** Services the engine exposes to a playbook while a step runs. */
export interface PlaybookContext {
  taskId: string;
  now: number;
  /** The verbatim user request — used by playbooks that resolve a target from it. */
  rawIntent: string;
  isCanceled(): boolean;
  /** Cancel-aware, bounded-retry capability execution (emits retry progress). */
  runCapability(cap: Capability, stepId: string): Promise<CapabilityResult>;
  emitProgress(stepId: string, detail: string): void;
  /** Accumulated retrieved datasets, keyed by capability id. */
  data: Record<string, unknown>;
  provenance: ProvenanceRef[];
  /** Extra evidence a playbook wants attached to the terminal result. */
  evidence: CommandEvidence[];
}

export interface TaskPlaybook {
  /** Matches the RealIntent id from `intents.ts`. */
  id: string;
  /** The capability whose health gates execution. */
  backboneCapabilityId: string;
  plan(taskId: string, normalizedIntent: string): CommandPlan;
  runStep(step: PlanStep, ctx: PlaybookContext): Promise<StepResult>;
  verify(ctx: PlaybookContext): VerifierResult;
}
