"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { STAGE_META, type PipelineStage, type Stage } from "@/lib/career/types";
import { cn } from "@/lib/utils";

const NODE_ACCENT: Record<string, string> = {
  violet: "var(--violet-bright)",
  cyan: "var(--cyan-bright)",
  green: "var(--green)",
  amber: "var(--amber)",
  rose: "var(--rose)",
  faint: "var(--ink-faint)",
};

export function PipelineOverview({ pipeline, selectedStage, onSelect }: { pipeline: PipelineStage[]; selectedStage?: Stage | null; onSelect?: (stage: Stage) => void }) {
  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Pipeline overview"
        action={
          <span className="font-mono text-[10px] text-ink-faint">
            {pipeline.reduce((s, p) => s + p.count, 0)} in flight
          </span>
        }
      />

      <div className="mt-5 overflow-x-auto pb-1">
        <div className="flex min-w-[640px] items-end justify-between gap-2">
          {pipeline.map((p, i) => {
            const meta = STAGE_META[p.stage];
            const color = NODE_ACCENT[meta.accent];
            const active = p.count > 0;
            return (
              <button type="button" key={p.stage} onClick={() => onSelect?.(p.stage)} aria-pressed={selectedStage === p.stage} className={cn("relative flex flex-1 flex-col items-center rounded-xl py-2 transition-colors hover:bg-white/[0.03]", selectedStage === p.stage && "bg-white/[0.05]")}>
                {/* connector */}
                {i < pipeline.length - 1 && (
                  <span className="absolute right-[-50%] top-[46px] h-px w-full bg-white/[0.08]" />
                )}

                {/* count */}
                <span
                  className="font-mono text-2xl font-semibold leading-none"
                  style={{ color: active ? color : "var(--ink-faint)" }}
                >
                  {p.count}
                </span>

                {/* node */}
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.05 * i, type: "spring", stiffness: 320, damping: 22 }}
                  className="relative z-10 mt-3 grid h-4 w-4 place-items-center rounded-full"
                  style={{
                    background: active ? color : "rgba(255,255,255,0.08)",
                    boxShadow: active ? `0 0 12px 1px ${color}66` : "none",
                  }}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-black/40" />
                </motion.span>

                {/* label */}
                <span className="mt-3 text-center text-[11px] leading-tight text-ink-muted">
                  {meta.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </GlassCard>
  );
}
