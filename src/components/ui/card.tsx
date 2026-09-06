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
        "relative isolate overflow-hidden rounded-[var(--radius-lg)]",
        interactive &&
          "cursor-pointer transition-[border-color,background-color,box-shadow] duration-300 hover:border-wine/30 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_24px_52px_-30px_rgba(0,0,0,0.9),0_12px_34px_-24px_rgba(201,84,115,0.35)]",
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
