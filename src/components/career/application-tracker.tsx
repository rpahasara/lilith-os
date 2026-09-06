"use client";

import { useMemo, useState } from "react";
import { GlassCard } from "@/components/ui/card";
import { EmptyState, FilterTabs, SectionHeader } from "@/components/ui/workspace";
import { BriefcaseBusiness, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApplicationRow } from "./application-row";
import type { Application, Stage } from "@/lib/career/types";
import { STAGE_META, TERMINAL_STAGES } from "@/lib/career/types";

type Filter = "active" | "attention" | "offers" | "all";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "active", label: "Active" },
  { key: "attention", label: "Needs attention" },
  { key: "offers", label: "Offers" },
  { key: "all", label: "All" },
];

export function ApplicationTracker({ applications, stageFilter, selectedId, onSelect }: { applications: Application[]; stageFilter?: Stage | null; selectedId?: string; onSelect: (application: Application) => void }) {
  const [filter, setFilter] = useState<Filter>("active");

  const shown = useMemo(() => {
    const terminal = TERMINAL_STAGES as readonly string[];
    const byRecency = (a: Application, b: Application) =>
      new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime();
    const scoped = stageFilter ? applications.filter((a) => a.stage === stageFilter) : applications;
    switch (filter) {
      case "active":
        return scoped.filter((a) => !terminal.includes(a.stage)).sort(byRecency);
      case "attention":
        return scoped.filter((a) => a.followUp || Date.now() - new Date(a.lastActivity).getTime() > 5 * 86400000).sort(byRecency);
      case "offers":
        return scoped.filter((a) => a.stage === "offer").sort(byRecency);
      default:
        return [...scoped].sort(byRecency);
    }
  }, [applications, filter, stageFilter]);

  return (
    <GlassCard className="flex flex-col p-5" animated={false}>
      <SectionHeader title="Application tracker" description={stageFilter ? `Pipeline focus · ${STAGE_META[stageFilter].label}` : `${shown.length} opportunities shown`} action={<Button size="sm" disabled title="Requires the career write API"><Plus className="h-3.5 w-3.5" />Add application</Button>} />

      {/* filter segmented control */}
      <div className="mt-4"><FilterTabs items={FILTERS} value={filter} onChange={setFilter} layoutId="tracker-filter" /></div>

      {/* rows */}
      <div
        key={filter}
        className="mt-4 space-y-2.5"
      >
        {shown.length === 0 ? (
          <EmptyState icon={BriefcaseBusiness} title="No applications in this view" description="Change the filter or select another pipeline stage." />
        ) : (
          shown.map((app) => <ApplicationRow key={app.id} app={app} selected={selectedId === app.id} onSelect={onSelect} />)
        )}
      </div>
    </GlassCard>
  );
}
