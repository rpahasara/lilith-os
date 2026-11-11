"use client";

import { useEffect, useState } from "react";

/**
 * The current time, re-read every `intervalMs` (and when the tab becomes
 * visible again), so countdowns derived from it never freeze. `null` until
 * mounted, which avoids an SSR/client clock mismatch.
 */
export function useNow(intervalMs = 30_000): number | null {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const id = window.setInterval(tick, intervalMs);
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs]);

  return now;
}
