"use client";

import type { ReactNode } from "react";
import { MotionConfig } from "framer-motion";

/**
 * Makes every Framer Motion animation in the app follow the system's
 * "reduce motion" setting. The global stylesheet already quiets CSS animations
 * and transitions; this covers the JavaScript-driven ones (page entrances,
 * drawers, sliding tab pills), which that rule cannot reach. With the setting
 * on, movement and scaling are skipped and only opacity changes remain.
 */
export function MotionPreferences({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
