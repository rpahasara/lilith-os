"use client";

import { motion } from "framer-motion";
import { Pencil, Play, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CommandTask } from "@/lib/command";
import { CommandStep } from "./command-step";

/**
 * Intent review — shown before a meaningful command runs. The user confirms
 * what Lilith understood and the plan she'll follow, then Runs, Edits, or
 * Cancels. Trivial conversational turns never reach this surface.
 */
export function CommandReview({
  task,
  onRun,
  onEdit,
  onCancel,
}: {
  task: CommandTask;
  onRun: () => void;
  onEdit: () => void;
  onCancel: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-strong w-full rounded-2xl p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow text-wine-bright/80">Review · confirm before running</p>
          <h3 className="mt-1 text-[15px] font-semibold tracking-tight text-ink">{task.title}</h3>
          <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">{task.normalizedIntent}</p>
        </div>
      </div>

      {task.contextSummary && (
        <p className="mt-2.5 inline-flex rounded-full border border-white/[0.07] bg-white/[0.03] px-2.5 py-1 text-[10px] text-ink-faint">
          {task.contextSummary}
        </p>
      )}

      {task.steps.length > 0 && (
        <ul className="mt-3.5 space-y-2.5 border-t border-white/[0.06] pt-3.5">
          {task.steps.map((s) => (
            <CommandStep key={s.id} step={s} />
          ))}
        </ul>
      )}

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onRun}
          className={cn(
            "flex items-center gap-1.5 rounded-full border border-wine-bright/55 bg-gradient-to-b from-wine-bright via-wine to-wine-deep px-4 py-1.5 text-[13px] font-medium text-white",
            "shadow-[inset_0_1px_0_rgba(255,255,255,0.4),0_8px_22px_-6px_rgba(201,79,109,0.85)] transition-transform hover:-translate-y-px",
          )}
        >
          <Play className="h-3.5 w-3.5" /> Run
        </button>
        <button
          onClick={onEdit}
          className="flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
        >
          <Pencil className="h-3.5 w-3.5" /> Edit
        </button>
        <button
          onClick={onCancel}
          className="ml-auto flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-ink-faint transition-colors hover:text-ink-muted"
        >
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
      </div>
    </motion.div>
  );
}
