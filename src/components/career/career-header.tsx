"use client";

import { motion } from "framer-motion";
import { Briefcase } from "lucide-react";
import type { CareerOverview } from "@/lib/career/types";
import type { Diagnostics } from "@/lib/api";
import { staggerContainer } from "@/lib/motion";
import { MetricTile, WorkspaceHeader } from "@/components/ui/primitives";

export function CareerHeader({
  overview,
  isDemo,
  diagnostics,
}: {
  overview: CareerOverview;
  isDemo: boolean;
  diagnostics?: Diagnostics;
}) {
  return (
    <div>
      <WorkspaceHeader icon={Briefcase} eyebrow="Opportunity field" title="Career Intelligence" description="Lilith is tracking your opportunities and moving the pipeline forward." isDemo={isDemo} diagnostics={diagnostics} />

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <MetricTile label="Active" value={overview.totalActive} accent="cyan" />
        <MetricTile label="Interviews" value={overview.interviews} accent="wine" />
        <MetricTile label="Offers" value={overview.offers} accent="green" />
        <MetricTile label="Response rate" value={overview.responseRate} suffix="%" accent="cyan" />
        <MetricTile label="Pipeline health" value={overview.pipelineHealth} suffix="/100" accent="orchid" />
      </motion.div>
    </div>
  );
}
