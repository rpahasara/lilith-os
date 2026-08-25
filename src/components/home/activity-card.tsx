"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader, accentText } from "@/components/ui/primitives";
import { activity } from "@/lib/data";
import { staggerContainer, riseIn } from "@/lib/motion";

export function ActivityCard() {
  return (
    <GlassCard className="flex min-h-0 flex-1 flex-col p-5">
      <PanelHeader
        title="Recent activity"
        action={
          <button className="font-mono text-[10px] text-ink-faint transition-colors hover:text-ink-muted">
            VIEW ALL
          </button>
        }
      />

      <motion.ul
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="scroll-area mt-4 -mr-2 space-y-1 overflow-y-auto pr-2"
      >
        {activity.map((a, i) => {
          const Icon = a.icon;
          return (
            <motion.li
              key={i}
              variants={riseIn}
              className="group flex items-start gap-3 rounded-xl p-2 transition-colors hover:bg-white/[0.03]"
            >
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/[0.04] hairline">
                <Icon className={`h-4 w-4 ${accentText[a.accent]}`} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] leading-snug text-ink-muted group-hover:text-ink">
                  {a.text}
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-ink-faint">
                  {a.time} ago
                </p>
              </div>
            </motion.li>
          );
        })}
      </motion.ul>
    </GlassCard>
  );
}
