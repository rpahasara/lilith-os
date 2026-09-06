"use client";

import { Activity, Braces, Cpu, Database, Gauge, Globe2, KeyRound, LockKeyhole, Mic2, MonitorCog, PlugZap, ShieldCheck, TriangleAlert, type LucideIcon } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { WorkspaceHeader } from "@/components/ui/primitives";
import { ContextAction, SectionHeader, StatusBadge } from "@/components/ui/workspace";

const integrations = [
  { name: "Gmail", purpose: "Career signals and meeting context" },
  { name: "Google Calendar", purpose: "Upcoming meetings and prep timing" },
  { name: "Career data", purpose: "Application pipeline and activity" },
  { name: "Automation runtime", purpose: "Services, timers, watchers, and agents" },
];

export default function SystemPage() {
  const environment = process.env.NODE_ENV === "production" ? "Production build" : "Development build";
  return <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
    <WorkspaceHeader icon={Activity} eyebrow="Control surface" title="System" description="Runtime visibility, integrations, permissions, and diagnostics in one place." />
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <GlassCard className="p-5" animated={false}>
          <SectionHeader title="Runtime" description="What this client can verify without exposing sensitive configuration." action={<StatusBadge label="Client active" tone="green"/>}/>
          <div className="mt-4 grid gap-3 sm:grid-cols-2"><RuntimeItem icon={Globe2} name="Application shell" detail={environment} status="Active" tone="green"/><RuntimeItem icon={MonitorCog} name="Avatar renderer" detail="Managed by the shared shell" status="Enabled" tone="cyan"/><RuntimeItem icon={Mic2} name="Voice pipeline" detail="Status remains in the voice surface" status="Module-owned" tone="faint"/><RuntimeItem icon={Cpu} name="Backend services" detail="Verified per workspace endpoint" status="Module-owned" tone="faint"/></div>
        </GlassCard>
        <GlassCard className="p-5" animated={false}>
          <SectionHeader title="Integrations" description="Capability boundaries are visible here; connection details stay private." action={<Button size="sm" disabled title="Integration management is not connected"><PlugZap className="h-3.5 w-3.5"/>Manage</Button>}/>
          <div className="mt-4 divide-y divide-white/[0.06]">{integrations.map((item) => <div key={item.name} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white/[0.04]"><PlugZap className="h-3.5 w-3.5 text-cyan-bright"/></span><div className="min-w-0 flex-1"><p className="text-sm text-ink">{item.name}</p><p className="truncate text-xs text-ink-faint">{item.purpose}</p></div><StatusBadge label="See module" tone="faint"/></div>)}</div>
        </GlassCard>
        <GlassCard className="p-5" animated={false}>
          <SectionHeader title="Privacy & permissions" description="Sensitive values are never rendered in this workspace." action={<StatusBadge label="Least privilege" tone="green"/>}/>
          <div className="mt-4 grid gap-3 sm:grid-cols-3"><Permission icon={KeyRound} title="Credentials" text="Stored outside the UI and never displayed."/><Permission icon={ShieldCheck} title="Write actions" text="Disabled until an approval-aware endpoint exists."/><Permission icon={Database} title="Local data" text="Views show normalized records, never raw secrets."/></div>
        </GlassCard>
      </div>
      <div className="space-y-4">
        <GlassCard className="p-5" animated={false}><SectionHeader title="Environment" /><dl className="mt-4 space-y-3"><Datum label="Application" value="LILITH OS"/><Datum label="Version" value="0.1.0"/><Datum label="Build mode" value={environment}/><Datum label="UI baseline" value="Home V2 approved"/></dl></GlassCard>
        <GlassCard className="p-5" animated={false}><SectionHeader title="Performance" description="Detailed telemetry is waiting for a measured runtime source." /><div className="mt-4"><ContextAction icon={Gauge} title="Runtime metrics" description="No performance endpoint is connected, so values are intentionally omitted." disabled/></div></GlassCard>
        <GlassCard className="p-5" animated={false}>
          <details className="group"><summary className="cursor-pointer list-none"><SectionHeader title="Advanced diagnostics" description="Development notes and low-level checks." action={<Braces className="h-4 w-4 text-ink-faint"/>}/></summary><div className="mt-4 space-y-3 border-t border-white/[0.06] pt-4"><div className="rounded-xl border border-amber/15 bg-amber/[0.04] p-3"><p className="flex items-center gap-2 text-xs font-medium text-amber"><TriangleAlert className="h-3.5 w-3.5"/>Known development-only renderer signal</p><p className="mt-1.5 text-[11px] leading-relaxed text-ink-faint">React Strict Mode may recreate the R3F canvas during development and report WebGL context loss. The approved production build remains the validation target.</p></div><p className="flex items-center gap-2 text-[10px] text-ink-faint"><LockKeyhole className="h-3 w-3"/>Tokens, keys, account addresses, and API targets are omitted.</p></div></details>
        </GlassCard>
      </div>
    </div>
  </div>;
}

function RuntimeItem({ icon: Icon, name, detail, status, tone }: { icon: LucideIcon; name: string; detail: string; status: string; tone: "green"|"cyan"|"faint" }) { return <div className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3"><Icon className="mt-0.5 h-4 w-4 text-ink-faint"/><div className="min-w-0 flex-1"><p className="text-xs font-medium text-ink">{name}</p><p className="mt-0.5 text-[10px] text-ink-faint">{detail}</p></div><StatusBadge label={status} tone={tone}/></div>; }
function Permission({ icon: Icon, title, text }: { icon: LucideIcon; title: string; text: string }) { return <div className="rounded-xl bg-white/[0.025] p-3"><Icon className="h-4 w-4 text-violet-bright"/><p className="mt-2 text-xs font-medium text-ink">{title}</p><p className="mt-1 text-[10px] leading-relaxed text-ink-faint">{text}</p></div>; }
function Datum({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-3"><dt className="text-xs text-ink-faint">{label}</dt><dd className="font-mono text-[11px] text-ink-muted">{value}</dd></div>; }
