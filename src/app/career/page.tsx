"use client";

import { useState } from "react";

import { useCareer } from "@/hooks/use-career";
import { CAREER_IDENTITY, CareerHeader } from "@/components/career/career-header";
import { DemoBanner, WorkspaceUnavailable } from "@/components/ui/data-state";
import { CareerSkeleton } from "@/components/career/career-skeleton";
import { PipelineOverview } from "@/components/career/pipeline-overview";
import { ApplicationTracker } from "@/components/career/application-tracker";
import { ActivityTimeline } from "@/components/career/activity-timeline";
import { LilithInsights } from "@/components/ui/lilith-insights";
import { NextSteps } from "@/components/career/next-steps";
import { ApplicationDetail } from "@/components/career/application-detail";
import type { Application, Stage } from "@/lib/career/types";

export default function CareerPage() {
  const { data, unavailable, loading, retry } = useCareer();
  const [selectedStage, setSelectedStage] = useState<Stage | null>(null);
  const [selected, setSelected] = useState<Application | null>(null);

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading ? (
        <CareerSkeleton />
      ) : unavailable ? (
        <WorkspaceUnavailable
          identity={CAREER_IDENTITY}
          what="Career data"
          diagnostics={unavailable.diagnostics}
          onRetry={retry}
        />
      ) : !data ? null : (
        <>
          {data.isDemo && <DemoBanner />}
          <CareerHeader isDemo={data.isDemo} diagnostics={data.diagnostics} />

          <PipelineOverview
            pipeline={data.pipeline}
            overview={data.overview}
            selectedStage={selectedStage}
            onSelect={(stage) => setSelectedStage((current) => (current === stage ? null : stage))}
          />

          <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
            {/* main column */}
            <div className="space-y-4">
              <ApplicationTracker applications={data.applications} stageFilter={selectedStage} selectedId={selected?.id} onSelect={setSelected} />
              <ActivityTimeline activity={data.activity} />
            </div>

            {/* rail: what to do, then what Lilith noticed */}
            <div className="space-y-4">
              <NextSteps applications={data.applications} selectedId={selected?.id} onSelect={setSelected} />
              <LilithInsights insights={data.insights} />
            </div>
          </div>
          <ApplicationDetail application={selected} activity={data.activity} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
