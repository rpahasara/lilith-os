"use client";

import { motion } from "framer-motion";
import { Brain } from "lucide-react";
import type { MemoryOverview } from "@/lib/memory/types";
import type { Diagnostics } from "@/lib/api";
import { staggerContainer } from "@/lib/motion";
import { MetricTile, WorkspaceHeader } from "@/components/ui/primitives";

export function MemoryHeader({
  overview,
  isDemo,
  diagnostics,
}: {
  overview: MemoryOverview;
  isDemo: boolean;
  diagnostics?: Diagnostics;
}) {
  return (
    <div>
      <WorkspaceHeader icon={Brain} eyebrow="Cognitive archive" title="Memory" description="Lilith's living knowledge — what she knows about your people, work, and world." isDemo={isDemo} diagnostics={diagnostics} />

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <MetricTile label="Memories" value={overview.total} accent="cyan" />
        <MetricTile label="Learned · 7d" value={overview.recentlyLearned} accent="wine" />
        <MetricTile label="Pinned" value={overview.pinned} accent="gold" />
        <MetricTile label="Entities" value={overview.entities} accent="cyan" />
        <MetricTile label="Avg confidence" value={overview.avgConfidence} suffix="/100" accent="green" />
      </motion.div>
    </div>
  );
}
