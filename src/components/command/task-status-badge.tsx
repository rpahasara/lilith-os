"use client";

import { StatusBadge } from "@/components/ui/workspace";
import type { CommandStatus } from "@/lib/command";

type Tone = Parameters<typeof StatusBadge>[0]["tone"];

const META: Record<CommandStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "faint" },
  reviewing: { label: "Review", tone: "violet" },
  queued: { label: "Queued", tone: "cyan" },
  planning: { label: "Planning", tone: "cyan" },
  waiting_for_approval: { label: "Needs approval", tone: "amber" },
  running: { label: "Running", tone: "cyan" },
  blocked: { label: "Unavailable", tone: "amber" },
  partial: { label: "Partial", tone: "amber" },
  succeeded: { label: "Done", tone: "green" },
  failed: { label: "Failed", tone: "rose" },
  cancelled: { label: "Cancelled", tone: "faint" },
};

export function TaskStatusBadge({ status }: { status: CommandStatus }) {
  const meta = META[status];
  return <StatusBadge label={meta.label} tone={meta.tone} />;
}

export function statusLabel(status: CommandStatus): string {
  return META[status].label;
}
