"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { Clock, FlaskConical, Link2, Route, X } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { ConfidenceMeter } from "@/components/memory/confidence-meter";
import { KindTag, ProvenanceBadge } from "@/components/memory/provenance-badge";
import { REGIONS, REGION_BY_ID } from "@/lib/memory/atlas/regions";
import type { AtlasStore } from "@/lib/memory/atlas/store";
import type { AtlasNode, AtlasRegion, AtlasState, RegionId } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";

function when(ms?: number) {
  if (!ms) return "—";
  return new Date(ms).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Section({ label, children, action }: { label: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section>
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        {action}
      </div>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Shell({
  region,
  onClose,
  children,
  footer,
  className,
}: {
  region: AtlasRegion;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <GlassCard strong animated={false} className={cn("flex max-h-full min-h-0 flex-col", className)}>
      {/* a breath of the region's colour at the top edge */}
      <span
        className="pointer-events-none absolute inset-x-0 top-0 h-24 opacity-60"
        style={{ background: `radial-gradient(70% 100% at 50% 0%, ${region.color}26, transparent 70%)` }}
      />
      <div className="relative flex items-center justify-between gap-3 px-5 pt-4">
        <span className="inline-flex items-center gap-2 text-xs font-medium" style={{ color: region.color }}>
          <span className="h-2 w-2 rounded-full" style={{ background: region.color, boxShadow: `0 0 10px ${region.color}` }} />
          {region.label}
          <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint">{region.lobe}</span>
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close inspector"
          className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white/[0.06] text-ink-muted transition-colors hover:text-ink"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="scroll-area relative min-h-0 flex-1 overflow-y-auto px-5 pb-4 pt-3">{children}</div>
      {footer && <div className="relative border-t border-white/[0.06] px-5 py-3">{footer}</div>}
    </GlassCard>
  );
}

const SYNTHETIC_NOTE = (
  <p className="flex items-center gap-1.5 text-[10px] leading-relaxed text-ink-faint">
    <FlaskConical className="h-3 w-3 shrink-0 text-amber" />
    Synthetic memory — invented for this prototype. Nothing real is read or changed.
  </p>
);

/* -------------------------------------------------------------------- node */

export function NodeInspector({
  node,
  store,
  onClose,
  onSelect,
  onTrace,
  className,
}: {
  node: AtlasNode;
  store: AtlasStore;
  onClose: () => void;
  onSelect: (id: string) => void;
  onTrace: (node: AtlasNode) => void;
  className?: string;
}) {
  const region = REGION_BY_ID[node.region];
  const associations = store
    .linksOf(node.id)
    .map((link) => ({ link, other: store.node(link.source === node.id ? link.target : link.source) }))
    .filter((a): a is { link: typeof a.link; other: AtlasNode } => Boolean(a.other))
    .sort((a, b) => b.link.strength - a.link.strength);

  return (
    <Shell
      region={region}
      onClose={onClose}
      className={className}
      footer={
        <div className="space-y-2.5">
          <button
            type="button"
            onClick={() => onTrace(node)}
            disabled={associations.length === 0}
            className="group flex w-full items-center justify-center gap-2 rounded-full border border-wine/30 bg-gradient-to-r from-wine-deep/50 to-wine/30 px-4 py-2 text-xs font-medium text-ink transition-[border-color,box-shadow] hover:border-wine-bright/50 hover:shadow-[0_10px_30px_-14px_rgba(201,84,115,0.9)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Route className="h-3.5 w-3.5 text-wine-bright" />
            Trace associations from here
          </button>
          {SYNTHETIC_NOTE}
        </div>
      }
    >
      <motion.div
        key={node.id}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-5"
      >
        <div>
          <div className="flex flex-wrap items-center gap-1.5">
            <KindTag kind={node.kind} />
            {node.live && (
              <span className="rounded-full bg-wine-bright/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-wine-bright">
                Learned this session
              </span>
            )}
          </div>
          <h2 className="mt-2.5 text-[15px] font-medium leading-snug text-ink">{node.title}</h2>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{node.detail}</p>
          {node.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {node.tags.map((tag) => (
                <span key={tag} className="rounded-md bg-white/[0.045] px-2 py-0.5 text-[11px] text-ink-muted">
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>

        <Section label="Why Lilith knows this">
          <div className="rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.02] p-3">
            <ProvenanceBadge provenance={{ kind: node.provenance.kind, label: node.provenance.label }} />
            <p className="mt-2 text-xs text-ink-muted">{node.provenance.label}</p>
            <p className="mt-1 font-mono text-[10px] text-ink-faint">signal · {when(node.provenance.at)}</p>
          </div>
        </Section>

        <Section label="Confidence & importance">
          <div className="space-y-2">
            <div>
              <p className="mb-1 text-[11px] text-ink-faint">Confidence</p>
              <ConfidenceMeter value={node.confidence} />
            </div>
            <div>
              <p className="mb-1 text-[11px] text-ink-faint">Importance</p>
              <ConfidenceMeter value={node.importance} />
            </div>
          </div>
        </Section>

        {node.entities.length > 0 && (
          <Section label="Related entities">
            <div className="flex flex-wrap gap-1.5">
              {node.entities.map((entity) => (
                <span
                  key={entity}
                  className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-1 text-xs text-ink-muted"
                >
                  {entity}
                </span>
              ))}
            </div>
          </Section>
        )}

        <Section
          label="Associations"
          action={<span className="font-mono text-[10px] text-ink-faint">{associations.length} pathways</span>}
        >
          {associations.length === 0 ? (
            <p className="text-xs text-ink-faint">No pathways lead here yet.</p>
          ) : (
            <ul className="-mx-2 space-y-0.5">
              {associations.map(({ link, other }) => {
                const r = REGION_BY_ID[other.region];
                return (
                  <li key={link.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(other.id)}
                      className="group flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.045]"
                    >
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: r.color, boxShadow: `0 0 8px ${r.color}` }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-xs text-ink-muted group-hover:text-ink">{other.title}</span>
                        <span className="mt-0.5 flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
                          <Link2 className="h-2.5 w-2.5" />
                          {link.kind}
                          {link.live && <span className="text-wine-bright">· new</span>}
                        </span>
                      </span>
                      {/* strength */}
                      <span className="mt-2 h-px w-8 shrink-0 overflow-hidden rounded-full bg-white/[0.08]">
                        <span className="block h-full" style={{ width: `${link.strength * 100}%`, background: r.color }} />
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        <Section label="Timeline">
          <ul className="space-y-1.5 font-mono text-[11px] text-ink-muted">
            <li className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-ink-faint">
                <Clock className="h-3 w-3" /> Learned
              </span>
              <span>{when(node.createdAt)}</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-ink-faint">Last reinforced</span>
              <span>{when(node.reinforcedAt)}</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-ink-faint">Reinforced · recalled</span>
              <span>
                {node.reinforcements}× · {node.recalls}×
              </span>
            </li>
          </ul>
        </Section>
      </motion.div>
    </Shell>
  );
}

/* ------------------------------------------------------------------ region */

export function RegionInspector({
  region: regionId,
  state,
  store,
  onClose,
  onSelect,
  className,
}: {
  region: RegionId;
  state: AtlasState;
  store: AtlasStore;
  onClose: () => void;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const region = REGION_BY_ID[regionId];
  const members = state.nodes.filter((n) => n.region === regionId);
  const confidence = members.length
    ? Math.round(members.reduce((s, n) => s + n.confidence, 0) / members.length)
    : 0;
  const inferred = members.filter((n) => n.kind === "inference").length;

  // where this region's pathways lead
  const bridges = new Map<RegionId, number>();
  let internal = 0;
  for (const link of state.links) {
    const a = store.node(link.source);
    const b = store.node(link.target);
    if (!a || !b) continue;
    if (a.region === regionId && b.region === regionId) internal += 1;
    else if (a.region === regionId) bridges.set(b.region, (bridges.get(b.region) ?? 0) + 1);
    else if (b.region === regionId) bridges.set(a.region, (bridges.get(a.region) ?? 0) + 1);
  }
  const bridgePeak = Math.max(1, ...bridges.values());
  const strongest = [...members].sort((a, b) => b.importance - a.importance).slice(0, 6);

  return (
    <Shell region={region} onClose={onClose} className={className} footer={SYNTHETIC_NOTE}>
      <motion.div
        key={regionId}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-5"
      >
        <div>
          <h2 className="text-[15px] font-medium text-ink">{region.label}</h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">{region.blurb}</p>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Memories", value: members.length },
            { label: "Pathways", value: internal + [...bridges.values()].reduce((s, v) => s + v, 0) },
            { label: "Inferred", value: inferred },
          ].map((m) => (
            <div key={m.label} className="rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint">{m.label}</p>
              <p className="mt-1 font-mono text-lg font-semibold tracking-tight" style={{ color: region.color }}>
                {m.value}
              </p>
            </div>
          ))}
        </div>

        <Section label="Average confidence">
          <ConfidenceMeter value={confidence} />
        </Section>

        <Section label="Bridges to other domains">
          <ul className="space-y-2">
            {REGIONS.filter((r) => r.id !== regionId && bridges.has(r.id))
              .sort((a, b) => (bridges.get(b.id) ?? 0) - (bridges.get(a.id) ?? 0))
              .map((r) => {
                const count = bridges.get(r.id) ?? 0;
                return (
                  <li key={r.id} className="flex items-center gap-2.5 text-xs">
                    <span className="w-24 shrink-0 text-ink-muted">{r.label}</span>
                    <span className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                      <motion.span
                        className="block h-full rounded-full"
                        style={{ background: `linear-gradient(90deg, ${region.color}, ${r.color})` }}
                        initial={{ width: 0 }}
                        animate={{ width: `${(count / bridgePeak) * 100}%` }}
                        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
                      />
                    </span>
                    <span className="w-5 text-right font-mono text-[10px] text-ink-faint">{count}</span>
                  </li>
                );
              })}
          </ul>
        </Section>

        <Section label="Strongest memories">
          <ul className="-mx-2 space-y-0.5">
            {strongest.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => onSelect(n.id)}
                  className="group flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.045]"
                >
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: region.color }} />
                  <span className="line-clamp-2 flex-1 text-xs text-ink-muted group-hover:text-ink">{n.title}</span>
                  <span className="font-mono text-[10px] text-ink-faint">{n.importance}</span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      </motion.div>
    </Shell>
  );
}
