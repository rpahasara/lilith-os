"use client";

import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Info } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { AutomationEvent } from "@/lib/automations/types";
import { timeAgo } from "@/lib/utils";
import { staggerContainer, riseIn } from "@/lib/motion";

const OUTCOME: Record<string, { icon: LucideIcon; color: string }> = {
  success: { icon: CheckCircle2, color: "text-green" },
  failure: { icon: XCircle, color: "text-rose" },
  skip: { icon: Info, color: "text-ink-faint" },
  info: { icon: Info, color: "text-cyan-bright" },
};

export function ExecutionTimeline({ activity }: { activity: AutomationEvent[] }) {
  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Execution timeline"
        action={
          <button className="font-mono text-[10px] text-ink-faint transition-colors hover:text-ink-muted">
            VIEW ALL
          </button>
        }
      />

      {activity.length === 0 ? (
        <p className="mt-4 text-sm text-ink-faint">No recent executions.</p>
      ) : (
        <motion.ol
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="relative mt-4 space-y-4 before:absolute before:left-[15px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-white/[0.07]"
        >
          {activity.map((e) => {
            const o = OUTCOME[e.outcome] ?? OUTCOME.info;
            const Icon = o.icon;
            return (
              <motion.li key={e.id} variants={riseIn} className="relative flex gap-3">
                <span className="relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-base-2 ring-1 ring-white/10">
                  <Icon className={`h-4 w-4 ${o.color}`} />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <p className="text-[13px] leading-snug text-ink-muted">
                    <span className="text-ink">{e.unit}</span> — {e.text}
                  </p>
                  <p className="mt-0.5 font-mono text-[10px] text-ink-faint">
                    {timeAgo(e.time)}
                  </p>
                </div>
              </motion.li>
            );
          })}
        </motion.ol>
      )}
    </GlassCard>
  );
}
