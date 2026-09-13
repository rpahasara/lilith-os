/**
 * Demo command fixtures — explicit, scripted timelines used by the V1 demo
 * adapter to validate the command UX end to end.
 *
 * These are deliberately *fixtures*, not free-running simulations: each beat is
 * a concrete lifecycle event with a relative delay. Nothing here executes
 * anything external, and every task produced from a fixture is marked
 * `source: "demo"` so the UI can label it as a preview and never present it as
 * real execution. When the Cognitive Core lands, it replaces the adapter that
 * reads these — the UI is untouched.
 */

import type { CommandEvent } from "./events";
import type { CommandEvidence, CommandKind, CommandStep } from "./types";

/** One scheduled beat in a fixture timeline. */
export interface ScriptBeat {
  /** ms to wait after the previous beat (or after Run, for the first beat). */
  delay: number;
  build: (ctx: { taskId: string; at: number }) => CommandEvent;
}

export interface CommandFixture {
  id: string;
  /** Lowercased-input patterns that select this fixture. */
  triggers: RegExp[];
  title: string;
  normalizedIntent: string;
  kind: CommandKind;
  contextSummary?: string;
  /** Proposed plan shown during intent review. */
  plan: { id: string; label: string }[];
  /** Timeline played after the user accepts the plan (Run). */
  script: ScriptBeat[];
  /** For `unsupported` fixtures: the capability boundary shown immediately. */
  unsupported?: { reason: string; evidence?: CommandEvidence[] };
}

function step(id: string, label: string): { id: string; label: string } {
  return { id, label };
}

/** Build the initial (all-pending) step list from a fixture plan. */
export function planToSteps(plan: { id: string; label: string }[]): CommandStep[] {
  return plan.map((p) => ({ id: p.id, label: p.label, status: "pending" as const }));
}

/* ------------------------------------------------------------- the fixtures */

