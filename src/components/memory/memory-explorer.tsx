"use client";

import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Search, SearchX, SlidersHorizontal, X } from "lucide-react";
import type { MemoryData, MemoryRecord } from "@/lib/memory/types";
import {
  EMPTY_FILTERS,
  activeFilterCount,
  applyFilters,
  coverage,
  facetIsUseful,
  facetNote,
  facets as computeFacets,
  sortRecords,
  type ExplorerFilters,
  type FacetValue,
  type Facets,
  type SortKey,
} from "@/lib/memory/explorer";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/ui/workspace";
import { MemoryDetail, MemoryDetailBody, MemoryReadOnlyFooter } from "./memory-detail";
import { MemoryRow, ROW_COLUMNS } from "./memory-row";

/** Two panes need room; below this the detail opens as a drawer instead. */
const WIDE = "(min-width: 1280px)";
function useWide(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const mq = window.matchMedia(WIDE);
      mq.addEventListener("change", notify);
      return () => mq.removeEventListener("change", notify);
    },
    () => window.matchMedia(WIDE).matches,
    () => false,
  );
}

type FacetKey = Exclude<keyof Facets, never>;
const FACET_TITLE: Record<FacetKey, string> = {
  categories: "Category",
  sources: "Source",
  kinds: "Classification",
  confidence: "Confidence",
  time: "When",
};
const FACET_ORDER: FacetKey[] = ["categories", "sources", "kinds", "confidence", "time"];

/**
 * The Memory Archive: search first, then a list of evidence on the left and
 * the selected memory in full on the right. Read-only, and only what the
 * backend returned — see `lib/memory/explorer`.
 */
