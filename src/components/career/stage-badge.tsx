import { STAGE_META, type Stage } from "@/lib/career/types";
import { cn } from "@/lib/utils";

const STYLES: Record<string, string> = {
  violet: "bg-violet-bright/12 text-violet-bright",
  cyan: "bg-cyan-bright/12 text-cyan-bright",
  green: "bg-green/12 text-green",
  amber: "bg-amber/12 text-amber",
  rose: "bg-rose/12 text-rose",
  faint: "bg-white/[0.05] text-ink-faint",
};

export function StageBadge({ stage, className }: { stage: Stage; className?: string }) {
  const meta = STAGE_META[stage];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium",
        STYLES[meta.accent],
        className,
      )}
    >
      {meta.label}
    </span>
  );
}