export const FIXTURES: CommandFixture[] = [
  /* ---- success: read-only analysis, all steps resolve --------------------- */
  {
    id: "aws-cost-compare",
    triggers: [/\baws\b.*cost/, /cost.*compare/, /compare.*(cost|spend|billing)/],
    title: "AWS cost comparison",
    normalizedIntent: "Compare current AWS spend against the previous period",
    kind: "action",
    contextSummary: "Read-only billing lookup · no changes made",
    plan: [
      step("s1", "Retrieve current billing period"),
      step("s2", "Retrieve previous period"),
      step("s3", "Compare major services"),
      step("s4", "Prepare summary"),
    ],
    script: [
      { delay: 500, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s1" }) },
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s1", outcome: "succeeded", detail: "$4,182 month-to-date" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s2" }) },
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s2", outcome: "succeeded", detail: "$3,640 prior month" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s3" }) },
      { delay: 1100, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s3", outcome: "succeeded", detail: "EC2 +18%, S3 flat, RDS +6%" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s4" }) },
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s4", outcome: "succeeded" }) },
      {
        delay: 300,
        build: ({ taskId, at }) => ({
          type: "result.available",
          taskId,
          at,
          result: {
            outcome: "succeeded",
            summary: "Spend is up 14.9% ($542) vs. last month, driven mainly by EC2.",
          },
          evidence: [
            { kind: "observed_state", label: "Current period", value: "$4,182.00" },
            { kind: "observed_state", label: "Previous period", value: "$3,640.00" },
            { kind: "artifact", label: "Cost comparison summary" },
          ],
        }),
      },
    ],
  },

  /* ---- partial: some work done, one item unresolved ---------------------- */
  {
    id: "inbox-triage",
    triggers: [/summari[sz]e.*inbox/, /inbox/, /what did i miss/, /triage/],
    title: "Inbox triage",
    normalizedIntent: "Summarise unread mail and draft replies where obvious",
    kind: "action",
    contextSummary: "Reads mail · drafts saved, nothing sent",
    plan: [
      step("s1", "Scan unread messages"),
      step("s2", "Group by thread"),
      step("s3", "Draft replies where clear"),
      step("s4", "Prepare digest"),
    ],
    script: [
      { delay: 500, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s1" }) },
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s1", outcome: "succeeded", detail: "23 unread" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s2" }) },
      { delay: 800, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s2", outcome: "succeeded", detail: "9 threads" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s3" }) },
      { delay: 1000, build: ({ taskId, at }) => ({ type: "step.progress", taskId, at, stepId: "s3", detail: "3 of 5 drafts written" }) },
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s3", outcome: "skipped", detail: "2 threads need your input" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s4" }) },
      { delay: 700, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s4", outcome: "succeeded" }) },
      {
        delay: 300,
        build: ({ taskId, at }) => ({
          type: "partial.result",
          taskId,
          at,
          result: {
            outcome: "partial",
            summary: "Digest ready and 3 replies drafted — 2 threads still need a decision from you.",
            unresolved: [
              "Re: Q3 contract renewal — needs your pricing call",
              "Re: Board deck — awaiting your headline number",
            ],
          },
          evidence: [
            { kind: "artifact", label: "Inbox digest (9 threads)" },
            { kind: "artifact", label: "3 draft replies" },
            { kind: "unresolved", label: "2 threads need input" },
          ],
        }),
      },
    ],
  },

  /* ---- approval gate then success --------------------------------------- */
  {
    id: "send-followups",
    triggers: [/send.*follow.?up/, /follow.?up.*email/, /email.*team/, /send.*email/],
    title: "Send meeting follow-ups",
    normalizedIntent: "Send follow-up emails to yesterday's meeting attendees",
    kind: "action",
    contextSummary: "Sends email on your behalf · requires approval",
    plan: [
      step("s1", "Gather attendees"),
      step("s2", "Assemble follow-up drafts"),
      step("s3", "Send emails"),
    ],
    script: [
      { delay: 500, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s1" }) },
      { delay: 800, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s1", outcome: "succeeded", detail: "4 attendees" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s2" }) },
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s2", outcome: "succeeded", detail: "4 drafts ready" }) },
      { delay: 300, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s3" }) },
      {
        delay: 700,
        build: ({ taskId, at }) => ({
          type: "approval.requested",
          taskId,
          at,
          approval: {
            status: "required",
            summary: "Send 4 follow-up emails",
            reason: "This sends email on your behalf to external recipients.",
          },
        }),
      },
      // Beats below only play once approval is granted.
      { delay: 900, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s3", outcome: "succeeded", detail: "4 sent" }) },
      {
        delay: 300,
        build: ({ taskId, at }) => ({
          type: "result.available",
          taskId,
          at,
          result: { outcome: "succeeded", summary: "Sent 4 follow-up emails." },
          evidence: [
            { kind: "external_id", label: "Message batch", value: "msg-batch-7f3a" },
            { kind: "observed_state", label: "Delivered", value: "4 / 4" },
          ],
        }),
      },
    ],
  },

  /* ---- failure: backend unavailable ------------------------------------- */
  {
    id: "restart-worker",
    triggers: [/restart.*(worker|service|hermes)/, /redeploy/, /\bdeploy\b/],
    title: "Restart Hermes worker",
    normalizedIntent: "Restart the Hermes message worker on the VM",
    kind: "action",
    contextSummary: "Requires the control backend · currently offline",
    plan: [
      step("s1", "Reach control backend"),
      step("s2", "Signal worker restart"),
      step("s3", "Verify healthy"),
    ],
    script: [
      { delay: 500, build: ({ taskId, at }) => ({ type: "step.started", taskId, at, stepId: "s1" }) },
      { delay: 1200, build: ({ taskId, at }) => ({ type: "step.progress", taskId, at, stepId: "s1", detail: "Connecting to control backend…" }) },
      { delay: 1200, build: ({ taskId, at }) => ({ type: "step.finished", taskId, at, stepId: "s1", outcome: "failed", detail: "No response from control backend" }) },
      {
        delay: 300,
        build: ({ taskId, at }) => ({
          type: "failed",
          taskId,
          at,
          error: "The control backend is unreachable, so the worker was not restarted.",
          evidence: [
            { kind: "error_detail", label: "Transport", value: "IAP tunnel · connection refused" },
            { kind: "observed_state", label: "Action taken", value: "None — safe to retry" },
          ],
        }),
      },
    ],
  },

  /* ---- unsupported: recognised intent, no capability -------------------- */
  {
    id: "delete-files",
    triggers: [/delete.*(file|folder|directory)/, /rm -rf/, /wipe/, /format/],
    title: "Delete files",
    normalizedIntent: "Delete files from local storage",
    kind: "unsupported",
    plan: [],
    script: [],
    unsupported: {
      reason:
        "I understand what you want, but I don't have filesystem write access in this environment yet.",
      evidence: [
        { kind: "observed_state", label: "Capability", value: "filesystem.write — not granted" },
      ],
    },
  },
  {
    id: "buy-something",
    triggers: [/\bbuy\b/, /purchase/, /order.*(now|amazon)/, /pay\b/],
    title: "Make a purchase",
    normalizedIntent: "Place an order / make a payment",
    kind: "unsupported",
    plan: [],
    script: [],
    unsupported: {
      reason:
        "I can't make purchases or move money. This action is unavailable in the current environment.",
      evidence: [
        { kind: "observed_state", label: "Capability", value: "payments — not available" },
      ],
    },
  },
];

/** Match input to a fixture, or null for a plain conversational turn. */
export function matchFixture(input: string): CommandFixture | null {
  const text = input.toLowerCase().trim();
  for (const fx of FIXTURES) {
    if (fx.triggers.some((re) => re.test(text))) return fx;
  }
  return null;
}
