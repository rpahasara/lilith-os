"use client";

import { motion } from "framer-motion";
import { Ban } from "lucide-react";
import type { CommandTask } from "@/lib/command";

/**
 * Capability boundary — a recognised intent Lilith cannot (yet) act on. It is
 * honest about *why* rather than faking confidence, preparing the user for the
 * edges of what the current environment allows.
 */
export function CommandUnsupported({
  task,
  onClose,
}: {
  task: CommandTask;
  onClose: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-white/12 bg-white/[0.05] text-ink-muted">
          <Ban className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="eyebrow text-ink-faint">Not available yet</p>
          <h3 className="mt-1 text-[14px] font-semibold tracking-tight text-ink">{task.title}</h3>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink-muted">
            {task.error ?? "I don't have a capability for that yet."}
          </p>
        </div>
      </div>

      {task.evidence.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-white/[0.06] pt-3">
          {task.evidence.map((e, i) => (
            <li key={i} className="flex items-center justify-between gap-3 text-[12px]">
              <span className="text-ink-faint">{e.label}</span>
              {e.value && <span className="font-mono text-[11px] text-ink-muted">{e.value}</span>}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex justify-end">
        <button
          onClick={onClose}
          className="rounded-full px-3.5 py-1.5 text-[13px] text-ink-faint transition-colors hover:text-ink-muted"
        >
          Close
        </button>
      </div>
    </motion.div>
  );
}
