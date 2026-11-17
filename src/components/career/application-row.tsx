"use client";

import { motion } from "framer-motion";
import { ArrowRight, Bell, Radio } from "lucide-react";
import { StageBadge } from "./stage-badge";
import { ConfidenceBar } from "./confidence-bar";
import type { Application } from "@/lib/career/types";
import { timeAgo, shortDate } from "@/lib/utils";

/*
 * Two layouts, chosen by the width the tracker card actually has (it is an
 * `@container`), not by the viewport:
 *
 *   @md and up (28rem+, every tablet and desktop width) — the approved row:
 *     company mark beside one column of title, activity, confidence and meta,
 *     with single-line titles that truncate.
 *   narrow (a phone) — the mark and the stage badge share the top line, the
 *     title and everything under it take the full row width, the details drop
 *     to one column on the narrowest cards, and titles, companies and contacts
 *     wrap instead of truncating: nothing is cut off, nothing scrolls sideways.
 *
 * The grid reproduces the old `flex gap-3` layout exactly at @md: the mark spans
 * both rows, so the body starts straight under the header as before. The meta
 * grid's 4 columns now follow the card width (@md) rather than the viewport
 * (sm); every tablet and desktop card is wider than @md, so they keep 4.
 */

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-micro uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      <p className="text-xs text-ink-muted [overflow-wrap:anywhere] @md:truncate">{value}</p>
    </div>
  );
}

export function ApplicationRow({ app, selected, onSelect }: { app: Application; selected?: boolean; onSelect: (app: Application) => void }) {
  return (
    <motion.button type="button" onClick={() => onSelect(app)} aria-pressed={selected}
      className={`group w-full rounded-[var(--radius-md)] border p-3 text-left transition-colors @md:p-4 ${selected ? "border-wine-bright/35 bg-wine/10" : "border-white/[0.06] bg-white/[0.015] hover:border-white/12 hover:bg-white/[0.03]"}`}
    >
      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-2.5 @md:gap-x-3">
        {/* company mark */}
        <div className="col-start-1 row-start-1 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-orchid-deep/60 to-cyan-deep/50 text-xs font-semibold text-white ring-1 ring-white/10 @md:row-span-2 @md:h-11 @md:w-11 @md:rounded-2xl @md:text-sm">
          {app.company.charAt(0)}
        </div>

        {/* header: narrow, its two parts join the row grid (badges beside the
            mark, title on its own full-width line); @md, the approved flex row */}
        <div className="contents @md:col-start-2 @md:row-start-1 @md:flex @md:min-w-0 @md:items-start @md:justify-between @md:gap-3">
          <div className="col-span-2 row-start-2 mt-2 min-w-0 @md:mt-0">
            <h3 className="text-lead font-medium text-ink [overflow-wrap:anywhere] @md:truncate">
              {app.role}
            </h3>
            <p className="text-xs text-ink-muted [overflow-wrap:anywhere] @md:truncate">
              {app.company}
              {app.location && (
                <span className="text-ink-faint"> · {app.location}</span>
              )}
            </p>
          </div>
          <div className="col-start-2 row-start-1 flex shrink-0 items-center gap-2 self-center justify-self-end @md:self-auto">
            {app.followUp && (
              <span
                title="Follow-up signal"
                className="grid h-6 w-6 place-items-center rounded-full bg-amber/12 text-amber"
              >
                <Bell className="h-3 w-3" />
              </span>
            )}
            <StageBadge stage={app.stage} />
          </div>
        </div>

        <div className="col-span-2 row-start-3 min-w-0 @md:col-span-1 @md:col-start-2 @md:row-start-2">
          {/* last activity — flows as one paragraph when narrow */}
          <p className="mt-2 text-xs text-ink-muted @md:flex @md:items-center @md:gap-1.5">
            <Radio className="mr-1.5 inline h-3 w-3 align-[-2px] text-cyan-bright/70 @md:mr-0" />
            {app.lastActivityLabel}
            <span className="ml-1 text-ink-faint @md:ml-0">· {timeAgo(app.lastActivity)}</span>
          </p>

          {/* confidence */}
          <div className="mt-3 flex items-center gap-3">
            <span className="font-mono text-micro uppercase tracking-wider text-ink-faint">
              Confidence
            </span>
            <ConfidenceBar value={app.confidence} className="max-w-[220px]" />
          </div>

          {/* meta grid */}
          <div className="mt-3 grid grid-cols-1 gap-x-4 gap-y-2 @min-[13rem]:grid-cols-2 @md:grid-cols-4">
            <Meta label="Source" value={app.sourceAccount} />
            <Meta label="Activity" value={`${app.activityCount} events`} />
            <Meta
              label="Contact"
              value={app.recruiter?.name ?? app.recruiter?.contact ?? "—"}
            />
            <Meta
              label="Next"
              value={
                app.nextAction
                  ? app.nextAction.due
                    ? `${shortDate(app.nextAction.due)}`
                    : "Pending"
                  : "—"
              }
            />
          </div>

          {/* next action call-to-action */}
          {app.nextAction && (
            <span className="mt-3 flex items-center gap-1.5 text-xs font-medium text-orchid-bright transition-opacity group-hover:opacity-80">
              {app.nextAction.label}
              <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
            </span>
          )}
        </div>
      </div>
    </motion.button>
  );
}
