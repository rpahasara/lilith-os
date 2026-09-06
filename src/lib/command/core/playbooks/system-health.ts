/**
 * System & Automation Health Summary playbook (Cognitive Core Vertical Slice 1),
 * ported onto the shared playbook engine. Behaviour is unchanged from Slice 1.
 */
import { getCapability, type OsOverview, type SystemStatus } from "../capabilities";
import { planSystemHealth } from "../planner";
import { verifySystemHealth } from "../verifier";
import type { PlanStep } from "../types";
import type { PlaybookContext, StepResult, TaskPlaybook } from "../playbook";
import { isUnitUnhealthy } from "../capabilities";

export const systemHealthPlaybook: TaskPlaybook = {
  id: "system.health_summary",
  backboneCapabilityId: "system.get_status",

  plan(taskId) {
    return planSystemHealth(taskId, "Summarise the health of LILITH's backend services");
  },

  async runStep(step: PlanStep, ctx: PlaybookContext): Promise<StepResult> {
    if (step.capabilityId === "os.get_overview") {
      const cap = getCapability("os.get_overview")!;
      const r = await ctx.runCapability(cap, step.id);
      if (ctx.isCanceled()) return { outcome: "skipped" };
      if (r.ok) {
        ctx.data["os.get_overview"] = r.data;
        ctx.provenance.push({ capabilityId: cap.id, executionId: r.executionId, source: r.source, fetchedAt: r.endedAt });
        return { outcome: "succeeded", detail: `LILITH ${(r.data as OsOverview).lilithStatus}` };
      }
      // Overview is context, not the backbone — degrade and continue.
      return { outcome: "skipped", detail: "overview unavailable" };
    }

    if (step.capabilityId === "system.get_status") {
      const cap = getCapability("system.get_status")!;
      const r = await ctx.runCapability(cap, step.id);
      if (ctx.isCanceled()) return { outcome: "skipped" };
      if (!r.ok) {
        return {
          outcome: "failed",
          detail: r.error,
          fatal: {
            reason:
              r.errorKind === "malformed"
                ? "The backend returned a malformed system status response."
                : "Could not retrieve system status from the control backend.",
            recovery: "Retry when the backend is healthy.",
          },
        };
      }
      const status = r.data as SystemStatus;
      ctx.data["system.get_status"] = status;
      ctx.data.__statusExecId = r.executionId;
      ctx.provenance.push({ capabilityId: cap.id, executionId: r.executionId, source: r.source, fetchedAt: r.endedAt });
      return { outcome: "succeeded", detail: `${status.units.length} units` };
    }

    // Analysis steps.
    if (step.id === "s3") {
      const status = ctx.data["system.get_status"] as SystemStatus | undefined;
      if (status) {
        const unhealthy = status.units.filter(isUnitUnhealthy).length;
        return { outcome: "succeeded", detail: unhealthy === 0 ? "all healthy" : `${unhealthy} need attention` };
      }
    }
    return { outcome: "succeeded" };
  },

  verify(ctx: PlaybookContext) {
    return verifySystemHealth({
      status: (ctx.data["system.get_status"] as SystemStatus) ?? null,
      overview: (ctx.data["os.get_overview"] as OsOverview) ?? null,
      statusExecutionId: ctx.data.__statusExecId as string | undefined,
    });
  },
};
