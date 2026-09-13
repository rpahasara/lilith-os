/**
 * Career note playbook — Vertical Slice 5. A second INTERNAL_WRITE that goes
 * through the identical engine + policy gate as the follow-up draft, proving the
 * lifecycle is generic. Saves an internal, reversible note on an application;
 * nothing is sent. The note text is taken verbatim from the user and frozen
 * before approval.
 */
import type { CommandEvidence } from "../../types";
import { careerListApplicationsCapability, type CareerApplication } from "../career-capabilities";
import {
  buildNote,
  createNoteCapability,
  getFollowupDraftCapability,
  resolveApplicationTarget,
  type DraftContent,
  type DraftRecord,
} from "../career-write";
import type { PlaybookContext, StepResult, TaskPlaybook } from "../playbook";
import { planCareerNote } from "../planner";
import type { PlanStep } from "../types";
import { verifyFollowupDraft } from "../verifier";

export const NOTE_WRITE_STEP_ID = "s3";

interface NoteData {
  application?: CareerApplication;
  draft?: DraftContent;
  writeResult?: { draft: DraftRecord; created?: boolean };
  readback?: DraftRecord | null;
}

/** Pull the note text the user typed after a ":" / "that" / "saying". */
function extractNoteText(rawIntent: string): string | null {
  const colon = rawIntent.match(/:\s*(.+)$/);
  if (colon && colon[1].trim()) return colon[1].trim();
  const kw = rawIntent.match(/\b(?:that|saying|note[d]?)\s+(.+)$/i);
  if (kw && kw[1].trim()) return kw[1].trim();
  return null;
}

export const careerNotePlaybook: TaskPlaybook = {
  id: "career.add_note",
  backboneCapabilityId: "career.list_applications",

  plan(taskId, intent) {
    return planCareerNote(taskId, intent);
  },

  async runStep(step: PlanStep, ctx: PlaybookContext): Promise<StepResult> {
    const data = ctx.data as NoteData;

    if (step.id === "s1") {
      const res = await ctx.runCapability(careerListApplicationsCapability, step.id);
      if (!res.ok) {
        return { outcome: "failed", detail: res.error, fatal: { reason: "Could not retrieve applications to note against.", recovery: "Retry when the career backend is reachable." } };
      }
      const apps = (res.data as CareerApplication[]) ?? [];
      ctx.provenance.push({ capabilityId: careerListApplicationsCapability.id, executionId: res.executionId, source: res.source, fetchedAt: Date.now() });
      const target = resolveApplicationTarget(ctx.rawIntent, apps);
      if ("error" in target) return { outcome: "failed", detail: target.error, fatal: { reason: target.error } };
      data.application = target;
      return { outcome: "succeeded", detail: `Target: ${target.company} · ${target.role} (#${target.id})` };
    }

    if (step.id === "s2") {
      const app = data.application;
      if (!app) return { outcome: "failed", fatal: { reason: "No target application was resolved." } };
      const text = extractNoteText(ctx.rawIntent);
      if (!text) {
        return { outcome: "failed", fatal: { reason: 'No note text found. Say e.g. "add a note to application #17: called the recruiter".' } };
      }
      data.draft = buildNote(app, text, ctx.taskId, NOTE_WRITE_STEP_ID);
      return { outcome: "succeeded", detail: `Note: "${text.slice(0, 40)}${text.length > 40 ? "…" : ""}"` };
    }

    if (step.id === NOTE_WRITE_STEP_ID) {
      const draft = data.draft;
      if (!draft) return { outcome: "failed", fatal: { reason: "No approved note content to write." } };
      const cap = createNoteCapability(draft, { taskId: ctx.taskId, stepId: step.id });
      const res = await ctx.runCapability(cap, step.id);
      if (!res.ok) {
        return { outcome: "failed", detail: res.error, fatal: { reason: "The note could not be saved.", recovery: "The write is idempotent — retry is safe once the backend is reachable." } };
      }
      const record = res.data as DraftRecord;
      data.writeResult = { draft: record, created: record.created };
      const ev: CommandEvidence = { kind: "external_id", label: "Saved note", value: record.draftId };
      ctx.evidence.push(ev);
      return { outcome: "succeeded", detail: record.created === false ? "existing note reused (idempotent)" : "note saved" };
    }

    if (step.id === "s4") {
      const id = data.writeResult?.draft.draftId ?? data.draft?.draftId;
      if (!id) { data.readback = null; return { outcome: "failed", detail: "no note id to read back" }; }
      const cap = getFollowupDraftCapability(id);
      const res = await ctx.runCapability(cap, step.id);
      if (!res.ok) { data.readback = null; return { outcome: "failed", detail: res.error }; }
      data.readback = res.data as DraftRecord;
      return { outcome: "succeeded", detail: "read back" };
    }

    return { outcome: "skipped" };
  },

  verify(ctx) {
    const data = ctx.data as NoteData;
    return verifyFollowupDraft({
      approved: data.draft ?? null,
      readback: data.readback ?? null,
      created: data.writeResult?.created,
      noun: "Note",
    });
  },
};
