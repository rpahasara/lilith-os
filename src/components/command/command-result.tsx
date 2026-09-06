"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileText,
  Fingerprint,
  RotateCcw,
  Slash,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CommandEvidence, CommandOutcome, CommandTask } from "@/lib/command";

const OUTCOME: Record<
  CommandOutcome,
  { icon: LucideIcon; label: string; tint: string; ring: string; text: string }
> = {
  succeeded: {
    icon: CheckCircle2,
    label: "Done",
    tint: "bg-green/[0.06] border-green/25",
    ring: "border-green/30 bg-green/10 text-green",
    text: "text-green",
  },
  partial: {
    icon: AlertTriangle,
    label: "Partial result",
    tint: "bg-amber/[0.06] border-amber/25",
    ring: "border-amber/30 bg-amber/10 text-amber",
    text: "text-amber",
  },
  failed: {
    icon: XCircle,
    label: "Failed",
    tint: "bg-rose/[0.06] border-rose/25",
    ring: "border-rose/30 bg-rose/10 text-rose",
    text: "text-rose",
  },
  cancelled: {
    icon: Slash,
    label: "Cancelled",
    tint: "bg-white/[0.03] border-white/[0.08]",
    ring: "border-white/12 bg-white/[0.05] text-ink-muted",
    text: "text-ink-muted",
  },
};

const EVIDENCE_ICON: Record<CommandEvidence["kind"], LucideIcon> = {
  artifact: FileText,
  link: ExternalLink,
  external_id: Fingerprint,
  observed_state: CheckCircle2,
  error_detail: AlertTriangle,
  unresolved: Slash,
};

/**
 * Result surface for a finished command. A partial result is styled distinctly
 * from success and always lists what remains unresolved. Evidence references
 * are shown but never fabricated — they come straight from the core.
 */
export function CommandResult({
  task,
  onRetry,
  onResume,
  onClose,
}: {
  task: CommandTask;
  onRetry: () => void;
  onResume: () => void;
  onClose: () => void;
}) {
  const result = task.result;
  if (!result) return null;
  const meta = OUTCOME[result.outcome];
  const Icon = meta.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("w-full rounded-2xl border p-4", meta.tint)}
    >
      <div className="flex items-start gap-3">
        <span className={cn("mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl border", meta.ring)}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className={cn("eyebrow", meta.text)}>{meta.label}</p>
          <h3 className="mt-1 text-[14px] font-semibold tracking-tight text-ink">{task.title}</h3>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink-muted">{result.summary}</p>
        </div>
      </div>

      {result.unresolved && result.unresolved.length > 0 && (
        <div className="mt-3 rounded-xl border border-amber/20 bg-amber/[0.06] p-3">
          <p className="eyebrow text-amber">Still needs you</p>
          <ul className="mt-1.5 space-y-1">
            {result.unresolved.map((u, i) => (
              <li key={i} className="flex items-start gap-2 text-[12px] text-ink-muted">
                <Slash className="mt-0.5 h-3 w-3 shrink-0 text-amber" />
                <span>{u}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {task.evidence.length > 0 && (
        <div className="mt-3 border-t border-white/[0.06] pt-3">
          <p className="eyebrow mb-2 text-ink-faint">Evidence</p>
          <ul className="space-y-1.5">
            {task.evidence.map((e, i) => {
              const EvIcon = EVIDENCE_ICON[e.kind];
              const body = (
                <>
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-white/[0.05] text-ink-muted">
                    <EvIcon className="h-3 w-3" />
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[12px] text-ink-muted">{e.label}</span>
                  {e.value && <span className="shrink-0 font-mono text-[11px] text-ink-faint">{e.value}</span>}
                  {e.href && <ExternalLink className="h-3 w-3 shrink-0 text-ink-faint" />}
                </>
              );
              return (
                <li key={i}>
                  {e.href ? (
                    <a
                      href={e.href}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 rounded-lg px-1 py-1 transition-colors hover:bg-white/[0.03]"
                    >
                      {body}
                    </a>
                  ) : (
                    <span className="flex items-center gap-2 px-1 py-1">{body}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2">
        {result.outcome === "failed" && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Retry
          </button>
        )}
        {task.resumability && result.outcome !== "failed" && (
          <button
            onClick={onResume}
            className="flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Resume
          </button>
        )}
        <button
          onClick={onClose}
          className="ml-auto rounded-full px-3.5 py-1.5 text-[13px] text-ink-faint transition-colors hover:text-ink-muted"
        >
          Close
        </button>
      </div>
    </motion.div>
  );
}
