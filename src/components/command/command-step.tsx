"use client";

import { Check, Circle, Loader2, Minus, Pause, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CommandStep as Step, CommandStepStatus } from "@/lib/command";

const ICON: Record<CommandStepStatus, { node: React.ReactNode; ring: string }> = {
  pending: { node: <Circle className="h-3 w-3" />, ring: "border-white/10 text-ink-faint" },
  running: { node: <Loader2 className="h-3 w-3 animate-spin" />, ring: "border-cyan-bright/40 text-cyan-bright" },
  waiting: { node: <Pause className="h-3 w-3" />, ring: "border-amber/40 text-amber" },
  succeeded: { node: <Check className="h-3 w-3" />, ring: "border-green/40 text-green" },
  failed: { node: <X className="h-3 w-3" />, ring: "border-rose/40 text-rose" },
  skipped: { node: <Minus className="h-3 w-3" />, ring: "border-white/10 text-ink-faint" },
};

function elapsed(step: Step): string | null {
  if (!step.startedAt) return null;
  const end = step.endedAt ?? Date.now();
  const s = Math.max(0, Math.round((end - step.startedAt) / 100) / 10);
  return `${s.toFixed(1)}s`;
}

export function CommandStep({ step, showTiming = false }: { step: Step; showTiming?: boolean }) {
  const icon = ICON[step.status];
  const active = step.status === "running" || step.status === "waiting";
  const time = showTiming && step.endedAt ? elapsed(step) : null;

  return (
    <li className="flex items-start gap-3">
      <span
        className={cn(
          "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border",
          icon.ring,
        )}
      >
        {icon.node}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-3">
          <span
            className={cn(
              "text-[13px] leading-snug",
              step.status === "pending"
                ? "text-ink-faint"
                : active
                  ? "text-ink"
                  : "text-ink-muted",
            )}
          >
            {step.label}
          </span>
          {time && <span className="shrink-0 font-mono text-[10px] text-ink-faint">{time}</span>}
        </span>
        {step.detail && (
          <span
            className={cn(
              "mt-0.5 block text-[11px] leading-relaxed",
              step.status === "failed" ? "text-rose/90" : "text-ink-faint",
            )}
          >
            {step.detail}
          </span>
        )}
      </span>
    </li>
  );
}
