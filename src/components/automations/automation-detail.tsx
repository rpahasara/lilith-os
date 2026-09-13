"use client";

import { Clock3, Hand, Pause, Play, ShieldCheck, Waypoints, Zap } from "lucide-react";
import { ContextAction, DetailDrawer, StatusBadge } from "@/components/ui/workspace";
import { KIND_META, STATUS_META, type AutomationEvent, type AutomationUnit } from "@/lib/automations/types";
import { timeAgo } from "@/lib/utils";

const tone = { green: "green", cyan: "cyan", amber: "amber", rose: "rose", faint: "faint" } as const;
export function AutomationDetail({ unit, activity, onClose }: { unit: AutomationUnit | null; activity: AutomationEvent[]; onClose: () => void }) {
  const events = unit ? activity.filter((item) => item.unit === unit.name || item.unit === unit.unit) : [];
  return <DetailDrawer open={Boolean(unit)} onClose={onClose} eyebrow="Automation detail" title={unit?.name ?? "Automation"}>{unit && <div className="space-y-6">
    <div className="flex flex-wrap items-center gap-2"><StatusBadge label={STATUS_META[unit.status].label} tone={tone[STATUS_META[unit.status].accent]} /><StatusBadge label={KIND_META[unit.kind].label} tone="violet" /><span className="font-mono text-[10px] text-ink-faint">{unit.unit}</span></div>
    <p className="text-sm leading-relaxed text-ink-muted">{unit.purpose}</p>
    <section><p className="eyebrow">Execution flow</p><div className="mt-3 grid grid-cols-4 gap-1">{[["Trigger", unit.schedule ?? unit.trigger], ["Condition", "No rules exposed"], ["Action", unit.purpose], ["Result", unit.lastResult ?? "No result"]].map(([label, value], index) => <div key={label} className="relative min-w-0 rounded-xl border border-white/[0.06] bg-white/[0.025] p-2.5"><p className="font-mono text-[8px] uppercase tracking-wider text-ink-faint">{index + 1} · {label}</p><p className="mt-1 line-clamp-2 text-[10px] text-ink-muted">{value}</p></div>)}</div></section>
    <section><p className="eyebrow">Schedule & scope</p><div className="mt-2 grid grid-cols-2 gap-2"><Info icon={Zap} label="Trigger" value={unit.trigger}/><Info icon={Clock3} label="Next run" value={unit.nextRun ? timeAgo(unit.nextRun) : "Not scheduled"}/><Info icon={Waypoints} label="Scope" value={unit.kind}/><Info icon={ShieldCheck} label="Permissions" value="Not exposed by API"/></div></section>
    <section><div className="flex items-center justify-between"><p className="eyebrow">Run history</p><StatusBadge label={`${events.length} linked`} tone={events.some((e) => e.outcome === "failure") ? "rose" : "cyan"}/></div>{events.length ? <ul className="mt-3 space-y-2">{events.map((event) => <li key={event.id} className="rounded-xl bg-white/[0.025] p-3"><div className="flex justify-between gap-3"><p className="text-xs text-ink-muted">{event.text}</p><StatusBadge label={event.outcome} tone={event.outcome === "failure" ? "rose" : event.outcome === "success" ? "green" : "faint"}/></div><p className="mt-1 font-mono text-[10px] text-ink-faint">{timeAgo(event.time)}</p></li>)}</ul> : <p className="mt-2 text-xs text-ink-faint">No unit-linked execution records are available.</p>}</section>
    <section><p className="eyebrow">Controls</p><div className="mt-2 grid gap-2"><ContextAction icon={Play} title="Run now" description="Requires a protected execution endpoint." disabled/><ContextAction icon={unit.enabled ? Pause : Play} title={unit.enabled ? "Pause automation" : "Resume automation"} description="Runtime state is read-only in this build." disabled/><ContextAction icon={Hand} title="Edit workflow" description="Editing arrives with the automation builder." disabled/></div></section>
  </div>}</DetailDrawer>;
}

function Info({ icon: Icon, label, value }: { icon: typeof Zap; label: string; value: string }) { return <div className="rounded-xl bg-white/[0.025] p-3"><p className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-ink-faint"><Icon className="h-3 w-3"/>{label}</p><p className="mt-1 truncate text-xs capitalize text-ink-muted">{value}</p></div>; }
