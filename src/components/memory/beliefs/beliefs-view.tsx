"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Scale, Search } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Eyebrow, WorkspaceHeader } from "@/components/ui/primitives";
import { WorkspaceUnavailable } from "@/components/ui/data-state";
import { DetailDrawer, EmptyState, FilterTabs, StatusBadge, type FilterItem } from "@/components/ui/workspace";
import { MemoryViewSwitch } from "@/components/memory/memory-view-switch";
import { fetchBelief, fetchWorld, WORLD_LIST_LIMIT } from "@/lib/world/client";
import {
  EPISTEMIC, LIFECYCLE, NO_FILTERS, TIER, confidenceBasis, countBeliefs, countLine, evidenceLine,
  filterBeliefs, formatStamp, formatValue, groupBySubject, humanize, stampTime,
  type BeliefFilters, type EpistemicFilter, type LifecycleFilter,
} from "@/lib/world/present";
import { toDiagnostics } from "@/lib/api";
import type { Belief, ConfidenceTier, WorldReadResult } from "@/lib/world/types";
import { cn } from "@/lib/utils";

/**
 * Memory → Beliefs: the World Model, read-only.
 *
 * Beliefs are LILITH's current interpretation of facts, reconciled from
 * evidence. They sit beside the memory lenses but are a different structure,
 * and the page says so. Every number is counted from the beliefs on screen;
 * owner-context beliefs are never requested or shown (see lib/world/client).
 */

export const BELIEFS_IDENTITY = {
  icon: Scale,
  eyebrow: "Memory · Beliefs",
  title: "Beliefs",
  description:
    "The World Model's current interpretation of what LILITH has received. Beliefs are neither memories nor verified facts: each shows how it was received, how consistently its sources agree and what supports it. Read-only.",
};

const DOT: Record<ConfidenceTier, string> = {
  high: "bg-green",
  medium: "bg-cyan-bright",
  low: "bg-amber",
  unknown: "bg-white/30",
};

function Confidence({ belief }: { belief: Belief }) {
  const { tier, value } = belief.confidence;
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-micro text-ink-faint" title={confidenceBasis(belief.confidence.basis)}>
      <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", DOT[tier])} />
      {TIER[tier]} · {value.toFixed(2)}
    </span>
  );
}

function Lifecycle({ belief }: { belief: Belief }) {
  if (belief.lifecycleState === "SUPERSEDED") return null;
  const l = LIFECYCLE[belief.lifecycleState];
  return <StatusBadge label={l.label} tone={l.tone} />;
}

