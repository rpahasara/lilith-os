"use client";

import { Video, Users } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { nextEvent } from "@/lib/data";

export function NextEventCard() {
  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Next event"
        action={
          <span className="rounded-full bg-violet-bright/15 px-2 py-0.5 font-mono text-[10px] text-violet-bright">
            in {nextEvent.inMinutes}m
          </span>
        }
      />

      <div className="mt-4 flex items-start gap-3">
        <div className="flex flex-col items-center rounded-xl bg-white/[0.04] px-3 py-2 hairline">
          <span className="font-mono text-lg font-semibold leading-none text-ink">
            {nextEvent.start}
          </span>
          <span className="mt-1 font-mono text-[10px] text-ink-faint">
            {nextEvent.end}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[15px] font-medium text-ink">
            {nextEvent.title}
          </h3>
          <p className="mt-0.5 text-xs text-ink-faint">{nextEvent.where}</p>
          <div className="mt-2 flex items-center gap-1.5 text-ink-faint">
            <Users className="h-3.5 w-3.5" />
            <span className="text-xs">{nextEvent.people} attending</span>
          </div>
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <Button variant="primary" size="sm" className="flex-1">
          <Video className="h-3.5 w-3.5" /> Join
        </Button>
        <Button variant="outline" size="sm" className="flex-1">
          Prep with Lilith
        </Button>
      </div>
    </GlassCard>
  );
}
