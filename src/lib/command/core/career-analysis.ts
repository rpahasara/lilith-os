/**
 * Career analysis — pure, deterministic. Entity linking, a small evidence-based
 * attention model (NOT ML), discrepancy detection, and verification. Every
 * finding carries a reason code + evidence refs so "why does this need
 * attention?" is always answerable. No fuzzy guessing: activities link only by
 * the explicit application_id join key; anything else is marked unresolved.
 */
import { STAGES, TERMINAL_STAGES } from "@/lib/career/types";
import type { CommandEvidence } from "../types";
import type { VerifierResult } from "./types";
import type { CareerActivity, CareerApplication, CareerPipeline } from "./career-capabilities";

const IDLE_MEDIUM_DAYS = 5;
const IDLE_HIGH_DAYS = 10;
const DAY = 86_400_000;

const STAGE_ORDER = new Map<string, number>(STAGES.map((s, i) => [s, i]));
const TERMINAL = new Set<string>(TERMINAL_STAGES);

export type Priority = "high" | "medium" | "low";
const PRIORITY_RANK: Record<Priority, number> = { low: 0, medium: 1, high: 2 };

export interface AttentionItem {
  applicationId: number;
  role: string;
  company: string;
  priority: Priority;
  reason: string;
  reasons: string[];
  explanation: string;
  idleDays: number | null;
  confidence: number;
  evidenceRefs: string[];
}

export interface Discrepancy {
  code: string;
  detail: string;
  evidenceRefs: string[];
}

export interface CareerSummaryCounts {
  activeApplications: number;
  needsAttention: number;
  interviews: number;
  offers: number;
  total: number;
}

/** Parse the backend's TZ-less "YYYY-MM-DD HH:MM:SS" to epoch ms (day-grain). */
export function parseTs(s?: string): number | null {
  if (!s) return null;
  const t = Date.parse(s.includes("T") ? s : s.replace(" ", "T"));
  return Number.isFinite(t) ? t : null;
}

export interface LinkResult {
  byApp: Map<number, CareerActivity[]>;
  unlinked: CareerActivity[];
}

/** Link activities to applications strictly by application_id. */
export function linkActivities(apps: CareerApplication[], activities: CareerActivity[]): LinkResult {
  const ids = new Set(apps.map((a) => a.id));
  const byApp = new Map<number, CareerActivity[]>();
  const unlinked: CareerActivity[] = [];
  for (const act of activities) {
    if (act.applicationId != null && ids.has(act.applicationId)) {
      const list = byApp.get(act.applicationId) ?? [];
      list.push(act);
      byApp.set(act.applicationId, list);
    } else {
      unlinked.push(act);
    }
  }
  // newest first within each app
  for (const list of byApp.values()) {
    list.sort((a, b) => (parseTs(b.occurredAt) ?? 0) - (parseTs(a.occurredAt) ?? 0));
  }
  return { byApp, unlinked };
}

export function summaryCounts(apps: CareerApplication[]): CareerSummaryCounts {
  const active = apps.filter((a) => !TERMINAL.has(a.stage));
  return {
    total: apps.length,
    activeApplications: active.length,
    needsAttention: 0, // filled by caller
    interviews: apps.filter((a) => ["interview", "final_interview"].includes(a.stage)).length,
    offers: apps.filter((a) => a.stage === "offer").length,
  };
}

/** Derive attention candidates from evidence only. */
export function deriveAttention(
  apps: CareerApplication[],
  byApp: Map<number, CareerActivity[]>,
  now: number,
): AttentionItem[] {
  const items: AttentionItem[] = [];

  for (const app of apps) {
    if (TERMINAL.has(app.stage)) continue;

    const reasons: string[] = [];
    let priority: Priority = "low";
    const bump = (p: Priority) => {
      if (PRIORITY_RANK[p] > PRIORITY_RANK[priority]) priority = p;
    };
    const evidenceRefs: string[] = [`application:${app.id}`, `stage:${app.stage}`];

    const lastTs = parseTs(app.lastActivity);
    const idleDays = lastTs != null ? Math.floor((now - lastTs) / DAY) : null;
    if (app.lastActivity) evidenceRefs.push(`lastActivity:${app.lastActivity}`);

    // needs_decision: surfaced but not yet applied.
    if (app.stage === "discovered") {
      reasons.push("needs_decision");
      bump("medium");
    }

    // idle_stale: no movement for a while (active stages only).
    if (idleDays != null && idleDays >= IDLE_MEDIUM_DAYS) {
      reasons.push("idle_stale");
      bump(idleDays >= IDLE_HIGH_DAYS ? "high" : "medium");
    }

    // stage_activity_mismatch: latest linked activity is ahead of the record.
    const latest = byApp.get(app.id)?.[0];
    if (latest) {
      evidenceRefs.push(`activity:${latest.id}`);
      const actStage = latest.activityType;
      if (TERMINAL.has(actStage) && !TERMINAL.has(app.stage)) {
        reasons.push("stage_activity_mismatch");
        bump("high");
      } else {
        const ao = STAGE_ORDER.get(actStage);
        const so = STAGE_ORDER.get(app.stage);
        if (ao != null && so != null && ao > so) {
          reasons.push("stage_activity_mismatch");
          bump("high");
        }
      }
    }

    if (reasons.length === 0) continue;

    const primary = reasons.includes("stage_activity_mismatch")
      ? "stage_activity_mismatch"
      : reasons.includes("idle_stale")
        ? "idle_stale"
        : reasons[0];

    const explanation =
      primary === "idle_stale"
        ? `No activity for ${idleDays} days`
        : primary === "needs_decision"
          ? "Surfaced but not yet applied"
          : primary === "stage_activity_mismatch"
            ? `Latest activity (${latest?.activityType}) is ahead of recorded stage (${app.stage})`
            : "Needs review";

    items.push({
      applicationId: app.id,
      role: app.role,
      company: app.company,
      priority,
      reason: primary,
      reasons,
      explanation,
      idleDays,
      confidence: Math.min(1, Math.max(0, app.confidence || 0)),
      evidenceRefs,
    });
  }

  items.sort((a, b) => {
    const p = PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority];
    if (p !== 0) return p;
    return (b.idleDays ?? 0) - (a.idleDays ?? 0);
  });
  return items;
}

