"use client";

import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { StatusDot, type Accent } from "@/components/ui/primitives";
import {
  INITIAL_SHELL_HEALTH,
  SHELL_HEALTH_INTERVAL_MS,
  probeShellHealth,
  shellHealthLabel,
  type ShellHealth,
} from "@/lib/system/shell-health";

const DOT: Record<ShellHealth["state"], Accent> = {
  checking: "orchid",
  live: "green",
  unconfigured: "amber",
  unreachable: "rose",
};

const TEXT: Record<ShellHealth["state"], string> = {
  checking: "text-ink-faint",
  live: "text-green",
  unconfigured: "text-amber",
  unreachable: "text-rose",
};

/**
 * Home status is a quiet floating capsule — not a full-width architectural bar.
 * Every value shown is measured: backend reachability and the browser-observed
 * API round-trip from one read-only probe (see `lib/system/shell-health`).
 * Nothing is displayed that the client cannot verify.
 */
export function StatusBar() {
  const [health, setHealth] = useState<ShellHealth>(INITIAL_SHELL_HEALTH);

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

    void run();
    const timer = window.setInterval(run, SHELL_HEALTH_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void run();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const title = health.checkedAt
    ? `Backend probe at ${new Date(health.checkedAt).toLocaleTimeString()} · ` +
      (health.httpStatus ? `HTTP ${health.httpStatus}` : "network error or timeout")
    : "Checking backend";

  return (
    <footer className="flex shrink-0 items-center justify-center px-6 pb-4 pt-1">
      <div
        role="status"
        aria-live="polite"
        title={title}
        data-shell-health={health.state}
        className="glass flex items-center gap-3 rounded-full px-4 py-2 font-mono text-micro leading-[15px] text-ink-faint shadow-[0_16px_38px_-24px_rgba(0,0,0,0.95)]"
      >
        <span className="flex items-center gap-1.5">
          <StatusDot accent={DOT[health.state]} />
          <span className="font-medium text-ink">Lilith OS</span>
          <span className={TEXT[health.state]}>{shellHealthLabel(health)}</span>
        </span>
        {health.state === "live" && health.latencyMs !== null && (
          <>
            <span className="hidden h-3 w-px bg-white/10 sm:block" />
            <span
              className="hidden items-center gap-1.5 sm:flex"
              title="Browser → API round-trip (not model latency)"
            >
              <Cpu className="h-3 w-3 text-ink-faint" />
              <span className="text-ink-muted">API {health.latencyMs}ms</span>
            </span>
          </>
        )}
      </div>
    </footer>
  );
}
