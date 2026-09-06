import * as React from "react";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { riseIn } from "@/lib/motion";
import type { Diagnostics } from "@/lib/api";
import { ConnectionStatus } from "@/components/ui/connection-status";

/* ---------------------------------------------------------------- Eyebrow */
export function Eyebrow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <p className={cn("eyebrow", className)}>{children}</p>;
}

/* ------------------------------------------------------------ PanelHeader */
export function PanelHeader({
  title,
  action,
  className,
}: {
  title: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between", className)}>
      <Eyebrow>{title}</Eyebrow>
      {action}
    </div>
  );
}

export function WorkspaceHeader({
  icon: Icon,
  eyebrow,
  title,
  description,
  isDemo,
  diagnostics,
}: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
  isDemo?: boolean;
  diagnostics?: Diagnostics;
}) {
  return (
    <div className="workspace-header flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3.5">
        <span className="glass relative grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-2xl text-wine-bright">
          <span className="absolute inset-x-1 top-0 h-px bg-gradient-to-r from-transparent via-pearl/55 to-transparent" />
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <Eyebrow className="mb-1 text-wine-bright/80">{eyebrow}</Eyebrow>
          <h1 className="text-[1.65rem] font-semibold tracking-[-0.035em] text-ink">{title}</h1>
          <p className="mt-0.5 max-w-2xl text-[13px] leading-relaxed text-ink-muted">{description}</p>
        </div>
      </div>
      {typeof isDemo === "boolean" && <ConnectionStatus isDemo={isDemo} diagnostics={diagnostics} />}
    </div>
  );
}

export function MetricTile({
  label,
  value,
  suffix,
  accent = "cyan",
}: {
  label: string;
  value: React.ReactNode;
  suffix?: string;
  accent?: Accent | "faint";
}) {
  const color = accent === "faint" ? "text-ink-muted" : accentText[accent];
  return (
    <motion.div variants={riseIn} className="glass metric-tile rounded-[var(--radius-md)] px-4 py-3.5">
      <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-muted">{label}</p>
      <p className="mt-1.5 flex items-baseline gap-1.5">
        <span className={cn("font-mono text-[1.4rem] font-semibold tracking-[-0.04em]", color)}>{value}</span>
        {suffix && <span className="text-[11px] text-ink-faint">{suffix}</span>}
      </p>
    </motion.div>
  );
}

/* --------------------------------------------------------------- Accent map */
export const accentText = {
  violet: "text-violet-bright",
  orchid: "text-orchid-bright",
  wine: "text-wine-bright",
  gold: "text-gold",
  cyan: "text-cyan-bright",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
} as const;

export const accentBg = {
  violet: "bg-violet-bright",
  orchid: "bg-orchid-bright",
  wine: "bg-wine-bright",
  gold: "bg-gold",
  cyan: "bg-cyan-bright",
  green: "bg-green",
  amber: "bg-amber",
  rose: "bg-rose",
} as const;

export type Accent = keyof typeof accentText;

/* ---------------------------------------------------------------- StatusDot */
export function StatusDot({
  accent = "green",
  className,
}: {
  accent?: Accent;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "status-dot inline-block h-1.5 w-1.5 rounded-full",
        accentBg[accent],
        className,
      )}
      style={{ color: `var(--${accent === "green" ? "green" : accent})` }}
    />
  );
}

/* ---------------------------------------------------------------- Bars mini */
export function Bars({
  values,
  accent = "cyan",
}: {
  values: number[];
  accent?: Accent;
}) {
  return (
    <div className="flex items-end gap-0.5">
      {values.map((v, i) => (
        <span
          key={i}
          className={cn("w-[3px] rounded-full", accentBg[accent])}
          style={{ height: `${v * 3}px`, opacity: 0.35 + v * 0.12 }}
        />
      ))}
    </div>
  );
}
