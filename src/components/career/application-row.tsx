"use client";

import { motion } from "framer-motion";
import { ArrowRight, Bell, Radio } from "lucide-react";
import { StageBadge } from "./stage-badge";
import { ConfidenceBar } from "./confidence-bar";
import type { Application } from "@/lib/career/types";
import { timeAgo, shortDate } from "@/lib/utils";
import { riseIn } from "@/lib/motion";

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[9px] uppercase tracking-wider text-ink-faint">
        {label}
      </p>
      <p className="truncate text-xs text-ink-muted">{value}</p>
    </div>
  );
}

export function ApplicationRow({ app }: { app: Application }) {
  return (
    <motion.article
      variants={riseIn}
      className="group rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.015] p-4 transition-colors hover:border-white/12 hover:bg-white/[0.03]"
    >
      <div className="flex items-start gap-3">
        {/* company mark */}
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-violet-deep/60 to-cyan-deep/50 text-sm font-semibold text-white ring-1 ring-white/10">
          {app.company.charAt(0)}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-[15px] font-medium text-ink">
                {app.role}
              </h3>
              <p className="truncate text-xs text-ink-muted">
                {app.company}
                {app.location && (
                  <span className="text-ink-faint"> · {app.location}</span>
                )}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
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

          {/* last activity */}
          <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-muted">
            <Radio className="h-3 w-3 text-cyan-bright/70" />
            {app.lastActivityLabel}
            <span className="text-ink-faint">· {timeAgo(app.lastActivity)}</span>
          </p>

          {/* confidence */}
          <div className="mt-3 flex items-center gap-3">
            <span className="font-mono text-[9px] uppercase tracking-wider text-ink-faint">
              Confidence
            </span>
            <ConfidenceBar value={app.confidence} className="max-w-[220px]" />
          </div>

          {/* meta grid */}
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
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
            <button className="mt-3 flex items-center gap-1.5 text-xs font-medium text-violet-bright transition-opacity hover:opacity-80">
              {app.nextAction.label}
              <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
            </button>
          )}
        </div>
      </div>
    </motion.article>
  );
}
