"use client";

import { motion } from "framer-motion";
import { confidenceTier, type Accent } from "@/lib/memory/types";
import { cn } from "@/lib/utils";
import { meter } from "@/lib/motion";

const FILL: Record<Accent, string> = {
  orchid: "bg-orchid-bright",
  cyan: "bg-cyan-bright",
  green: "bg-green",
  amber: "bg-amber",
  rose: "bg-rose",
  faint: "bg-white/20",
};

/**
 * Confidence as a small labelled bar. When the source expresses no confidence
 * (e.g. a file-backed memory) we render an explicit "unknown" state rather than
 * inventing a number.
 */
export function ConfidenceMeter({
  value,
  className,
  showLabel = true,
}: {
  value?: number;
  className?: string;
  showLabel?: boolean;
}) {
  const tier = confidenceTier(value);
  const known = typeof value === "number";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
        {known ? (
          <motion.div
            className={cn("h-full rounded-full", FILL[tier.accent])}
            initial={{ width: 0 }}
            animate={{ width: `${value}%` }}
            transition={meter}
          />
        ) : (
          <div className="h-full w-full bg-[repeating-linear-gradient(90deg,rgba(255,255,255,0.08)_0_4px,transparent_4px_8px)]" />
        )}
      </div>
      {showLabel && (
        <span className="w-14 shrink-0 text-right font-mono text-micro text-ink-muted">
          {known ? `${value}%` : "—"}
        </span>
      )}
    </div>
  );
}
