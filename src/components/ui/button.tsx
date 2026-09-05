"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wine-bright disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]",
  {
    variants: {
      variant: {
        primary:
          "border border-wine/55 bg-wine/[0.16] text-white backdrop-blur-md shadow-[inset_0_1px_0_0_rgba(243,238,244,0.32),0_10px_28px_-10px_rgba(0,0,0,0.6),0_8px_26px_-12px_rgba(201,79,109,0.6)] hover:bg-wine/[0.26] hover:border-wine/70 hover:shadow-[inset_0_1px_0_0_rgba(243,238,244,0.4),0_12px_32px_-8px_rgba(0,0,0,0.65),0_10px_32px_-8px_rgba(201,79,109,0.9)]",
        ghost:
          "text-ink-muted hover:text-ink hover:bg-white/5",
        glass:
          "glass text-ink hover:border-white/15 hover:text-ink",
        outline:
          "border border-white/15 bg-white/[0.04] text-ink-muted backdrop-blur-md shadow-[inset_0_1px_0_0_rgba(243,238,244,0.14),0_8px_22px_-12px_rgba(0,0,0,0.55)] hover:text-ink hover:border-white/25 hover:bg-white/[0.07]",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-sm",
        icon: "h-10 w-10",
        "icon-sm": "h-8 w-8",
      },
    },
    defaultVariants: { variant: "glass", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(button({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
