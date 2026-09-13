"use client";

import { motion } from "framer-motion";
import { CalendarDays, Flag, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { brief, pipeline } from "@/lib/data";
import { staggerContainer, riseIn } from "@/lib/motion";

const ICONS: LucideIcon[] = [CalendarDays, Flag, Target];

/**
 * TODAY — the single "what matters today" glass object. Consolidates the old
 * Morning Brief + Focus into one calm surface: meetings, one key deadline, and
 * the current focus recommendation. Full module dashboards live in the sidebar.
 */
export function TodayCard() {
  return (
    <GlassCard panel interactive className="w-full max-w-[284px] px-4 py-4">
      <span className="pointer-events-none absolute inset-y-5 left-0 w-px bg-gradient-to-b from-transparent via-wine-bright/55 to-transparent" />
      <div className="flex items-center justify-between">
        <span className="eyebrow text-ink">Today</span>
        <span className="font-mono text-[10px] text-gold/85">
          Focus {pipeline.focusScore}
        </span>
      </div>

      <motion.ul
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-3 space-y-2"
      >
        {brief.map((b, i) => {
          const Icon = ICONS[i] ?? CalendarDays;
          return (
            <motion.li
              key={b.text}
              variants={riseIn}
              className="flex items-center gap-2.5"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-wine/15 bg-wine/[0.12] text-wine-bright shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]">
                <Icon className="h-3 w-3" />
              </span>
              <div className="min-w-0 leading-tight">
                <span className="text-[13px] text-ink">{b.text}</span>
                <span className="ml-1.5 text-[11px] text-ink-faint">{b.meta}</span>
              </div>
            </motion.li>
          );
        })}
      </motion.ul>
    </GlassCard>
  );
}
