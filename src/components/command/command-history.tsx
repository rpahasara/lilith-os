"use client";

import { History } from "lucide-react";
import { DetailDrawer, EmptyState } from "@/components/ui/workspace";
import { cn } from "@/lib/utils";
import { useCommand } from "./command-provider";
import { TaskStatusBadge } from "./task-status-badge";

function relativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const m = Math.round(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

/**
 * Lightweight command history — recent commands, their outcome and time, with
 * one-tap reopen to review a past result. A drawer, not an analytics page.
 */
export function CommandHistory() {
  const { history, historyOpen, setHistoryOpen, reopen } = useCommand();

  return (
    <DetailDrawer
      open={historyOpen}
      onClose={() => setHistoryOpen(false)}
      eyebrow="Command system"
      title="History"
    >
      {history.length === 0 ? (
        <EmptyState
          icon={History}
          title="No commands yet"
          description="Commands you run will appear here with their outcome, so you can reopen and review them."
        />
      ) : (
        <ul className="space-y-2">
          {history.map((t) => (
            <li key={t.taskId}>
              <button
                onClick={() => reopen(t.taskId)}
                className={cn(
                  "group flex w-full items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 text-left transition-colors",
                  "hover:border-white/15 hover:bg-white/[0.045]",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-ink">{t.title}</span>
                  <span className="mt-0.5 block truncate text-[11px] text-ink-faint">
                    {t.result?.summary ?? t.error ?? t.normalizedIntent}
                  </span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <TaskStatusBadge status={t.status} />
                  <span className="font-mono text-[10px] text-ink-faint">{relativeTime(t.updatedAt)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </DetailDrawer>
  );
}
