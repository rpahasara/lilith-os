import * as React from "react";
import { cn } from "@/lib/utils";

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

/* --------------------------------------------------------------- Accent map */
export const accentText = {
  violet: "text-violet-bright",
  cyan: "text-cyan-bright",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
} as const;

export const accentBg = {
  violet: "bg-violet-bright",
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
