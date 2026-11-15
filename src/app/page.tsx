"use client";

import { motion } from "framer-motion";
import { PresenceHero } from "@/components/presence/presence-hero";
import { TodayCard } from "@/components/home/today-card";
import { NextCard } from "@/components/home/next-card";
import { staggerContainer } from "@/lib/motion";
import { useMeetings } from "@/hooks/use-meetings";
import { useNow } from "@/hooks/use-now";
import { deriveHomeMeetings } from "@/lib/home/meetings-view";

/**
 * Home is not a dashboard — Lilith is the OS. The screen answers "what matters
 * right now?" with just TODAY and NEXT floating quietly at staggered heights so
 * they never form parallel walls around her. Everything else lives in its own
 * sidebar module. She holds the centre and the light flows around her.
 */
export default function CommandCenter() {
  // One read-only meetings fetch feeds both cards; the clock re-derives the
  // countdowns every 30 s so they never freeze. No clock yet means loading.
  const { data, loading } = useMeetings();
  const now = useNow();
  const view = now == null ? ({ kind: "loading" } as const) : deriveHomeMeetings(data, loading, now);

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="grid grid-cols-1 gap-6 py-1 xl:h-full xl:grid-cols-[260px_minmax(420px,1fr)_280px] xl:gap-10 xl:py-0"
    >
      {/* TODAY — floats near the top-left, clear of her face */}
      <div className="order-2 flex items-start justify-center xl:order-1 xl:justify-start xl:pt-12">
        <TodayCard view={view} now={now} />
      </div>

      {/* Centre — Lilith dominates */}
      <div className="order-1 min-h-[62vh] xl:order-2 xl:min-h-0">
        <PresenceHero />
      </div>

      {/* NEXT — floats lower-right, staggered against TODAY */}
      <div className="order-3 flex justify-center xl:items-end xl:justify-end xl:pb-20">
        <NextCard view={view} />
      </div>
    </motion.div>
  );
}
