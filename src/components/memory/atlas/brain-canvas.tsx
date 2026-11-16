"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { REGIONS, REGION_RGB, REGION_BY_ID } from "@/lib/memory/atlas/regions";
import { detectWebGL } from "@/lib/presence/capabilities";
import type { BrainSceneProps } from "./scene/brain-scene";

function Boot() {
  return (
    <div className="absolute inset-0 grid place-items-center">
      <div className="h-48 w-64 rounded-[50%] bg-[radial-gradient(circle,rgba(201,84,115,0.4),rgba(91,199,216,0.1)_55%,transparent_72%)] blur-2xl animate-breathe" />
    </div>
  );
}

// three.js and the scene load only in the browser, and only on this route.
const BrainScene = dynamic(() => import("./scene/brain-scene").then((m) => m.BrainScene), {
  ssr: false,
  loading: Boot,
});

/**
 * Hosts the WebGL brain and degrades gracefully: where WebGL is unavailable the
 * same particle layout and the same memories are drawn once to a 2D canvas — a
 * still portrait instead of a blank page. Domain labels, the inspector, recall
 * and the timeline keep working; only orbiting and picking a memory directly on
 * the brain need WebGL.
 */
export function BrainCanvas(props: BrainSceneProps & { onWebGL?: (available: boolean) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [webgl, setWebgl] = useState(true);
  const { onWebGL } = props;

  useEffect(() => {
    const available = detectWebGL();
    setWebgl(available);
    onWebGL?.(available);
  }, [onWebGL]);

  // R3F measures its canvas with a ResizeObserver that can miss late layout
  // shifts; observe the host and force a re-measure (see presence-orb.tsx).
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={host} className="absolute inset-0">
      {webgl ? <BrainScene {...props} /> : <BrainStill {...props} />}
    </div>
  );
}

/* ------------------------------------------------------------ still fallback */

// the home view: left profile turned slightly toward the viewer, seen from just above
const YAW = Math.PI + 0.3;
const TILT = 0.13;

/** Static 2D portrait of the brain for browsers without WebGL. */
function BrainStill({ layout, store, focus, asOf, insets, anchors, labels, visuals }: BrainSceneProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const parent = ref.current?.parentElement;
    if (!parent) return;
    const measure = () => setSize({ w: parent.clientWidth, h: parent.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(parent);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    const { w, h } = size;
    if (!canvas || !ctx || !w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = "lighter";

    // the same free area the live brain centres itself in
    const freeW = Math.max(220, w - insets.left - insets.right);
    const freeH = Math.max(220, h - insets.top - insets.bottom);
    const cx = insets.left + freeW / 2;
    const cy = insets.top + freeH / 2;
    const scale = Math.min(freeW / 3.9, freeH / 2.8);
    const cyw = Math.cos(YAW), syw = Math.sin(YAW), ct = Math.cos(TILT), st = Math.sin(TILT);
    const project = (x: number, y: number, z: number) => {
      const rx = x * cyw - z * syw;
      const rz = x * syw + z * cyw;
      return {
        x: cx + rx * scale,
        y: cy - (y * ct - rz * st + 0.14) * scale,
        depth: 0.45 + 0.55 * ((rz * ct + y * st + 1.3) / 2.6),
      };
    };
    const gain = visuals.glow;

    for (let i = 0; i < layout.count; i++) {
      if (layout.born[i] > asOf || layout.regions[i] > 6.5) continue;
      const p = project(layout.positions[i * 3], layout.positions[i * 3 + 1], layout.positions[i * 3 + 2]);
      const dim = focus.region >= 0 && layout.regions[i] !== focus.region ? 0.25 : 1;
      const r = Math.round(Math.min(255, layout.colors[i * 3] * 255 * gain));
      const g = Math.round(Math.min(255, layout.colors[i * 3 + 1] * 255 * gain));
      const b = Math.round(Math.min(255, layout.colors[i * 3 + 2] * 255 * gain));
      ctx.fillStyle = `rgba(${r},${g},${b},${(0.9 * p.depth * dim).toFixed(2)})`;
      ctx.fillRect(p.x, p.y, 1.5, 1.5);
    }

    // the memories, with the current focus picked out
    for (const node of store.getState().nodes) {
      if (node.born > asOf) continue;
      const p = project(node.position[0], node.position[1], node.position[2]);
      const [r, g, b] = REGION_RGB[REGION_BY_ID[node.region].index].map((v) => Math.round(v * 255));
      const state = focus.nodes.get(node.id) ?? 0;
      const dim = focus.dim && !state ? 0.25 : 1;
      const radius = (2.2 + (node.importance / 100) * 3.2) * (state === 2 ? 1.7 : 1);
      const halo = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius * 3);
      halo.addColorStop(0, `rgba(${r},${g},${b},${(0.85 * p.depth * dim).toFixed(2)})`);
      halo.addColorStop(0.35, `rgba(${r},${g},${b},${(0.3 * p.depth * dim).toFixed(2)})`);
      halo.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius * 3, 0, Math.PI * 2);
      ctx.fill();
      if (state === 2) {
        ctx.strokeStyle = "rgba(255,240,244,0.85)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius * 2.2, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // domain labels sit where the live scene would first place them
    const live = anchors.current;
    if (live) {
      for (const region of REGIONS) {
        const el = live.els.get(`region:${region.id}`) as HTMLElement | undefined;
        if (!el) continue;
        const p = project(region.labelAt[0], region.labelAt[1], 0);
        el.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0)`;
        el.style.opacity = labels ? "1" : "0";
        el.style.visibility = labels ? "visible" : "hidden";
      }
    }
  }, [layout, store, focus, asOf, insets, anchors, labels, visuals, size]);

  return (
    <canvas
      ref={ref}
      className="absolute inset-0 h-full w-full"
      role="img"
      aria-label="Still rendering of the cognitive atlas"
    />
  );
}
