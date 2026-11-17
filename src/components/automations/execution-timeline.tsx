"use client";

import { CheckCircle2, Info, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { EventTimeline } from "@/components/ui/event-timeline";
import type { AutomationEvent } from "@/lib/automations/types";
import { timeAgo } from "@/lib/utils";

const OUTCOME: Record<string, { icon: LucideIcon; color: string }> = {
  success: { icon: CheckCircle2, color: "text-green" },
  failure: { icon: XCircle, color: "text-rose" },
  skip: { icon: Info, color: "text-ink-faint" },
  info: { icon: Info, color: "text-cyan-bright" },
};

export function ExecutionTimeline({ activity }: { activity: AutomationEvent[] }) {
  return (
    <EventTimeline
      title="Execution timeline"
      empty="No recent executions."
      items={activity.map((event) => {
        const outcome = OUTCOME[event.outcome] ?? OUTCOME.info;
        return {
          id: event.id,
          icon: outcome.icon,
          color: outcome.color,
          text: (
            <>
              <span className="text-ink">{event.unit}</span> — {event.text}
            </>
          ),
          meta: timeAgo(event.time),
        };
      })}
    />
  );
}
