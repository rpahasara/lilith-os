"use client";

import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { Ring } from "@/components/ui/ring";
import type { AutomationHealth } from "@/lib/automations/types";
import { cn } from "@/lib/utils";

/**
 * The fleet at a glance: health, and how many units are in each state. (Unit
 * kinds are counted on the filter tabs, where they also filter.)
 */
export function FleetOverview({ health }: { health: AutomationHealth }) {
  const states = [
    { label: "Running", value: health.running, dot: "bg-green" },
    { label: "Active", value: health.active, dot: "bg-cyan-bright" },
    { label: "Scheduled", value: health.waiting, dot: "bg-ink-faint" },
    { label: "Failed", value: health.failed, dot: health.failed ? "bg-rose" : "bg-white/15" },
  ];

  return (
    <GlassCard className="p-5">
      <PanelHeader title="Fleet" action={<span className="font-mono text-micro text-ink-faint">{health.total} units</span>} />
      <div className="mt-4 flex items-center gap-5">
        <Ring value={health.score} size={104} stroke={8} label={`${health.score}%`} sub="healthy" from="var(--cyan-bright)" to="var(--green)" />
        <ul className="flex-1 space-y-2">
          {states.map((state) => (
            <li key={state.label} className="flex items-center gap-2 text-xs">
              <span className={cn("h-2 w-2 rounded-full", state.dot)} />
              <span className="flex-1 text-ink-muted">{state.label}</span>
              <span className={cn("font-mono", state.label === "Failed" && state.value ? "text-rose" : "text-ink-faint")}>{state.value}</span>
            </li>
          ))}
        </ul>
      </div>
    </GlassCard>
  );
}
