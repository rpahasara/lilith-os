"use client";

import { Check } from "lucide-react";
import { PREP_META, type PrepStatus } from "@/lib/meetings/types";
import { cn } from "@/lib/utils";

const BADGE: Record<string, string> = {
  violet: "bg-violet-bright/12 text-violet-bright",
  cyan: "bg-cyan-bright/12 text-cyan-bright",
  green: "bg-green/12 text-green",
  amber: "bg-amber/12 text-amber",
  faint: "bg-white/[0.05] text-ink-faint",
};

/** Compact prep-status pill. */
export function PrepBadge({ status, className }: { status: PrepStatus; className?: string }) {
  const meta = PREP_META[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium",
        BADGE[meta.accent],
        className,
      )}
    >
      {meta.label}
    </span>
  );
}

const STEPS: { key: Exclude<PrepStatus, "scheduled">; label: string }[] = [
  { key: "detected", label: "Detected" },
  { key: "context_gathered", label: "Context" },
  { key: "delivered", label: "Prepared" },
  { key: "completed", label: "Completed" },
];

const ORDER: PrepStatus[] = ["scheduled", "detected", "context_gathered", "delivered", "completed"];

/**
 * The real prep lifecycle: detected → context gathered → prepared/delivered →
 * completed. Derived from actual state; "scheduled" means Lilith hasn't picked
 * it up yet (she prepares ~15 min before start).
 */
export function PrepLifecycle({ status }: { status: PrepStatus }) {
  const current = ORDER.indexOf(status); // 0 == scheduled

  return (
    <div className="flex items-center">
      {STEPS.map((step, i) => {
        const stepIndex = i + 1; // detected == 1
        const done = current >= stepIndex;
        const isCurrent = current === stepIndex;
        return (
          <div key={step.key} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <span
                className={cn(
                  "grid h-6 w-6 place-items-center rounded-full border text-[10px] transition-colors",
                  done
                    ? "border-transparent bg-violet-bright/20 text-violet-bright"
                    : "border-white/10 bg-white/[0.03] text-ink-faint",
                  isCurrent && "ring-2 ring-violet-bright/40",
                )}
              >
                {done && step.key !== "completed" ? (
                  <Check className="h-3 w-3" />
                ) : done && step.key === "completed" ? (
                  <Check className="h-3 w-3" />
                ) : (
                  i + 1
                )}
              </span>
              <span className={cn("text-[9px]", done ? "text-ink-muted" : "text-ink-faint")}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span
                className={cn(
                  "mx-1 h-px flex-1 self-start mt-3",
                  current > stepIndex ? "bg-violet-bright/40" : "bg-white/[0.08]",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
