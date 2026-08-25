"use client";

import { useEffect, useState } from "react";
import { Video, Users, ArrowRight, CalendarClock, Sparkles } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/primitives";
import type { MeetingEvent } from "@/lib/meetings/types";
import { formatClock, shortDate } from "@/lib/utils";
import { PrepBadge } from "./prep-lifecycle";

function useCountdown(startISO?: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  if (!startISO) return null;
  const diff = new Date(startISO).getTime() - now;
  return Math.round(diff / 60_000); // minutes (negative if started)
}

function label(mins: number | null): string {
  if (mins == null) return "";
  if (mins <= 0 && mins > -5) return "starting now";
  if (mins < 0) return "in progress";
  if (mins < 60) return `in ${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h < 24) return `in ${h}h${m ? ` ${m}m` : ""}`;
  return `in ${Math.floor(h / 24)}d ${h % 24}h`;
}

export function NextMeeting({
  event,
  contextCount,
  onOpen,
}: {
  event?: MeetingEvent | null;
  contextCount?: number;
  onOpen: (id: string) => void;
}) {
  const mins = useCountdown(event?.start);

  if (!event) {
    return (
      <GlassCard strong className="relative overflow-hidden p-6" animated={false}>
        <span className="pointer-events-none absolute -right-10 -top-16 h-40 w-40 rounded-full bg-cyan-bright/10 blur-3xl" />
        <Eyebrow>Next meeting</Eyebrow>
        <div className="mt-6 flex flex-col items-center gap-2 py-6 text-center">
          <CalendarClock className="h-7 w-7 text-ink-faint" />
          <p className="text-sm text-ink">No meetings ahead in your window.</p>
          <p className="text-xs text-ink-faint">
            Your time is open — Lilith will prep the next one ~15 min before it starts.
          </p>
        </div>
      </GlassCard>
    );
  }

  const when = event.start ? new Date(event.start) : null;
  const isToday = when ? when.toDateString() === new Date().toDateString() : false;

  return (
    <GlassCard strong className="relative overflow-hidden p-6" animated={false}>
      {/* soft temporal glow */}
      <span className="pointer-events-none absolute -right-12 -top-16 h-44 w-44 rounded-full bg-violet-bright/12 blur-3xl" />
      <span className="pointer-events-none absolute -left-12 bottom-0 h-40 w-40 rounded-full bg-cyan-bright/10 blur-3xl" />

      <div className="relative flex items-start justify-between gap-3">
        <Eyebrow>Next meeting</Eyebrow>
        <span className="flex items-center gap-2">
          <PrepBadge status={event.prepStatus} />
        </span>
      </div>

      <div className="relative mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-lg font-semibold tracking-tight text-ink">{event.title}</h2>
        <span className="animate-breathe font-mono text-sm text-violet-bright">{label(mins)}</span>
      </div>

      <div className="relative mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
        {when && (
          <span className="font-mono">
            {isToday ? "Today" : shortDate(event.start)} · {formatClock(when)}
            {event.end ? `–${formatClock(new Date(event.end))}` : ""}
          </span>
        )}
        {event.durationMinutes != null && <span className="text-ink-faint">· {event.durationMinutes}m</span>}
        {event.calendar && <span className="text-ink-faint">· {event.calendar}</span>}
      </div>

      {/* attendees */}
      {event.attendees.length > 0 && (
        <div className="relative mt-4 flex flex-wrap items-center gap-1.5">
          <Users className="h-3.5 w-3.5 text-ink-faint" />
          {event.attendees.slice(0, 5).map((a, i) => (
            <span
              key={i}
              className="rounded-md bg-white/[0.04] px-2 py-0.5 text-[11px] text-ink-muted"
              title={a.emailMasked || undefined}
            >
              {a.displayName || a.emailMasked || "Guest"}
            </span>
          ))}
          {event.attendeeCount > event.attendees.length && (
            <span className="text-[10px] text-ink-faint">+{event.attendeeCount - event.attendees.length}</span>
          )}
        </div>
      )}

      {/* actions */}
      <div className="relative mt-5 flex flex-wrap items-center gap-2">
        {event.joinLink && (
          <a
            href={event.joinLink}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 rounded-lg bg-violet-bright/15 px-3 py-1.5 text-xs font-medium text-violet-bright transition-colors hover:bg-violet-bright/25"
          >
            <Video className="h-3.5 w-3.5" />
            Join
          </a>
        )}
        <button
          onClick={() => onOpen(event.id)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:border-white/15"
        >
          {event.briefAvailable ? (
            <>
              <Sparkles className="h-3.5 w-3.5 text-violet-bright" /> Open brief
            </>
          ) : (
            <>
              View intelligence <ArrowRight className="h-3.5 w-3.5" />
            </>
          )}
        </button>
        {contextCount ? (
          <span className="font-mono text-[10px] text-ink-faint">{contextCount} related items</span>
        ) : null}
      </div>
    </GlassCard>
  );
}
