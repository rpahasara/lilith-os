"use client";

import { Component, type ReactNode } from "react";
import { reportProblem } from "@/lib/diagnostics";

/**
 * A pure-CSS presence: a soft orchid→cyan bloom, no WebGL, no render loop.
 *
 * Used whenever a live renderer can't or shouldn't run — WebGL unavailable,
 * the "orb" preference under reduced motion, a renderer crash, or a detected
 * low-performance device. It keeps Lilith *present* at zero GPU cost. The
 * gentle breathe animation is disabled by the global reduced-motion CSS rule.
 */
export function StaticPresence({ animate = true }: { animate?: boolean }) {
  return (
    <div className="relative h-full w-full">
      <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <div
          className={
            "h-40 w-40 rounded-full bg-[radial-gradient(circle,rgba(139,92,246,0.5),rgba(34,211,238,0.18)_45%,transparent_70%)] blur-2xl" +
            (animate ? " animate-breathe" : "")
          }
        />
      </div>
    </div>
  );
}

/**
 * Catches any error thrown by a presence renderer (WebGL context loss, asset
 * failure, shader compile error) and falls back to the static presence instead
 * of crashing the Command Center.
 */
export class PresenceErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode; onFailure?: () => void },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    // Non-fatal by design: report one sanitized line, keep the OS running.
    reportProblem("presence", "renderer failed, falling back to static", error);
    this.props.onFailure?.();
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback ?? <StaticPresence />;
    }
    return this.props.children;
  }
}
