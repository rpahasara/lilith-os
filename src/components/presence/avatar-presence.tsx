"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { PresenceSignal } from "@/lib/presence";

// Load the WebGL scene only on the client; soft glow while it boots.
const AvatarScene = dynamic(
  () => import("./avatar-scene").then((m) => m.AvatarScene),
  {
    ssr: false,
    loading: () => (
      <div className="absolute inset-0 grid place-items-center">
        <div className="h-44 w-32 rounded-full bg-gradient-to-b from-violet-bright/30 to-cyan-bright/20 blur-2xl animate-breathe" />
      </div>
    ),
  },
);

export function AvatarPresence({
  signal,
  paused = false,
}: {
  signal: PresenceSignal;
  paused?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  // Same container-observed re-measure the orb uses (see presence-orb).
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() =>
        window.dispatchEvent(new Event("resize")),
      );
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={ref} className="relative h-full w-full">
      {/* soft backlight for depth — dimmer than the orb bloom */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[70%] w-[55%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(139,92,246,0.22),rgba(34,211,238,0.08)_50%,transparent_72%)] blur-2xl" />
      <AvatarScene signal={signal} paused={paused} />
    </div>
  );
}
