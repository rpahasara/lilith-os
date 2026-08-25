"use client";

import { motion } from "framer-motion";
import { Cpu } from "lucide-react";
import type { AutomationHealth } from "@/lib/automations/types";
import type { Diagnostics } from "@/lib/api";
import { ConnectionStatus } from "@/components/ui/connection-status";
import { staggerContainer, riseIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

function Tile({
  label,
  value,
  suffix,
  accent = "cyan",
}: {
  label: string;
  value: string | number;
  suffix?: string;
  accent?: "violet" | "cyan" | "green" | "amber" | "rose" | "faint";
}) {
  const color = {
    violet: "text-violet-bright",
    cyan: "text-cyan-bright",
    green: "text-green",
    amber: "text-amber",
    rose: "text-rose",
    faint: "text-ink-muted",
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-violet-bright/25 to-cyan-bright/15 hairline">
            <Cpu className="h-5 w-5 text-violet-bright" />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">
              Autonomous Operations
            </h1>
            <p className="text-xs text-ink-muted">
              Lilith&apos;s background agents, watchers, and services — live.
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
        <Tile label="Health" value={health.score} suffix="/100" accent={health.failed ? "amber" : "green"} />
        <Tile label="Running" value={health.running} accent="green" />
        <Tile label="Active" value={health.active} accent="cyan" />
        <Tile label="Waiting" value={health.waiting} accent="faint" />
        <Tile label="Failed" value={health.failed} accent={health.failed ? "rose" : "faint"} />
      </motion.div>
    </div>
  );
}