export function MemoryExplorer({ data }: { data: MemoryData }) {
  const wide = useWide();
  const [filters, setFilters] = useState<ExplorerFilters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<SortKey>("newest");
  const [refine, setRefine] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const refineId = useId();
  const list = useRef<HTMLDivElement | null>(null);

  // One clock reading per data load keeps "last 7 days" stable while browsing.
  const now = useMemo(() => Date.now(), [data.records]); // eslint-disable-line react-hooks/exhaustive-deps
  const available = useMemo(() => computeFacets(data.records, now), [data.records, now]);
  const shown = useMemo(
    () => sortRecords(applyFilters(data.records, filters, now), sort),
    [data.records, filters, sort, now],
  );
  const selected = data.records.find((r) => r.id === selectedId) ?? null;
  const active = activeFilterCount(filters);
  const filtering = active > 0 || filters.query.trim() !== "";
  const entityFilter = filters.entityId
    ? (data.entities.find((e) => e.id === filters.entityId)?.label ??
      data.records.flatMap((r) => r.entities).find((e) => e.id === filters.entityId)?.label ??
      "one entity")
    : null;
  const canSortByConfidence = data.records.some((r) => typeof r.confidence === "number");

  // A selection that the filters have hidden is released, so the pane never
  // shows a memory that is not in the list beside it.
  useEffect(() => {
    if (selectedId && !shown.some((r) => r.id === selectedId)) setSelectedId(null);
  }, [shown, selectedId]);

  function toggle<K extends FacetKey>(facet: K, key: ExplorerFilters[K][number]) {
    setFilters((f) => {
      const current = f[facet] as string[];
      const next = current.includes(key) ? current.filter((k) => k !== key) : [...current, key];
      return { ...f, [facet]: next };
    });
  }

  function onRowKey(e: React.KeyboardEvent<HTMLButtonElement>) {
    const rows = [...(list.current?.querySelectorAll<HTMLButtonElement>("[data-memory-row]") ?? [])];
    const at = rows.indexOf(e.currentTarget);
    const to =
      e.key === "ArrowDown" ? Math.min(rows.length - 1, at + 1)
      : e.key === "ArrowUp" ? Math.max(0, at - 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? rows.length - 1
      : -1;
    if (to < 0 || to === at) return;
    e.preventDefault();
    rows[to].focus();
    // With the pane beside the list, moving through it reads each memory. In a
    // drawer that would open and close on every key, so there Enter selects.
    if (wide) setSelectedId(rows[to].getAttribute("data-memory-row"));
  }

  const focusable = selectedId && shown.some((r) => r.id === selectedId) ? selectedId : shown[0]?.id;

  return (
    <div className="space-y-4" data-memory-explorer="">
      {/* ------------------------------------------------------------ search */}
      <div role="search" className="space-y-3">
        <div className="flex items-center gap-3 rounded-xl border border-white/[0.09] bg-black/25 px-4 py-3 transition-colors focus-within:border-wine/40">
          <Search aria-hidden className="h-4 w-4 shrink-0 text-ink-faint" />
          <input
            type="search"
            value={filters.query}
            onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
            placeholder="Search what Lilith remembers…"
            aria-label="Search Lilith's memory"
            className="w-full bg-transparent text-lead text-ink outline-none placeholder:text-ink-faint focus-visible:outline-none! [&::-webkit-search-cancel-button]:hidden"
          />
          {filters.query && (
            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, query: "" }))}
              aria-label="Clear search"
              className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white/[0.06] text-ink-faint hover:text-ink"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <button
            type="button"
            onClick={() => setRefine((v) => !v)}
            aria-expanded={refine}
            aria-controls={refineId}
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-caption transition-colors",
              refine || active > 0 ? "border-wine/30 bg-wine/[0.08] text-ink" : "border-white/[0.09] text-ink-muted hover:text-ink",
            )}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Refine
            {active > 0 && <span className="font-mono text-micro text-wine-bright">{active}</span>}
          </button>

          {/* what is narrowing the list, each removable */}
          {FACET_ORDER.flatMap((facet) =>
            (filters[facet] as string[]).map((key) => {
              const value = (available[facet] as FacetValue<string>[]).find((v) => v.key === key);
              return (
                <ActiveChip key={`${facet}:${key}`} label={`${FACET_TITLE[facet]}: ${value?.label ?? key}`}
                  onRemove={() => toggle(facet, key as never)} />
              );
            }),
          )}
          {entityFilter && (
            <ActiveChip label={`About: ${entityFilter}`} onRemove={() => setFilters((f) => ({ ...f, entityId: null }))} />
          )}
          {filtering && (
            <button
              type="button"
              onClick={() => setFilters(EMPTY_FILTERS)}
              className="text-caption text-ink-faint underline-offset-2 hover:text-ink hover:underline"
            >
              Clear all
            </button>
          )}

          <p role="status" aria-live="polite" className="ml-auto font-mono text-micro text-ink-faint" data-result-count={shown.length}>
            {shown.length === data.records.length
              ? `${shown.length} ${shown.length === 1 ? "memory" : "memories"}`
              : `${shown.length} of ${data.records.length}`}
          </p>
          <div className="flex items-center gap-0.5 rounded-full border border-white/[0.07] p-0.5" role="group" aria-label="Sort">
            <SortButton on={sort === "newest"} onClick={() => setSort("newest")}>Newest</SortButton>
            {canSortByConfidence && (
              <SortButton on={sort === "confidence"} onClick={() => setSort("confidence")}>Confidence</SortButton>
            )}
          </div>
        </div>

        {refine && (
          <div id={refineId} className="grid gap-x-8 gap-y-4 rounded-xl border border-white/[0.07] bg-black/20 p-4 sm:grid-cols-2 xl:grid-cols-5">
            {FACET_ORDER.map((facet) => {
              const values = available[facet] as FacetValue<string>[];
              return (
                <fieldset key={facet} data-facet={facet} className="min-w-0">
                  <legend className="eyebrow">{FACET_TITLE[facet]}</legend>
                  {facetIsUseful(values) ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {values.map((v) => {
                        const on = (filters[facet] as string[]).includes(v.key);
                        return (
                          <button
                            key={v.key}
                            type="button"
                            aria-pressed={on}
                            onClick={() => toggle(facet, v.key as never)}
                            className={cn(
                              "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-caption transition-colors",
                              on ? "border-wine/35 bg-wine/[0.12] text-ink" : "border-white/[0.08] text-ink-muted hover:border-white/20 hover:text-ink",
                            )}
                          >
                            {v.label}
                            <span className="font-mono text-micro text-ink-faint">{v.count}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="mt-2 text-caption leading-snug text-ink-faint" data-facet-note="">{facetNote(facet, values)}</p>
                  )}
                </fieldset>
              );
            })}
          </div>
        )}
      </div>

      {/* --------------------------------------------------------- two panes */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,430px)] xl:items-start">
        <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-black/20">
          <div aria-hidden className={cn("hidden border-b border-white/[0.06] px-4 py-2 font-mono text-micro uppercase tracking-[0.12em] text-ink-faint", ROW_COLUMNS)}>
            <span className="pl-4">Memory</span>
            <span>Source</span>
            <span>Class</span>
            <span>Confidence</span>
            <span className="text-right">When</span>
          </div>
          {shown.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title="No memory matches"
              description={
                data.records.length === 0
                  ? "Lilith has no memories to show yet."
                  : "Nothing Lilith remembers fits this search and these filters. Nothing is hidden: widen them to see the rest."
              }
              action={
                filtering && (
                  <button
                    type="button"
                    onClick={() => setFilters(EMPTY_FILTERS)}
                    className="rounded-full border border-white/[0.1] bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
                  >
                    Clear search and filters
                  </button>
                )
              }
            />
          ) : (
            <div ref={list} role="listbox" aria-label="Memories" aria-orientation="vertical" className="divide-y divide-white/[0.05]">
              {shown.map((r) => (
                <MemoryRow
                  key={r.id}
                  record={r}
                  selected={r.id === selectedId}
                  tabIndex={r.id === focusable ? 0 : -1}
                  onSelect={(rec) => setSelectedId(rec.id)}
                  onKeyDown={onRowKey}
                />
              ))}
            </div>
          )}
        </div>

        {/* the selected memory, beside the list when there is room */}
        {wide && (
          <aside aria-label={selected ? "Selected memory" : "About this archive"} className="glass sticky top-0 flex max-h-[calc(100dvh-11rem)] flex-col overflow-hidden rounded-xl">
            {selected ? (
              <>
                <div className="scroll-area min-h-0 flex-1 overflow-y-auto p-5">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <h2 className="text-body font-semibold leading-snug tracking-[-0.01em] text-ink">{selected.summary}</h2>
                    <button
                      type="button"
                      onClick={() => setSelectedId(null)}
                      aria-label="Close memory"
                      className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-ink-faint transition-colors hover:bg-white/[0.06] hover:text-ink"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <MemoryDetailBody
                    record={selected}
                    allRecords={data.records}
                    entities={data.entities}
                    relationships={data.relationships}
                    onSelectRelated={(r) => setSelectedId(r.id)}
                    onFilterEntity={(id) => setFilters((f) => ({ ...f, entityId: id }))}
                  />
                </div>
                <div className="border-t border-white/[0.06] p-4">
                  <MemoryReadOnlyFooter />
                </div>
              </>
            ) : (
              <ArchiveOverview data={data} available={available} />
            )}
          </aside>
        )}
      </div>

      {!wide && (
        <MemoryDetail
          record={selected}
          allRecords={data.records}
          entities={data.entities}
          relationships={data.relationships}
          onClose={() => setSelectedId(null)}
          onSelectRelated={(r) => setSelectedId(r.id)}
          onFilterEntity={(id) => {
            setFilters((f) => ({ ...f, entityId: id }));
            setSelectedId(null);
          }}
        />
      )}
    </div>
  );
}

function ActiveChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="flex items-center gap-1 rounded-full border border-white/[0.09] bg-white/[0.04] py-1 pl-2.5 pr-1 text-caption text-ink-muted" data-active-filter="">
      {label}
      <button type="button" onClick={onRemove} aria-label={`Remove filter ${label}`}
        className="grid h-5 w-5 place-items-center rounded-full text-ink-faint hover:bg-white/[0.08] hover:text-ink">
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

function SortButton({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick}
      className={cn("rounded-full px-2.5 py-1 text-caption transition-colors", on ? "bg-white/10 text-ink" : "text-ink-faint hover:text-ink-muted")}>
      {children}
    </button>
  );
}

/**
 * Shown while nothing is selected: what the archive holds, and how much of
 * each kind of metadata the source actually supplied. Counts only.
 */
function ArchiveOverview({ data, available }: { data: MemoryData; available: Facets }) {
  const c = coverage(data.records);
  const rows: [string, number][] = [
    ["Classification stated", c.classified],
    ["Confidence stated", c.withConfidence],
    ["Dated", c.dated],
    ["Entities attached", c.withEntities],
    ["Linked to other memories", c.linked],
  ];
  return (
    <div className="scroll-area overflow-y-auto p-5" data-archive-overview="">
      <h2 className="text-body font-semibold tracking-[-0.01em] text-ink">Select a memory to read it in full</h2>
      <p className="mt-1 text-caption leading-relaxed text-ink-muted">
        Each one opens here with its source, what kind of claim it is, and what it connects to.
      </p>

      <dl className="mt-5 grid grid-cols-3 gap-3">
        {[
          ["Memories", c.total],
          ["Entities", data.entities.length],
          ["Relations", data.relationships.length],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="eyebrow">{label}</dt>
            <dd className="mt-1 font-mono text-xl text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      <h3 className="eyebrow mt-6">By source</h3>
      <ul className="mt-2 space-y-1">
        {available.sources.map((s) => (
          <li key={s.key} className="flex items-center justify-between text-caption text-ink-muted">
            {s.label}
            <span className="font-mono text-micro text-ink-faint">{s.count}</span>
          </li>
        ))}
      </ul>

      <h3 className="eyebrow mt-6">What the source records</h3>
      <ul className="mt-2 space-y-1" data-coverage="">
        {rows.map(([label, n]) => (
          <li key={label} className="flex items-center justify-between text-caption text-ink-muted">
            {label}
            <span className={cn("font-mono text-micro", n === 0 ? "text-ink-faint" : "text-ink-muted")}>
              {n} of {c.total}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-micro leading-relaxed text-ink-faint">
        Where the source says nothing, the Archive shows a dash. It does not guess a classification or a confidence.
      </p>
    </div>
  );
}
