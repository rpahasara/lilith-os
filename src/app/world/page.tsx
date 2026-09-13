"use client";

/**
 * World Model inspector (Slice 7) — read-only, diagnostic route at /world.
 *
 * Renders LILITH's current beliefs when the /os/world backend is live, and an
 * explicit, honest "unavailable" state otherwise. It NEVER shows invented
 * beliefs — an unavailable World Model is a rendered state, not a placeholder.
 *
 * Built with the current visual design system (WorkspaceHeader / GlassCard /
 * MetricTile / StatusBadge / EmptyState). Renders inside AppShell automatically;
 * not wired into the sidebar rail (diagnostic route, reachable at /world).
 */

import { useEffect, useState } from "react";
import { Globe2, CloudOff } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Eyebrow, PanelHeader, MetricTile, WorkspaceHeader } from "@/components/ui/primitives";
import { EmptyState, StatusBadge } from "@/components/ui/workspace";
import { fetchWorld } from "@/lib/world/client";
import type { Belief, LifecycleState, WorldReadResult } from "@/lib/world/types";

type Tone = "green" | "cyan" | "amber" | "rose" | "violet" | "faint";

const LIFECYCLE_TONE: Record<LifecycleState, Tone> = {
  ACTIVE: "green",
  CONFLICTED: "amber",
  STALE: "faint",
  SUPERSEDED: "faint",
};

function confidenceDot(tier: Belief["confidence"]["tier"]): string {
  return tier === "high"
    ? "bg-green"
    : tier === "medium"
      ? "bg-cyan-bright"
      : tier === "low"
        ? "bg-amber"
        : "bg-white/30";
}

function BeliefRow({ belief }: { belief: Belief }) {
  const c = belief.confidence;
  return (
    <div className="rounded-[var(--radius-md)] bg-white/[0.02] hairline p-4">
      <div className="flex items-baseline justify-between gap-3">
        <code className="font-mono text-xs text-ink">{belief.key}</code>
        <span className="font-mono text-[10px] text-ink-faint">r{belief.revision}</span>
      </div>
      <div className="mt-1.5 text-sm text-ink">
        {typeof belief.value === "object"
          ? JSON.stringify(belief.value)
          : String(belief.value)}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <StatusBadge label={belief.lifecycleState} tone={LIFECYCLE_TONE[belief.lifecycleState]} />
        <span className="eyebrow">{belief.epistemicState}</span>
        <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-ink-faint">
          <span className={`h-1.5 w-1.5 rounded-full ${confidenceDot(c.tier)}`} />
          {c.tier} · {c.value.toFixed(2)} · {c.basis}
        </span>
        <span className="font-mono text-[10px] text-ink-faint">
          {belief.provenance.length} evidence
        </span>
      </div>
    </div>
  );
}

function unavailableTitle(reason: Extract<WorldReadResult, { available: false }>["reason"]): string {
  return reason === "endpoint-not-live"
    ? "World Model — backend not yet implemented"
    : reason === "backend-not-configured"
      ? "World Model — backend not configured"
      : "World Model — currently unavailable";
}

export default function WorldPage() {
  const [state, setState] = useState<WorldReadResult | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchWorld({}, ctrl.signal).then(setState);
    return () => ctrl.abort();
  }, []);

  const available = state?.available === true ? state : null;
  const unavailable = state && state.available === false ? state : null;
  const meta = available?.meta;

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      <WorkspaceHeader
        icon={Globe2}
        eyebrow="Slice 7 · World Model"
        title="World Model"
        description="What LILITH currently believes is true — reconciled from observations, tasks and memory, with provenance and confidence on every belief. Read-only; beliefs are never mutated from here."
        diagnostics={available?.diagnostics}
      />

      {state === null ? (
        <GlassCard className="p-6" animated={false}>
          <Eyebrow>Reading belief store…</Eyebrow>
        </GlassCard>
      ) : available ? (
        <>
          <GlassCard className="p-5" animated={false} panel>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <MetricTile label="Beliefs" value={meta?.total ?? available.beliefs.length} accent="cyan" />
              <MetricTile label="Active" value={meta?.byLifecycle?.ACTIVE ?? 0} accent="green" />
              <MetricTile label="Conflicted" value={meta?.conflicted ?? 0} accent="amber" />
              <MetricTile label="Stale" value={meta?.stale ?? 0} accent="faint" />
            </div>
          </GlassCard>

          <GlassCard className="p-5" animated={false}>
            <PanelHeader
              title="Current beliefs"
              action={
                <StatusBadge
                  label={`Live · ${available.beliefs.length}`}
                  tone="green"
                />
              }
            />
            <div className="mt-4 space-y-2">
              {available.beliefs.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  The store is live but holds no beliefs yet.
                </p>
              ) : (
                available.beliefs.map((b) => <BeliefRow key={b.key} belief={b} />)
              )}
            </div>
          </GlassCard>
        </>
      ) : unavailable ? (
        <GlassCard className="p-4" animated={false} panel>
          <EmptyState
            icon={unavailable.reason === "endpoint-not-live" ? Globe2 : CloudOff}
            title={unavailableTitle(unavailable.reason)}
            description={`${unavailable.detail}  (reason: ${unavailable.reason}). No beliefs are shown until the backend responds — by design.`}
          />
        </GlassCard>
      ) : null}
    </div>
  );
}
