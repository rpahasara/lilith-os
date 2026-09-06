"use client";

import { motion } from "framer-motion";
import { FlaskConical, Radio, XCircle } from "lucide-react";
import type { CommandTask } from "@/lib/command";
import { CommandStep } from "./command-step";
import { TaskStatusBadge } from "./task-status-badge";

/**
 * Execution progress — the ordered plan with live per-step state. It shows the
 * overall status, the current step, and (for demo tasks) an explicit
 * "Simulated" marker so preview state is never mistaken for real execution.
 */
export function CommandProgress({
  task,
  onCancel,
}: {
  task: CommandTask;
  onCancel: () => void;
}) {
  const completed = task.steps.filter(
    (s) => s.status === "succeeded" || s.status === "skipped" || s.status === "failed",
  ).length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-strong w-full rounded-2xl p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold tracking-tight text-ink">{task.title}</h3>
          <p className="mt-0.5 font-mono text-[10px] text-ink-faint">
            {completed}/{task.steps.length} steps
            {task.cancelRequested && " · cancelling…"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {task.source === "demo" ? (
            <span
              className="flex items-center gap-1 rounded-full border border-amber/20 bg-amber/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-amber"
              title="Preview state — no real external execution"
            >
              <FlaskConical className="h-2.5 w-2.5" /> Simulated
            </span>
          ) : task.source === "core" ? (
            <span
              className="flex items-center gap-1 rounded-full border border-green/20 bg-green/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-green"
              title="Real read-only backend execution"
            >
              <Radio className="h-2.5 w-2.5" /> Live
            </span>
          ) : null}
          <TaskStatusBadge status={task.status} />
        </div>
      </div>

      <ul className="mt-3.5 space-y-2.5 border-t border-white/[0.06] pt-3.5">
        {task.steps.map((s) => (
          <CommandStep key={s.id} step={s} showTiming />
        ))}
      </ul>

      {task.cancelability && (
        <div className="mt-4 flex justify-end">
          <button
            onClick={onCancel}
            disabled={task.cancelRequested}
            className="flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:border-rose/30 hover:text-rose disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" />
            {task.cancelRequested ? "Cancelling…" : "Cancel"}
          </button>
        </div>
      )}
    </motion.div>
  );
}
