/**
 * LILITH Command System V1 — the typed command/task *presentation* contract.
 *
 * This is the UI-facing shape of a command as it moves through its lifecycle.
 * It is deliberately a presentation contract, not the Cognitive Core's internal
 * task model: the UI must be able to render a command truthfully without
 * pretending execution exists where it does not.
 *
 * The future Cognitive Core V2 will produce these tasks (via the
 * {@link CommandCore} seam in `./events`); V1 produces them from a clearly
 * labelled demo adapter. Nothing here assumes a real executor.
 */

/**
 * The lifecycle a command visibly moves through. Not every command touches
 * every state — a plain conversational turn skips review/planning entirely; an
 * unsupported request stops at `blocked`.
 *
 *   draft                — captured, not yet classified
 *   reviewing            — intent + proposed plan shown for confirmation
 *   queued               — accepted, awaiting a runner
 *   planning             — the core is expanding the plan
 *   waiting_for_approval — a sensitive step needs explicit user approval
 *   running              — executing steps
 *   blocked              — cannot proceed (missing capability / environment)
 *   partial              — finished with some steps unresolved
 *   succeeded            — finished, all steps resolved
 *   failed               — stopped on an error
 *   cancelled            — stopped at the user's request
 */
export type CommandStatus =
  | "draft"
  | "reviewing"
  | "queued"
  | "planning"
  | "waiting_for_approval"
  | "running"
  | "blocked"
  | "partial"
  | "succeeded"
  | "failed"
  | "cancelled";

/** Terminal states — a task in one of these will not change again on its own. */
export const TERMINAL_STATUSES: readonly CommandStatus[] = [
  "partial",
  "succeeded",
  "failed",
  "cancelled",
  "blocked",
];

export function isTerminal(status: CommandStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

/** Per-step state within a running command. */
export type CommandStepStatus =
  | "pending"
  | "running"
  | "waiting"
  | "succeeded"
  | "failed"
  | "skipped";

export interface CommandStep {
  id: string;
  label: string;
  /** Optional human detail shown under the step while/after it runs. */
  detail?: string;
  status: CommandStepStatus;
  /** Epoch ms. */
  startedAt?: number;
  endedAt?: number;
}

/**
 * Where a task's state comes from. Critical for honesty: `demo` state is a
 * scripted preview and must never be presented as real external execution.
 */
export type CommandSource = "conversation" | "demo" | "core";

/**
 * How a command reads to the user. `chat` is a plain conversational turn that
 * bypasses the command lifecycle; `action` runs the full review→run lifecycle;
 * `unsupported` is a recognised intent with no capability behind it yet.
 */
export type CommandKind = "chat" | "action" | "unsupported";

/** Approval lifecycle for a sensitive step (send email, delete, external write). */
export type ApprovalStatus =
  | "not_required"
  | "required"
  | "approved"
  | "denied"
  | "expired";

export interface CommandApproval {
  status: ApprovalStatus;
  /** What is being approved, in plain language. */
  summary?: string;
  /** Why it needs approval (e.g. "sends an email on your behalf"). */
  reason?: string;
  /** Epoch ms after which a `required` approval should be treated as stale. */
  expiresAt?: number;
  /**
   * Structured detail for an approval-gated write (Slice 4). All optional so the
   * existing demo approval — which only sets summary/reason — is unaffected.
   */
  /** The exact action/capability verb, e.g. "Create follow-up draft". */
  action?: string;
  /** The concrete object the action acts on, e.g. "NEXT · Senior DevOps Engineer". */
  target?: string;
  /** The exact content that will be written/sent, shown verbatim before approval. */
  contentPreview?: string;
  /** One-line description of the side effect. */
  sideEffect?: string;
  /** Whether the side effect can be undone. */
  reversible?: boolean;
  /** The capability id behind the write (provenance). */
  capabilityId?: string;
}

/** A pointer to something a finished command produced or observed. */
export type CommandEvidenceKind =
  | "artifact"
  | "link"
  | "external_id"
  | "observed_state"
  | "error_detail"
  | "unresolved";

export interface CommandEvidence {
  kind: CommandEvidenceKind;
  label: string;
  /** Present for `link`. */
  href?: string;
  /** Free-form value: an id, an observed value, an error string. */
  value?: string;
}

export type CommandOutcome = "succeeded" | "partial" | "failed" | "cancelled";

export interface CommandResult {
  outcome: CommandOutcome;
  /** One-line summary of what happened. A partial result must not read as success. */
  summary: string;
  /** Items that could not be completed — populated on `partial`. */
  unresolved?: string[];
}

/**
 * The complete presentation contract for one command/task.
 */
export interface CommandTask {
  taskId: string;
  /** Raw user input, verbatim. */
  userInput: string;
  /** The core's normalised reading of the intent (may equal userInput early). */
  normalizedIntent: string;
  /** Short display title. */
  title: string;
  status: CommandStatus;
  kind: CommandKind;
  source: CommandSource;

  createdAt: number;
  updatedAt: number;

  steps: CommandStep[];
  /** Index into `steps` of the currently active step, or null. */
  currentStep: number | null;

  approval: CommandApproval;

  /** Whether a cancel request is meaningful in the current state. */
  cancelability: boolean;
  /** Whether the task can be resumed after a cancel/failure. */
  resumability: boolean;
  /** True while a cancel has been requested but not yet acknowledged. */
  cancelRequested: boolean;

  result?: CommandResult;
  /** Human-readable failure/blocked reason. */
  error?: string;
  evidence: CommandEvidence[];

  /** Short, non-sensitive summary of the context this task ran against. */
  contextSummary?: string;
}
