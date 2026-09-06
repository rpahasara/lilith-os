"use client";

import { useState } from "react";

import { useAutomations } from "@/hooks/use-automations";
import { AutomationsHeader } from "@/components/automations/automations-header";
import { AutomationsSkeleton } from "@/components/automations/automations-skeleton";
import { SystemsGrid } from "@/components/automations/systems-grid";
import { ExecutionTimeline } from "@/components/automations/execution-timeline";
import { OpsInsights } from "@/components/automations/ops-insights";
import { FleetOverview } from "@/components/automations/fleet-overview";
import { AutomationDetail } from "@/components/automations/automation-detail";
import type { AutomationUnit } from "@/lib/automations/types";

export default function AutomationsPage() {
  const { data, loading } = useAutomations();
  const [selected, setSelected] = useState<AutomationUnit | null>(null);

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading || !data ? (
        <AutomationsSkeleton />
      ) : (
        <>
          <AutomationsHeader
            health={data.health}
            isDemo={data.isDemo}
            diagnostics={data.diagnostics}
          />

          <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
            {/* operations column */}
            <div className="space-y-4">
              <SystemsGrid units={data.units} selectedId={selected?.id} onSelect={setSelected} />
              <ExecutionTimeline activity={data.activity} />
            </div>

            {/* intelligence rail */}
            <div className="space-y-4">
              <FleetOverview units={data.units} score={data.health.score} />
              <OpsInsights insights={data.insights} />
            </div>
          </div>
          <AutomationDetail unit={selected} activity={data.activity} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
