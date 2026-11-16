import type { Variants, Transition } from "framer-motion";

/**
 * The motion vocabulary — every animated thing in the shell and the workspaces
 * draws from here, so motion reads as one hand.
 *
 *   durations  four named steps
 *   easing     one curve
 *   springs    two: one for surfaces, one for selection
 *
 * Spend motion on state (Lilith responding, a drawer arriving), not on
 * decoration. Reduced motion is handled once, in the shell
 * (`components/layout/motion-preferences.tsx`) and in the stylesheet; nothing
 * here needs to check it.
 *
 * The same values exist for CSS as `--duration-*` and `--ease-lilith`
 * (`app/globals.css`). The avatar, the orb and the Cognitive Atlas run their
 * own render loops and are deliberately outside this file.
 */

/** Seconds. `instant` for feedback, `fast` for small state changes, `base` for
 *  content arriving, `slow` for entrances. */
export const DURATION = {
  instant: 0.12,
  fast: 0.2,
  base: 0.3,
  slow: 0.6,
} as const;

/** The house curve: quick to start, long to settle. */
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/** Surfaces: drawers, panels, cards lifting. Controlled, barely any overshoot. */
export const spring: Transition = {
  type: "spring",
  stiffness: 320,
  damping: 30,
  mass: 0.7,
};

/** Selection: the pill that slides between tabs and nav items. Crisp. */
export const springSnap: Transition = {
  type: "spring",
  stiffness: 400,
  damping: 32,
};

/** Entrances. */
export const ease: Transition = {
  duration: DURATION.slow,
  ease: EASE_OUT,
};

/** Small state changes: a row appearing, a popover, a status swap. */
export const fade: Transition = {
  duration: DURATION.fast,
  ease: EASE_OUT,
};

/** Content arriving in place: a message, a result. */
export const settle: Transition = {
  duration: DURATION.base,
  ease: EASE_OUT,
};

/** A measured value filling in: meters, rings, confidence bars. */
export const meter: Transition = {
  duration: 1,
  ease: EASE_OUT,
};

/** Container that staggers its children on mount. */
export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.07, delayChildren: 0.1 },
  },
};

/**
 * Panel entrance: fade and a short rise. No blur — animating `filter` on every
 * card is expensive and makes text shimmer while it settles.
 */
export const riseIn: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: ease,
  },
};
