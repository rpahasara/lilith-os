"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Fragment } from "react";
import { Brain, History, Library, Scale, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { atlasPreviewEnabled } from "@/lib/memory/atlas/preview";

/** Brain and Timeline are the Cognitive Atlas; a build without it offers Archive and Beliefs only. */
const ATLAS_VIEWS: MemoryView[] = ["brain", "timeline"];

export type MemoryView = "brain" | "archive" | "timeline" | "beliefs";

const VIEWS: { key: MemoryView; label: string; icon: LucideIcon; href: string }[] = [
  { key: "brain", label: "Brain", icon: Brain, href: "/memory/atlas" },
  { key: "archive", label: "Archive", icon: Library, href: "/memory" },
  { key: "timeline", label: "Timeline", icon: History, href: "/memory/atlas?view=timeline" },
  { key: "beliefs", label: "Beliefs", icon: Scale, href: "/memory/beliefs" },
];

/** Beliefs are not memories: a hairline sets the World Model apart from the three memory lenses. */
const SET_APART: MemoryView = "beliefs";

/**
 * Brain · Archive · Timeline | Beliefs — the ways into Memory.
 *
 * Brain, Archive and Timeline are three views of the same memory records
 * (Archive at /memory; Brain and Timeline in the Cognitive Atlas at
 * /memory/atlas, which reads either its simulation or real memory). Beliefs is
 * a different structure, the World Model at /memory/beliefs, so it sits after a
 * divider. A view the current page can switch in place is passed through
 * `onSelect`; everything else is a plain link.
 */
export function MemoryViewSwitch({
  active,
  onSelect,
  inPlace = [],
  className,
}: {
  active: MemoryView;
  onSelect?: (view: MemoryView) => void;
  /** views the host page renders itself, without navigating. */
  inPlace?: MemoryView[];
  className?: string;
}) {
  return (
    <nav
      aria-label="Memory views"
      className={cn(
        "glass inline-flex items-center gap-0.5 rounded-full p-1",
        className,
      )}
    >
      {VIEWS.filter((v) => atlasPreviewEnabled() || !ATLAS_VIEWS.includes(v.key)).map((view) => {
        const on = view.key === active;
        const Icon = view.icon;
        const inner = (
          <>
            {on && (
              <motion.span
                layoutId="memory-view-active"
                className="absolute inset-0 rounded-full bg-white/[0.09] shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_8px_22px_-14px_rgba(201,84,115,0.9)] ring-1 ring-wine/25"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative flex items-center gap-1.5">
              <Icon className={cn("h-3.5 w-3.5", on ? "text-wine-bright" : "")} strokeWidth={on ? 2.1 : 1.8} />
              {/* on phone-width screens only the current view keeps its word */}
              <span className={cn(!on && "max-[480px]:sr-only")}>{view.label}</span>
            </span>
          </>
        );
        const cls = cn(
          "relative rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors",
          on ? "text-ink" : "text-ink-faint hover:text-ink-muted",
        );
        const control = onSelect && inPlace.includes(view.key) ? (
          <button
            type="button"
            aria-current={on ? "page" : undefined}
            onClick={() => onSelect(view.key)}
            className={cls}
          >
            {inner}
          </button>
        ) : (
          <Link href={view.href} aria-current={on ? "page" : undefined} className={cls}>
            {inner}
          </Link>
        );
        return (
          <Fragment key={view.key}>
            {view.key === SET_APART && <span aria-hidden data-memory-divider="" className="mx-1 h-4 w-px shrink-0 bg-white/[0.12]" />}
            {control}
          </Fragment>
        );
      })}
    </nav>
  );
}
