"use client";

import { useMemo, useState } from "react";
import { GlassCard } from "@/components/ui/card";
import { EmptyState, FilterTabs, SectionHeader } from "@/components/ui/workspace";
import { Button } from "@/components/ui/button";
import { Plus, Workflow } from "lucide-react";
import { UnitCard } from "./unit-card";
import type { AutomationUnit, UnitKind } from "@/lib/automations/types";

type Filter = "all" | UnitKind | "failed" | "paused";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "service", label: "Services" },
  { key: "watcher", label: "Watchers" },
  { key: "timer", label: "Timers" },
  { key: "agent", label: "Agents" },
  { key: "failed", label: "Failed" },
  { key: "paused", label: "Paused" },
];

// failed first (needs attention), then running, active, waiting, inactive
const STATUS_ORDER: Record<string, number> = {
  failed: 0,
  running: 1,
  active: 2,
  waiting: 3,
  inactive: 4,
};

export function SystemsGrid({ units, selectedId, onSelect }: { units: AutomationUnit[]; selectedId?: string; onSelect: (unit: AutomationUnit) => void }) {
  const [filter, setFilter] = useState<Filter>("all");

  const shown = useMemo(() => {
    const list = filter === "all" ? units : filter === "failed" ? units.filter((u) => u.status === "failed") : filter === "paused" ? units.filter((u) => !u.enabled || u.status === "inactive") : units.filter((u) => u.kind === filter);
    return [...list].sort(
      (a, b) =>
        (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9) ||
        a.name.localeCompare(b.name),
    );
  }, [units, filter]);

  return (
    <GlassCard className="flex flex-col p-5" animated={false}>
      <SectionHeader title="Automation systems" description={`${shown.length} unit${shown.length === 1 ? "" : "s"} in this view`} action={<Button size="sm" disabled title="Automation creation API is not connected"><Plus className="h-3.5 w-3.5" />Create automation</Button>} />

      <div className="mt-4"><FilterTabs items={FILTERS} value={filter} onChange={setFilter} layoutId="systems-filter" /></div>

      <div
        key={filter}
        className="mt-4 grid gap-3 sm:grid-cols-2"
      >
        {shown.length ? shown.map((u) => <UnitCard key={u.id} unit={u} selected={selectedId === u.id} onSelect={onSelect} />) : <div className="sm:col-span-2"><EmptyState icon={Workflow} title="No automation units here" description="Choose another filter to inspect the fleet." /></div>}
      </div>
    </GlassCard>
  );
}
