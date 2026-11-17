"use client";

import { REGIONS, REGION_BY_ID } from "@/lib/memory/atlas/regions";
import { regionLabel } from "@/lib/memory/atlas/real-source";
import type { AtlasNode, AtlasOrigin, RegionId } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";

type Register = (key: string) => (el: HTMLElement | SVGElement | null) => void;

/**
 * DOM that floats in brain space — the brain's own interface.
 *
 * Each domain is a callout: a label, and a fine leader line running from the
 * label to the part of the cortex it names. The scene's frame loop owns their
 * geometry (it writes transforms and line endpoints directly, without a React
 * render), so a label stays tied to its region as the brain turns, steps
 * outside the silhouette, and moves aside for its neighbours.
 *
 * The layer is fixed to the viewport because the canvas is: both share one
 * coordinate space.
 */
export function AtlasLabels({
  register,
  counts,
  live,
  active,
  quiet,
  hovered,
  onHoverRegion,
  onSelectRegion,
  origin = "synthetic",
}: {
  /** real memory names the Career field "Career · Work" (it holds both). */
  origin?: AtlasOrigin;
  register: Register;
  counts: Map<RegionId, number>;
  /** simulation: learned this session; real: newly observed this session. */
  live: Map<RegionId, number>;
  active: RegionId | null;
  /** fade the callouts back (a memory or a recall has the stage). */
  quiet: boolean;
  hovered: AtlasNode | null;
  onHoverRegion: (region: RegionId | null) => void;
  onSelectRegion: (region: RegionId | null) => void;
}) {
  const hoveredRegion = hovered ? REGION_BY_ID[hovered.region] : null;
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">
      {/* leaders */}
      <svg
        aria-hidden
        className={cn("absolute inset-0 h-full w-full transition-opacity duration-500", quiet && "opacity-30")}
      >
        {REGIONS.map((region) => (
          <g key={region.id}>
            <line
              ref={register(`line:${region.id}`)}
              stroke={region.color}
              strokeWidth={1}
              strokeLinecap="round"
              style={{ opacity: 0 }}
            />
            <circle
              ref={register(`dot:${region.id}`)}
              r={2.25}
              fill="none"
              stroke={region.color}
              strokeWidth={1}
              style={{ opacity: 0 }}
            />
          </g>
        ))}
      </svg>

      {REGIONS.map((region) => {
        const on = active === region.id;
        const fresh = live.get(region.id) ?? 0;
        const count = counts.get(region.id) ?? 0;
        return (
          <div
            key={region.id}
            ref={register(`region:${region.id}`)}
            className="absolute left-0 top-0 will-change-transform"
            style={{ opacity: 0, visibility: "hidden" }}
          >
            <button
              type="button"
              aria-pressed={on}
              aria-label={`${regionLabel(region.id, origin)}: ${count} ${origin === "real" ? "records" : "memories"}. ${region.blurb}`}
              onMouseEnter={() => onHoverRegion(region.id)}
              onMouseLeave={() => onHoverRegion(null)}
              onFocus={() => onHoverRegion(region.id)}
              onBlur={() => onHoverRegion(null)}
              onClick={() => onSelectRegion(on ? null : region.id)}
              // the global focus ring squares corners; keep the pill round
              style={{
                borderRadius: 9999,
                ...(on ? { borderColor: `${region.color}aa`, boxShadow: `0 0 26px -8px ${region.color}` } : null),
              }}
              className={cn(
                "pointer-events-auto flex -translate-x-1/2 -translate-y-1/2 items-center gap-2 whitespace-nowrap border bg-[rgba(10,7,12,0.62)] py-1.5 pl-2.5 pr-3 font-mono text-[10.5px] uppercase tracking-[0.15em] shadow-[0_8px_24px_-12px_rgba(0,0,0,0.9)] backdrop-blur-md transition-[opacity,border-color,color,background-color] duration-500 hover:bg-[rgba(10,7,12,0.8)] [@media(pointer:coarse)]:py-2.5 max-sm:gap-1.5 max-sm:pl-2 max-sm:pr-2.5 max-sm:text-[9px] max-sm:tracking-[0.1em] max-sm:[@media(pointer:coarse)]:py-2",
                on ? "text-ink" : "border-white/[0.1] text-ink/85 hover:border-white/25 hover:text-ink",
                quiet && !on ? "opacity-30 hover:opacity-100 focus-visible:opacity-100" : "opacity-100",
              )}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: region.color, boxShadow: `0 0 8px ${region.color}` }}
              />
              {regionLabel(region.id, origin)}
              {/* counts are dropped on phone-width screens to keep labels off the brain */}
              <span className="text-ink-faint max-sm:hidden">{count}</span>
              {fresh > 0 && <span className="max-sm:hidden" style={{ color: region.color }}>+{fresh}</span>}
            </button>
          </div>
        );
      })}

      {/* hover card for the memory under the pointer */}
      <div
        ref={register("hover")}
        className="pointer-events-none absolute left-0 top-0 z-10 will-change-transform"
        style={{ opacity: 0 }}
      >
        {hovered && hoveredRegion && (
          <div className="glass-strong w-max max-w-[250px] -translate-x-1/2 -translate-y-[calc(100%+22px)] rounded-xl px-3 py-2">
            <p className="text-xs leading-snug text-ink">{hovered.title}</p>
            <p
              className="mt-1 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.14em]"
              style={{ color: hoveredRegion.color }}
            >
              <span className="h-1 w-1 rounded-full" style={{ background: hoveredRegion.color }} />
              {regionLabel(hoveredRegion.id, origin)}
              {/* only a confidence the source stated */}
              {typeof hovered.confidence === "number" && (
                <span className="text-ink-faint">· {hovered.confidence}% confident</span>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
