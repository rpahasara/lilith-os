"use client";

import { useEffect, useMemo, useState } from "react";
import { useMeetings } from "@/hooks/use-meetings";
import { getMeetingBrief } from "@/lib/meetings/client";
import { demoBriefFor } from "@/lib/meetings/demo";
import type { PrepBrief } from "@/lib/meetings/types";
import { MeetingsHeader } from "@/components/meetings/meetings-header";
import { NextMeeting } from "@/components/meetings/next-meeting";
import { TimelineToday } from "@/components/meetings/timeline-today";
import { MeetingIntelligence } from "@/components/meetings/meeting-intelligence";
import { FocusWindows } from "@/components/meetings/focus-windows";
import { FollowupsPanel } from "@/components/meetings/followups-panel";
import { MeetingsSkeleton } from "@/components/meetings/meetings-skeleton";

export default function MeetingsPage() {
  const { data, loading } = useMeetings();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [brief, setBrief] = useState<PrepBrief | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);

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

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading || !data ? (
        <MeetingsSkeleton />
      ) : (
        <>
          <MeetingsHeader
            overview={data.overview}
            isDemo={data.isDemo}
            diagnostics={data.diagnostics}
          />

          <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
            {/* time column */}
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
              <TimelineToday
                events={data.events}
                selectedId={effectiveId ?? undefined}
                onSelect={setSelectedId}
              />
              <MeetingIntelligence
                event={selectedEvent}
                context={data.context}
                brief={brief}
                briefLoading={briefLoading}
              />
            </div>

            {/* intelligence rail */}
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
