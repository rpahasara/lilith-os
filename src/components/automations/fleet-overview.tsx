"use client";

import { GlassCard } from "@/components/ui/card";
import { PanelHeader } from "@/components/ui/primitives";
import { Ring } from "@/components/ui/ring";
import { KIND_META, type AutomationUnit, type UnitKind } from "@/lib/automations/types";

const ACCENT_VAR: Record<string, string> = {
  violet: "var(--violet-bright)",
  cyan: "var(--cyan-bright)",
  green: "var(--green)",
  amber: "var(--amber)",
};

const ORDER: UnitKind[] = ["service", "watcher", "timer", "agent"];

export function FleetOverview({
  units,
  score,
}: {
  units: AutomationUnit[];
  score: number;
}) {
  const counts = ORDER.map((kind) => ({
    kind,
    count: units.filter((u) => u.kind === kind).length,
  }));

  return (
    <GlassCard className="p-5" interactive>
      <PanelHeader title="Fleet" />

      <div className="mt-4 flex items-center gap-5">
        <Ring
          value={score}
          size={104}
          stroke={8}
          label={`${score}%`}
          sub="healthy"
          from="var(--cyan-bright)"
          to="var(--green)"
        />
        <ul className="flex-1 space-y-2">
          {counts.map(({ kind, count }) => {
            const meta = KIND_META[kind];
            return (
              <li key={kind} className="flex items-center gap-2 text-xs">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: ACCENT_VAR[meta.accent] }}
                />
                <span className="flex-1 text-ink-muted">{meta.label}s</span>
                <span className="font-mono text-ink-faint">{count}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </GlassCard>
  );
}
