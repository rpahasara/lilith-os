"use client";

import { useAutomations } from "@/hooks/use-automations";
import { AutomationsHeader } from "@/components/automations/automations-header";
import { AutomationsSkeleton } from "@/components/automations/automations-skeleton";
import { SystemsGrid } from "@/components/automations/systems-grid";
import { ExecutionTimeline } from "@/components/automations/execution-timeline";
import { OpsInsights } from "@/components/automations/ops-insights";
import { FleetOverview } from "@/components/automations/fleet-overview";

export default function AutomationsPage() {
  const { data, loading } = useAutomations();

  return (
    <div className="scroll-area h-full space-y-4 overflow-y-auto pb-6 pr-1">
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
              <SystemsGrid units={data.units} />
              <ExecutionTimeline activity={data.activity} />
            </div>

            {/* intelligence rail */}
            <div className="space-y-4">
              <FleetOverview units={data.units} score={data.health.score} />
              <OpsInsights insights={data.insights} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
