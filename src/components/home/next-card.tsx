"use client";

import { CloudOff, Video, Users } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatClock } from "@/lib/utils";
import { countdownLabel, type HomeMeetingsView } from "@/lib/home/meetings-view";

/**
 * NEXT — the single immediate contextual item: the next (or current) meeting
 * from the live read-only meetings data. The countdown is recomputed from the
 * start time on every clock tick, never taken from a stored snapshot.
 *
 * Actions: Join opens the meeting's own https link in a new tab, and only
 * when one exists. "Prep with Lilith" is not connected yet, so it is a
 * disabled control. When no live data is available the card says so and
 * offers no actions.
 */
export function NextCard({ view }: { view: HomeMeetingsView }) {
  const next = view.kind === "live" ? view.next : null;

  return (
    <GlassCard
      panel
      interactive
      className="w-full max-w-[300px] p-5"
      data-home-card="next"
      data-home-state={view.kind}
    >
      <span className="pointer-events-none absolute inset-y-5 right-0 w-px bg-gradient-to-b from-transparent via-gold/50 to-transparent" />
      <div className="flex items-center justify-between">
        <span className="eyebrow text-ink">Next</span>
        {next && (
          <span className="rounded-full border border-gold/15 bg-gold/[0.08] px-2.5 py-1 font-mono text-[10px] text-gold">
            {countdownLabel(next)}
          </span>
        )}
      </div>

      {view.kind === "loading" && (
        <div className="mt-4 space-y-2.5" aria-busy="true" aria-label="Loading next meeting">
          <span className="block h-6 w-24 animate-pulse rounded bg-white/[0.06]" />
          <span className="block h-4 w-44 animate-pulse rounded bg-white/[0.06]" />
          <span className="block h-3 w-28 animate-pulse rounded bg-white/[0.06]" />
        </div>
      )}

      {view.kind === "unavailable" && (
        <div className="mt-4 flex items-start gap-2.5" role="status">
          <CloudOff className="mt-0.5 h-4 w-4 shrink-0 text-ink-faint" />
          <div className="leading-tight">
            <p className="text-[13px] text-ink">Meetings unavailable</p>
            <p className="mt-1 text-[11px] text-ink-faint">
              No calendar data can be read right now.
            </p>
          </div>
        </div>
      )}

      {view.kind === "live" && !next && (
        <div className="mt-4 leading-tight">
          <p className="text-[15px] font-medium text-ink">Nothing scheduled</p>
          <p className="mt-1 text-xs text-ink-faint">No upcoming meetings on your calendar.</p>
        </div>
      )}

      {next && (
        <>
          <div className="mt-4">
            <div className="flex items-baseline gap-2 font-mono">
              <span className="text-[1.7rem] font-semibold leading-none tracking-[-0.04em] text-ink">
                {formatClock(new Date(next.startMs))}
              </span>
              {next.endMs != null && (
                <span className="text-[11px] text-ink-faint">– {formatClock(new Date(next.endMs))}</span>
              )}
            </div>
            <h3 className="mt-2.5 text-[15px] font-medium leading-tight text-ink">{next.title}</h3>
            {next.calendar && <p className="mt-1 text-xs text-ink-faint">{next.calendar}</p>}
            {next.attendeeCount > 0 && (
              <div className="mt-2 flex items-center gap-1.5 text-ink-faint">
                <Users className="h-3.5 w-3.5" />
                <span className="text-xs">
                  {next.attendeeCount} {next.attendeeCount === 1 ? "attendee" : "attendees"}
                </span>
              </div>
            )}
          </div>

          <div className="mt-4 flex gap-2">
            {next.joinUrl ? (
              <a
                href={next.joinUrl}
                target="_blank"
                rel="noopener noreferrer"
                data-home-action="join"
                className="inline-flex h-8 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-full border border-wine/55 bg-gradient-to-b from-wine-bright/35 via-wine/25 to-wine-deep/35 px-3 text-xs font-medium text-white shadow-[inset_0_1px_0_0_rgba(243,238,244,0.35),0_10px_28px_-10px_rgba(0,0,0,0.6),0_8px_26px_-12px_rgba(201,79,109,0.6)] backdrop-blur-md transition-all duration-200 hover:border-wine-bright/75 hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wine-bright"
              >
                <Video className="h-3.5 w-3.5" /> Join
              </a>
            ) : (
              <Button
                type="button"
                variant="primary"
                size="sm"
                className="flex-1"
                disabled
                title="This meeting has no join link"
                data-home-action="join"
              >
                <Video className="h-3.5 w-3.5" /> Join
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="flex-1"
              disabled
              title="Prep with Lilith isn't available yet"
              data-home-action="prep"
            >
              Prep with Lilith
            </Button>
          </div>
        </>
      )}
    </GlassCard>
  );
}
