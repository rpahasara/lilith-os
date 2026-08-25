import { ShieldCheck, Cloud, Cpu, Zap } from "lucide-react";
import { StatusDot } from "@/components/ui/primitives";
import { Clock } from "./clock";

const items = [
  { icon: Cloud, label: "Cloud sync", value: "Live" },
  { icon: Zap, label: "Automations", value: "Healthy" },
  { icon: ShieldCheck, label: "Security", value: "Private" },
  { icon: Cpu, label: "Latency", value: "48ms" },
];

export function StatusBar() {
  return (
    <footer className="flex h-9 shrink-0 items-center justify-between px-6 font-mono text-[11px] text-ink-faint">
      <div className="flex items-center gap-2">
        <StatusDot accent="green" />
        <span className="text-ink-muted">Lilith OS</span>
        <span>v1.0.0</span>
        <span className="text-green">Online</span>
      </div>

      <div className="hidden items-center gap-6 lg:flex">
        {items.map(({ icon: Icon, label, value }) => (
          <span key={label} className="flex items-center gap-1.5">
            <Icon className="h-3 w-3" />
            <span>{label}</span>
            <span className="text-ink-muted">{value}</span>
          </span>
        ))}
      </div>

      <Clock />
    </footer>
  );
}
