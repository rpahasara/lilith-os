import { CircleCheck, Sparkles } from "lucide-react";
import { PROVENANCE_META, type MemoryKind, type Provenance, type Accent } from "@/lib/memory/types";
import { cn } from "@/lib/utils";

const CHIP: Record<Accent, string> = {
  violet: "bg-violet-bright/10 text-violet-bright",
  cyan: "bg-cyan-bright/10 text-cyan-bright",
  green: "bg-green/10 text-green",
  amber: "bg-amber/10 text-amber",
  rose: "bg-rose/10 text-rose",
  faint: "bg-white/[0.05] text-ink-faint",
};

/** Where a memory came from — "why Lilith knows this". */
export function ProvenanceBadge({
  provenance,
  showAccount = false,
  className,
}: {
  provenance: Provenance;
  showAccount?: boolean;
  className?: string;
}) {
  const meta = PROVENANCE_META[provenance.kind];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium",
        CHIP[meta.accent],
        className,
      )}
      title={provenance.label}
    >
      <Icon className="h-3 w-3" />
      {meta.label}
      {showAccount && provenance.sourceAccount && (
        <span className="font-mono text-ink-faint">· {provenance.sourceAccount}</span>
      )}
    </span>
  );
}

/**
 * FACT vs INFERENCE — a first-class distinction. Facts were stated/observed;
 * inferences were derived by Lilith and may be wrong.
 */
export function KindTag({ kind, className }: { kind: MemoryKind; className?: string }) {
  const isFact = kind === "fact";
  const Icon = isFact ? CircleCheck : Sparkles;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em]",
        isFact
          ? "bg-cyan-bright/10 text-cyan-bright"
          : "bg-amber/10 text-amber",
        className,
      )}
      title={isFact ? "Directly stated or observed" : "Derived by Lilith — may be wrong"}
    >
      <Icon className="h-2.5 w-2.5" />
      {isFact ? "Fact" : "Inference"}
    </span>
  );
}
