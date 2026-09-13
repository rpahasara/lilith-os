"use client";

import { motion } from "framer-motion";
import { SearchX } from "lucide-react";
import type { MemoryRecord } from "@/lib/memory/types";
import { staggerContainer } from "@/lib/motion";
import { ShardCard } from "./shard-card";
import { EmptyState } from "@/components/ui/workspace";

export function MemoryGrid({
  records,
  onSelect,
}: {
  records: MemoryRecord[];
  onSelect: (r: MemoryRecord) => void;
}) {
  if (records.length === 0) {
    return (
      <EmptyState icon={SearchX} title="No memories match here" description="Try another category, select a constellation node, or clear the search." className="py-16" />
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
