"use client";

import { motion } from "framer-motion";
import { Cpu } from "lucide-react";
import type { AutomationHealth } from "@/lib/automations/types";
import type { Diagnostics } from "@/lib/api";
import { staggerContainer } from "@/lib/motion";
import { MetricTile, WorkspaceHeader } from "@/components/ui/primitives";

export function AutomationsHeader({
  health,
  isDemo,
  diagnostics,
}: {
  health: AutomationHealth;
  isDemo: boolean;
  diagnostics?: Diagnostics;
}) {
  return (
    <div>
      <WorkspaceHeader icon={Cpu} eyebrow="Agent fabric" title="Autonomous Operations" description="Lilith's background agents, watchers, and services — live." isDemo={isDemo} diagnostics={diagnostics} />

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <MetricTile label="Health" value={health.score} suffix="/100" accent={health.failed ? "amber" : "green"} />
        <MetricTile label="Running" value={health.running} accent="green" />
        <MetricTile label="Active" value={health.active} accent="cyan" />
        <MetricTile label="Waiting" value={health.waiting} accent="faint" />
        <MetricTile label="Failed" value={health.failed} accent={health.failed ? "rose" : "faint"} />
      </motion.div>
    </div>
  );
}
