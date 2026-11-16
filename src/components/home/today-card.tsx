"use client";

import { motion } from "framer-motion";
import { CalendarDays, CloudOff, Flag, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { staggerContainer, riseIn } from "@/lib/motion";
import {
  clockIn,
  dueLabel,
  durationLabel,
  zoneHint,
  type HomeMeetingsView,
} from "@/lib/home/meetings-view";

interface Row {
  icon: LucideIcon;
  text: string;
  meta?: string;
}

function rowsFor(view: Extract<HomeMeetingsView, { kind: "live" }>, now: number): Row[] {
  const { today, nextDue, focus, timeZone } = view;
  const meetings: Row =
    today.total === 0
      ? { icon: CalendarDays, text: "No meetings today" }
      : {
          icon: CalendarDays,
          text: `${today.total} ${today.total === 1 ? "meeting" : "meetings"} today`,
          meta: today.remaining === 0 ? "all done" : `${today.remaining} left`,
        };
  const followup: Row = nextDue
    ? { icon: Flag, text: nextDue.title, meta: dueLabel(nextDue.dueMs, now, timeZone) }
    : { icon: Flag, text: "No follow-ups due" };
  const window: Row = focus
    ? focus.current
      ? {
          icon: Target,
          text: "Focus window open",
          meta: `${durationLabel(focus.minutes)}, until ${clockIn(focus.endMs, timeZone)}`,
        }
      : {
          icon: Target,
          text: "Next focus window",
          meta: `${clockIn(focus.startMs, timeZone)}, ${durationLabel(focus.minutes)}`,
        }
    : { icon: Target, text: "No focus window in the next 48h" };
  return [meetings, followup, window];
}

/**
 * TODAY — the single "what matters today" glass object: meetings, the next
 * dated follow-up, and the current or next focus window (a real gap between
 * meetings, never a score). Everything comes from the live read-only meetings
 * data; when that is unavailable the card says so instead of inventing a day.
 */
export function TodayCard({ view, now }: { view: HomeMeetingsView; now: number | null }) {
  return (
    <GlassCard
      panel
      interactive
      className="w-full max-w-[284px] px-4 py-4"
      data-home-card="today"
      data-home-state={view.kind}
    >
      <span className="pointer-events-none absolute inset-y-5 left-0 w-px bg-gradient-to-b from-transparent via-wine-bright/55 to-transparent" />
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow text-ink">Today</span>
        {view.kind === "live" && view.stale ? (
          <span
            className="font-mono text-micro text-amber/90"
            title="The agenda has not refreshed recently"
          >
            {view.asOf ? `as of ${clockIn(new Date(view.asOf).getTime(), view.timeZone)}` : "freshness unknown"}
          </span>
        ) : view.kind === "live" && zoneHint(view.timeZone) ? (
          <span className="font-mono text-micro text-ink-faint" title={`Times shown in ${view.timeZone}`} data-home-zone="">
            {zoneHint(view.timeZone)}
          </span>
        ) : null}
      </div>

      {view.kind === "live" && now != null ? (
        <motion.ul
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="mt-3 space-y-2"
        >
          {rowsFor(view, now).map((r) => (
            <motion.li key={r.text} variants={riseIn} className="flex items-center gap-2.5">
              <RowIcon icon={r.icon} />
              <div className="min-w-0 leading-tight">
                <span className="text-compact text-ink">{r.text}</span>
                {r.meta && <span className="ml-1.5 text-micro text-ink-faint">{r.meta}</span>}
              </div>
            </motion.li>
          ))}
        </motion.ul>
      ) : view.kind === "unavailable" ? (
        <div className="mt-3 flex items-center gap-2.5" role="status">
          <RowIcon icon={CloudOff} />
          <div className="min-w-0 leading-tight">
            <span className="block text-compact text-ink">Agenda unavailable</span>
            <span className="block text-micro text-ink-faint">
              The meetings service isn&apos;t reachable, so nothing is shown.
            </span>
          </div>
        </div>
      ) : (
        <ul className="mt-3 space-y-2" aria-busy="true" aria-label="Loading today">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex items-center gap-2.5">
              <span className="h-7 w-7 shrink-0 animate-pulse rounded-full bg-white/[0.06]" />
              <span className="h-3 w-40 animate-pulse rounded bg-white/[0.06]" />
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}

function RowIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-wine/15 bg-wine/[0.12] text-wine-bright shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]">
      <Icon className="h-3 w-3" />
    </span>
  );
}
