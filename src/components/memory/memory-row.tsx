import { CATEGORY_META, KIND_META, PROVENANCE_META, type Accent, type MemoryRecord } from "@/lib/memory/types";
import { recordTime } from "@/lib/memory/explorer";
import { cn } from "@/lib/utils";

const DOT: Record<Accent, string> = {
  orchid: "bg-orchid-bright",
  cyan: "bg-cyan-bright",
  green: "bg-green",
  amber: "bg-amber",
  rose: "bg-rose",
  faint: "bg-white/30",
};
const KIND_TEXT: Record<Accent, string> = {
  orchid: "text-orchid-bright",
  cyan: "text-cyan-bright",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
  faint: "text-ink-faint",
};

/** Column template shared by the header and every row (md and up). */
export const ROW_COLUMNS = "md:grid md:grid-cols-[minmax(0,1fr)_128px_92px_84px_76px] md:items-center md:gap-4";

function shortDate(iso?: string): string | null {
  const t = iso ? new Date(iso) : null;
  if (!t || !Number.isFinite(t.getTime())) return null;
  return t.toLocaleDateString("en-US", { month: "short", day: "numeric", year: t.getFullYear() === new Date().getFullYear() ? undefined : "2-digit" });
}

/**
 * One memory as a line of evidence: what it says, then where it came from,
 * what kind of claim it is, how sure the source was, and when. A value the
 * source did not give is shown as a dash with its reason, never filled in.
 */
export function MemoryRow({
  record,
  selected,
  tabIndex,
  onSelect,
  onKeyDown,
}: {
  record: MemoryRecord;
  selected: boolean;
  tabIndex: number;
  onSelect: (r: MemoryRecord) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLButtonElement>) => void;
}) {
  const cat = CATEGORY_META[record.category];
  const prov = PROVENANCE_META[record.provenance.kind];
  const kind = KIND_META[record.kind];
  const when = shortDate(recordTime(record));
  const stated = typeof record.confidence === "number";

  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      tabIndex={tabIndex}
      data-memory-row={record.id}
      onClick={() => onSelect(record)}
      onKeyDown={onKeyDown}
      className={cn(
        "relative block w-full px-4 py-3 text-left transition-colors focus-visible:z-10",
        ROW_COLUMNS,
        selected ? "bg-white/[0.06]" : "hover:bg-white/[0.03]",
      )}
    >
      {selected && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-wine-bright" />}

      <span className="flex min-w-0 items-start gap-2.5">
        <span aria-hidden className={cn("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full", DOT[cat.accent])} />
        <span className="min-w-0">
          <span className={cn("line-clamp-2 text-compact leading-snug md:line-clamp-1", selected ? "text-ink" : "text-ink-muted")}>
            {record.summary}
          </span>
          <span className="mt-0.5 block truncate text-micro text-ink-faint">
            {cat.label}
            {record.entities.length > 0 && ` · ${record.entities.map((e) => e.label).slice(0, 3).join(", ")}`}
          </span>
        </span>
      </span>

      {/* On narrow screens the four columns fold into one quiet line. */}
      <span className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 pl-4 text-micro md:contents">
        <span className="flex items-center gap-1.5 truncate text-ink-muted md:pl-0" title={record.provenance.label}>
          <prov.icon aria-hidden className="h-3 w-3 shrink-0 text-ink-faint" />
          <span className="truncate">{prov.label}</span>
        </span>
        <span className={cn("truncate", KIND_TEXT[kind.accent])} title={kind.title} data-row-kind={record.kind}>
          {record.kind === "unknown" ? <span aria-label="Classification not stated">—</span> : kind.label}
        </span>
        <span className="font-mono text-ink-muted" data-row-confidence={stated ? record.confidence : "unstated"}>
          {stated ? `${record.confidence}%` : <span className="text-ink-faint" aria-label="Confidence not stated">—</span>}
        </span>
        <span className="font-mono text-ink-faint md:text-right">
          {when ?? <span aria-label="Undated">—</span>}
        </span>
      </span>
    </button>
  );
}
