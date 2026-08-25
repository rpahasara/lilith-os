"use client";

import { motion } from "framer-motion";
import { CheckCircle2, ChevronRight } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { Application } from "@/lib/career/types";
import { shortDate } from "@/lib/utils";
import { staggerContainer, riseIn } from "@/lib/motion";

export function NextActions({ applications }: { applications: Application[] }) {
  const actions = applications
    .filter((a) => a.nextAction)
    .sort((a, b) => {
      const da = a.nextAction?.due ? new Date(a.nextAction.due).getTime() : Infinity;
      const db = b.nextAction?.due ? new Date(b.nextAction.due).getTime() : Infinity;
      return da - db;
    })
    .slice(0, 5);

  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Next actions"
        action={
          <span className="font-mono text-[10px] text-amber">
            {applications.filter((a) => a.followUp).length} follow-ups
          </span>
        }
      />

      <motion.ul
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 space-y-1"
      >
        {actions.map((a) => (
          <motion.li
            key={a.id}
            variants={riseIn}
            className="group flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-white/[0.03]"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-ink-faint transition-colors group-hover:text-green" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] text-ink">{a.nextAction?.label}</p>
              <p className="truncate text-[11px] text-ink-faint">
                {a.company}
                {a.nextAction?.due && ` · due ${shortDate(a.nextAction.due)}`}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" />
          </motion.li>
        ))}
      </motion.ul>
    </GlassCard>
  );
}
