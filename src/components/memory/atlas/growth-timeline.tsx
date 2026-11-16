"use client";

import { type KeyboardEvent, type PointerEvent, useMemo, useRef } from "react";
import { Pause, Play, SkipForward } from "lucide-react";
import { REGIONS } from "@/lib/memory/atlas/regions";
import type { AtlasLink, AtlasNode } from "@/lib/memory/atlas/types";
import { cn } from "@/lib/utils";

const BINS = 72;
const W = 1000;
const H = 100;
/** `born` runs 0–0.96 across history; the chart works in 0–1. */
const frac = (born: number) => Math.min(1, born / 0.96);

/**
 * Growth timeline — how the atlas filled in. A slim strip beneath the brain:
 * a stacked stream of memories per domain, and a marker. Moving the marker
 * rewinds the brain itself, so the strip stays a control and the brain stays
 * the thing you watch.
 */
export function GrowthTimeline({
  nodes,
  links,
  origin,
  now,
  scrub,
  playing,
  onScrub,
  onPlay,
  className,
}: {
  nodes: AtlasNode[];
  links: AtlasLink[];
  origin: number;
  now: number;
  /** 0 = start of history, 1 = now. */
  scrub: number;
  playing: boolean;
  onScrub: (value: number) => void;
  onPlay: () => void;
  className?: string;
}) {
  const track = useRef<HTMLDivElement>(null);

  const layers = useMemo(() => {
    const total = Math.max(1, nodes.length);
    const base = new Float32Array(BINS);
    return REGIONS.map((region) => {
      const members = nodes.filter((n) => n.region === region.id).map((n) => frac(n.born));
      const top: string[] = [];
      const bottom: string[] = [];
      for (let k = 0; k < BINS; k++) {
        const t = k / (BINS - 1);
        const count = members.reduce((s, b) => s + (b <= t ? 1 : 0), 0);
        const y0 = H - (base[k] / total) * (H - 6);
        base[k] += count;
        const y1 = H - (base[k] / total) * (H - 6);
        const x = (t * W).toFixed(1);
        top.push(`${x},${y1.toFixed(1)}`);
        bottom.unshift(`${x},${y0.toFixed(1)}`);
      }
      return { region, area: `M${top.join("L")}L${bottom.join("L")}Z`, line: `M${top.join("L")}` };
    });
  }, [nodes]);

  const months = useMemo(() => {
    const out: { label: string; at: number }[] = [];
    const d = new Date(origin);
    d.setDate(1);
    d.setHours(0, 0, 0, 0);
    d.setMonth(d.getMonth() + 1);
    while (d.getTime() < now) {
      out.push({
        label: d.toLocaleDateString("en-GB", { month: "short" }),
        at: (d.getTime() - origin) / (now - origin),
      });
      d.setMonth(d.getMonth() + 1);
    }
    return out;
  }, [origin, now]);

  const memories = nodes.filter((n) => frac(n.born) <= scrub).length;
  const pathways = links.filter((l) => frac(l.born) <= scrub).length;
  const atNow = scrub >= 0.999;
  const date = new Date(origin + scrub * (now - origin));

  const seek = (e: PointerEvent<HTMLDivElement>) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect) return;
    onScrub(Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft") onScrub(Math.max(0, scrub - 0.02));
    else if (e.key === "ArrowRight") onScrub(Math.min(1, scrub + 0.02));
    else if (e.key === "Home") onScrub(0);
    else if (e.key === "End") onScrub(1);
    else return;
    e.preventDefault();
    // the arrows belong to the marker here, not to the camera
    e.stopPropagation();
  };

  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-white/[0.09] bg-[rgba(12,8,13,0.5)] px-4 pb-2.5 pt-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.07),0_18px_40px_-24px_rgba(0,0,0,0.95)] backdrop-blur-xl",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onPlay}
          aria-label={playing ? "Pause growth playback" : atNow ? "Replay growth from the start" : "Play growth"}
          style={{ borderRadius: 9999 }}
          className="grid h-8 w-8 shrink-0 place-items-center border border-wine/35 bg-gradient-to-br from-wine-deep/70 to-wine/45 text-ink transition-[border-color,box-shadow] hover:border-wine-bright/60 hover:shadow-[0_8px_24px_-12px_rgba(201,84,115,0.9)] [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11"
        >
          {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-px" />}
        </button>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-x-2.5">
            <span className="text-sm font-medium text-ink">
              {atNow ? "Now" : date.toLocaleDateString("en-GB", { day: "numeric", month: "long" })}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
              {memories} memories · {pathways} pathways
            </span>
          </p>
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint">
            {playing ? "Replaying growth" : atNow ? "Growth timeline · drag the marker to rewind" : "Growth timeline"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onScrub(1)}
          disabled={atNow}
          aria-label="Jump to now"
          title="Jump to now"
          style={{ borderRadius: 9999 }}
          className="grid h-8 w-8 shrink-0 place-items-center text-ink-muted transition-colors hover:bg-white/[0.06] hover:text-ink disabled:opacity-30 [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11"
        >
          <SkipForward className="h-3.5 w-3.5" />
        </button>
      </div>

      <div
        ref={track}
        role="slider"
        tabIndex={0}
        aria-label="Growth timeline position"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(scrub * 100)}
        aria-valuetext={atNow ? "Now" : date.toDateString()}
        onKeyDown={onKey}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          seek(e);
        }}
        onPointerMove={(e) => {
          if (e.currentTarget.hasPointerCapture(e.pointerId)) seek(e);
        }}
        className="relative mt-2.5 h-[52px] cursor-ew-resize touch-none select-none"
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible">
          {layers.map(({ region, area, line }) => (
            <g key={region.id}>
              <path d={area} fill={region.color} fillOpacity={0.3} />
              <path d={line} fill="none" stroke={region.color} strokeOpacity={0.85} strokeWidth={1} vectorEffect="non-scaling-stroke" />
            </g>
          ))}
          {/* everything after the marker has not happened yet */}
          <rect x={scrub * W} y={0} width={(1 - scrub) * W} height={H} fill="#0a070c" fillOpacity={0.8} />
          <line x1={0} x2={W} y1={H} y2={H} stroke="rgba(255,255,255,0.12)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        </svg>
        {/* marker */}
        <div className="pointer-events-none absolute inset-y-0" style={{ left: `${scrub * 100}%` }}>
          <span className="absolute -inset-y-1 -left-px w-0.5 rounded-full bg-gradient-to-b from-pearl via-wine-bright to-wine/40" />
          <span className="absolute -left-[5px] -top-2 h-2.5 w-2.5 rounded-full bg-pearl shadow-[0_0_12px_rgba(225,132,157,0.95)]" />
        </div>
      </div>

      <div className="relative mt-1 h-3.5">
        {months.map((m) => (
          <span
            key={m.at}
            className="absolute -translate-x-1/2 font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint"
            style={{ left: `${m.at * 100}%` }}
          >
            {m.label}
          </span>
        ))}
        <span className="absolute right-0 font-mono text-[9px] uppercase tracking-[0.14em] text-wine-bright/80">Now</span>
      </div>
    </div>
  );
}