/** One fact about a subject; opens the inspector. */
function FactRow({ belief, selected, onOpen }: { belief: Belief; selected: boolean; onOpen: (b: Belief) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(belief)}
        aria-pressed={selected}
        data-belief-key=""
        className={cn(
          "group w-full rounded-[var(--radius-md)] border px-3.5 py-3 text-left transition-colors",
          selected ? "border-wine-bright/35 bg-wine/10" : "border-white/[0.05] bg-white/[0.015] hover:border-white/12 hover:bg-white/[0.03]",
        )}
      >
        <span className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <span className="font-mono text-micro uppercase tracking-wider text-ink-faint">{humanize(belief.predicate)}</span>
          <Confidence belief={belief} />
        </span>
        <span className="mt-1 block text-sm text-ink [overflow-wrap:anywhere]">{formatValue(belief.value)}</span>
        <span className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-micro text-ink-faint">
          <Lifecycle belief={belief} />
          <span>{EPISTEMIC[belief.epistemicState]?.label ?? humanize(belief.epistemicState)}</span>
          <span aria-hidden>·</span>
          <span>{belief.provenance.length} {belief.provenance.length === 1 ? "piece" : "pieces"} of evidence</span>
        </span>
      </button>
    </li>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3 py-2 text-xs">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="text-ink-muted [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

/** The read-only inspector for one belief. */
function Inspector({ belief, subject, notice }: { belief: Belief; subject: string; notice?: string }) {
  const epi = EPISTEMIC[belief.epistemicState];
  const life = belief.lifecycleState === "SUPERSEDED" ? null : LIFECYCLE[belief.lifecycleState];
  const conflicts = belief.contradictedBy?.length ?? 0;
  return (
    <div className="space-y-5" data-belief-inspector="">
      {notice && <p role="status" className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-xs text-ink-muted">{notice}</p>}

      <section>
        <Eyebrow>Current interpretation</Eyebrow>
        <p className="mt-1.5 text-lg font-medium text-ink [overflow-wrap:anywhere]">{formatValue(belief.value)}</p>
        <p className="mt-1 text-xs text-ink-faint">{humanize(belief.predicate)} of {subject}</p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
          <Eyebrow>How LILITH received this</Eyebrow>
          <p className="mt-1 text-sm font-medium text-ink">{epi?.label ?? humanize(belief.epistemicState)}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-ink-faint">{epi?.detail}</p>
        </div>
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
          <Eyebrow>Status</Eyebrow>
          <p className="mt-1 text-sm font-medium text-ink">{life?.label ?? "Superseded"}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-ink-faint">{life?.detail}</p>
        </div>
      </section>

      {conflicts > 0 && (
        <section className="rounded-2xl border border-amber/25 bg-amber/[0.06] p-3" data-belief-conflict="">
          <Eyebrow className="text-amber">Unresolved conflict</Eyebrow>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">
            {conflicts === 1 ? "One competing claim is" : `${conflicts} competing claims are`} recorded against this belief. The store
            does not expose the competing values yet, so only the current interpretation is shown.
          </p>
        </section>
      )}

      <section>
        <Eyebrow>Confidence</Eyebrow>
        <div className="mt-2 flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div className={cn("h-full rounded-full", DOT[belief.confidence.tier])} style={{ width: `${Math.round(belief.confidence.value * 100)}%` }} />
          </div>
          <span className="font-mono text-xs text-ink">{TIER[belief.confidence.tier]} · {belief.confidence.value.toFixed(2)}</span>
        </div>
        <p className="mt-1.5 text-xs text-ink-faint">{confidenceBasis(belief.confidence.basis)}. Derived from fixed rules about its sources; it says how consistently they agree, not whether this is true.</p>
      </section>

      <section>
        <Eyebrow>Timeline</Eyebrow>
        <dl className="mt-1 divide-y divide-white/[0.05]">
          {belief.observedAt && <Row label="Observed">{formatStamp(belief.observedAt) ?? belief.observedAt}</Row>}
          <Row label="First held">{formatStamp(belief.createdAt) ?? belief.createdAt}</Row>
          <Row label="Last reconciled">{formatStamp(belief.updatedAt) ?? belief.updatedAt}</Row>
          <Row label="Revision">{belief.revision}</Row>
          {belief.expiresAt && <Row label="Fresh until">{formatStamp(belief.expiresAt) ?? belief.expiresAt}</Row>}
        </dl>
      </section>

      <section>
        <Eyebrow>Evidence · {belief.provenance.length}</Eyebrow>
        {belief.provenance.length === 0 ? (
          <p className="mt-1.5 text-xs text-ink-faint">No current evidence is recorded for this belief.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {belief.provenance.map((p, i) => {
              const e = evidenceLine(p);
              return (
                <li key={i} className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5" data-belief-evidence="">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <span className="text-xs font-medium text-ink">{e.source}</span>
                    {e.confidence && <span className="font-mono text-micro text-ink-faint">{e.confidence}</span>}
                  </div>
                  <p className="mt-0.5 text-micro text-ink-faint">{[e.kind, e.when && `observed ${e.when}`].filter(Boolean).join(" · ")}</p>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <p className="border-t border-white/[0.06] pt-3 text-micro leading-relaxed text-ink-faint">
        Read-only. This is the World Model&apos;s current interpretation of what it received, not a verified fact. Earlier
        values are not kept by the store yet. Source identifiers and free-text notes are not shown.
      </p>
    </div>
  );
}

export function BeliefsView() {
  const [state, setState] = useState<WorldReadResult | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [filters, setFilters] = useState<BeliefFilters>(NO_FILTERS);
  const [open, setOpen] = useState<Belief | null>(null);
  const [detail, setDetail] = useState<{ key: string; belief: Belief | null; notice?: string } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchWorld({}, ctrl.signal).then(setState);
    return () => ctrl.abort();
  }, [attempt]);

  // The inspector re-reads the belief it shows, under the same visibility rules.
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    fetchBelief(open.key, ctrl.signal).then((r) => {
      if (ctrl.signal.aborted) return;
      if (r.available) setDetail({ key: open.key, belief: r.beliefs[0] ?? null });
      else if (r.reason === "endpoint-not-live") setDetail({ key: open.key, belief: null, notice: "This belief is no longer in the current picture." });
      else setDetail({ key: open.key, belief: null, notice: "The belief could not be re-read just now; showing the copy from the list." });
    });
    return () => ctrl.abort();
  }, [open]);

  const all = useMemo(() => (state?.available ? state.beliefs : []), [state]);
  const totals = useMemo(() => countBeliefs(all), [all]);
  const shown = useMemo(() => filterBeliefs(all, filters), [all, filters]);
  const shownCounts = useMemo(() => countBeliefs(shown), [shown]);
  const subjects = useMemo(() => groupBySubject(shown), [shown]);
  const subjectTitle = useMemo(() => new Map(groupBySubject(all).map((s) => [s.id, s.title])), [all]);
  // Latest reconciliation among the beliefs shown here (not the store-wide value).
  const lastReconciled = useMemo(() => all.reduce<string | undefined>((m, b) => (!m || stampTime(b.updatedAt) > stampTime(m) ? b.updatedAt : m), undefined), [all]);

  const lifecycleTabs: FilterItem<LifecycleFilter>[] = [
    { key: "all", label: "All", count: totals.lifecycle.all },
    { key: "ACTIVE", label: LIFECYCLE.ACTIVE.label, count: totals.lifecycle.ACTIVE },
    { key: "CONFLICTED", label: LIFECYCLE.CONFLICTED.label, count: totals.lifecycle.CONFLICTED },
    { key: "STALE", label: LIFECYCLE.STALE.label, count: totals.lifecycle.STALE },
  ];
  const kinds = Object.keys(totals.epistemic) as (keyof typeof EPISTEMIC)[];
  const epistemicTabs: FilterItem<EpistemicFilter>[] = [
    { key: "all", label: "Any source" },
    ...kinds.map((k) => ({ key: k, label: EPISTEMIC[k]?.label ?? humanize(k), count: totals.epistemic[k] })),
  ];
  const filtered = filters.lifecycle !== "all" || filters.epistemic !== "all" || filters.query.trim() !== "";
  const close = useCallback(() => { setOpen(null); setDetail(null); }, []);
  const shownBelief = open && detail?.key === open.key && detail.belief ? detail.belief : open;
  const openSubject = open ? subjectTitle.get(`${open.entity.entityType}:${open.entity.entityId}`) ?? "this subject" : "";

  if (state && !state.available) {
    return (
      <>
        <WorkspaceUnavailable identity={BELIEFS_IDENTITY} what="Beliefs" diagnostics={state.diagnostics ?? toDiagnostics("unavailable", [])} onRetry={() => { setState(null); setAttempt((n) => n + 1); }} />
        <div className="flex justify-end"><MemoryViewSwitch active="beliefs" /></div>
      </>
    );
  }

  return (
    <>
      <WorkspaceHeader {...BELIEFS_IDENTITY} />
      <div className="flex justify-end"><MemoryViewSwitch active="beliefs" /></div>

      {state === null ? (
        <GlassCard className="p-6" animated={false} data-beliefs-state="loading">
          <Eyebrow>Reading the belief store…</Eyebrow>
        </GlassCard>
      ) : all.length === 0 ? (
        <GlassCard className="p-4" animated={false} panel data-beliefs-state="empty">
          <EmptyState icon={Scale} title="No beliefs yet" description="The belief store answered but holds no beliefs that can be shown here." />
        </GlassCard>
      ) : (
        <>
          <GlassCard className="@container p-4 sm:p-5" animated={false} data-beliefs-state="live">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="text-sm font-medium text-ink" data-beliefs-count="">{countLine(totals.beliefs, totals.subjects)}</p>
              {lastReconciled && <p className="font-mono text-micro text-ink-faint">last reconciled {formatStamp(lastReconciled) ?? lastReconciled}</p>}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-ink-faint">
              Interpretations, not verified facts: confidence describes how consistently the sources agree, and only a
              Verified belief has been independently checked. Private owner context is not shown here.{all.length >= WORLD_LIST_LIMIT && ` The store returned its first ${WORLD_LIST_LIMIT}.`}
            </p>

            {/* one row only on a wide card (56rem+); below that the filters stack and wrap, never scroll */}
            <div className="mt-4 flex flex-col gap-2.5 @4xl:flex-row @4xl:items-center">
              <FilterTabs items={lifecycleTabs} value={filters.lifecycle} onChange={(lifecycle) => setFilters((f) => ({ ...f, lifecycle }))} layoutId="beliefs-lifecycle" className="flex-wrap rounded-2xl @md:flex-nowrap @md:rounded-full" />
              {kinds.length > 1 && (
                <FilterTabs items={epistemicTabs} value={filters.epistemic} onChange={(epistemic) => setFilters((f) => ({ ...f, epistemic }))} layoutId="beliefs-epistemic" className="flex-wrap rounded-2xl @md:flex-nowrap @md:rounded-full" />
              )}
              <label className="relative @4xl:ml-auto @4xl:w-60">
                <span className="sr-only">Search beliefs</span>
                <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
                <input
                  type="search"
                  value={filters.query}
                  onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
                  placeholder="Search subjects and values"
                  className="h-9 w-full rounded-full border border-white/[0.08] bg-white/[0.03] pl-8 pr-3 text-xs text-ink placeholder:text-ink-faint focus:border-wine-bright/40"
                />
              </label>
            </div>
            {filtered && (
              <p role="status" className="mt-3 text-xs text-ink-muted" data-beliefs-shown="">
                Showing {countLine(shownCounts.beliefs, shownCounts.subjects)}
                <button type="button" onClick={() => setFilters(NO_FILTERS)} className="ml-2 text-wine-bright hover:underline">Clear filters</button>
              </p>
            )}
          </GlassCard>

          {subjects.length === 0 ? (
            <GlassCard className="p-4" animated={false} panel>
              <EmptyState icon={Search} title="No beliefs match" description="Change the filters or the search." />
            </GlassCard>
          ) : (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2" data-beliefs-subjects="">
              {subjects.map((s) => (
                <GlassCard key={s.id} className="p-4 sm:p-5" animated={false}>
                  <section aria-labelledby={`subject-${s.id}`}>
                    <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
                      <div className="min-w-0">
                        <Eyebrow>{s.typeLabel}</Eyebrow>
                        <h3 id={`subject-${s.id}`} className="mt-1 text-lead font-medium text-ink [overflow-wrap:anywhere]">{s.title}</h3>
                        {s.subtitle && <p className="text-xs text-ink-muted [overflow-wrap:anywhere]">{s.subtitle}</p>}
                      </div>
                      {s.conflicted > 0 && <StatusBadge label={`${s.conflicted} conflicted`} tone="amber" />}
                    </div>
                    <ul className="mt-3 space-y-2">
                      {s.beliefs.map((b) => <FactRow key={b.key} belief={b} selected={open?.key === b.key} onOpen={setOpen} />)}
                    </ul>
                  </section>
                </GlassCard>
              ))}
            </div>
          )}
        </>
      )}

      <DetailDrawer open={!!open} onClose={close} eyebrow="Belief" title={open ? `${humanize(open.predicate)} · ${openSubject}` : ""}>
        {shownBelief && <Inspector belief={shownBelief} subject={openSubject} notice={detail?.key === open?.key ? detail?.notice : undefined} />}
      </DetailDrawer>
    </>
  );
}
