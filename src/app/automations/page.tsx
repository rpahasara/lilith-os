"use client";

import { useState } from "react";

import { useAutomations } from "@/hooks/use-automations";
import { AUTOMATIONS_IDENTITY, AutomationsHeader } from "@/components/automations/automations-header";
import { DemoBanner, WorkspaceUnavailable } from "@/components/ui/data-state";
import { AutomationsSkeleton } from "@/components/automations/automations-skeleton";
import { SystemsGrid } from "@/components/automations/systems-grid";
import { ExecutionTimeline } from "@/components/automations/execution-timeline";
import { LilithInsights } from "@/components/ui/lilith-insights";
import { FleetOverview } from "@/components/automations/fleet-overview";
import { AutomationDetail } from "@/components/automations/automation-detail";
import type { AutomationUnit } from "@/lib/automations/types";

export default function AutomationsPage() {
  const { data, unavailable, loading, retry } = useAutomations();
  const [selected, setSelected] = useState<AutomationUnit | null>(null);

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading ? (
        <AutomationsSkeleton />
      ) : unavailable ? (
        <WorkspaceUnavailable
          identity={AUTOMATIONS_IDENTITY}
          what="Automation status"
          diagnostics={unavailable.diagnostics}
          onRetry={retry}
        />
      ) : !data ? null : (
        <>
          {data.isDemo && <DemoBanner />}
          <AutomationsHeader isDemo={data.isDemo} diagnostics={data.diagnostics} />

          <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
            {/* operations column */}
            <div className="space-y-4">
              <SystemsGrid units={data.units} selectedId={selected?.id} onSelect={setSelected} />
              <ExecutionTimeline activity={data.activity} />
            </div>

            {/* rail: the fleet, then what Lilith noticed */}
            <div className="space-y-4">
              <FleetOverview health={data.health} />
              <LilithInsights insights={data.insights} />
            </div>
          </div>
          <AutomationDetail unit={selected} activity={data.activity} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
