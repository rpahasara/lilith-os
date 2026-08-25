"use client";

import { Fragment } from "react";
import { motion } from "framer-motion";
import { Video } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { MeetingEvent } from "@/lib/meetings/types";
import { formatClock } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { PrepBadge } from "./prep-lifecycle";

export function TimelineToday({
  events,
  selectedId,
  onSelect,
}: {
  events: MeetingEvent[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  const now = Date.now();
  const today = new Date().toDateString();

  const todays = events
    .filter((e) => e.start && new Date(e.start).toDateString() === today)
    .sort((a, b) => new Date(a.start!).getTime() - new Date(b.start!).getTime());

  // index at which "now" falls
  const nowIdx = todays.findIndex((e) => new Date(e.start!).getTime() > now);
  const insertAt = nowIdx === -1 ? todays.length : nowIdx;

  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Today"
        action={
          <span className="font-mono text-[10px] text-ink-faint">
            {todays.length} {todays.length === 1 ? "event" : "events"}
          </span>
        }
      />

      {todays.length === 0 ? (
        <p className="mt-6 py-6 text-center text-sm text-ink-faint">
          Nothing on the calendar today — the day is yours.
        </p>
      ) : (
        <ol className="mt-4 space-y-1">
          {todays.map((e, i) => (
            <Fragment key={e.id}>
              {i === insertAt && <NowMarker />}
              <TimelineRow
                event={e}
                past={new Date(e.end || e.start!).getTime() < now}
                selected={e.id === selectedId}
                onSelect={onSelect}
              />
            </Fragment>
          ))}
          {insertAt === todays.length && <NowMarker />}
        </ol>
      )}
    </GlassCard>
  );
}

function NowMarker() {
  return (
    <li className="flex items-center gap-3 py-1" aria-hidden>
      <span className="w-14 shrink-0 text-right font-mono text-[10px] text-violet-bright">now</span>
      <span className="relative flex h-2 w-2 items-center justify-center">
        <span className="status-dot h-2 w-2 rounded-full bg-violet-bright text-violet-bright" />
      </span>
      <span className="h-px flex-1 bg-gradient-to-r from-violet-bright/50 to-transparent" />
    </li>
  );
}

function TimelineRow({
  event,
  past,
  selected,
  onSelect,
}: {
  event: MeetingEvent;
  past: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <li>
      <motion.button
        type="button"
        onClick={() => onSelect(event.id)}
        whileHover={{ x: 2 }}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors",
          selected ? "bg-white/[0.06]" : "hover:bg-white/[0.03]",
          past && "opacity-55",
        )}
      >
        <span className="w-14 shrink-0 text-right font-mono text-[11px] text-ink-muted">
          {event.start ? formatClock(new Date(event.start)) : "--:--"}
        </span>
        <span
          className={cn(
            "h-2 w-2 shrink-0 rounded-full",
            past ? "bg-white/20" : "bg-cyan-bright",
          )}
        />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm text-ink">{event.title}</span>
            {event.joinLink && <Video className="h-3 w-3 shrink-0 text-ink-faint" />}
          </span>
          <span className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-faint">
            {event.durationMinutes != null && <span>{event.durationMinutes}m</span>}
            {event.attendeeCount > 0 && <span>· {event.attendeeCount} people</span>}
          </span>
        </span>
        <PrepBadge status={event.prepStatus} />
      </motion.button>
    </li>
  );
}
