"use client";

import { Focus } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { MeetingEvent } from "@/lib/meetings/types";
import { computeFocusWindows } from "@/lib/meetings/focus";
import { formatClock } from "@/lib/utils";
import { cn } from "@/lib/utils";

function dur(mins: number): string {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function FocusWindows({ events }: { events: MeetingEvent[] }) {
  const windows = computeFocusWindows(events).slice(0, 5);

  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Focus windows"
        action={<Focus className="h-3.5 w-3.5 text-cyan-bright/70" />}
      />

      {windows.length === 0 ? (
        <p className="mt-4 text-xs text-ink-faint">No open windows in the next 48 hours.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {windows.map((w, i) => (
            <li
              key={i}
              className={cn(
                "flex items-center justify-between rounded-lg px-3 py-2",
                w.current ? "bg-cyan-bright/[0.06] hairline" : "bg-white/[0.02]",
              )}
            >
              <span className="flex items-center gap-2 text-xs">
                {w.current && (
                  <span className="status-dot h-1.5 w-1.5 rounded-full bg-cyan-bright text-cyan-bright" />
                )}
                <span className={cn(w.current ? "text-ink" : "text-ink-muted")}>
                  {formatClock(new Date(w.start))} – {formatClock(new Date(w.end))}
                </span>
                {w.current && <span className="font-mono text-[9px] uppercase text-cyan-bright">open now</span>}
              </span>
              <span className="font-mono text-[11px] text-ink-faint">{dur(w.minutes)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[10px] text-ink-faint">Derived from real gaps between meetings.</p>
    </GlassCard>
  );
}
