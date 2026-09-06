"use client";

import { motion } from "framer-motion";
import { CalendarClock } from "lucide-react";
import type { MeetingsOverview } from "@/lib/meetings/types";
import type { Diagnostics } from "@/lib/api";
import { staggerContainer } from "@/lib/motion";
import { MetricTile, WorkspaceHeader } from "@/components/ui/primitives";

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
      <WorkspaceHeader icon={CalendarClock} eyebrow="Temporal field" title="Meetings Intelligence" description="Everything Lilith knows and prepares around your time." isDemo={isDemo} diagnostics={diagnostics} />

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
      >
        <MetricTile label="Next in" value={overview.next ? fmtCountdown(overview.next.minutesUntil) : "—"} accent="wine" />
        <MetricTile label="Today" value={c.todayTotal} accent="cyan" />
        <MetricTile label="Prepared" value={c.prepared} accent="green" />
        <MetricTile label="Follow-ups" value={c.followupsPending} suffix={`/ ${c.followupsTotal}`} accent="gold" />
        <MetricTile label="Context items" value={c.contextMessages} accent="cyan" />
      </motion.div>
    </div>
  );
}
