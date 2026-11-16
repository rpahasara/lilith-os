"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  INITIAL_SHELL_HEALTH,
  SHELL_HEALTH_INTERVAL_MS,
  probeShellHealth,
  type ShellHealth,
} from "@/lib/system/shell-health";

/**
 * One measured answer to "can the backend be reached?", shared by everything
 * in the shell that needs it: the status capsule, the global command surface
 * and Lilith's presence mark. It is the same read-only probe the status capsule
 * always ran (see `lib/system/shell-health`), now run once instead of once per
 * consumer. Nothing here can write.
 */
interface ShellHealthValue {
  health: ShellHealth;
  /** Probe again now (e.g. after a failed turn, or "Check again"). */
  refresh: () => void;
}

const ShellHealthContext = createContext<ShellHealthValue | null>(null);

export function ShellHealthProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<ShellHealth>(INITIAL_SHELL_HEALTH);
  const probe = useRef<() => void>(() => {});

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;

    const run = async () => {
      if (inFlight || document.visibilityState === "hidden") return;
      inFlight = true;
      try {
        const next = await probeShellHealth();
        if (!cancelled) setHealth(next);
      } finally {
        inFlight = false;
      }
    };
    probe.current = () => void run();

    void run();
    const timer = window.setInterval(run, SHELL_HEALTH_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void run();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      probe.current = () => {};
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const refresh = useCallback(() => probe.current(), []);
  const value = useMemo(() => ({ health, refresh }), [health, refresh]);
  return <ShellHealthContext.Provider value={value}>{children}</ShellHealthContext.Provider>;
}

export function useShellHealth(): ShellHealthValue {
  const ctx = useContext(ShellHealthContext);
  if (!ctx) throw new Error("useShellHealth must be used within a ShellHealthProvider");
  return ctx;
}
