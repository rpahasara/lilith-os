"use client";

import { Briefcase } from "lucide-react";
import type { Diagnostics } from "@/lib/api";
import { WorkspaceHeader } from "@/components/ui/primitives";
import type { WorkspaceIdentity } from "@/components/ui/data-state";

export const CAREER_IDENTITY: WorkspaceIdentity = {
  icon: Briefcase,
  eyebrow: "Opportunity field",
  title: "Career Intelligence",
  description: "Lilith is tracking your opportunities and moving the pipeline forward.",
};

/**
 * The page header. The five-tile row that sat under it repeated the pipeline
 * (active, interviews, offers); the two figures it alone showed — response rate
 * and pipeline health — now sit on the pipeline itself.
 */
export function CareerHeader({ isDemo, diagnostics }: { isDemo: boolean; diagnostics?: Diagnostics }) {
  return <WorkspaceHeader {...CAREER_IDENTITY} isDemo={isDemo} diagnostics={diagnostics} />;
}
