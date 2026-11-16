"use client";

import { motion } from "framer-motion";
import { X } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { REGIONS } from "@/lib/memory/atlas/regions";
import type { AtlasNode, RegionId } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";

/**
 * The seven domains, each a region of the brain. Hovering a row lights its
 * region; selecting it isolates the region and opens its summary.
 */
export function RegionIndex({
  nodes,
  active,
  onHover,
  onSelect,
  onClose,
  className,
}: {
  nodes: AtlasNode[];
  active: RegionId | null;
  onHover: (region: RegionId | null) => void;
  onSelect: (region: RegionId | null) => void;
  onClose?: () => void;
  className?: string;
}) {
  const stats = new Map<RegionId, { total: number; live: number }>();
  for (const n of nodes) {
    const s = stats.get(n.region) ?? { total: 0, live: 0 };
    s.total += 1;
    if (n.live) s.live += 1;
    stats.set(n.region, s);
  }
  const peak = Math.max(1, ...[...stats.values()].map((s) => s.total));

  return (
    <GlassCard strong animated={false} className={cn("p-3", className)}>
      <div className="flex items-center justify-between px-1.5 pb-2 pt-0.5">
        <p className="eyebrow">Domains</p>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close domains"
            className="grid h-6 w-6 place-items-center rounded-full bg-white/[0.06] text-ink-muted transition-colors hover:text-ink"
          >
            <X className="h-3 w-3" />
          </button>
        ) : (
          <span className="font-mono text-[10px] text-ink-faint">{REGIONS.length} regions</span>
        )}
      </div>
      <ul className="space-y-0.5" onMouseLeave={() => onHover(null)}>
        {REGIONS.map((region) => {
          const s = stats.get(region.id) ?? { total: 0, live: 0 };
          const on = active === region.id;
          return (
            <li key={region.id}>
              <button
                type="button"
                aria-pressed={on}
                onMouseEnter={() => onHover(region.id)}
                onFocus={() => onHover(region.id)}
                onBlur={() => onHover(null)}
                onClick={() => onSelect(on ? null : region.id)}
                className={cn(
                  "group relative w-full rounded-xl px-2.5 py-2 text-left transition-colors",
                  on ? "bg-white/[0.07]" : "hover:bg-white/[0.04]",
                )}
              >
                {on && (
                  <motion.span
                    layoutId="region-active"
                    className="absolute inset-0 rounded-xl ring-1 ring-white/15"
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                  />
                )}
                <span className="relative flex items-center gap-2.5">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full transition-transform duration-300 group-hover:scale-125"
                    style={{ background: region.color, boxShadow: `0 0 10px ${region.color}` }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className={cn("block text-[13px] leading-tight", on ? "text-ink" : "text-ink-muted group-hover:text-ink")}>
                      {region.label}
                    </span>
                    <span className="block font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint">
                      {region.lobe}
                    </span>
                  </span>
                  {s.live > 0 && (
                    <span
                      className="rounded-full px-1.5 py-px font-mono text-[9px]"
                      style={{ color: region.color, background: `${region.color}1f` }}
                      title={`${s.live} learned this session`}
                    >
                      +{s.live}
                    </span>
                  )}
                  <span className="w-6 text-right font-mono text-xs text-ink">{s.total}</span>
                </span>
                {/* density */}
                <span className="relative mt-1.5 block h-px w-full overflow-hidden rounded-full bg-white/[0.06]">
                  <motion.span
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{ background: `linear-gradient(90deg, ${region.color}, transparent)` }}
                    initial={false}
                    animate={{ width: `${(s.total / peak) * 100}%` }}
                    transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
                  />
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </GlassCard>
  );
}
