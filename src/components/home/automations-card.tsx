"use client";

import { GlassCard } from "@/components/ui/card";
import { PanelHeader, StatusDot } from "@/components/ui/primitives";
import { Ring } from "@/components/ui/ring";
import { automations } from "@/lib/data";

export function AutomationsCard() {
  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader
        title="Automation health"
        action={
          <span className="flex items-center gap-1.5 font-mono text-[10px] text-green">
            <StatusDot accent="green" /> All systems go
          </span>
        }
      />

      <div className="mt-4 flex items-center gap-5">
        <Ring
          value={automations.healthy}
          size={96}
          stroke={8}
          label={`${automations.healthy}%`}
          from="var(--cyan-bright)"
          to="var(--green)"
        />
        <div className="flex-1 space-y-2">
          <Stat label="Running" value={automations.running} accent="var(--cyan-bright)" />
          <Stat label="Idle" value={automations.idle} accent="var(--ink-faint)" />
          <Stat label="Failed" value={automations.failed} accent="var(--green)" />
        </div>
      </div>

      <div className="mt-4 space-y-1.5">
        {automations.items.map((a) => (
          <div
            key={a.name}
            className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.03]"
          >
            <span className="text-xs text-ink-muted">{a.name}</span>
            <span
              className={`font-mono text-[10px] ${
                a.status === "running" ? "text-cyan-bright" : "text-ink-faint"
              }`}
            >
              {a.status}
            </span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-ink-muted">{label}</span>
      <span className="font-mono text-sm font-medium" style={{ color: accent }}>
        {value}
      </span>
    </div>
  );
}
