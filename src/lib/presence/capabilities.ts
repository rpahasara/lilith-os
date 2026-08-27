/**
 * Runtime capability + preference detection for the presence layer.
 *
 * These decide *how much* presence to render — never crashing, always
 * degrading gracefully: full renderer → orb → static glow → nothing.
 * All probes are SSR-safe (guarded for `window`/`document`).
 */

"use client";

import { useEffect, useState } from "react";
import type { RendererKind } from "./types";

/** User preference for how present Lilith should be. Control lands in Settings. */
export type PresencePreference = "full" | "orb" | "off";

export const PRESENCE_PREF_KEY = "lilith-os:presence-pref";

/**
 * Dev-only override for which renderer the engine boots into. Not a user
 * setting — it exists so `rendererKind="avatar"` can be previewed without a
 * real model. Set via `localStorage["lilith-os:presence-renderer"] = "avatar"`
 * (or the dev `window.__lilithPresence.setRendererKind` helper).
 */
export const PRESENCE_RENDERER_KEY = "lilith-os:presence-renderer";

/** One-shot WebGL support probe. Returns false if a context can't be created. */
export function detectWebGL(): boolean {
  if (typeof document === "undefined") return true; // assume yes during SSR
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl");
    return !!gl;
  } catch {
    return false;
  }
}

/** Read the stored presence preference (defaults to "full"). */
export function readPresencePreference(): PresencePreference {
  if (typeof window === "undefined") return "full";
  try {
    const v = window.localStorage.getItem(PRESENCE_PREF_KEY);
    if (v === "full" || v === "orb" || v === "off") return v;
  } catch {
    /* storage unavailable */
  }
  return "full";
}

/** Persist the presence preference. */
export function writePresencePreference(pref: PresencePreference): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PRESENCE_PREF_KEY, pref);
  } catch {
    /* ignore */
  }
}

/** Read the dev renderer override, if any (see {@link PRESENCE_RENDERER_KEY}). */
export function readRendererOverride(): RendererKind | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(PRESENCE_RENDERER_KEY);
    if (v === "orb" || v === "avatar" || v === "edge" || v === "voice") return v;
  } catch {
    /* storage unavailable */
  }
  return null;
}

/* ----------------------------------------------------------------- hooks */

/** `prefers-reduced-motion: reduce`, live. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return reduced;
}

/** `true` while the tab is hidden — used to pause the render loop. */
export function usePageHidden(): boolean {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    if (typeof document === "undefined") return;
    const update = () => setHidden(document.hidden);
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return hidden;
}

/** WebGL availability, evaluated once on the client. */
export function useWebGL(): boolean {
  const [ok, setOk] = useState(true); // optimistic; corrected on mount
  useEffect(() => {
    setOk(detectWebGL());
  }, []);
  return ok;
}

/** Live presence preference, reacting to storage changes across tabs. */
export function usePresencePreference(): PresencePreference {
  const [pref, setPref] = useState<PresencePreference>("full");
  useEffect(() => {
    setPref(readPresencePreference());
    if (typeof window === "undefined") return;
    const onStorage = (e: StorageEvent) => {
      if (e.key === PRESENCE_PREF_KEY) setPref(readPresencePreference());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  return pref;
}
