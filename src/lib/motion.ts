import type { Variants, Transition } from "framer-motion";

/** Springy but controlled — the house transition for interactive lifts. */
export const spring: Transition = {
  type: "spring",
  stiffness: 320,
  damping: 30,
  mass: 0.7,
};

/** Smooth cinematic ease for entrances. */
export const ease: Transition = {
  duration: 0.6,
  ease: [0.22, 1, 0.36, 1],
};

/** Container that staggers its children on mount. */
export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.07, delayChildren: 0.1 },
  },
};

/** Panel entrance: fade + rise. */
export const riseIn: Variants = {
  hidden: { opacity: 0, y: 16, filter: "blur(6px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: ease,
  },
};

/** Softer fade for secondary content. */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.8, ease: "easeOut" } },
};
