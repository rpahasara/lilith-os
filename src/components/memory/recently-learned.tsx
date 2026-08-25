"use client";

import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import {
  CATEGORY_META,
  type Accent,
  type RecentMemoryEvent,
} from "@/lib/memory/types";
import { cn, timeAgo } from "@/lib/utils";

const DOT: Record<Accent, string> = {
  violet: "bg-violet-bright",
  cyan: "bg-cyan-bright",
  green: "bg-green",
  amber: "bg-amber",
  rose: "bg-rose",
  faint: "bg-white/30",
};

const KIND_LABEL: Record<RecentMemoryEvent["kind"], string> = {
  learned: "learned",
  updated: "updated",
  reinforced: "reinforced",
};

export function RecentlyLearned({ events }: { events: RecentMemoryEvent[] }) {
  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader title="Recently learned" />

      {events.length === 0 ? (
        <p className="mt-4 text-xs text-ink-faint">No recent memory activity.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {events.map((e) => (
            <li key={e.id} className="relative flex gap-3">
              <div className="flex flex-col items-center pt-1">
                <span className={cn("h-1.5 w-1.5 rounded-full", DOT[CATEGORY_META[e.category].accent])} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs leading-snug text-ink-muted">{e.text}</p>
                <p className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] text-ink-faint">
                  <span className="uppercase tracking-wider">{KIND_LABEL[e.kind]}</span>
                  <span>·</span>
                  <span>{timeAgo(e.at)}</span>
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}
