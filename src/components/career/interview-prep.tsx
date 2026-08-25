"use client";

import { GraduationCap, Sparkles } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { StageBadge } from "./stage-badge";
import type { Application } from "@/lib/career/types";
import { shortDate } from "@/lib/utils";

const PREP_STAGES = ["screening", "assessment", "interview", "final_interview"];

export function InterviewPrep({ applications }: { applications: Application[] }) {
  const upcoming = applications
    .filter((a) => PREP_STAGES.includes(a.stage))
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 4);

  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Interview prep"
        action={
          <span className="grid h-7 w-7 place-items-center rounded-full bg-violet-bright/12">
            <GraduationCap className="h-3.5 w-3.5 text-violet-bright" />
          </span>
        }
      />

      {upcoming.length === 0 ? (
        <p className="mt-4 text-sm text-ink-faint">No interviews in progress.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {upcoming.map((a) => (
            <li
              key={a.id}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-medium text-ink">
                    {a.company}
                  </p>
                  <p className="truncate text-[11px] text-ink-faint">{a.role}</p>
                </div>
                <StageBadge stage={a.stage} />
              </div>
              {a.nextAction?.due && (
                <p className="mt-2 text-[11px] text-ink-muted">
                  Next: {a.nextAction.label} · {shortDate(a.nextAction.due)}
                </p>
              )}
              <button className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-b from-violet-bright/20 to-violet-deep/20 py-1.5 text-xs font-medium text-violet-bright transition-colors hover:from-violet-bright/30 hover:to-violet-deep/30">
                <Sparkles className="h-3 w-3" /> Prep with Lilith
              </button>
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}
