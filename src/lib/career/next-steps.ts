/**
 * Career's "Next steps" — one list where there used to be two rail panels
 * ("Next actions" and "Interview prep") that mostly listed the same
 * applications. A step is an application with a stated next action, or one in
 * an interview stage; each appears once.
 *
 * Order: dated actions first (soonest first), then interview-stage
 * applications without a date, then the rest; ties keep recency. Pure, covered
 * by `ui-p16-self-test.ts`.
 */
import type { Application, Stage } from "./types";

/** Stages where an application needs preparation, not just a reply. */
export const PREP_STAGES: readonly Stage[] = ["screening", "assessment", "interview", "final_interview"];

export interface NextStep {
  application: Application;
  /** the stated next action, if the source gives one. */
  label?: string;
  due?: string;
  /** in an interview stage. */
  prep: boolean;
}

export function nextSteps(applications: Application[], limit = 6): NextStep[] {
  const time = (iso?: string) => {
    const t = iso ? Date.parse(iso) : NaN;
    return Number.isFinite(t) ? t : Infinity;
  };
  return applications
    .map((application, index) => ({
      application,
      index,
      label: application.nextAction?.label,
      due: application.nextAction?.due,
      prep: PREP_STAGES.includes(application.stage),
    }))
    .filter((step) => step.label || step.prep)
    .sort((a, b) => time(a.due) - time(b.due) || Number(b.prep) - Number(a.prep) || a.index - b.index)
    .slice(0, limit)
    .map(({ application, label, due, prep }) => ({ application, label, due, prep }));
}
