"use client";

import { motion } from "framer-motion";
import { Sparkles, TrendingUp, AlertTriangle, Info } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { AutomationInsight } from "@/lib/automations/types";
import { staggerContainer, riseIn } from "@/lib/motion";

const TONE = {
  opportunity: { icon: TrendingUp, color: "text-green", ring: "bg-green/12" },
  risk: { icon: AlertTriangle, color: "text-amber", ring: "bg-amber/12" },
  info: { icon: Info, color: "text-cyan-bright", ring: "bg-cyan-bright/12" },
} as const;

export function OpsInsights({ insights }: { insights: AutomationInsight[] }) {
  return (
    <GlassCard strong className="p-5" interactive>
      <PanelHeader
        title="Lilith insights"
        action={
          <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-violet-bright/30 to-cyan-bright/20">
            <Sparkles className="h-3.5 w-3.5 text-violet-bright" />
          </span>
        }
      />
      <motion.ul
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 space-y-3"
      >
        {insights.map((ins) => {
          const tone = TONE[ins.tone];
          const Icon = tone.icon;
          return (
            <motion.li
              key={ins.id}
              variants={riseIn}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3"
            >
              <div className="flex items-start gap-2.5">
                <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg ${tone.ring}`}>
                  <Icon className={`h-3.5 w-3.5 ${tone.color}`} />
                </span>
                <div className="min-w-0">
                  <p className="text-[13px] font-medium leading-snug text-ink">{ins.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-ink-muted">{ins.detail}</p>
                </div>
              </div>
            </motion.li>
          );
        })}
      </motion.ul>
    </GlassCard>
  );
}
