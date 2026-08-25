"use client";

import type * as React from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";
import { riseIn, spring } from "@/lib/motion";

interface GlassCardProps extends Omit<HTMLMotionProps<"div">, "children"> {
  children?: React.ReactNode;
  /** stronger blur + fill for hero-level panels */
  strong?: boolean;
  /** lift + border-brighten on hover */
  interactive?: boolean;
  /** participate in a parent stagger container */
  animated?: boolean;
}

export function GlassCard({
  className,
  strong,
  interactive,
  animated = true,
  children,
  ...props
}: GlassCardProps) {
  return (
    <motion.div
      variants={animated ? riseIn : undefined}
      whileHover={
        interactive
          ? { y: -3, transition: spring }
          : undefined
      }
      className={cn(
        strong ? "glass-strong" : "glass",
        "relative rounded-[var(--radius-lg)]",
        interactive &&
          "cursor-pointer transition-colors hover:border-white/15",
        className,
      )}
      {...props}
    >
      {/* top edge highlight */}
      <span className="pointer-events-none absolute inset-x-5 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
      {children}
    </motion.div>
  );
}
