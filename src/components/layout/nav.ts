import type { LucideIcon } from "lucide-react";
import {
  LayoutGrid,
  Briefcase,
  Brain,
  Workflow,
  CalendarClock,
  Activity,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** true once the module has a real, built experience */
  ready?: boolean;
}

/**
 * Primary OS workspaces. Lilith herself is present everywhere through the
 * global command bar + presence engine, so Chat is not a primary destination;
 * Integrations live under System/Settings, not the top-level rail.
 */
export const nav: NavItem[] = [
  { label: "Command", href: "/", icon: LayoutGrid, ready: true },
  { label: "Career", href: "/career", icon: Briefcase, ready: true },
  { label: "Memory", href: "/memory", icon: Brain, ready: true },
  { label: "Automations", href: "/automations", icon: Workflow },
  { label: "Meetings", href: "/meetings", icon: CalendarClock },
  { label: "System", href: "/system", icon: Activity },
];
