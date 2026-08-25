"use client";

import { motion } from "framer-motion";
import { Brain } from "lucide-react";
import type { MemoryOverview } from "@/lib/memory/types";
import type { Diagnostics } from "@/lib/api";
import { staggerContainer, riseIn } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { ConnectionStatus } from "@/components/ui/connection-status";

function Tile({
  label,
  value,
  suffix,
  accent = "cyan",
}: {
  label: string;
  value: string | number;
  suffix?: string;
  accent?: "violet" | "cyan" | "green" | "amber";
}) {
  const color = {
    violet: "text-violet-bright",
    cyan: "text-cyan-bright",
    green: "text-green",
    amber: "text-amber",
  }[accent];
  return (
    <motion.div variants={riseIn} className="glass rounded-[var(--radius-md)] px-4 py-3">
      <p className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">{label}</p>
      <p className="mt-1 flex items-baseline gap-1">
        <span className={cn("font-mono text-2xl font-semibold", color)}>{value}</span>
        {suffix && <span className="text-xs text-ink-faint">{suffix}</span>}
      </p>
    </motion.div>
  );
}

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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-violet-bright/25 to-cyan-bright/15 hairline">
            <Brain className="h-5 w-5 text-violet-bright" />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">Memory</h1>
            <p className="text-xs text-ink-muted">
              Lilith&apos;s living knowledge — what she knows about your people, work, and world.
            </p>
          </div>
        </div>

        <ConnectionStatus isDemo={isDemo} diagnostics={diagnostics} />
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <Tile label="Memories" value={overview.total} accent="cyan" />
        <Tile label="Learned · 7d" value={overview.recentlyLearned} accent="violet" />
        <Tile label="Pinned" value={overview.pinned} accent="amber" />
        <Tile label="Entities" value={overview.entities} accent="cyan" />
        <Tile label="Avg confidence" value={overview.avgConfidence} suffix="/100" accent="green" />
      </motion.div>
    </div>
  );
}
