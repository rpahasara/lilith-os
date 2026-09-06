"use client";

import { useCareer } from "@/hooks/use-career";
import { CareerHeader } from "@/components/career/career-header";
import { CareerSkeleton } from "@/components/career/career-skeleton";
import { PipelineOverview } from "@/components/career/pipeline-overview";
import { ApplicationTracker } from "@/components/career/application-tracker";
import { ActivityTimeline } from "@/components/career/activity-timeline";
import { InsightsPanel } from "@/components/career/insights-panel";
import { NextActions } from "@/components/career/next-actions";
import { InterviewPrep } from "@/components/career/interview-prep";

export default function CareerPage() {
  const { data, loading } = useCareer();

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

          <PipelineOverview pipeline={data.pipeline} />

          <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
            {/* main column */}
            <div className="space-y-4">
              <ApplicationTracker applications={data.applications} />
              <ActivityTimeline activity={data.activity} />
            </div>

            {/* intelligence rail */}
            <div className="space-y-4">
              <InsightsPanel insights={data.insights} />
              <NextActions applications={data.applications} />
              <InterviewPrep applications={data.applications} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
