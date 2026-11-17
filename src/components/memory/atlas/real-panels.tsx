"use client";

/**
 * Panels for Real memory — the same shells as the simulation's, saying only
 * what the read model says.
 *
 * What these never show for a real record: an importance or confidence the
 * source did not state, a "learned" or "recalled" moment, reinforcement
 * counts, or a link strength (pathway brightness is a drawing weight).
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, Database, FlaskConical, Focus, Link2, Loader2, RefreshCw, Route, Share2 } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { ConfidenceMeter } from "@/components/memory/confidence-meter";
import { KindTag, ProvenanceBadge } from "@/components/memory/provenance-badge";
import { entityRelations } from "@/lib/memory/explorer";
import { CATEGORY_META, ENTITY_META, type Entity, type MemoryCategory, type Relationship } from "@/lib/memory/types";
import { FAILURE_LINE, UNMAPPED_REGIONS, associationsOf, regionLabel, type SnapshotFailure } from "@/lib/memory/atlas/real-source";
import { REGIONS, REGION_BY_ID } from "@/lib/memory/atlas/regions";
import type { AtlasStore } from "@/lib/memory/atlas/store";
import type { AtlasLink, AtlasNode, AtlasState, RegionId } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";
import { Section, Shell, when } from "./atlas-inspector";
import { CloseButton, FeedRow, useTick } from "./cognition-feed";

const REAL_NOTE = (
  <p className="flex items-center gap-1.5 text-[10px] leading-relaxed text-ink-faint">
    <Database className="h-3 w-3 shrink-0 text-cyan-bright" />
    Real record · read-only. Nothing here changes Lilith’s memory.
  </p>
);

function clock(ms: number) {
  return new Date(ms).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

/** "Work · shown in the Career · Work field", or just the category. */
function CategoryLine({ node }: { node: AtlasNode }) {
  if (!node.category) return null;
  const meta = CATEGORY_META[node.category];
  const where = regionLabel(node.region, "real");
  return (
    <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
      Category <span className="text-ink-muted">{meta.label}</span>
      {where !== meta.label && <span> · drawn in the {where} field</span>}
    </p>
  );
}

/* -------------------------------------------------------------------- node */

