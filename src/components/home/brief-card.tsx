"use client";

import { motion } from "framer-motion";
import { Sun, ChevronRight } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader, accentBg } from "@/components/ui/primitives";
import { brief } from "@/lib/data";
import { staggerContainer, riseIn } from "@/lib/motion";

export function BriefCard() {
  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Morning brief"
        action={
          <span className="grid h-7 w-7 place-items-center rounded-full bg-amber/10 text-amber">
            <Sun className="h-3.5 w-3.5" />
          </span>
        }
      />

      <motion.ul
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 space-y-3"
      >
        {brief.map((b) => (
          <motion.li
            key={b.text}
            variants={riseIn}
            className="flex items-start gap-3"
          >
            <span
              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${accentBg[b.accent]}`}
            />
            <div className="min-w-0">
              <p className="text-sm leading-tight text-ink">{b.text}</p>
              <p className="mt-0.5 text-xs text-ink-faint">{b.meta}</p>
            </div>
          </motion.li>
        ))}
      </motion.ul>

      <button className="mt-4 flex w-full items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-xs text-ink-muted transition-colors hover:border-white/15 hover:text-ink">
        Open full brief
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </GlassCard>
  );
}
