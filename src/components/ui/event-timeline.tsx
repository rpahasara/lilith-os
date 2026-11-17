"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { riseIn, staggerContainer } from "@/lib/motion";

/** One line on a timeline: what happened, and when (already formatted). */
export interface TimelineItem {
  id: string;
  icon: LucideIcon;
  /** text colour class for the icon, e.g. "text-green". */
  color: string;
  text: ReactNode;
  meta: string;
}

/**
 * A vertical event timeline — one component for Career activity and the
 * Automations execution log, which were the same markup copied twice.
 */
export function EventTimeline({ title, items, empty }: { title: string; items: TimelineItem[]; empty: string }) {
  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader title={title} />
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-ink-faint">{empty}</p>
      ) : (
        <motion.ol
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="relative mt-4 space-y-4 before:absolute before:left-[15px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-white/[0.07]"
        >
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <motion.li key={item.id} variants={riseIn} className="relative flex gap-3">
                <span className="relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-base-2 ring-1 ring-white/10">
                  <Icon className={`h-4 w-4 ${item.color}`} />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <p className="text-compact leading-snug text-ink-muted">{item.text}</p>
                  <p className="mt-0.5 font-mono text-micro text-ink-faint">{item.meta}</p>
                </div>
              </motion.li>
            );
          })}
        </motion.ol>
      )}
    </GlassCard>
  );
}
