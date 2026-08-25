"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import type { PresenceState } from "@/lib/presence";

// Load the WebGL scene only on the client; render a soft glow while it boots.
const OrbScene = dynamic(
  () => import("./orb-scene").then((m) => m.OrbScene),
  {
    ssr: false,
    loading: () => (
      <div className="absolute inset-0 grid place-items-center">
        <div className="h-40 w-40 rounded-full bg-gradient-to-br from-violet-bright/40 to-cyan-bright/30 blur-2xl animate-breathe" />
      </div>
    ),
  },
);

export function PresenceOrb({ state }: { state: PresenceState }) {
  const ref = useRef<HTMLDivElement>(null);

  // R3F sizes its canvas from a ResizeObserver that can miss late layout
  // shifts (web-font load, flex reflow). Observe the container ourselves and
  // force a re-measure whenever it changes size — guarantees a full-bleed orb.
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
      {/* ambient bloom behind the canvas — fakes post-processing glow cheaply */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[62%] w-[62%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(139,92,246,0.35),rgba(34,211,238,0.12)_45%,transparent_70%)] blur-2xl" />
      <OrbScene state={state} />
    </div>
  );
}
