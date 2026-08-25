"use client";

import { motion } from "framer-motion";
import { SearchX } from "lucide-react";
import type { MemoryRecord } from "@/lib/memory/types";
import { staggerContainer } from "@/lib/motion";
import { ShardCard } from "./shard-card";

export function MemoryGrid({
  records,
  onSelect,
}: {
  records: MemoryRecord[];
  onSelect: (r: MemoryRecord) => void;
}) {
  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
        <SearchX className="h-6 w-6 text-ink-faint" />
        <p className="text-sm text-ink-muted">No memories match here.</p>
        <p className="text-xs text-ink-faint">
          Try a different category or clear the search.
        </p>
      </div>
    );
  }

  return (
    <motion.div
      // re-key by the visible set so cards restagger when filters change
      key={records.map((r) => r.id).join(",").slice(0, 64) + records.length}
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="grid gap-3 sm:grid-cols-2"
    >
      {records.map((r) => (
        <ShardCard key={r.id} record={r} onSelect={onSelect} />
      ))}
    </motion.div>
  );
}
