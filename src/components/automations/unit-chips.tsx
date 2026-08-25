import { KIND_META, STATUS_META, type UnitKind, type UnitStatus } from "@/lib/automations/types";
import { cn } from "@/lib/utils";

const KIND_STYLE: Record<string, string> = {
  violet: "bg-violet-bright/12 text-violet-bright",
  cyan: "bg-cyan-bright/12 text-cyan-bright",
  green: "bg-green/12 text-green",
  amber: "bg-amber/12 text-amber",
};

export function KindBadge({ kind }: { kind: UnitKind }) {
  const meta = KIND_META[kind];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider",
        KIND_STYLE[meta.accent],
      )}
    >
      {meta.label}
    </span>
  );
}

const DOT_COLOR: Record<string, string> = {
  green: "var(--green)",
  cyan: "var(--cyan-bright)",
  amber: "var(--amber)",
  rose: "var(--rose)",
  faint: "var(--ink-faint)",
};

export function StatusPill({ status }: { status: UnitStatus }) {
  const meta = STATUS_META[status];
  const color = DOT_COLOR[meta.accent];
  const pulse = status === "running" || status === "failed";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color }}>
      <span className="relative inline-flex h-1.5 w-1.5">
        {pulse && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
            style={{ background: color }}
          />
        )}
        <span
          className="relative inline-flex h-1.5 w-1.5 rounded-full"
          style={{ background: color }}
        />
      </span>
      {meta.label}
    </span>
  );
}
