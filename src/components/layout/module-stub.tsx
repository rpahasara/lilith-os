"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { Eyebrow } from "@/components/ui/primitives";

/**
 * Compact "in development" state for OS workspaces not yet built.
 * Intentionally small — a quiet marker, not a large empty hero.
 */
export function ModuleStub({
  icon: Icon,
  title,
  note,
  order,
}: {
  icon: LucideIcon;
  title: string;
  note: string;
  order?: string;
}) {
  return (
    <div className="grid h-full place-items-center">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="flex max-w-sm flex-col items-center text-center"
      >
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/[0.04] hairline">
          <Icon className="h-5 w-5 text-ink-muted" />
        </div>
        <h2 className="mt-4 text-lg font-medium tracking-tight text-ink">
          {title}
        </h2>
        <p className="mt-1.5 text-sm text-ink-muted">{note}</p>
        <Eyebrow className="mt-4 flex items-center gap-2">
          <span className="h-1 w-1 rounded-full bg-cyan-bright" />
          {order ?? "On the roadmap"}
        </Eyebrow>
      </motion.div>
    </div>
  );
}
