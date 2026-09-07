"use client";

import { motion } from "framer-motion";
import { Check, FlaskConical, Radio, RotateCcw, ShieldAlert, X } from "lucide-react";
import type { CommandTask } from "@/lib/command";

/**
 * Approval gate — a sensitive step (send email, delete, external write) needs
 * explicit user consent before it proceeds. This is the UI foundation for the
 * future policy engine; V1 wires the states, not a real policy.
 */
export function ApprovalRequest({
  task,
  onApprove,
  onDeny,
}: {
  task: CommandTask;
  onApprove: () => void;
  onDeny: () => void;
}) {
  const { approval } = task;
  const expired = approval.status === "expired";
  const live = task.source === "core";
  const hasDetail =
    approval.action || approval.target || approval.sideEffect || approval.reversible != null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full rounded-2xl border border-amber/25 bg-amber/[0.07] p-4"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl border border-amber/30 bg-amber/10 text-amber">
          <ShieldAlert className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="eyebrow text-amber">Approval required</p>
            {/* Honesty: a real approval is a LIVE write, never a simulation. */}
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                live ? "border-green/40 bg-green/10 text-green" : "border-amber/40 bg-amber/10 text-amber"
              }`}
            >
              {live ? <Radio className="h-3 w-3" /> : <FlaskConical className="h-3 w-3" />}
              {live ? "Live" : "Simulated"}
            </span>
          </div>
          <h3 className="mt-1 text-[15px] font-semibold tracking-tight text-ink">
            {approval.summary ?? "Confirm this action"}
          </h3>
          {approval.reason && (
            <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">{approval.reason}</p>
          )}

          {hasDetail && (
            <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px]">
              {approval.action && (
                <>
                  <dt className="text-ink-muted">Action</dt>
                  <dd className="text-ink">{approval.action}</dd>
                </>
              )}
              {approval.target && (
                <>
                  <dt className="text-ink-muted">Target</dt>
                  <dd className="truncate text-ink" title={approval.target}>{approval.target}</dd>
                </>
              )}
              {approval.sideEffect && (
                <>
                  <dt className="text-ink-muted">Side effect</dt>
                  <dd className="text-ink">{approval.sideEffect}</dd>
                </>
              )}
              {approval.reversible != null && (
                <>
                  <dt className="text-ink-muted">Reversible</dt>
                  <dd className="inline-flex items-center gap-1 text-ink">
                    {approval.reversible ? (
                      <><RotateCcw className="h-3 w-3 text-green" /> Yes — can be discarded</>
                    ) : (
                      "No"
                    )}
                  </dd>
                </>
              )}
            </dl>
          )}

          {approval.contentPreview && (
            <div className="mt-2.5">
              <p className="eyebrow text-ink-muted">Exact content</p>
              <pre className="mt-1 max-h-52 overflow-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/20 p-3 text-[12px] leading-relaxed text-ink">
                {approval.contentPreview}
              </pre>
            </div>
          )}

          {expired && (
            <p className="mt-1.5 text-[11px] text-amber">
              This approval has gone stale — review it again before continuing.
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onApprove}
          className="flex items-center gap-1.5 rounded-full border border-green/40 bg-green/15 px-4 py-1.5 text-[13px] font-medium text-green transition-colors hover:bg-green/25"
        >
          <Check className="h-3.5 w-3.5" /> Approve
        </button>
        <button
          onClick={onDeny}
          className="flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:border-rose/30 hover:text-rose"
        >
          <X className="h-3.5 w-3.5" /> Deny
        </button>
      </div>
    </motion.div>
  );
}
