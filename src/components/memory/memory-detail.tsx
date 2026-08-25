"use client";

import { type ReactNode, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Pin, Pencil, Trash2, Clock, Lock, Link2 } from "lucide-react";
import {
  CATEGORY_META,
  ENTITY_META,
  PROVENANCE_META,
  type Accent,
  type MemoryRecord,
} from "@/lib/memory/types";
import { cn } from "@/lib/utils";
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
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const related = record
    ? record.related
        .map((id) => allRecords.find((r) => r.id === id))
        .filter((r): r is MemoryRecord => Boolean(r))
    : [];

  const cat = record ? CATEGORY_META[record.category] : null;
  const prov = record ? PROVENANCE_META[record.provenance.kind] : null;

  return (
    <AnimatePresence>
      {record && cat && prov && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="glass-strong scroll-area fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col overflow-y-auto p-6"
            role="dialog"
            aria-modal="true"
            aria-label="Memory detail"
          >
            {/* header */}
            <div className="flex items-start justify-between gap-3">
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
              <button
                onClick={onClose}
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white/[0.06] text-ink-muted hover:text-ink"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* content */}
            <p className="mt-4 text-[15px] leading-relaxed text-ink">{record.content}</p>

            {/* tags */}
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

              {/* confidence + importance */}
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

              {/* related entities */}
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

              {/* related memories */}
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

              {/* timestamps */}
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

            {/* read-only footer — write actions are deferred */}
            <div className="mt-6 border-t border-white/[0.06] pt-4">
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
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
