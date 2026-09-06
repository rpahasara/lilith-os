"use client";

import { useState } from "react";

import { useCareer } from "@/hooks/use-career";
import { CareerHeader } from "@/components/career/career-header";
import { CareerSkeleton } from "@/components/career/career-skeleton";
import { PipelineOverview } from "@/components/career/pipeline-overview";
import { ApplicationTracker } from "@/components/career/application-tracker";
import { ActivityTimeline } from "@/components/career/activity-timeline";
import { InsightsPanel } from "@/components/career/insights-panel";
import { NextActions } from "@/components/career/next-actions";
import { InterviewPrep } from "@/components/career/interview-prep";
import { ApplicationDetail } from "@/components/career/application-detail";
import type { Application, Stage } from "@/lib/career/types";

export default function CareerPage() {
  const { data, loading } = useCareer();
  const [selectedStage, setSelectedStage] = useState<Stage | null>(null);
  const [selected, setSelected] = useState<Application | null>(null);

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading || !data ? (
        <CareerSkeleton />
      ) : (
        <>
          <CareerHeader
            overview={data.overview}
            isDemo={data.isDemo}
            diagnostics={data.diagnostics}
          />

          <PipelineOverview pipeline={data.pipeline} selectedStage={selectedStage} onSelect={(stage) => setSelectedStage((current) => current === stage ? null : stage)} />

          <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
            {/* main column */}
            <div className="space-y-4">
              <ApplicationTracker applications={data.applications} stageFilter={selectedStage} selectedId={selected?.id} onSelect={setSelected} />
              <ActivityTimeline activity={data.activity} />
            </div>

            {/* intelligence rail */}
            <div className="space-y-4">
              <InsightsPanel insights={data.insights} />
              <NextActions applications={data.applications} />
              <InterviewPrep applications={data.applications} />
            </div>
          </div>
          <ApplicationDetail application={selected} activity={data.activity} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
