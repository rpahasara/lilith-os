"use client";

import { CheckCircle2, Cpu, GitBranch, Sparkles, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { EventTimeline } from "@/components/ui/event-timeline";
import type { ActivityEvent } from "@/lib/career/types";
import { timeAgo } from "@/lib/utils";

const KIND: Record<ActivityEvent["kind"], { icon: LucideIcon; color: string }> = {
  stage: { icon: GitBranch, color: "text-orchid-bright" },
  recruiter: { icon: UserRound, color: "text-cyan-bright" },
  insight: { icon: Sparkles, color: "text-orchid-bright" },
  action: { icon: CheckCircle2, color: "text-amber" },
  system: { icon: Cpu, color: "text-cyan-bright" },
};

export function ActivityTimeline({ activity }: { activity: ActivityEvent[] }) {
  return (
    <EventTimeline
      title="Career activity"
      empty="No career activity yet."
      items={activity.map((event) => {
        const kind = KIND[event.kind] ?? KIND.system;
        return {
          id: event.id,
          icon: kind.icon,
          color: kind.color,
          text: event.text,
          meta: `${event.company ? `${event.company} · ` : ""}${timeAgo(event.time)}`,
        };
      })}
    />
  );
}
