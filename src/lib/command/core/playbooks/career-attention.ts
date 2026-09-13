/**
 * Career / Application Intelligence Summary playbook (Vertical Slice 2).
 *
 * Multi-endpoint read-only retrieval → deterministic entity linking →
 * evidence-based attention ranking → verification. Degrades to PARTIAL when
 * pipeline or activity is unavailable (applications remain the backbone). No
 * writes, no scraping, no new integrations.
 */
import { getCapability } from "../capabilities";
import type { CareerActivity, CareerApplication, CareerPipeline } from "../career-capabilities";
import { linkActivities, deriveAttention, verifyCareer } from "../career-analysis";
import { planCareerAttention } from "../planner";
import type { PlanStep } from "../types";
import type { PlaybookContext, StepResult, TaskPlaybook } from "../playbook";

export const careerAttentionPlaybook: TaskPlaybook = {
  id: "career.attention_summary",
  backboneCapabilityId: "career.list_applications",

  plan(taskId) {
    return planCareerAttention(taskId, "Summarise which job applications need attention");
  },

  async runStep(step: PlanStep, ctx: PlaybookContext): Promise<StepResult> {
    if (step.capabilityId === "career.list_applications") {
      const cap = getCapability("career.list_applications")!;
      const r = await ctx.runCapability(cap, step.id);
      if (ctx.isCanceled()) return { outcome: "skipped" };
      if (!r.ok) {
        return {
          outcome: "failed",
          detail: r.error,
          fatal: {
            reason:
              r.errorKind === "malformed"
                ? "The backend returned malformed application data."
                : "Could not retrieve job applications from the backend.",
            recovery: "Retry when the career backend is reachable.",
          },
        };
      }
      const apps = r.data as CareerApplication[];
      ctx.data["career.list_applications"] = apps;
      ctx.data.__appsExecId = r.executionId;
      ctx.provenance.push({ capabilityId: cap.id, executionId: r.executionId, source: r.source, fetchedAt: r.endedAt });
      return { outcome: "succeeded", detail: `${apps.length} applications` };
    }

    if (step.capabilityId === "career.get_pipeline") {
      const cap = getCapability("career.get_pipeline")!;
      const r = await ctx.runCapability(cap, step.id);
      if (ctx.isCanceled()) return { outcome: "skipped" };
      if (r.ok) {
        ctx.data["career.get_pipeline"] = r.data;
        ctx.provenance.push({ capabilityId: cap.id, executionId: r.executionId, source: r.source, fetchedAt: r.endedAt });
        return { outcome: "succeeded", detail: "pipeline snapshot" };
      }
      return { outcome: "skipped", detail: "pipeline unavailable" };
    }

    if (step.capabilityId === "career.get_activity") {
      const cap = getCapability("career.get_activity")!;
      const r = await ctx.runCapability(cap, step.id);
      if (ctx.isCanceled()) return { outcome: "skipped" };
      if (r.ok) {
        ctx.data["career.get_activity"] = r.data;
        ctx.provenance.push({ capabilityId: cap.id, executionId: r.executionId, source: r.source, fetchedAt: r.endedAt });
        return { outcome: "succeeded", detail: `${(r.data as CareerActivity[]).length} activity records` };
      }
      return { outcome: "skipped", detail: "activity unavailable" };
    }

    // Analysis steps.
    const apps = (ctx.data["career.list_applications"] as CareerApplication[]) ?? [];
    const activities = ctx.data["career.get_activity"] as CareerActivity[] | undefined;

    if (step.id === "s4") {
      if (activities == null) return { outcome: "skipped", detail: "no activity to link" };
      const link = linkActivities(apps, activities);
      const linked = apps.length ? apps.filter((a) => (link.byApp.get(a.id)?.length ?? 0) > 0).length : 0;
      return { outcome: "succeeded", detail: `${linked} linked · ${link.unlinked.length} unresolved` };
    }
    if (step.id === "s5") {
      const link = linkActivities(apps, activities ?? []);
      const attention = deriveAttention(apps, link.byApp, ctx.now);
      return { outcome: "succeeded", detail: attention.length ? `${attention.length} need attention` : "all up to date" };
    }
    return { outcome: "succeeded" };
  },

  verify(ctx: PlaybookContext) {
    return verifyCareer({
      applications: (ctx.data["career.list_applications"] as CareerApplication[]) ?? null,
      pipeline: (ctx.data["career.get_pipeline"] as CareerPipeline) ?? null,
      activities: (ctx.data["career.get_activity"] as CareerActivity[]) ?? null,
      execIds: { applications: ctx.data.__appsExecId as string | undefined },
      now: ctx.now,
    });
  },
};
