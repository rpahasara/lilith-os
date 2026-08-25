"use client";

import { motion } from "framer-motion";
import {
  GitBranch,
  UserRound,
  Sparkles,
  CheckCircle2,
  Cpu,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { ActivityEvent } from "@/lib/career/types";
import { timeAgo } from "@/lib/utils";
import { staggerContainer, riseIn } from "@/lib/motion";

const KIND: Record<ActivityEvent["kind"], { icon: LucideIcon; color: string }> = {
  stage: { icon: GitBranch, color: "text-violet-bright" },
  recruiter: { icon: UserRound, color: "text-cyan-bright" },
  insight: { icon: Sparkles, color: "text-violet-bright" },
  action: { icon: CheckCircle2, color: "text-amber" },
  system: { icon: Cpu, color: "text-cyan-bright" },
};

export function ActivityTimeline({ activity }: { activity: ActivityEvent[] }) {
  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Career activity"
        action={
          <button className="font-mono text-[10px] text-ink-faint transition-colors hover:text-ink-muted">
            VIEW ALL
          </button>
        }
      />

      <motion.ol
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="relative mt-4 space-y-4 before:absolute before:left-[15px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-white/[0.07]"
      >
        {activity.map((e) => {
          const k = KIND[e.kind] ?? KIND.system;
          const Icon = k.icon;
          return (
            <motion.li key={e.id} variants={riseIn} className="relative flex gap-3">
              <span className="relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-base-2 ring-1 ring-white/10">
                <Icon className={`h-4 w-4 ${k.color}`} />
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <p className="text-[13px] leading-snug text-ink-muted">{e.text}</p>
                <p className="mt-0.5 font-mono text-[10px] text-ink-faint">
                  {e.company ? `${e.company} · ` : ""}
                  {timeAgo(e.time)}
                </p>
              </div>
            </motion.li>
          );
        })}
      </motion.ol>
    </GlassCard>
  );
}
