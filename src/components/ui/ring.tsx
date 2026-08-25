"use client";

import { motion } from "framer-motion";

interface RingProps {
  value: number; // 0..100
  size?: number;
  stroke?: number;
  label?: string;
  sub?: string;
  from?: string;
  to?: string;
}

/** Animated circular progress with a violet→cyan gradient stroke. */
export function Ring({
  value,
  size = 116,
  stroke = 8,
  label,
  sub,
  from = "var(--violet-bright)",
  to = "var(--cyan-bright)",
}: RingProps) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  const gid = `ring-${from}-${to}`.replace(/[^a-z0-9]/gi, "");

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={gid} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={from} />
            <stop offset="100%" stopColor={to} />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`url(#${gid})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute grid place-items-center text-center">
        {label && (
          <span className="font-mono text-2xl font-semibold tracking-tight text-ink">
            {label}
          </span>
        )}
        {sub && <span className="text-[10px] text-ink-faint">{sub}</span>}
      </div>
    </div>
  );
}
