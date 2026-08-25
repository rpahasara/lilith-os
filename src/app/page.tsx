"use client";

import { motion } from "framer-motion";
import { PresenceHero } from "@/components/presence/presence-hero";
import { BriefCard } from "@/components/home/brief-card";
import { FocusCard } from "@/components/home/focus-card";
import { ActivityCard } from "@/components/home/activity-card";
import { NextEventCard } from "@/components/home/next-event-card";
import { MemoryCard } from "@/components/home/memory-card";
import { AutomationsCard } from "@/components/home/automations-card";
import { staggerContainer } from "@/lib/motion";

export default function CommandCenter() {
  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="grid grid-cols-1 gap-4 py-1 lg:h-full lg:grid-cols-[320px_1fr_340px] lg:py-0"
    >
      {/* left intelligence stack */}
      <div className="scroll-area order-2 flex min-h-0 flex-col gap-4 pb-2 lg:order-1 lg:overflow-y-auto lg:pr-1">
        <BriefCard />
        <FocusCard />
        <ActivityCard />
      </div>

      {/* center — the presence */}
      <div className="order-1 min-h-[68vh] lg:order-2 lg:min-h-0">
        <PresenceHero />
      </div>

      {/* right context stack */}
      <div className="scroll-area order-3 flex min-h-0 flex-col gap-4 pb-2 lg:overflow-y-auto lg:pr-1">
        <NextEventCard />
        <MemoryCard />
        <AutomationsCard />
      </div>
    </motion.div>
  );
}