export function RealNodeInspector({
  node,
  store,
  entities,
  relationships,
  entitiesStale = false,
  nodes,
  links,
  focusedEntity = null,
  onFocusEntity,
  onClose,
  onSelect,
  onExplore,
  className,
}: {
  /** the whole graph, so every association is listed, not only drawn ones. */
  nodes: readonly AtlasNode[];
  links: readonly AtlasLink[];
  /** the entity whose records are highlighted on the brain, if any. */
  focusedEntity?: string | null;
  onFocusEntity?: (entityId: string) => void;
  node: AtlasNode;
  store: AtlasStore;
  entities: Entity[];
  relationships: Relationship[];
  /** the latest entities read failed; relationships are from an earlier read. */
  entitiesStale?: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onExplore: (node: AtlasNode) => void;
  className?: string;
}) {
  const region = REGION_BY_ID[node.region];
  // every association, from the data — the brain may draw only some of them
  const all = associationsOf(node.id, nodes, links);
  const resolve = (id: string) => store.node(id);
  const explicit = all.explicit
    .map((id) => ({ other: resolve(id), drawn: true, note: "stated relation" }))
    .filter((a): a is { other: AtlasNode; drawn: boolean; note: string } => Boolean(a.other));
  const shared = all.shared
    .map(({ id, via }) => ({ other: resolve(id), drawn: Boolean(store.between(node.id, id)), note: via.join(", ") }))
    .filter((a): a is { other: AtlasNode; drawn: boolean; note: string } => Boolean(a.other));
  const total = explicit.length + shared.length;
  const drawnCount = explicit.length + shared.filter((a) => a.drawn).length;
  const refs = node.entityRefs ?? [];
  const membersOf = (entityId: string) => nodes.filter((n) => n.entityRefs?.some((e) => e.id === entityId)).length;

  return (
    <Shell
      region={region}
      regionName={regionLabel(node.region, "real")}
      onClose={onClose}
      className={className}
      footer={
        <div className="space-y-2.5">
          <button
            type="button"
            onClick={() => onExplore(node)}
            disabled={drawnCount === 0}
            className="group flex w-full items-center justify-center gap-2 rounded-full border border-wine/30 bg-gradient-to-r from-wine-deep/50 to-wine/30 px-4 py-2 text-xs font-medium text-ink transition-[border-color,box-shadow] hover:border-wine-bright/50 hover:shadow-[0_10px_30px_-14px_rgba(201,84,115,0.9)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Route className="h-3.5 w-3.5 text-wine-bright" />
            Follow associations from here
          </button>
          {REAL_NOTE}
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
              <span
                className="rounded-full bg-cyan/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-cyan-bright"
                title="First seen in a later snapshot of this session. Not proof of when Lilith learned it."
              >
                Newly observed
              </span>
            )}
          </div>
          <h2 className="mt-2.5 text-[15px] font-medium leading-snug text-ink">{node.title}</h2>
          {node.detail && node.detail !== node.title && (
            <p className="mt-1.5 whitespace-pre-line text-xs leading-relaxed text-ink-muted">{node.detail}</p>
          )}
          <div className="mt-3">
            <CategoryLine node={node} />
          </div>
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

        <Section label="Source">
          <div className="rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.02] p-3">
            <ProvenanceBadge
              provenance={{ kind: node.provenance.kind, label: node.provenance.label, sourceAccount: node.provenance.account }}
              showAccount
            />
            <p className="mt-2 text-xs text-ink-muted">{node.provenance.label}</p>
            {node.provenance.at !== undefined && (
              <p className="mt-1 font-mono text-[10px] text-ink-faint">signal · {when(node.provenance.at)}</p>
            )}
          </div>
        </Section>

        <Section label="As stated by the source">
          <div className="space-y-2">
            <div>
              <p className="mb-1 text-[11px] text-ink-faint">Confidence</p>
              <ConfidenceMeter value={node.confidence} />
            </div>
            <div>
              <p className="mb-1 text-[11px] text-ink-faint">Importance</p>
              <ConfidenceMeter value={node.importance} />
            </div>
            {(node.confidence === undefined || node.importance === undefined) && (
              <p className="text-[10px] leading-snug text-ink-faint">
                “—” means the source did not state it. The node’s size on the brain is a drawing default, not a value.
              </p>
            )}
          </div>
        </Section>

        {refs.length > 0 && (
          <Section label="Entities">
            <ul className="space-y-2">
              {refs.map((ref) => {
                const rels = entityRelations(ref.id, entities, relationships);
                const Icon = ENTITY_META[ref.type]?.icon;
                const count = membersOf(ref.id);
                const on = focusedEntity === ref.id;
                return (
                  <li
                    key={ref.id}
                    className={cn(
                      "rounded-lg border bg-white/[0.02] px-2.5 py-1.5 transition-colors",
                      on ? "border-white/25 bg-white/[0.05]" : "border-white/[0.06]",
                    )}
                  >
                    <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                      {Icon && <Icon className="h-3 w-3 text-ink-faint" />}
                      {ref.label}
                      <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
                        {ENTITY_META[ref.type]?.label ?? ref.type}
                      </span>
                      {onFocusEntity && count > 1 && (
                        <button
                          type="button"
                          aria-pressed={on}
                          onClick={() => onFocusEntity(ref.id)}
                          title={on ? "Stop highlighting" : `Highlight the ${count} records that carry ${ref.label}`}
                          className={cn(
                            "ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] transition-colors",
                            on ? "bg-white/[0.1] text-ink" : "text-ink-faint hover:bg-white/[0.06] hover:text-ink",
                          )}
                        >
                          <Focus className="h-2.5 w-2.5" />
                          {count} records
                        </button>
                      )}
                    </p>
                    {rels.length > 0 && (
                      <ul className="mt-1 space-y-0.5 pl-4">
                        {rels.map((rel) => (
                          <li key={rel.id} className="text-[11px] text-ink-faint">
                            {rel.direction === "out" ? (
                              <>
                                {rel.kind} <span className="text-ink-muted">{rel.other.label}</span>
                              </>
                            ) : (
                              <>
                                <span className="text-ink-muted">{rel.other.label}</span> {rel.kind} this
                              </>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="mt-1.5 text-[10px] leading-snug text-ink-faint">
              Relationships here are between entities, as the source records them — not between memories.
            </p>
            {entitiesStale && (
              <p className="mt-1.5 flex items-start gap-1.5 text-[10px] leading-snug text-amber">
                <AlertTriangle className="mt-px h-3 w-3 shrink-0" />
                The latest read of entities failed; these relationships are from an earlier read.
              </p>
            )}
          </Section>
        )}

        <Section
          label="Associations"
          action={
            <span className="font-mono text-[10px] text-ink-faint">
              {total}
              {drawnCount !== total && <> · {drawnCount} drawn</>}
            </span>
          }
        >
          {drawnCount !== total && (
            <p className="mb-2 text-[10px] leading-snug text-ink-faint">
              The brain draws a simplified set of pathways. While this record is selected, all {total} are shown.
            </p>
          )}
          {total === 0 ? (
            <p className="text-xs text-ink-faint">The source links this record to no other, and it shares no entity with one.</p>
          ) : (
            <div className="space-y-3">
              {explicit.length > 0 && (
                <AssociationList
                  heading="Linked by the source"
                  icon={Link2}
                  items={explicit}
                  onSelect={onSelect}
                />
              )}
              {shared.length > 0 && (
                <AssociationList
                  heading="Share an entity · derived here"
                  icon={Share2}
                  items={shared}
                  onSelect={onSelect}
                />
              )}
            </div>
          )}
        </Section>

        <Section label="Record dates">
          <ul className="space-y-1.5 font-mono text-[11px] text-ink-muted">
            <li className="flex items-center justify-between">
              <span className="text-ink-faint">Created</span>
              <span>{node.createdAt !== undefined ? when(node.createdAt) : "not stated"}</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-ink-faint">Updated</span>
              <span>{node.updatedAt !== undefined ? when(node.updatedAt) : "not stated"}</span>
            </li>
          </ul>
          <p className="mt-1.5 text-[10px] leading-snug text-ink-faint">
            Dates of the record itself (an update may be a file change), not when Lilith learned it.
          </p>
        </Section>
      </motion.div>
    </Shell>
  );
}

function AssociationList({
  heading,
  icon: Icon,
  items,
  onSelect,
}: {
  heading: string;
  icon: typeof Link2;
  items: { other: AtlasNode; drawn: boolean; note: string }[];
  onSelect: (id: string) => void;
}) {
  return (
    <div>
      <p className="mb-1 flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.12em] text-ink-faint">
        <Icon className="h-2.5 w-2.5" />
        {heading}
      </p>
      <ul className="-mx-2 space-y-0.5">
        {items.map(({ other, drawn, note }) => {
          const r = REGION_BY_ID[other.region];
          return (
            <li key={other.id}>
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
                  <span className="mt-0.5 block truncate font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
                    {note}
                    {!drawn && <span title="Not among the simplified pathways; shown while selected"> · not drawn</span>}
                    {other.live && <span className="text-cyan-bright"> · newly observed</span>}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ region */

export function RealRegionInspector({
  region: regionId,
  state,
  store,
  associations,
  onClose,
  onSelect,
  className,
}: {
  region: RegionId;
  state: AtlasState;
  store: AtlasStore;
  /** every association touching this region (drawn or not). */
  associations: number;
  onClose: () => void;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const region = REGION_BY_ID[regionId];
  const members = state.nodes.filter((n) => n.region === regionId);
  const byCategory = new Map<MemoryCategory, number>();
  for (const n of members) if (n.category) byCategory.set(n.category, (byCategory.get(n.category) ?? 0) + 1);

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
  const unmapped = UNMAPPED_REGIONS.includes(regionId);
  const listed = [...members].sort((a, b) => (b.updatedAt ?? b.createdAt ?? 0) - (a.updatedAt ?? a.createdAt ?? 0));

  return (
    <Shell region={region} regionName={regionLabel(regionId, "real")} onClose={onClose} className={className} footer={REAL_NOTE}>
      <motion.div
        key={regionId}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="space-y-5"
      >
        <div>
          <h2 className="text-[15px] font-medium text-ink">{regionLabel(regionId, "real")}</h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">
            {unmapped
              ? "No category of the memory model maps to this domain, so in Real memory it holds nothing. People and their relationships are recorded under People."
              : regionId === "career"
                ? "Holds records categorised Career and records categorised Work. Each keeps its own category."
                : region.blurb}
          </p>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Records", value: members.length },
            { label: "Drawn", value: internal + [...bridges.values()].reduce((s, v) => s + v, 0) },
            { label: "Associations", value: associations },
          ].map((m) => (
            <div key={m.label} className="rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint">{m.label}</p>
              <p className="mt-1 font-mono text-lg font-semibold tracking-tight" style={{ color: region.color }}>
                {m.value}
              </p>
            </div>
          ))}
        </div>

        {byCategory.size > 0 && (
          <Section label="Categories">
            <ul className="space-y-1 text-xs text-ink-muted">
              {[...byCategory].map(([category, count]) => (
                <li key={category} className="flex items-center justify-between">
                  <span>{CATEGORY_META[category].label}</span>
                  <span className="font-mono text-[10px] text-ink-faint">{count}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {bridges.size > 0 && (
          <Section label="Bridges to other domains">
            <ul className="space-y-2">
              {REGIONS.filter((r) => r.id !== regionId && bridges.has(r.id))
                .sort((a, b) => (bridges.get(b.id) ?? 0) - (bridges.get(a.id) ?? 0))
                .map((r) => {
                  const count = bridges.get(r.id) ?? 0;
                  return (
                    <li key={r.id} className="flex items-center gap-2.5 text-xs">
                      <span className="w-24 shrink-0 truncate text-ink-muted">{regionLabel(r.id, "real")}</span>
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
        )}

        {listed.length > 0 && (
          <Section label="Records">
            <ul className="-mx-2 space-y-0.5">
              {listed.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(n.id)}
                    className="group flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.045]"
                  >
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: region.color }} />
                    <span className="line-clamp-2 flex-1 text-xs text-ink-muted group-hover:text-ink">{n.title}</span>
                    {n.category && (
                      <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
                        {CATEGORY_META[n.category].label}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </motion.div>
    </Shell>
  );
}

/* --------------------------------------------------------- observed changes */

export function ObservedChanges({
  state,
  firstAt,
  lastGoodAt,
  stale,
  checking,
  onCheck,
  onSelect,
  onClose,
  className,
}: {
  state: AtlasState;
  firstAt: number;
  lastGoodAt: number;
  stale: { failure: SnapshotFailure; at: number } | null;
  checking: boolean;
  onCheck: () => void;
  onSelect: (id: string) => void;
  onClose?: () => void;
  className?: string;
}) {
  const now = useTick(5000);
  const { changes } = state;
  return (
    <GlassCard strong animated={false} className={cn("flex min-h-0 flex-col", className)}>
      <div className="flex items-center justify-between gap-2 px-5 pt-4">
        <div className="mr-auto flex items-center gap-2.5">
          <span className={cn("inline-block h-1.5 w-1.5 rounded-full", stale ? "bg-amber" : "bg-cyan-bright")} />
          <p className="eyebrow">Observed changes</p>
          <span className="inline-flex items-center gap-1 rounded-full border border-cyan/25 bg-cyan/10 px-1.5 py-px font-mono text-[8px] uppercase tracking-[0.12em] text-cyan-bright">
            <Database className="h-2.5 w-2.5" />
            Read-only
          </span>
        </div>
        <button
          type="button"
          onClick={onCheck}
          disabled={checking}
          aria-label="Check for changes now"
          className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted transition-colors hover:border-white/20 hover:text-ink disabled:opacity-50"
        >
          {checking ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <RefreshCw className="h-2.5 w-2.5" />}
          Check
        </button>
        {onClose && <CloseButton label="Close observed changes" onClick={onClose} />}
      </div>

      <p className="px-5 pt-2 text-[11px] leading-relaxed text-ink-faint">
        Differences between successive reads of the memory records since {clock(firstAt)}. A difference shows what
        the read model returns now — not proof that Lilith just learned or forgot something.
      </p>
      {stale && (
        <p className="mx-5 mt-2 flex items-start gap-1.5 rounded-lg border border-amber/20 bg-amber/[0.06] px-2.5 py-1.5 text-[11px] leading-snug text-amber">
          <AlertTriangle className="mt-px h-3 w-3 shrink-0" />
          The last check at {clock(stale.at)} failed. {FAILURE_LINE[stale.failure]} Showing the snapshot from {clock(lastGoodAt)}.
        </p>
      )}

      <div className="grid grid-cols-4 gap-1.5 px-5 pt-3">
        {[
          { label: "Observed", value: changes.observed },
          { label: "Changed", value: changes.changed },
          { label: "Gone", value: changes.withdrawn },
          { label: "Links", value: changes.links },
        ].map((m) => (
          <div key={m.label} className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-2 py-1.5">
            <p className="font-mono text-sm font-semibold text-ink">{m.value}</p>
            <p className="font-mono text-[8px] uppercase tracking-[0.12em] text-ink-faint">{m.label}</p>
          </div>
        ))}
      </div>

      <div className="scroll-area relative mt-3 min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {state.activity.length === 0 ? (
          <div className="px-2 py-6 text-center">
            <p className="text-xs text-ink-muted">No differences since the first read.</p>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">
              Last successful read {clock(lastGoodAt)}. The records are read again every minute while this page is open.
            </p>
          </div>
        ) : (
          <ul className="space-y-0.5">
            {state.activity.slice(0, 20).map((item) => (
              <FeedRow key={item.id} item={item} now={now} onSelect={onSelect} />
            ))}
          </ul>
        )}
      </div>
    </GlassCard>
  );
}

/* ------------------------------------------------------------------ timeline */

/** Real memory has no growth history to replay; say so instead of drawing one. */
export function RealTimelineNotice({ nodes }: { nodes: AtlasNode[] }) {
  const created = nodes.filter((n) => n.createdAt !== undefined).length;
  const updated = nodes.filter((n) => n.updatedAt !== undefined).length;
  return (
    <GlassCard strong animated={false} className="px-5 py-4">
      <p className="eyebrow">Timeline</p>
      <p className="mt-2 text-xs leading-relaxed text-ink-muted">
        The memory records carry no learning history, so Real memory has no growth to replay. A record’s dates
        describe the record (an update can be a file change), not the moment Lilith learned it.
      </p>
      <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
        {nodes.length} records · {created} with a creation date · {updated} with an update date
      </p>
    </GlassCard>
  );
}

/* ------------------------------------------------------------ source switch */

export type AtlasSource = "simulation" | "real";

export function SourceSwitch({ value, onChange }: { value: AtlasSource; onChange: (next: AtlasSource) => void }) {
  const options: { key: AtlasSource; label: string; icon: typeof Database }[] = [
    { key: "simulation", label: "Simulation", icon: FlaskConical },
    { key: "real", label: "Real memory", icon: Database },
  ];
  return (
    <div
      role="radiogroup"
      aria-label="Atlas source"
      className="flex rounded-full border border-white/[0.09] bg-[rgba(12,8,13,0.5)] p-0.5 backdrop-blur-xl"
    >
      {options.map(({ key, label, icon: Icon }) => {
        const on = value === key;
        return (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => !on && onChange(key)}
            style={{ borderRadius: 9999 }}
            className={cn(
              "inline-flex min-h-7 items-center gap-1.5 px-2.5 text-[11px] transition-colors duration-200 [@media(pointer:coarse)]:min-h-10",
              on
                ? key === "real"
                  ? "bg-cyan/12 text-cyan-bright"
                  : "bg-amber/10 text-amber"
                : "text-ink-faint hover:text-ink-muted",
            )}
          >
            <Icon className="h-3 w-3" />
            {label}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------ status overlay */

/** Shown in place of memories when there is no confirmed snapshot to draw. */
export function RealStateNotice({
  phase,
  failure,
  checking,
  onRetry,
  onSimulation,
}: {
  phase: "loading" | "unavailable" | "empty";
  failure?: SnapshotFailure;
  checking?: boolean;
  onRetry?: () => void;
  onSimulation: () => void;
}) {
  return (
    <div className="pointer-events-none absolute inset-0 z-[15] grid place-items-center px-4">
      <GlassCard strong animated={false} className="pointer-events-auto w-[min(100%,360px)] px-5 py-4 text-center">
        {phase === "loading" ? (
          <p className="flex items-center justify-center gap-2 text-xs text-ink-muted" role="status">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading memory records…
          </p>
        ) : (
          <>
            <p className="text-sm font-medium text-ink">
              {phase === "empty" ? "The memory read model returned no records" : "Real memory is unavailable"}
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
              {phase === "empty"
                ? "There is nothing to draw. Nothing has been put in its place."
                : `${failure ? FAILURE_LINE[failure] : ""} Nothing is shown in its place — no sample or simulated memories.`}
            </p>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  disabled={checking}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.1] bg-white/[0.04] px-3 py-1.5 text-[11px] text-ink transition-colors hover:border-white/25 disabled:opacity-50"
                >
                  {checking ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                  Try again
                </button>
              )}
              <button
                type="button"
                onClick={onSimulation}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] text-ink-muted transition-colors hover:text-ink"
              >
                <FlaskConical className="h-3 w-3" /> Show the simulation
              </button>
              <Link href="/memory" className="rounded-full px-3 py-1.5 text-[11px] text-ink-muted transition-colors hover:text-ink">
                Open the Archive
              </Link>
            </div>
          </>
        )}
      </GlassCard>
    </div>
  );
}
