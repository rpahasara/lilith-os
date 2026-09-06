"use client";

import { useMemo, useState } from "react";
import { useMemory } from "@/hooks/use-memory";
import type { MemoryRecord, SearchScope } from "@/lib/memory/types";
import { MemoryHeader } from "@/components/memory/memory-header";
import { MemorySearch } from "@/components/memory/memory-search";
import { MemoryConstellation } from "@/components/memory/memory-constellation";
import { CategoryFilter, type CategorySelection } from "@/components/memory/category-filter";
import { MemoryGrid } from "@/components/memory/memory-grid";
import { RecentlyLearned } from "@/components/memory/recently-learned";
import { PinnedPanel } from "@/components/memory/pinned-panel";
import { RelationshipPreview } from "@/components/memory/relationship-preview";
import { MemoryDetail } from "@/components/memory/memory-detail";
import { MemorySkeleton } from "@/components/memory/memory-skeleton";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/ui/workspace";

/** Client-side keyword match over a record. Semantic search arrives with the backend. */
function matches(r: MemoryRecord, q: string): boolean {
  const hay = [
    r.summary,
    r.content,
    r.category,
    r.kind,
    ...r.tags,
    ...r.entities.map((e) => e.label),
    r.provenance.label,
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export default function MemoryPage() {
  const { data, loading } = useMemory();
  const [category, setCategory] = useState<CategorySelection>("all");
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<SearchScope>("memory");
  const [selected, setSelected] = useState<MemoryRecord | null>(null);

  const shown = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    return data.records
      .filter((r) => (category === "all" ? true : r.category === category))
      .filter((r) => (q ? matches(r, q) : true))
      .sort(
        (a, b) =>
          Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) ||
          (b.importance ?? 0) - (a.importance ?? 0) ||
          new Date(b.updatedAt ?? 0).getTime() - new Date(a.updatedAt ?? 0).getTime(),
      );
  }, [data, category, query]);

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading || !data ? (
        <MemorySkeleton />
      ) : (
        <>
          <MemoryHeader
            overview={data.overview}
            isDemo={data.isDemo}
            diagnostics={data.diagnostics}
          />

          <MemorySearch
            query={query}
            onQuery={setQuery}
            scope={scope}
            onScope={setScope}
            resultCount={shown.length}
          />

          <div className="flex flex-wrap items-center gap-2 px-1" aria-label="Planned memory architecture">
            <span className="eyebrow mr-1">Memory model</span>
            <StatusBadge label="Episodic · planned" tone="violet" />
            <StatusBadge label="Semantic · planned" tone="cyan" />
            <StatusBadge label="Preferences · mapped" tone="green" />
            <StatusBadge label="Entities · mapped" tone="amber" />
            <StatusBadge label="Procedural · planned" tone="faint" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
            {/* memory field */}
            <div className="space-y-4">
              <MemoryConstellation
                overview={data.overview}
                records={data.records}
                active={category}
                onSelect={setCategory}
              />

              <GlassCard className="p-5" animated={false}>
                <PanelHeader
                  title="Memory shards"
                  action={
                    <span className="font-mono text-[10px] text-ink-faint">
                      {shown.length} shown
                    </span>
                  }
                />
                <div className="mt-4">
                  <CategoryFilter
                    active={category}
                    onChange={setCategory}
                    counts={data.overview.byCategory}
                    total={data.records.length}
                  />
                </div>
                <div className="mt-4">
                  <MemoryGrid records={shown} onSelect={setSelected} />
                </div>
              </GlassCard>
            </div>

            {/* cognition rail */}
            <div className="space-y-4">
              <RecentlyLearned events={data.overview.recentActivity} />
              <PinnedPanel records={data.records} onSelect={setSelected} />
              <RelationshipPreview
                entities={data.entities}
                relationships={data.relationships}
              />
            </div>
          </div>

          <MemoryDetail
            record={selected}
            allRecords={data.records}
            onClose={() => setSelected(null)}
            onSelectRelated={setSelected}
          />
        </>
      )}
    </div>
  );
}
