"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { meter } from "@/lib/motion";

export function ConfidenceBar({
  value,
  className,
  showLabel = true,
}: {
  value: number;
  className?: string;
  showLabel?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-orchid-bright to-cyan-bright"
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={meter}
        />
      </div>
      {showLabel && (
        <span className="w-8 shrink-0 text-right font-mono text-micro text-ink-muted">
          {value}%
        </span>
      )}
    </div>
  );
}
