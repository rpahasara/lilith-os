"use client";

import { CheckCircle2, Circle } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import type { Followup } from "@/lib/meetings/types";
import { cn } from "@/lib/utils";

export function FollowupsPanel({ followups }: { followups: Followup[] }) {
  const sorted = [...followups].sort(
    (a, b) => Number(a.status === "resolved") - Number(b.status === "resolved"),
  );

  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Follow-ups"
        action={
          <span className="font-mono text-[10px] text-ink-faint">
            {followups.filter((f) => f.status === "waiting").length} pending
          </span>
        }
      />

      {sorted.length === 0 ? (
        <p className="mt-4 text-xs text-ink-faint">No follow-ups tracked.</p>
      ) : (
        <ul className="mt-4 space-y-2.5">
          {sorted.map((f) => {
            const resolved = f.status === "resolved";
            return (
              <li key={f.id} className="flex gap-2.5">
                {resolved ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green/70" />
                ) : (
                  <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber/80" />
                )}
                <div className="min-w-0 flex-1">
                  <p className={cn("text-xs leading-snug", resolved ? "text-ink-faint line-through" : "text-ink-muted")}>
                    {f.title}
                  </p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-1.5 font-mono text-[10px] text-ink-faint">
                    {f.source && <span className="uppercase tracking-wider">{f.source}</span>}
                    {f.due && (
                      <>
                        <span>·</span>
                        <span>{f.dueKind === "window" ? "due " : "due "}{f.due}</span>
                      </>
                    )}
                    {resolved && (
                      <>
                        <span>·</span>
                        <span className="text-green/70">resolved</span>
                      </>
                    )}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </GlassCard>
  );
}
