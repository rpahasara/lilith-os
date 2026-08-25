"use client";

import { motion } from "framer-motion";
import { Pin } from "lucide-react";
import { CATEGORY_META, type Accent, type MemoryRecord } from "@/lib/memory/types";
import { riseIn } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { ProvenanceBadge, KindTag } from "./provenance-badge";
import { ConfidenceMeter } from "./confidence-meter";

const ACCENT_VAR: Record<Accent, string> = {
  violet: "var(--violet-bright)",
  cyan: "var(--cyan-bright)",
  green: "var(--green)",
  amber: "var(--amber)",
  rose: "var(--rose)",
  faint: "var(--ink-faint)",
};

/**
 * A single memory "shard" — something Lilith knows. Read-only: selecting it
 * opens the detail drawer. No edit/forget affordances (deferred until a backend
 * approval flow exists).
 */
export function ShardCard({
  record,
  onSelect,
}: {
  record: MemoryRecord;
  onSelect: (r: MemoryRecord) => void;
}) {
  const cat = CATEGORY_META[record.category];
  const color = ACCENT_VAR[cat.accent];
  const CatIcon = cat.icon;

  return (
    <motion.button
      type="button"
      variants={riseIn}
      onClick={() => onSelect(record)}
      whileHover={{ y: -3 }}
      transition={{ type: "spring", stiffness: 320, damping: 30 }}
      className="glass group relative w-full overflow-hidden rounded-[var(--radius-md)] p-4 text-left transition-colors hover:border-white/15"
    >
      {/* category accent seam + soft confidence glow */}
      <span
        className="pointer-events-none absolute inset-y-0 left-0 w-[2px]"
        style={{ background: color, opacity: 0.5 }}
      />
      <span
        className="pointer-events-none absolute -left-8 top-1/2 h-24 w-24 -translate-y-1/2 rounded-full blur-2xl transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: color, opacity: 0.05 + (record.confidence ?? 0) / 100 * 0.12 }}
      />

      {/* header row */}
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-medium" style={{ color }}>
          <CatIcon className="h-3 w-3" />
          {cat.label}
        </span>
        <div className="flex items-center gap-1.5">
          {record.pinned && <Pin className="h-3 w-3 fill-current text-violet-bright" />}
          <KindTag kind={record.kind} />
        </div>
      </div>

      {/* summary */}
      <p className="mt-2 line-clamp-2 text-sm leading-snug text-ink">{record.summary}</p>

      {/* entities */}
      {record.entities.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1">
          {record.entities.slice(0, 3).map((e) => (
            <span
              key={e.id}
              className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-ink-muted"
            >
              {e.label}
            </span>
          ))}
          {record.entities.length > 3 && (
            <span className="px-1 py-0.5 text-[10px] text-ink-faint">
              +{record.entities.length - 3}
            </span>
          )}
        </div>
      )}

      {/* footer: provenance + confidence */}
      <div className="mt-3 flex items-center justify-between gap-3">
        <ProvenanceBadge provenance={record.provenance} />
        <div className="w-24">
          <ConfidenceMeter value={record.confidence} showLabel={false} />
        </div>
      </div>
    </motion.button>
  );
}
