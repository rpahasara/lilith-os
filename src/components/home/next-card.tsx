"use client";

import { Video, Users } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { nextEvent } from "@/lib/data";

/**
 * NEXT — the single immediate contextual item (the next meeting). Memory and
 * Automations no longer live on Home; they have their own sidebar modules.
 */
export function NextCard() {
  return (
    <GlassCard panel interactive className="w-full max-w-[300px] p-5">
      <span className="pointer-events-none absolute inset-y-5 right-0 w-px bg-gradient-to-b from-transparent via-gold/50 to-transparent" />
      <div className="flex items-center justify-between">
        <span className="eyebrow text-ink">Next</span>
        <span className="rounded-full border border-gold/15 bg-gold/[0.08] px-2.5 py-1 font-mono text-[10px] text-gold">
          in {nextEvent.inMinutes}m
        </span>
      </div>

      <div className="mt-4">
        <div className="flex items-baseline gap-2 font-mono">
          <span className="text-[1.7rem] font-semibold leading-none tracking-[-0.04em] text-ink">
            {nextEvent.start}
          </span>
          <span className="text-[11px] text-ink-faint">– {nextEvent.end}</span>
        </div>
        <h3 className="mt-2.5 text-[15px] font-medium leading-tight text-ink">
          {nextEvent.title}
        </h3>
        <p className="mt-1 text-xs text-ink-faint">{nextEvent.where}</p>
        <div className="mt-2 flex items-center gap-1.5 text-ink-faint">
          <Users className="h-3.5 w-3.5" />
          <span className="text-xs">{nextEvent.people} attending</span>
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
