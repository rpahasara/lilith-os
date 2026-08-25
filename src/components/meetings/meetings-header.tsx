"use client";

import { motion } from "framer-motion";
import { CalendarClock } from "lucide-react";
import type { MeetingsOverview } from "@/lib/meetings/types";
import type { Diagnostics } from "@/lib/api";
import { staggerContainer, riseIn } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { ConnectionStatus } from "@/components/ui/connection-status";

export function fmtCountdown(mins?: number | null): string {
  if (mins == null) return "—";
  if (mins < 0) return "now";
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h < 24) return m ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

function Tile({
  label,
  value,
  suffix,
  accent = "cyan",
}: {
  label: string;
  value: string | number;
  suffix?: string;
  accent?: "violet" | "cyan" | "green" | "amber";
}) {
  const color = {
    violet: "text-violet-bright",
    cyan: "text-cyan-bright",
    green: "text-green",
    amber: "text-amber",
  }[accent];
  return (
    <motion.div variants={riseIn} className="glass rounded-[var(--radius-md)] px-4 py-3">
      <p className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">{label}</p>
      <p className="mt-1 flex items-baseline gap-1">
        <span className={cn("font-mono text-2xl font-semibold", color)}>{value}</span>
        {suffix && <span className="text-xs text-ink-faint">{suffix}</span>}
      </p>
    </motion.div>
  );
}

export function MeetingsHeader({
  overview,
  isDemo,
  diagnostics,
}: {
  overview: MeetingsOverview;
  isDemo: boolean;
  diagnostics?: Diagnostics;
}) {
  const c = overview.counts;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-violet-bright/25 to-cyan-bright/15 hairline">
            <CalendarClock className="h-5 w-5 text-violet-bright" />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">
              Meetings Intelligence
            </h1>
            <p className="text-xs text-ink-muted">
              Everything Lilith knows and prepares around your time.
            </p>
          </div>
        </div>
        <ConnectionStatus isDemo={isDemo} diagnostics={diagnostics} />
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <Tile label="Next in" value={overview.next ? fmtCountdown(overview.next.minutesUntil) : "—"} accent="violet" />
        <Tile label="Today" value={c.todayTotal} accent="cyan" />
        <Tile label="Prepared" value={c.prepared} accent="green" />
        <Tile label="Follow-ups" value={c.followupsPending} suffix={`/ ${c.followupsTotal}`} accent="amber" />
        <Tile label="Context items" value={c.contextMessages} accent="cyan" />
      </motion.div>
    </div>
  );
}
