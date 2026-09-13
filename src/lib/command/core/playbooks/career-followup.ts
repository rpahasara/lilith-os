/**
 * Career follow-up draft playbook — Vertical Slice 4 (approval-gated write).
 *
 * Steps:
 *   s1  retrieve application context (read) + resolve the target application
 *   s2  compose the exact draft (analysis) — content is FROZEN here, before any
 *       approval is requested, so the user approves precisely what will be saved
 *   s3  create the draft (WRITE, approval_required) — the engine gates BEFORE
 *       this step; only after approval does the one bounded, idempotent mutation
 *       run
 *   s4  read the draft back (read) for the verifier to confirm
 *
 * The playbook owns no persistence, approval, retry, or cancellation — those are
 * the RealCommandCore engine's job. It only produces context, the frozen draft,
 * runs the two bound capabilities, and verifies via read-back.
 */
import type { CommandEvidence } from "../../types";
import { getCapability } from "../capabilities";
import { careerListApplicationsCapability, type CareerApplication } from "../career-capabilities";
import {
  buildFollowupDraft,
  createFollowupDraftCapability,
  getFollowupDraftCapability,
  resolveApplicationTarget,
  type DraftContent,
  type DraftRecord,
} from "../career-write";
import type { PlaybookContext, StepResult, TaskPlaybook } from "../playbook";
import { planCareerFollowup } from "../planner";
import type { PlanStep } from "../types";
import { verifyFollowupDraft } from "../verifier";

/** The plan step that performs the (approval-gated) write. */
export const FOLLOWUP_WRITE_STEP_ID = "s3";

interface FollowupData {
  __apps?: CareerApplication[];
  application?: CareerApplication;
  draft?: DraftContent;
  writeResult?: { draft: DraftRecord; created?: boolean };
  readback?: DraftRecord | null;
}

export const careerFollowupPlaybook: TaskPlaybook = {
  id: "career.create_followup_draft",
  backboneCapabilityId: "career.list_applications",

  plan(taskId, intent) {
    return planCareerFollowup(taskId, intent);
  },

  async runStep(step: PlanStep, ctx: PlaybookContext): Promise<StepResult> {
    const data = ctx.data as FollowupData;

    // s1 — retrieve applications + resolve the target.
    if (step.id === "s1") {
      const res = await ctx.runCapability(careerListApplicationsCapability, step.id);
      if (!res.ok) {
        return { outcome: "failed", detail: res.error, fatal: { reason: "Could not retrieve applications to draft against.", recovery: "Retry when the career backend is reachable." } };
      }
      const apps = (res.data as CareerApplication[]) ?? [];
      data.__apps = apps;
      ctx.provenance.push({ capabilityId: careerListApplicationsCapability.id, executionId: res.executionId, source: res.source, fetchedAt: Date.now() });
      const target = resolveApplicationTarget(ctx.rawIntent, apps);
      if ("error" in target) {
        return { outcome: "failed", detail: target.error, fatal: { reason: target.error } };
      }
      data.application = target;
      return { outcome: "succeeded", detail: `Target: ${target.company} · ${target.role} (#${target.id})` };
    }

    // s2 — compose + freeze the exact draft (no side effect).
    if (step.id === "s2") {
      const app = data.application;
      if (!app) return { outcome: "failed", fatal: { reason: "No target application was resolved." } };
      const draft = buildFollowupDraft(app, ctx.taskId, FOLLOWUP_WRITE_STEP_ID);
      data.draft = draft;
      return { outcome: "succeeded", detail: `Drafted "${draft.subject}"` };
    }

    // s3 — the WRITE. The engine only runs this after approval; the content is
    // the frozen draft (or, after a reload, the persisted pendingWrite the
    // engine restored into ctx.data.draft).
    if (step.id === FOLLOWUP_WRITE_STEP_ID) {
      const draft = data.draft;
      if (!draft) return { outcome: "failed", fatal: { reason: "No approved draft content to write." } };
      const cap = createFollowupDraftCapability(draft, { taskId: ctx.taskId, stepId: step.id });
      const res = await ctx.runCapability(cap, step.id);
      if (!res.ok) {
        return { outcome: "failed", detail: res.error, fatal: { reason: "The draft could not be created.", recovery: "The write is idempotent — retry is safe once the backend is reachable." } };
      }
      const record = res.data as DraftRecord;
      data.writeResult = { draft: record, created: record.created };
      const ev: CommandEvidence = { kind: "external_id", label: "Created draft", value: record.draftId };
      ctx.evidence.push(ev);
      return { outcome: "succeeded", detail: record.created === false ? "existing draft reused (idempotent)" : "draft created" };
    }

    // s4 — read back the created draft for verification.
    if (step.id === "s4") {
      const id = data.writeResult?.draft.draftId ?? data.draft?.draftId;
      if (!id) {
        data.readback = null;
        return { outcome: "failed", detail: "no draft id to read back" };
      }
      const cap = getFollowupDraftCapability(id);
      const res = await ctx.runCapability(cap, step.id);
      if (!res.ok) {
        data.readback = null;
        // Not fatal: the verifier turns a missing read-back into an honest FAIL.
        return { outcome: "failed", detail: res.error };
      }
      data.readback = res.data as DraftRecord;
      return { outcome: "succeeded", detail: "read back" };
    }

    return { outcome: "skipped" };
  },

  verify(ctx) {
    const data = ctx.data as FollowupData;
    return verifyFollowupDraft({
      approved: data.draft ?? null,
      readback: data.readback ?? null,
      created: data.writeResult?.created,
    });
  },
};
