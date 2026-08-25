"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import {
  CATEGORIES,
  CATEGORY_META,
  type Accent,
  type MemoryCategory,
  type MemoryRecord,
  type MemoryOverview,
} from "@/lib/memory/types";
import type { CategorySelection } from "./category-filter";

const COLOR: Record<Accent, string> = {
  violet: "var(--violet-bright)",
  cyan: "var(--cyan-bright)",
  green: "var(--green)",
  amber: "var(--amber)",
  rose: "var(--rose)",
  faint: "var(--ink-faint)",
};

const CX = 200;
const CY = 134;
const R = 92;

/**
 * A restrained "knowledge constellation": each category is a node orbiting the
 * LILITH core, sized by how many memories it holds and glowing by their average
 * confidence, linked by soft neural traces. Clicking a node filters the grid.
 * Deliberately NOT a force-directed graph.
 */
export function MemoryConstellation({
  overview,
  records,
  active,
  onSelect,
}: {
  overview: MemoryOverview;
  records: MemoryRecord[];
  active: CategorySelection;
  onSelect: (c: CategorySelection) => void;
}) {
  // average confidence per category → glow intensity
  const conf = new Map<MemoryCategory, number>();
  const nById = new Map<MemoryCategory, number[]>();
  for (const r of records) {
    if (typeof r.confidence === "number") {
      const arr = nById.get(r.category) ?? [];
      arr.push(r.confidence);
      nById.set(r.category, arr);
    }
  }
  for (const c of CATEGORIES) {
    const arr = nById.get(c) ?? [];
    conf.set(c, arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0);
  }

  const nodes = CATEGORIES.map((c, i) => {
    const a = -Math.PI / 2 + i * ((2 * Math.PI) / CATEGORIES.length);
    const count = overview.byCategory[c] ?? 0;
    return {
      c,
      count,
      x: CX + R * Math.cos(a),
      y: CY + R * Math.sin(a),
      r: Math.min(24, 10 + count * 2.6),
      angle: a,
      color: COLOR[CATEGORY_META[c].accent],
      confidence: conf.get(c) ?? 0,
    };
  });

  return (
    <GlassCard className="p-5" animated={false}>
      <PanelHeader
        title="Knowledge constellation"
        action={
          <button
            onClick={() => onSelect("all")}
            className="font-mono text-[10px] text-ink-faint transition-colors hover:text-ink-muted"
          >
            {active === "all" ? "all categories" : "reset"}
          </button>
        }
      />

      <div className="mt-2">
        <svg
          viewBox="0 0 400 268"
          className="w-full"
          role="group"
          aria-label="Memory categories"
        >
          {/* neural links */}
          {nodes.map((n) => {
            const dim = active !== "all" && active !== n.c;
            return (
              <motion.line
                key={`l-${n.c}`}
                x1={CX}
                y1={CY}
                x2={n.x}
                y2={n.y}
                stroke={n.color}
                strokeWidth={active === n.c ? 1.4 : 0.7}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: dim ? 0.08 : 0.28 }}
                transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
              />
            );
          })}

          {/* satellite memory dots per category (restrained) */}
          {nodes.map((n) =>
            Array.from({ length: Math.min(n.count, 5) }).map((_, j) => {
              const spread = (j - (Math.min(n.count, 5) - 1) / 2) * 0.32;
              const rr = n.r + 8 + (j % 2) * 4;
              const dim = active !== "all" && active !== n.c;
              return (
                <motion.circle
                  key={`d-${n.c}-${j}`}
                  cx={n.x + rr * Math.cos(n.angle + spread)}
                  cy={n.y + rr * Math.sin(n.angle + spread)}
                  r={1.4}
                  fill={n.color}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: dim ? 0.12 : 0.55 }}
                  transition={{ duration: 0.8, delay: 0.4 + j * 0.05 }}
                />
              );
            }),
          )}

          {/* central LILITH core */}
          <circle cx={CX} cy={CY} r={30} fill="var(--violet-deep)" opacity={0.14} />
          <motion.circle
            cx={CX}
            cy={CY}
            r={13}
            fill="url(#core)"
            animate={{ opacity: [0.7, 1, 0.7], scale: [1, 1.06, 1] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            style={{ transformOrigin: `${CX}px ${CY}px` }}
          />
          <text
            x={CX}
            y={CY + 3}
            textAnchor="middle"
            className="fill-ink"
            style={{ fontSize: 7, fontFamily: "var(--font-mono)", letterSpacing: "0.1em" }}
          >
            LILITH
          </text>

          {/* category nodes */}
          {nodes.map((n) => {
            const dim = active !== "all" && active !== n.c;
            const on = active === n.c;
            return (
              <g
                key={`n-${n.c}`}
                onClick={() => onSelect(on ? "all" : n.c)}
                style={{ cursor: "pointer" }}
                opacity={dim ? 0.4 : 1}
              >
                {/* confidence glow halo */}
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={n.r + 6}
                  fill={n.color}
                  opacity={0.04 + (n.confidence / 100) * 0.14}
                />
                <motion.circle
                  cx={n.x}
                  cy={n.y}
                  r={n.r}
                  fill={n.color}
                  fillOpacity={on ? 0.28 : 0.16}
                  stroke={n.color}
                  strokeWidth={on ? 1.6 : 1}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.15 }}
                  style={{ transformOrigin: `${n.x}px ${n.y}px` }}
                  whileHover={{ scale: 1.12 }}
                />
                <text
                  x={n.x}
                  y={n.y + 1}
                  textAnchor="middle"
                  className="fill-ink"
                  style={{ fontSize: 8, fontFamily: "var(--font-mono)", fontWeight: 600 }}
                >
                  {n.count}
                </text>
                <text
                  x={n.x}
                  y={n.y + n.r + 11}
                  textAnchor="middle"
                  className="fill-ink-muted"
                  style={{ fontSize: 8 }}
                >
                  {CATEGORY_META[n.c].label}
                </text>
              </g>
            );
          })}

          <defs>
            <radialGradient id="core" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="var(--violet-bright)" />
              <stop offset="100%" stopColor="var(--violet-deep)" />
            </radialGradient>
          </defs>
        </svg>
      </div>
    </GlassCard>
  );
}
