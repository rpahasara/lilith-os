import { Brain } from "lucide-react";
import type { Diagnostics } from "@/lib/api";
import { WorkspaceHeader } from "@/components/ui/primitives";
import type { WorkspaceIdentity } from "@/components/ui/data-state";

export const MEMORY_IDENTITY: WorkspaceIdentity = {
  icon: Brain,
  eyebrow: "Cognitive archive",
  title: "Memory",
  description: "Lilith's living knowledge — what she knows about your people, work, and world.",
};

/** Identity and connection state. The counts live in the explorer's overview. */
export function MemoryHeader({ isDemo, diagnostics }: { isDemo: boolean; diagnostics?: Diagnostics }) {
  return <WorkspaceHeader {...MEMORY_IDENTITY} isDemo={isDemo} diagnostics={diagnostics} />;
}
