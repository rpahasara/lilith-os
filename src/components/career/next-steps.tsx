"use client";

import { motion } from "framer-motion";
import { ArrowRight, CalendarClock, GraduationCap } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { Application } from "@/lib/career/types";
import { nextSteps } from "@/lib/career/next-steps";
import { riseIn, staggerContainer } from "@/lib/motion";
import { cn, shortDate } from "@/lib/utils";
import { StageBadge } from "./stage-badge";

/**
 * What to do next, in one list: stated next actions and applications in an
 * interview stage (they were two panels that repeated each other). Each step
 * opens its application.
 */
export function NextSteps({ applications, selectedId, onSelect }: { applications: Application[]; selectedId?: string; onSelect: (application: Application) => void }) {
  const steps = nextSteps(applications);
  const followUps = applications.filter((a) => a.followUp).length;

  return (
    <GlassCard className="p-5">
      <PanelHeader
        title="Next steps"
        action={followUps > 0 ? <span className="font-mono text-micro text-amber">{followUps} follow-up{followUps === 1 ? "" : "s"}</span> : undefined}
      />
      {steps.length === 0 ? (
        <p className="mt-4 text-xs text-ink-faint">Nothing is waiting on you.</p>
      ) : (
        <motion.ul variants={staggerContainer} initial="hidden" animate="show" className="-mx-2 mt-3 space-y-0.5">
          {steps.map(({ application, label, due, prep }) => (
            <motion.li key={application.id} variants={riseIn}>
              <button
                type="button"
                onClick={() => onSelect(application)}
                aria-pressed={selectedId === application.id}
                className={cn(
                  "group flex w-full items-start gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-white/[0.04]",
                  selectedId === application.id && "bg-white/[0.05]",
                )}
              >
                <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-white/[0.04]">
                  {prep ? <GraduationCap className="h-3.5 w-3.5 text-orchid-bright" /> : <CalendarClock className="h-3.5 w-3.5 text-ink-faint" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-compact text-ink">{label ?? "Prepare for the next round"}</span>
                  <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-micro text-ink-faint">
                    <span className="truncate">{application.company}</span>
                    {due && <span className="shrink-0">· due {shortDate(due)}</span>}
                  </span>
                </span>
                {prep ? <StageBadge stage={application.stage} /> : <ArrowRight className="mt-1 h-3 w-3 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />}
              </button>
            </motion.li>
          ))}
        </motion.ul>
      )}
    </GlassCard>
  );
}
