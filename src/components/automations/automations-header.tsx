"use client";

import { Cpu } from "lucide-react";
import type { Diagnostics } from "@/lib/api";
import { WorkspaceHeader } from "@/components/ui/primitives";
import type { WorkspaceIdentity } from "@/components/ui/data-state";

export const AUTOMATIONS_IDENTITY: WorkspaceIdentity = {
  icon: Cpu,
  eyebrow: "Agent fabric",
  title: "Autonomous Operations",
  description: "Lilith's background agents, watchers, and services.",
};

/**
 * The page header. The five-tile row that sat under it repeated the fleet
 * panel; health and the status counts now live there, and the unit-kind counts
 * on the filter tabs.
 */
export function AutomationsHeader({ isDemo, diagnostics }: { isDemo: boolean; diagnostics?: Diagnostics }) {
  return <WorkspaceHeader {...AUTOMATIONS_IDENTITY} isDemo={isDemo} diagnostics={diagnostics} />;
}