/** Detect real data conflicts. Surfaced as evidence, never silently fixed. */
export function detectDiscrepancies(
  apps: CareerApplication[],
  pipeline: CareerPipeline | null,
  link: LinkResult,
): Discrepancy[] {
  const out: Discrepancy[] = [];

  // duplicate application ids
  const seen = new Map<number, number>();
  for (const a of apps) seen.set(a.id, (seen.get(a.id) ?? 0) + 1);
  for (const [id, n] of seen) {
    if (n > 1) out.push({ code: "duplicate_application", detail: `application #${id} appears ${n} times`, evidenceRefs: [`application:${id}`] });
  }

  // pipeline vs applications per stage
  if (pipeline) {
    const counts = new Map<string, number>();
    for (const a of apps) counts.set(a.stage, (counts.get(a.stage) ?? 0) + 1);
    const stages = new Set<string>([...Object.keys(pipeline), ...counts.keys()]);
    for (const stage of stages) {
      const p = pipeline[stage] ?? 0;
      const c = counts.get(stage) ?? 0;
      if (p !== c) {
        out.push({
          code: "pipeline_mismatch",
          detail: `stage "${stage}": pipeline=${p}, applications=${c}`,
          evidenceRefs: [`pipeline:${stage}`],
        });
      }
    }
  }

  // activities referencing a missing/unknown application
  if (link.unlinked.length > 0) {
    out.push({
      code: "unlinked_activity",
      detail: `${link.unlinked.length} activity record(s) could not be linked to an application`,
      evidenceRefs: link.unlinked.slice(0, 5).map((a) => `activity:${a.id}`),
    });
  }

  return out;
}

/* ---------------------------------------------------------------- verifier */

export interface CareerVerifyInput {
  applications: CareerApplication[] | null;
  pipeline: CareerPipeline | null;
  activities: CareerActivity[] | null;
  execIds: { applications?: string; pipeline?: string; activity?: string };
  now?: number;
}

export function verifyCareer(input: CareerVerifyInput): VerifierResult {
  const now = input.now ?? Date.now();
  const apps = input.applications;

  if (!apps) {
    return {
      verdict: "FAIL",
      summary: "Could not retrieve job applications from the backend.",
      evidence: [],
      unresolved: ["Applications were unavailable or malformed."],
      recovery: "Retry when the career backend is reachable.",
    };
  }

  const activities = input.activities ?? [];
  const link = linkActivities(apps, activities);
  const attention = deriveAttention(apps, link.byApp, now);
  const discrepancies = detectDiscrepancies(apps, input.pipeline, link);
  const counts = summaryCounts(apps);
  counts.needsAttention = attention.length;

  const evidence: CommandEvidence[] = [
    { kind: "observed_state", label: "Applications", value: String(counts.total) },
    { kind: "observed_state", label: "Active", value: String(counts.activeApplications) },
    { kind: "observed_state", label: "Need attention", value: String(counts.needsAttention) },
  ];
  if (counts.interviews) evidence.push({ kind: "observed_state", label: "Interviews", value: String(counts.interviews) });
  if (counts.offers) evidence.push({ kind: "observed_state", label: "Offers", value: String(counts.offers) });
  if (input.execIds.applications) evidence.push({ kind: "external_id", label: "career.list_applications", value: input.execIds.applications });

  // top attention items as evidence (traceable to applicationId)
  for (const it of attention.slice(0, 5)) {
    evidence.push({
      kind: "artifact",
      label: `${it.role} — ${it.company}`,
      value: `${it.priority} · ${it.explanation} (app #${it.applicationId})`,
    });
  }
  for (const d of discrepancies) {
    evidence.push({ kind: "error_detail", label: d.code, value: d.detail });
  }

  // unresolved: the human "still needs you" list.
  const unresolved: string[] = attention.map(
    (it) => `${it.role} @ ${it.company} — ${it.explanation} [${it.priority}] (app #${it.applicationId})`,
  );

  const headline =
    counts.total === 0
      ? "No job applications are being tracked yet."
      : counts.needsAttention === 0
        ? `All ${counts.activeApplications} active applications look up to date.`
        : `${counts.needsAttention} application${counts.needsAttention === 1 ? "" : "s"} need attention · ${counts.activeApplications} active.`;

  // PARTIAL when context is incomplete: activity dataset missing, pipeline
  // missing, or some activities could not be linked.
  const activityMissing = input.activities == null;
  const pipelineMissing = input.pipeline == null;
  if (activityMissing || pipelineMissing || link.unlinked.length > 0) {
    const limits: string[] = [];
    if (activityMissing) limits.push("Recent activity was unavailable — attention is based on application records only.");
    if (pipelineMissing) limits.push("Pipeline snapshot was unavailable — counts could not be cross-checked.");
    if (link.unlinked.length > 0) limits.push(`${link.unlinked.length} activity record(s) could not be linked to an application.`);
    return {
      verdict: "PARTIAL",
      summary: headline,
      evidence,
      unresolved: [...unresolved, ...limits],
      recovery: "Retry to refresh the missing data.",
    };
  }

  return { verdict: "PASS", summary: headline, evidence, unresolved };
}
