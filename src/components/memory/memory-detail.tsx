"use client";

import { type ReactNode } from "react";
import { ArrowRight, Clock, Filter, Link2, Lock, Pencil, Pin, Trash2 } from "lucide-react";
import {
  CATEGORY_META,
  ENTITY_META,
  KIND_META,
  type Accent,
  type Entity,
  type MemoryRecord,
  type Relationship,
} from "@/lib/memory/types";
import { entityRelations, sharedEntityRecords } from "@/lib/memory/explorer";
import { cn } from "@/lib/utils";
import { DetailDrawer } from "@/components/ui/workspace";
import { ProvenanceBadge, KindTag } from "./provenance-badge";
import { ConfidenceMeter } from "./confidence-meter";

const TEXT: Record<Accent, string> = {
  orchid: "text-orchid-bright",
  cyan: "text-cyan-bright",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
  faint: "text-ink-faint",
};

function fmt(iso?: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return null;
  return d.toLocaleString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="eyebrow">{label}</h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

/** A value the source did not give. Said plainly, never filled in. */
function NotStated({ children = "Not stated by the source." }: { children?: ReactNode }) {
  return <p className="text-caption text-ink-faint" data-not-stated="">{children}</p>;
}

export interface MemoryDetailProps {
  record: MemoryRecord;
  allRecords: MemoryRecord[];
  entities?: Entity[];
  relationships?: Relationship[];
  onSelectRelated: (r: MemoryRecord) => void;
  /** Narrow the list to memories about one entity. */
  onFilterEntity?: (entityId: string) => void;
}

/**
 * One memory as evidence: what it says, what kind of claim it is, why Lilith
 * knows it, how sure the source was, what it is about and what it connects to.
 * Every field is what the backend returned; a missing one is shown as missing.
 */
export function MemoryDetailBody({
  record,
  allRecords,
  entities = [],
  relationships = [],
  onSelectRelated,
  onFilterEntity,
}: MemoryDetailProps) {
  const cat = CATEGORY_META[record.category];
  const kind = KIND_META[record.kind];
  const linked = record.related
    .map((id) => allRecords.find((r) => r.id === id))
    .filter((r): r is MemoryRecord => Boolean(r));
  const shared = sharedEntityRecords(record, allRecords).slice(0, 6);
  const times: [string, string | null][] = [
    ["Recorded", fmt(record.createdAt)],
    ["Updated", fmt(record.updatedAt)],
    ["Last accessed", fmt(record.lastAccessed)],
  ];

  return (
    <div data-memory-detail={record.id}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", TEXT[cat.accent])}>
          <cat.icon className="h-3.5 w-3.5" />
          {cat.label}
        </span>
        <KindTag kind={record.kind} />
        {record.pinned && (
          <span className="inline-flex items-center gap-1 rounded-full bg-orchid-bright/10 px-2 py-0.5 text-micro text-orchid-bright">
            <Pin className="h-2.5 w-2.5 fill-current" />
            Pinned
          </span>
        )}
      </div>

      <p className="mt-4 whitespace-pre-wrap break-words text-lead leading-relaxed text-ink">{record.content}</p>

      {record.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {record.tags.map((t) => (
            <span key={t} className="rounded-md bg-white/[0.04] px-2 py-0.5 text-micro text-ink-muted">
              #{t}
            </span>
          ))}
        </div>
      )}

      <div className="mt-6 space-y-6">
        {/* provenance — the heart of trust */}
        <Section label="Why Lilith knows this">
          <div className="rounded-md border border-white/[0.06] bg-white/[0.02] p-3">
            <ProvenanceBadge provenance={record.provenance} showAccount />
            <p className="mt-2 text-caption text-ink-muted">{record.provenance.label}</p>
            {fmt(record.provenance.at) && (
              <p className="mt-1 font-mono text-micro text-ink-faint">signal · {fmt(record.provenance.at)}</p>
            )}
          </div>
        </Section>

        <Section label="Kind of claim">
          <p className="text-caption leading-relaxed text-ink-muted" data-kind={record.kind}>
            <span className="font-medium text-ink">{kind.label}.</span> {kind.title}.
          </p>
        </Section>

        <Section label="Confidence">
          {typeof record.confidence === "number" ? (
            <ConfidenceMeter value={record.confidence} />
          ) : (
            <NotStated />
          )}
          {typeof record.importance === "number" && (
            <div className="mt-3">
              <p className="mb-1 text-micro text-ink-faint">Importance</p>
              <ConfidenceMeter value={record.importance} />
            </div>
          )}
        </Section>

        <Section label="About">
          {record.entities.length === 0 ? (
            <NotStated>The source attached no entities to this memory.</NotStated>
          ) : (
            <ul className="space-y-2.5">
              {record.entities.map((e) => {
                const EIcon = ENTITY_META[e.type].icon;
                const relations = entityRelations(e.id, entities, relationships);
                return (
                  <li key={e.id} data-entity={e.id}>
                    <div className="flex items-center gap-2">
                      <EIcon className="h-3.5 w-3.5 shrink-0 text-cyan-bright" />
                      <span className="min-w-0 truncate text-compact text-ink">{e.label}</span>
                      <span className="shrink-0 text-micro text-ink-faint">{ENTITY_META[e.type].label}</span>
                      {onFilterEntity && (
                        <button
                          type="button"
                          onClick={() => onFilterEntity(e.id)}
                          aria-label={`Show only memories about ${e.label}`}
                          title={`Show only memories about ${e.label}`}
                          className="ml-auto grid h-6 w-6 shrink-0 place-items-center rounded-full text-ink-faint transition-colors hover:bg-white/[0.06] hover:text-ink"
                        >
                          <Filter className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                    {relations.length > 0 && (
                      <ul className="ml-[22px] mt-1 space-y-0.5">
                        {relations.map((rel) => (
                          <li key={rel.id} className="flex items-center gap-1.5 text-micro text-ink-faint">
                            {/* the edge as the source gave it: from, relation, to */}
                            <span className={rel.direction === "out" ? "" : "text-ink-muted"}>{rel.direction === "out" ? e.label : rel.other.label}</span>
                            <span>{rel.kind}</span>
                            <ArrowRight className="h-2.5 w-2.5" />
                            <span className={rel.direction === "out" ? "text-ink-muted" : ""}>{rel.direction === "out" ? rel.other.label : e.label}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        {(linked.length > 0 || shared.length > 0) && (
          <Section label="Connected memories">
            <ul className="space-y-1">
              {linked.map((r) => (
                <RelatedRow key={r.id} record={r} note="Linked by the source" onSelect={onSelectRelated} />
              ))}
              {shared.map((link) => (
                <RelatedRow
                  key={link.record.id}
                  record={link.record}
                  note={`Also about ${link.via.map((e) => e.label).join(", ")}`}
                  onSelect={onSelectRelated}
                />
              ))}
            </ul>
          </Section>
        )}

        <Section label="Timeline">
          <dl className="space-y-1.5 font-mono text-micro">
            {times.map(([label, value], i) => (
              <div key={label} className="flex items-center justify-between gap-3">
                <dt className="flex items-center gap-1.5 text-ink-faint">
                  {i === 0 && <Clock className="h-3 w-3" />}
                  {label}
                </dt>
                <dd className={value ? "text-ink-muted" : "text-ink-faint"}>{value ?? "Not recorded"}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>
    </div>
  );
}

function RelatedRow({ record, note, onSelect }: { record: MemoryRecord; note: string; onSelect: (r: MemoryRecord) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(record)}
        className="group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
      >
        <Link2 className="mt-0.5 h-3 w-3 shrink-0 text-ink-faint group-hover:text-cyan-bright" />
        <span className="min-w-0">
          <span className="line-clamp-2 text-caption text-ink-muted group-hover:text-ink">{record.summary}</span>
          <span className="block text-micro text-ink-faint">{note}</span>
        </span>
      </button>
    </li>
  );
}

/** The read-only stance, with its reason. Write actions stay disabled. */
export function MemoryReadOnlyFooter() {
  return (
    <div data-memory-readonly="">
      <div className="flex items-center gap-2">
        {[
          { icon: Pin, label: "Pin" },
          { icon: Pencil, label: "Edit" },
          { icon: Trash2, label: "Forget" },
        ].map((a) => (
          <button
            key={a.label}
            type="button"
            disabled
            title="Read-only · write actions arrive with the backend approval flow"
            className="flex flex-1 cursor-not-allowed items-center justify-center gap-1.5 rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-2 text-xs text-ink-faint opacity-60"
          >
            <a.icon className="h-3.5 w-3.5" />
            {a.label}
          </button>
        ))}
      </div>
      <p className="mt-2 flex items-center justify-center gap-1.5 text-micro text-ink-faint">
        <Lock className="h-3 w-3" />
        Read-only — Lilith won&apos;t change or forget memories without your approval.
      </p>
    </div>
  );
}

/** The same detail in the shared drawer, for screens too narrow for two panes. */
export function MemoryDetail({
  record,
  onClose,
  ...rest
}: Omit<MemoryDetailProps, "record"> & { record: MemoryRecord | null; onClose: () => void }) {
  const cat = record ? CATEGORY_META[record.category] : null;
  return (
    <DetailDrawer
      open={Boolean(record)}
      onClose={onClose}
      eyebrow={cat ? `Memory · ${cat.label}` : "Memory"}
      title={record?.summary ?? "Memory"}
      footer={<MemoryReadOnlyFooter />}
    >
      {record && <MemoryDetailBody record={record} {...rest} />}
    </DetailDrawer>
  );
}
