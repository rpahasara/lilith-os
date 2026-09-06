import { ShieldCheck, Cloud, Cpu, Zap } from "lucide-react";
import { StatusDot } from "@/components/ui/primitives";

const items = [
  { icon: Cloud, label: "Cloud sync", value: "Live" },
  { icon: Zap, label: "Automations", value: "Healthy" },
  { icon: ShieldCheck, label: "Security", value: "Private" },
  { icon: Cpu, label: "Latency", value: "48ms" },
];

/**
 * Home status is a quiet floating capsule — not a full-width architectural bar.
 * It keeps the essential system-state glanceable without completing a box
 * around Lilith.
 */
export function StatusBar() {
  return (
    <footer className="flex shrink-0 items-center justify-center px-6 pb-4 pt-1">
      <div className="glass flex items-center gap-3 rounded-full px-4 py-2 font-mono text-[10px] text-ink-faint shadow-[0_16px_38px_-24px_rgba(0,0,0,0.95)]">
        <span className="flex items-center gap-1.5">
          <StatusDot accent="green" />
          <span className="font-medium text-ink">Lilith OS</span>
          <span className="text-green">Online</span>
        </span>
        <span className="hidden h-3 w-px bg-white/10 sm:block" />
        <span className="hidden items-center gap-4 sm:flex">
          {items.map(({ icon: Icon, label, value }) => (
            <span key={label} className="flex items-center gap-1.5">
              <Icon className="h-3 w-3 text-ink-faint" />
              <span className="text-ink-muted">{value}</span>
            </span>
          ))}
        </span>
      </div>
    </footer>
  );
}
