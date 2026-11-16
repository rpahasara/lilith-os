"use client";

import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
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
    <GlassCard className="p-5">
      <PanelHeader
        title="Next actions"
        action={
          <span className="font-mono text-micro text-amber">
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
            className="flex items-center gap-3 rounded-2xl p-2"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-ink-faint" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-compact text-ink">{a.nextAction?.label}</p>
              <p className="truncate text-micro text-ink-faint">
                {a.company}
                {a.nextAction?.due && ` · due ${shortDate(a.nextAction.due)}`}
              </p>
            </div>
          </motion.li>
        ))}
      </motion.ul>
    </GlassCard>
  );
}
