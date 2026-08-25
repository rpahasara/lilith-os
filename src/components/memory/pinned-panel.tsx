"use client";

import { Pin } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { CATEGORY_META, type Accent, type MemoryRecord } from "@/lib/memory/types";
import { cn } from "@/lib/utils";

const TEXT: Record<Accent, string> = {
  violet: "text-violet-bright",
  cyan: "text-cyan-bright",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
  faint: "text-ink-faint",
};

/** Pinned first, then by importance — the memories Lilith treats as load-bearing. */
export function PinnedPanel({
  records,
  onSelect,
}: {
  records: MemoryRecord[];
  onSelect: (r: MemoryRecord) => void;
}) {
  const items = [...records]
    .sort(
      (a, b) =>
        Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) ||
        (b.importance ?? 0) - (a.importance ?? 0),
    )
    .slice(0, 5);

  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Pinned & important"
        action={<Pin className="h-3.5 w-3.5 text-violet-bright/70" />}
      />

      <ul className="mt-4 space-y-2">
        {items.map((r) => {
          const cat = CATEGORY_META[r.category];
          const CatIcon = cat.icon;
          return (
            <li key={r.id}>
              <button
                onClick={() => onSelect(r)}
                className="group flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
              >
                <CatIcon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", TEXT[cat.accent])} />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-xs text-ink-muted group-hover:text-ink">
                    {r.summary}
                  </span>
                </span>
                {r.pinned && (
                  <Pin className="mt-0.5 h-3 w-3 shrink-0 fill-current text-violet-bright/80" />
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </GlassCard>
  );
}
