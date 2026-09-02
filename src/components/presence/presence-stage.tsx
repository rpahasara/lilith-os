"use client";

import { useEffect, useRef, useState } from "react";
import {
  usePageHidden,
  usePresencePreference,
  useReducedMotion,
  useWebGL,
} from "@/lib/presence";
import { usePresence } from "./presence-engine";
import { PresenceOrb } from "./presence-orb";
import { AvatarPresence } from "./avatar-presence";
import { PresenceErrorBoundary, StaticPresence } from "./presence-fallback";

/**
 * Resolves *which* presence to draw from the live signal + the runtime
 * capabilities, and guarantees graceful degradation:
 *
 *   preference "off"        → nothing
 *   reduced motion          → static bloom, no animation
 *   no WebGL / low perf     → static bloom (breathing)
 *   preference "orb"/"full" → the orb renderer (avatar slots in here later)
 *
 * Any renderer crash is caught and downgraded to the static bloom, so the
 * Command Center never goes blank.
 */

/**
 * Lightweight FPS guard. Samples in 1s windows while `enabled`; latches
 * `degraded` after two consecutive low windows so we don't oscillate. Skips
 * hidden-tab windows (which read as 0 fps). One-way: reload to re-evaluate.
 */
function usePerfGuard(enabled: boolean, graceMs = 0): boolean {
  const [degraded, setDegraded] = useState(false);
  const lowStreak = useRef(0);

  useEffect(() => {
    if (!enabled || degraded) return;
    if (typeof window === "undefined") return;

    let raf = 0;
    let frames = 0;
    let windowStart = performance.now();
    const measureAfter = windowStart + graceMs;
    let stopped = false;

    const tick = (now: number) => {
      if (stopped) return;
      if (now < measureAfter) {
        frames = 0;
        windowStart = now;
        raf = requestAnimationFrame(tick);
        return;
      }
      frames += 1;
      const elapsed = now - windowStart;
      if (elapsed >= 1000) {
        const fps = (frames * 1000) / elapsed;
        if (!document.hidden && fps < 20) {
          lowStreak.current += 1;
          if (lowStreak.current >= 2) {
            setDegraded(true);
            stopped = true;
            return;
          }
        } else {
          lowStreak.current = 0;
        }
        frames = 0;
        windowStart = now;
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
    };
  }, [enabled, degraded, graceMs]);

  return degraded;
}

export function PresenceStage() {
  const { signal, rendererKind } = usePresence();
  const preference = usePresencePreference();
  const reducedMotion = useReducedMotion();
  const webgl = useWebGL();
  const hidden = usePageHidden();

  // Which renderer would we *like* to draw? "orb" preference pins the orb even
  // when an avatar becomes available; "full" follows the engine's rendererKind.
  const kind = preference === "orb" ? "orb" : rendererKind;
  const wantsLive = preference !== "off" && !reducedMotion && webgl;
  // Large local avatars need time to download and parse before FPS is a useful
  // signal. The guard remains active after this one-time startup grace period.
  const degraded = usePerfGuard(wantsLive, kind === "avatar" ? 20_000 : 0);

  let content: React.ReactNode;
  if (preference === "off") {
    content = null;
  } else if (reducedMotion) {
    content = <StaticPresence animate={false} />;
  } else if (!webgl || degraded) {
    content = <StaticPresence />;
  } else if (kind === "avatar") {
    content = <AvatarPresence signal={signal} paused={hidden} />;
  } else if (kind === "orb") {
    content = <PresenceOrb signal={signal} paused={hidden} />;
  } else {
    // edge/voice renderers land in later phases; orb is the safe default.
    content = <PresenceOrb signal={signal} paused={hidden} />;
  }

  return (
    <div
      className="relative h-full w-full"
      data-presence-renderer={preference === "off" ? "off" : kind}
      data-presence-activity={signal.activity}
    >
      <PresenceErrorBoundary fallback={<StaticPresence />}>
        {content}
      </PresenceErrorBoundary>
    </div>
  );
}
