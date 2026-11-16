"use client";

import { type ReactNode } from "react";
import { Pin, Pencil, Trash2, Clock, Lock, Link2 } from "lucide-react";
import {
  CATEGORY_META,
  ENTITY_META,
  type Accent,
  type MemoryRecord,
} from "@/lib/memory/types";
import { cn } from "@/lib/utils";
import { DetailDrawer } from "@/components/ui/workspace";
import { ProvenanceBadge, KindTag } from "./provenance-badge";
import { ConfidenceMeter } from "./confidence-meter";

const TEXT: Record<Accent, string> = {
  violet: "text-violet-bright",
  cyan: "text-cyan-bright",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
  faint: "text-ink-faint",
};

function fmt(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return "—";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="eyebrow">{label}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

/**
 * One memory in full: what it says, why Lilith knows it, how sure she is, and
 * what it connects to. Uses the shared detail drawer, so it gets the same
 * motion, keyboard handling and focus behaviour as every other workspace.
 */
export function MemoryDetail({
  record,
  allRecords,
  onClose,
  onSelectRelated,
}: {
  record: MemoryRecord | null;
  allRecords: MemoryRecord[];
  onClose: () => void;
  onSelectRelated: (r: MemoryRecord) => void;
}) {
  const related = record
    ? record.related
        .map((id) => allRecords.find((r) => r.id === id))
        .filter((r): r is MemoryRecord => Boolean(r))
    : [];
  const cat = record ? CATEGORY_META[record.category] : null;

  return (
    <DetailDrawer
      open={Boolean(record)}
      onClose={onClose}
      eyebrow={cat ? `Memory · ${cat.label}` : "Memory"}
      title={record?.summary ?? "Memory"}
      footer={
        <>
          <div className="flex items-center gap-2">
            {[
              { icon: Pin, label: "Pin" },
              { icon: Pencil, label: "Edit" },
              { icon: Trash2, label: "Forget" },
            ].map((a) => (
              <button
                key={a.label}
                disabled
                title="Read-only · write actions arrive with the backend approval flow"
                className="flex flex-1 cursor-not-allowed items-center justify-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-2 text-xs text-ink-faint opacity-60"
              >
                <a.icon className="h-3.5 w-3.5" />
                {a.label}
              </button>
            ))}
          </div>
          <p className="mt-2 flex items-center justify-center gap-1.5 text-[10px] text-ink-faint">
            <Lock className="h-3 w-3" />
            Read-only — Lilith won&apos;t change or forget memories without your approval.
          </p>
        </>
      }
    >
      {record && cat && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", TEXT[cat.accent])}>
              <cat.icon className="h-3.5 w-3.5" />
              {cat.label}
            </span>
            <KindTag kind={record.kind} />
            {record.pinned && (
              <span className="inline-flex items-center gap-1 rounded-full bg-violet-bright/10 px-2 py-0.5 text-[10px] text-violet-bright">
                <Pin className="h-2.5 w-2.5 fill-current" />
                Pinned
              </span>
            )}
          </div>

          <p className="mt-4 text-[15px] leading-relaxed text-ink">{record.content}</p>

          {record.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {record.tags.map((t) => (
                <span key={t} className="rounded-md bg-white/[0.04] px-2 py-0.5 text-[11px] text-ink-muted">
                  #{t}
                </span>
              ))}
            </div>
          )}

          <div className="mt-6 space-y-6">
            {/* provenance — the heart of trust */}
            <Section label="Why Lilith knows this">
              <div className="rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.02] p-3">
                <div className="flex items-center gap-2">
                  <ProvenanceBadge provenance={record.provenance} showAccount />
                </div>
                <p className="mt-2 text-xs text-ink-muted">{record.provenance.label}</p>
                {record.provenance.at && (
                  <p className="mt-1 font-mono text-[10px] text-ink-faint">
                    signal · {fmt(record.provenance.at)}
                  </p>
                )}
              </div>
            </Section>

            <Section label="Confidence & importance">
              <div className="space-y-2.5">
                <div>
                  <div className="mb-1 flex items-center justify-between text-[11px] text-ink-faint">
                    <span>Confidence</span>
                  </div>
                  <ConfidenceMeter value={record.confidence} />
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-[11px] text-ink-faint">
                    <span>Importance</span>
                  </div>
                  <ConfidenceMeter value={record.importance} />
                </div>
              </div>
            </Section>

            {record.entities.length > 0 && (
              <Section label="Related entities">
                <div className="flex flex-wrap gap-1.5">
                  {record.entities.map((e) => {
                    const EIcon = ENTITY_META[e.type].icon;
                    return (
                      <span
                        key={e.id}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-1 text-xs text-ink-muted"
                      >
                        <EIcon className="h-3 w-3 text-cyan-bright" />
                        {e.label}
                        <span className="text-[10px] text-ink-faint">{ENTITY_META[e.type].label}</span>
                      </span>
                    );
                  })}
                </div>
              </Section>
            )}

            {related.length > 0 && (
              <Section label="Related memories">
                <ul className="space-y-1.5">
                  {related.map((r) => (
                    <li key={r.id}>
                      <button
                        onClick={() => onSelectRelated(r)}
                        className="group flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
                      >
                        <Link2 className="mt-0.5 h-3 w-3 shrink-0 text-ink-faint group-hover:text-cyan-bright" />
                        <span className="line-clamp-2 text-xs text-ink-muted group-hover:text-ink">
                          {r.summary}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <Section label="Timeline">
              <ul className="space-y-1.5 font-mono text-[11px] text-ink-muted">
                <li className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-ink-faint">
                    <Clock className="h-3 w-3" /> Created
                  </span>
                  <span>{fmt(record.createdAt)}</span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-ink-faint">Updated</span>
                  <span>{fmt(record.updatedAt)}</span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-ink-faint">Last accessed</span>
                  <span>{fmt(record.lastAccessed)}</span>
                </li>
              </ul>
            </Section>
          </div>
        </>
      )}
    </DetailDrawer>
  );
}
