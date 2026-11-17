"use client";

import { CalendarClock } from "lucide-react";
import type { Diagnostics } from "@/lib/api";
import { WorkspaceHeader } from "@/components/ui/primitives";
import type { WorkspaceIdentity } from "@/components/ui/data-state";

export const MEETINGS_IDENTITY: WorkspaceIdentity = {
  icon: CalendarClock,
  eyebrow: "Temporal field",
  title: "Meetings Intelligence",
  description: "Everything Lilith knows and prepares around your time.",
};

/**
 * The page header. The five-tile row that sat under it restated the next
 * meeting, the schedule and the follow-ups beneath it; those panels carry the
 * counts now (the schedule also says how many are prepared).
 */
export function MeetingsHeader({ isDemo, diagnostics }: { isDemo: boolean; diagnostics?: Diagnostics }) {
  return <WorkspaceHeader {...MEETINGS_IDENTITY} isDemo={isDemo} diagnostics={diagnostics} />;
}
