"use client";

import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { Ring } from "@/components/ui/ring";
import { pipeline } from "@/lib/data";

export function FocusCard() {
  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Focus"
        action={
          <span className="font-mono text-[10px] text-green">↑ 6 this week</span>
        }
      />

      <div className="mt-4 flex items-center gap-5">
        <Ring value={pipeline.focusScore} label={String(pipeline.focusScore)} sub="/ 100" />
        <div className="flex-1 space-y-2.5">
          {pipeline.stages.map((s) => (
            <div key={s.label} className="flex items-center justify-between">
              <span className="text-xs text-ink-muted">{s.label}</span>
              <span
                className="font-mono text-sm font-medium"
                style={{
                  color:
                    s.accent === "violet"
                      ? "var(--violet-bright)"
                      : "var(--cyan-bright)",
                }}
              >
                {s.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  );
}
