"use client";

import type * as React from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";
import { riseIn, spring } from "@/lib/motion";

interface GlassCardProps extends Omit<HTMLMotionProps<"div">, "children"> {
  children?: React.ReactNode;
  /** stronger blur + fill for hero-level panels (Tier 3) */
  strong?: boolean;
  /** passive Tier-1 glass: highly transparent, local text attenuation only */
  panel?: boolean;
  /** lift + border-brighten on hover */
  interactive?: boolean;
  /** participate in a parent stagger container */
  animated?: boolean;
}

export function GlassCard({
  className,
  strong,
  panel,
  interactive,
  animated = true,
  children,
  ...props
}: GlassCardProps) {
  const surface = panel ? "glass-panel" : strong ? "glass-strong" : "glass";
  return (
    <motion.div
      variants={animated ? riseIn : undefined}
      whileHover={
        interactive
          ? { y: -3, transition: spring }
          : undefined
      }
      className={cn(
        surface,
        "relative rounded-[var(--radius-lg)]",
        interactive &&
          "cursor-pointer transition-colors hover:border-orchid/30",
        className,
      )}
      {...props}
    >
      {/* inner illumination — soft top diffusion + corner specular (volume) */}
      <span className="glass-sheen" />
      {/* top edge specular — a thin line of glass light, brightest at centre */}
      <span className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />
      {children}
    </motion.div>
  );
}
