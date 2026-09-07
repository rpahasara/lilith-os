"use client";

/**
 * World Model inspector (Slice 7 Phase A) — read-only.
 *
 * Renders LILITH's current beliefs when the /os/world backend is live, and an
 * explicit, honest "backend pending" state otherwise. It NEVER shows invented
 * beliefs: an unavailable World Model is a rendered state, not a placeholder.
 *
 * Not wired into the primary nav by design — this is a diagnostic/inspection
 * surface for Phase A, reachable at /world. The nav/IA visual constants are
 * intentionally left untouched until the backend ships (Phase B).
 */

import { useEffect, useState } from "react";
import { Globe2 } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Eyebrow, PanelHeader } from "@/components/ui/primitives";
import { fetchWorld } from "@/lib/world/client";
import { WORLD_MODEL_PHASE } from "@/lib/world/types";
import type { Belief, WorldReadResult } from "@/lib/world/types";

function ConfidenceTag({ belief }: { belief: Belief }) {
  const t = belief.confidence.tier;
  const dot =
    t === "high"
      ? "bg-green-400"
      : t === "medium"
        ? "bg-cyan-bright"
        : t === "low"
          ? "bg-amber-400"
          : "bg-white/30";
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-ink-faint">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {t} · {belief.confidence.value.toFixed(2)} · {belief.confidence.basis}
    </span>
  );
}

function BeliefRow({ belief }: { belief: Belief }) {
  return (
    <div className="rounded-xl bg-white/[0.02] hairline p-4">
      <div className="flex items-baseline justify-between gap-3">
        <code className="font-mono text-xs text-ink">{belief.key}</code>
        <span className="font-mono text-[10px] text-ink-faint">
          r{belief.revision}
        </span>
      </div>
      <div className="mt-1.5 text-sm text-ink">
        {typeof belief.value === "object"
          ? JSON.stringify(belief.value)
          : String(belief.value)}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-[10px] uppercase tracking-wide text-ink-muted">
          {belief.lifecycleState} · {belief.epistemicState}
        </span>
        <ConfidenceTag belief={belief} />
        <span className="font-mono text-[10px] text-ink-faint">
          {belief.provenance.length} evidence
        </span>
      </div>
    </div>
  );
}

/** Honest empty/pending state — names the exact reason the store is unavailable. */
function PendingState({ result }: { result: Extract<WorldReadResult, { available: false }> }) {
  const phaseB = result.reason === "endpoint-not-live";
  return (
    <GlassCard className="p-6" animated={false}>
      <div className="flex flex-col items-start gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-white/[0.04] hairline">
          <Globe2 className="h-5 w-5 text-ink-muted" />
        </div>
        <div>
          <h2 className="text-base font-medium tracking-tight text-ink">
            {phaseB
              ? "World Model — backend not yet implemented"
              : "World Model — currently unavailable"}
          </h2>
          <p className="mt-1.5 max-w-prose text-sm text-ink-muted">
            {result.detail}
          </p>
        </div>
        <div className="mt-1 rounded-lg bg-white/[0.02] hairline px-3 py-2 font-mono text-[11px] text-ink-faint">
          reason: {result.reason}
        </div>
        {phaseB && (
          <p className="max-w-prose text-xs text-ink-faint">
            The durable belief store, controlled ingestion, and reconciliation
            ship in Slice&nbsp;7 Phase&nbsp;B on the backend. This surface goes
            live automatically once <code className="font-mono">/os/world</code>{" "}
            responds — no frontend change required. No beliefs are shown until
            then, by design.
          </p>
        )}
      </div>
    </GlassCard>
  );
}

export default function WorldPage() {
  const [state, setState] = useState<WorldReadResult | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchWorld({}, ctrl.signal).then(setState);
    return () => ctrl.abort();
  }, []);

  return (
    <div className="scroll-area h-full space-y-4 overflow-y-auto pb-6 pr-1">
      <GlassCard className="p-5" animated={false}>
        <PanelHeader
          title="World Model"
          action={
            <Eyebrow className="flex items-center gap-2">
              <span className="h-1 w-1 rounded-full bg-cyan-bright" />
              Slice 7 · Phase {WORLD_MODEL_PHASE}
            </Eyebrow>
          }
        />
        <p className="mt-3 max-w-prose text-sm text-ink-muted">
          What LILITH currently believes is true — reconciled from observations,
          tasks and memory, with provenance and confidence on every belief.
          Read-only; beliefs are never mutated from here.
        </p>
      </GlassCard>

      {state === null ? (
        <GlassCard className="p-6" animated={false}>
          <span className="font-mono text-xs text-ink-faint">
            Reading belief store…
          </span>
        </GlassCard>
      ) : state.available ? (
        <GlassCard className="p-5" animated={false}>
          <PanelHeader
            title="Current beliefs"
            action={
              <span className="font-mono text-[10px] text-ink-faint">
                {state.beliefs.length} beliefs
                {state.meta ? ` · ${state.meta.conflicted} conflicted` : ""}
              </span>
            }
          />
          <div className="mt-4 space-y-2">
            {state.beliefs.length === 0 ? (
              <p className="text-sm text-ink-muted">
                The store is live but holds no beliefs yet.
              </p>
            ) : (
              state.beliefs.map((b) => <BeliefRow key={b.key} belief={b} />)
            )}
          </div>
        </GlassCard>
      ) : (
        <PendingState result={state} />
      )}
    </div>
  );
}
