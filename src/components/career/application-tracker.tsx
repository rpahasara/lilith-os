"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { ApplicationRow } from "./application-row";
import type { Application } from "@/lib/career/types";
import { TERMINAL_STAGES } from "@/lib/career/types";
import { staggerContainer } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Filter = "active" | "attention" | "offers" | "all";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "active", label: "Active" },
  { key: "attention", label: "Needs attention" },
  { key: "offers", label: "Offers" },
  { key: "all", label: "All" },
];

export function ApplicationTracker({ applications }: { applications: Application[] }) {
  const [filter, setFilter] = useState<Filter>("active");

  const shown = useMemo(() => {
    const terminal = TERMINAL_STAGES as readonly string[];
    const byRecency = (a: Application, b: Application) =>
      new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime();
    switch (filter) {
      case "active":
        return applications.filter((a) => !terminal.includes(a.stage)).sort(byRecency);
      case "attention":
        return applications.filter((a) => a.followUp).sort(byRecency);
      case "offers":
        return applications.filter((a) => a.stage === "offer").sort(byRecency);
      default:
        return [...applications].sort(byRecency);
    }
  }, [applications, filter]);

  return (
    <GlassCard className="flex flex-col p-5" animated={false}>
      <PanelHeader
        title="Application tracker"
        action={
          <span className="font-mono text-[10px] text-ink-faint">
            {shown.length} shown
          </span>
        }
      />

      {/* filter segmented control */}
      <div className="mt-4 flex flex-wrap gap-1 rounded-full border border-white/[0.06] bg-white/[0.02] p-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "relative rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
              filter === f.key ? "text-ink" : "text-ink-faint hover:text-ink-muted",
            )}
          >
            {filter === f.key && (
              <motion.span
                layoutId="tracker-filter"
                className="absolute inset-0 rounded-full bg-white/10"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative">{f.label}</span>
          </button>
        ))}
      </div>

      {/* rows */}
      <motion.div
        key={filter}
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 space-y-2.5"
      >
        {shown.length === 0 ? (
          <p className="py-10 text-center text-sm text-ink-faint">
            Nothing here right now.
          </p>
        ) : (
          shown.map((app) => <ApplicationRow key={app.id} app={app} />)
        )}
      </motion.div>
    </GlassCard>
  );
}
