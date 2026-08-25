"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { UnitCard } from "./unit-card";
import type { AutomationUnit, UnitKind } from "@/lib/automations/types";
import { staggerContainer } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Filter = "all" | UnitKind;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "service", label: "Services" },
  { key: "watcher", label: "Watchers" },
  { key: "timer", label: "Timers" },
  { key: "agent", label: "Agents" },
];

// failed first (needs attention), then running, active, waiting, inactive
const STATUS_ORDER: Record<string, number> = {
  failed: 0,
  running: 1,
  active: 2,
  waiting: 3,
  inactive: 4,
};

export function SystemsGrid({ units }: { units: AutomationUnit[] }) {
  const [filter, setFilter] = useState<Filter>("all");

  const shown = useMemo(() => {
    const list = filter === "all" ? units : units.filter((u) => u.kind === filter);
    return [...list].sort(
      (a, b) =>
        (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9) ||
        a.name.localeCompare(b.name),
    );
  }, [units, filter]);

  return (
    <GlassCard className="flex flex-col p-5" animated={false}>
      <PanelHeader
        title="Systems"
        action={
          <span className="font-mono text-[10px] text-ink-faint">
            {shown.length} unit{shown.length === 1 ? "" : "s"}
          </span>
        }
      />

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
                layoutId="systems-filter"
                className="absolute inset-0 rounded-full bg-white/10"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative">{f.label}</span>
          </button>
        ))}
      </div>

      <motion.div
        key={filter}
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid gap-3 sm:grid-cols-2"
      >
        {shown.map((u) => (
          <UnitCard key={u.id} unit={u} />
        ))}
      </motion.div>
    </GlassCard>
  );
}
