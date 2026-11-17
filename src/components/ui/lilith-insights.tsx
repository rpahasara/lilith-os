"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Info, Sparkles, TrendingUp } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { riseIn, staggerContainer } from "@/lib/motion";

/** One observation from Lilith about a workspace. Career and Automations share it. */
export interface LilithInsight {
  id: string;
  title: string;
  detail: string;
  tone: "opportunity" | "risk" | "info";
}

const TONE = {
  opportunity: { icon: TrendingUp, color: "text-green", ring: "bg-green/12" },
  risk: { icon: AlertTriangle, color: "text-amber", ring: "bg-amber/12" },
  info: { icon: Info, color: "text-cyan-bright", ring: "bg-cyan-bright/12" },
} as const;

/**
 * "Lilith insights" — the one rail panel for what Lilith noticed about a
 * workspace. Previously copied per page; now one component, one treatment.
 */
export function LilithInsights({ insights, empty = "Nothing to point out right now." }: { insights: LilithInsight[]; empty?: string }) {
  return (
    <GlassCard strong className="p-5">
      <PanelHeader
        title="Lilith insights"
        action={
          <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-orchid-bright/30 to-cyan-bright/20">
            <Sparkles className="h-3.5 w-3.5 text-orchid-bright" />
          </span>
        }
      />
      {insights.length === 0 ? (
        <p className="mt-4 text-xs text-ink-faint">{empty}</p>
      ) : (
        <motion.ul variants={staggerContainer} initial="hidden" animate="show" className="mt-4 space-y-3">
          {insights.map((insight) => {
            const tone = TONE[insight.tone] ?? TONE.info;
            const Icon = tone.icon;
            return (
              <motion.li key={insight.id} variants={riseIn} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
                <div className="flex items-start gap-2.5">
                  <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-xl ${tone.ring}`}>
                    <Icon className={`h-3.5 w-3.5 ${tone.color}`} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-compact font-medium leading-snug text-ink">{insight.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-muted">{insight.detail}</p>
                  </div>
                </div>
              </motion.li>
            );
          })}
        </motion.ul>
      )}
    </GlassCard>
  );
}
