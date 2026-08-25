"use client";

import { motion } from "framer-motion";
import { Layers } from "lucide-react";
import {
  CATEGORIES,
  CATEGORY_META,
  type Accent,
  type MemoryCategory,
} from "@/lib/memory/types";
import { cn } from "@/lib/utils";

const DOT: Record<Accent, string> = {
  violet: "bg-violet-bright",
  cyan: "bg-cyan-bright",
  green: "bg-green",
  amber: "bg-amber",
  rose: "bg-rose",
  faint: "bg-white/30",
};

export type CategorySelection = MemoryCategory | "all";

export function CategoryFilter({
  active,
  onChange,
  counts,
  total,
}: {
  active: CategorySelection;
  onChange: (c: CategorySelection) => void;
  counts: Record<MemoryCategory, number>;
  total: number;
}) {
  const items: { key: CategorySelection; label: string; dot?: Accent; count: number }[] = [
    { key: "all", label: "All", count: total },
    ...CATEGORIES.map((c) => ({
      key: c,
      label: CATEGORY_META[c].label,
      dot: CATEGORY_META[c].accent,
      count: counts[c] ?? 0,
    })),
  ];

  return (
    <div className="scroll-area flex gap-1 overflow-x-auto rounded-full border border-white/[0.06] bg-white/[0.02] p-1">
      {items.map((it) => {
        const on = active === it.key;
        return (
          <button
            key={it.key}
            onClick={() => onChange(it.key)}
            className={cn(
              "relative flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
              on ? "text-ink" : "text-ink-faint hover:text-ink-muted",
            )}
          >
            {on && (
              <motion.span
                layoutId="memory-category-filter"
                className="absolute inset-0 rounded-full bg-white/10"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative flex items-center gap-1.5">
              {it.dot ? (
                <span className={cn("h-1.5 w-1.5 rounded-full", DOT[it.dot])} />
              ) : (
                <Layers className="h-3 w-3" />
              )}
              {it.label}
              <span className="font-mono text-[10px] text-ink-faint">{it.count}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
