"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { DURATION, EASE_OUT } from "@/lib/motion";

/** Routes that bring their own entrance and are left alone. */
export const OWN_ENTRANCE = ["/memory/atlas"];

/**
 * The quiet route transition: the page content fades in over 200ms while the
 * shell (rail, top bar, status bar) holds still.
 *
 * Opacity only — no movement, no scaling, no blur — so it reads the same with
 * "reduce motion" on, never blocks input, and does not create a containing
 * block that would move fixed layers (drawers, the Atlas canvas). The Atlas has
 * its own assembly and is excluded.
 *
 * React's <ViewTransition> was considered (proposal §6): in this build it is
 * only in Next's bundled React canary, not in the project's React 19.2, and the
 * animations it relies on are Chromium-first. Revisit when React 19.3 is stable.
 */
export function RouteTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  if (OWN_ENTRANCE.some((route) => pathname === route || pathname.startsWith(`${route}/`))) {
    return <div className="h-full">{children}</div>;
  }
  return (
    <motion.div
      key={pathname}
      className="h-full"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: DURATION.fast, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}
