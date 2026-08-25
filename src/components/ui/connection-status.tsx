"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FlaskConical, Radio, ChevronDown, Check, X } from "lucide-react";
import type { Diagnostics } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ConnectionStatus({
  isDemo,
  diagnostics,
}: {
  isDemo: boolean;
  diagnostics?: Diagnostics;
}) {
  const [open, setOpen] = useState(false);
  const okCount = diagnostics?.endpoints.filter((e) => e.ok).length ?? 0;
  const total = diagnostics?.endpoints.length ?? 0;

  return (
    <div className="relative">
      <button
        onClick={() => diagnostics && setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors",
          isDemo
            ? "border-amber/20 bg-amber/10 text-amber"
            : "border-green/20 bg-green/10 text-green",
          diagnostics && "hover:brightness-110",
        )}
      >
        {isDemo ? (
          <>
            <FlaskConical className="h-3 w-3" />
            Demo data · backend offline
          </>
        ) : (
          <>
            <Radio className="h-3 w-3" />
            Live · {okCount}/{total} endpoints
          </>
        )}
        {diagnostics && (
          <ChevronDown
            className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
          />
        )}
      </button>

      <AnimatePresence>
        {open && diagnostics && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="glass-strong absolute right-0 z-30 mt-2 w-72 rounded-xl p-3"
          >
            <div className="flex items-center justify-between">
              <span className="eyebrow">Backend connection</span>
              <span className="font-mono text-[10px] text-ink-faint">
                {diagnostics.transport}
              </span>
            </div>
            <ul className="mt-2 space-y-1">
              {diagnostics.endpoints.map((e) => (
                <li
                  key={e.path}
                  className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-xs"
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={cn(
                        "grid h-4 w-4 place-items-center rounded-full",
                        e.ok ? "bg-green/15 text-green" : "bg-rose/15 text-rose",
                      )}
                    >
                      {e.ok ? <Check className="h-2.5 w-2.5" /> : <X className="h-2.5 w-2.5" />}
                    </span>
                    <span className="font-mono text-ink-muted">{e.path}</span>
                  </span>
                  <span className="font-mono text-[10px] text-ink-faint">
                    {e.status || e.error || "—"}
                  </span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
