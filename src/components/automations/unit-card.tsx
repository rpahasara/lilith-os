"use client";

import { motion } from "framer-motion";
import {
  Infinity as InfinityIcon,
  Clock,
  Zap,
  Hand,
  AlertTriangle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { KindBadge, StatusPill } from "./unit-chips";
import { RunHistory } from "./run-history";
import type { AutomationUnit, TriggerType } from "@/lib/automations/types";
import { timeAgo, shortDate, cn } from "@/lib/utils";
import { riseIn } from "@/lib/motion";

const TRIGGER_ICON: Record<TriggerType, LucideIcon> = {
  continuous: InfinityIcon,
  schedule: Clock,
  event: Zap,
  manual: Hand,
};

function relClock(iso?: string) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const diff = t - Date.now();
  const abs = Math.abs(diff);
  const m = Math.round(abs / 60000);
  if (m < 60) return diff >= 0 ? `in ${m}m` : `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return diff >= 0 ? `in ${h}h` : `${h}h ago`;
  return shortDate(iso);
}

export function UnitCard({ unit, selected, onSelect }: { unit: AutomationUnit; selected?: boolean; onSelect: (unit: AutomationUnit) => void }) {
  const TriggerIcon = TRIGGER_ICON[unit.trigger];
  const failed = unit.status === "failed";

  return (
    <motion.button type="button" onClick={() => onSelect(unit)} aria-pressed={selected}
      variants={riseIn}
      className={cn(
        "group rounded-[var(--radius-md)] border bg-white/[0.015] p-4 transition-colors",
        selected ? "border-wine-bright/35 bg-wine/10 text-left" : failed
          ? "border-rose/25 hover:border-rose/40"
          : "border-white/[0.06] text-left hover:border-white/12 hover:bg-white/[0.03]",
      )}
    >
      {/* header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-[15px] font-medium text-ink">{unit.name}</h3>
            <KindBadge kind={unit.kind} />
          </div>
          <p className="mt-0.5 truncate font-mono text-[10px] text-ink-faint">
            {unit.unit}
          </p>
        </div>
        <StatusPill status={unit.status} />
      </div>

      {/* purpose */}
      <p className="mt-2.5 line-clamp-2 text-xs leading-relaxed text-ink-muted">
        {unit.purpose}
      </p>

      {/* meta */}
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
        <Meta icon={TriggerIcon} label="Trigger">
          <span className="capitalize">{unit.trigger}</span>
          {unit.schedule && <span className="text-ink-faint"> · {unit.schedule}</span>}
        </Meta>
        <Meta
          icon={AlertTriangle}
          label="Failures"
          tone={(unit.failures ?? 0) > 0 ? "rose" : undefined}
        >
          {unit.failures == null
            ? "—"
            : unit.failures > 0
              ? `${unit.failures} recent`
              : "None"}
        </Meta>
        <Meta icon={Clock} label="Last run">
          {relClock(unit.lastRun)}
        </Meta>
        <Meta icon={Clock} label="Next run">
          {unit.nextRun ? relClock(unit.nextRun) : "—"}
        </Meta>
      </div>

      {/* footer */}
      <div className="mt-3 flex items-center justify-between border-t border-white/[0.05] pt-3">
        <RunHistory history={unit.history} />
        <span className="font-mono text-[10px] text-ink-faint">
          {unit.runsToday != null ? `${unit.runsToday} runs today` : ""}
        </span>
      </div>
    </motion.button>
  );
}

function Meta({
  icon: Icon,
  label,
  children,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  children: React.ReactNode;
  tone?: "rose";
}) {
  return (
    <div className="min-w-0">
      <p className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-ink-faint">
        <Icon className="h-2.5 w-2.5" />
        {label}
      </p>
      <p className={cn("truncate text-xs", tone === "rose" ? "text-rose" : "text-ink-muted")}>
        {children}
      </p>
    </div>
  );
}
