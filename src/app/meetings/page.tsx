"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMeetings } from "@/hooks/use-meetings";
import { getMeetingBrief } from "@/lib/meetings/client";
import { demoBriefFor } from "@/lib/meetings/demo";
import type { PrepBrief } from "@/lib/meetings/types";
import { MEETINGS_IDENTITY, MeetingsHeader } from "@/components/meetings/meetings-header";
import { DemoBanner, WorkspaceUnavailable } from "@/components/ui/data-state";
import { NextMeeting } from "@/components/meetings/next-meeting";
import { TimelineToday } from "@/components/meetings/timeline-today";
import { MeetingIntelligence } from "@/components/meetings/meeting-intelligence";
import { FocusWindows } from "@/components/meetings/focus-windows";
import { FollowupsPanel } from "@/components/meetings/followups-panel";
import { MeetingsSkeleton } from "@/components/meetings/meetings-skeleton";

export default function MeetingsPage() {
  const { data, unavailable, loading, retry } = useMeetings();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [brief, setBrief] = useState<PrepBrief | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const intelligence = useRef<HTMLDivElement>(null);

  // Nearest upcoming meeting (backend's `next`, matched to the full event).
  const nextEvent = useMemo(() => {
    if (!data) return null;
    const byNext = data.overview.next
      ? data.events.find((e) => e.id === data.overview.next!.id)
      : undefined;
    if (byNext) return byNext;
    return (
      data.events
        .filter((e) => (e.minutesUntil ?? -1) >= 0)
        .sort((a, b) => (a.minutesUntil ?? 0) - (b.minutesUntil ?? 0))[0] ?? null
    );
  }, [data]);

  // Default selection follows the next meeting until the user picks one.
  const effectiveId = selectedId ?? nextEvent?.id ?? null;
  const selectedEvent = data?.events.find((e) => e.id === effectiveId) ?? null;

  // Lazily load the persisted brief for the selected meeting.
  useEffect(() => {
    if (!data || !selectedEvent || !selectedEvent.briefAvailable) {
      setBrief(null);
      setBriefLoading(false);
      return;
    }
    if (data.isDemo) {
      setBrief(demoBriefFor(selectedEvent.id));
      setBriefLoading(false);
      return;
    }
    const ac = new AbortController();
    setBriefLoading(true);
    getMeetingBrief(selectedEvent.id, ac.signal)
      .then((b) => setBrief(b))
      .finally(() => setBriefLoading(false));
    return () => ac.abort();
  }, [data, selectedEvent]);

  /** Choosing a meeting in the schedule brings its brief into view (it sits above). */
  const selectFromSchedule = (id: string) => {
    setSelectedId(id);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    intelligence.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
  };

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading ? (
        <MeetingsSkeleton />
      ) : unavailable ? (
        <WorkspaceUnavailable
          identity={MEETINGS_IDENTITY}
          what="Meetings"
          diagnostics={unavailable.diagnostics}
          onRetry={retry}
        />
      ) : !data ? null : (
        <>
          {data.isDemo && <DemoBanner />}
          <MeetingsHeader isDemo={data.isDemo} diagnostics={data.diagnostics} />

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
            {/* time column: the meeting, its brief right beneath it, then the day */}
            <div className="space-y-4">
              <NextMeeting
                event={nextEvent}
                contextCount={
                  data.context && data.context.eventId === nextEvent?.id
                    ? data.context.messageCount
                    : undefined
                }
                onOpen={setSelectedId}
              />
              <div ref={intelligence} className="scroll-mt-4">
                <MeetingIntelligence
                  event={selectedEvent}
                  context={data.context}
                  brief={brief}
                  briefLoading={briefLoading}
                />
              </div>
              <TimelineToday
                events={data.events}
                selectedId={effectiveId ?? undefined}
                onSelect={selectFromSchedule}
              />
            </div>

            {/* rail */}
            <div className="space-y-4">
              <FocusWindows events={data.events} />
              <FollowupsPanel followups={data.followups} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
