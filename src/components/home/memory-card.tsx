"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { memory } from "@/lib/data";

const COLORS = {
  violet: "var(--violet-bright)",
  cyan: "var(--cyan-bright)",
} as const;

export function MemoryCard() {
  const size = 96;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  let acc = 0;

  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Memory"
        action={
          <span className="font-mono text-[10px] text-cyan-bright">
            +{memory.fresh} today
          </span>
        }
      />

      <div className="mt-4 flex items-center gap-5">
        <div className="relative grid place-items-center" style={{ width: size, height: size }}>
          <svg width={size} height={size} className="-rotate-90">
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke="rgba(255,255,255,0.05)"
              strokeWidth={stroke}
            />
            {memory.shards.map((s, i) => {
              const len = (s.value / 100) * c;
              const seg = (
                <motion.circle
                  key={s.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={COLORS[s.accent]}
                  strokeWidth={stroke}
                  strokeLinecap="round"
                  strokeDasharray={`${len} ${c - len}`}
                  initial={{ strokeDashoffset: c }}
                  animate={{ strokeDashoffset: -acc }}
                  transition={{ duration: 1, delay: 0.1 * i, ease: [0.22, 1, 0.36, 1] }}
                  style={{ opacity: 0.85 - i * 0.12 }}
                />
              );
              acc += len;
              return seg;
            })}
          </svg>
          <div className="absolute text-center">
            <span className="font-mono text-lg font-semibold text-ink">
              {(memory.total / 1000).toFixed(1)}k
            </span>
          </div>
        </div>

        <ul className="flex-1 space-y-1.5">
          {memory.shards.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-xs">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: COLORS[s.accent] }}
              />
              <span className="flex-1 text-ink-muted">{s.label}</span>
              <span className="font-mono text-ink-faint">{s.value}%</span>
            </li>
          ))}
        </ul>
      </div>
    </GlassCard>
  );
}
