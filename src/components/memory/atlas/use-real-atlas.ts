"use client";

/**
 * Real memory for the Atlas: one read-only store, kept in step with the memory
 * read model by comparing successive successful snapshots (`stepReal`).
 *
 * - Nothing is persisted. Records live in this hook's memory only, and are
 *   dropped when Real mode is left or the page unmounts.
 * - A failed or malformed read never removes anything: the last good graph
 *   stays, marked stale, until a successful snapshot says otherwise.
 * - The first snapshot builds the graph whole (no "newly observed" animation
 *   for what was simply already there); later ones apply only differences.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { BrainLayout } from "@/lib/memory/atlas/brain-shape";
import {
  fetchSnapshot,
  stepReal,
  type RealView,
  type SnapshotFailure,
  type SnapshotFetch,
} from "@/lib/memory/atlas/real-source";

/** How often the read model is read again while Real mode is on screen. */
export const REAL_POLL_MS = 60_000;

export type RealAtlas =
  | { phase: "off" }
  | { phase: "loading" }
  | { phase: "unavailable"; failure: SnapshotFailure; attemptedAt: number; checking: boolean }
  | ({ phase: "ready"; checking: boolean } & RealView);

export function useRealAtlas(
  layout: BrainLayout,
  enabled: boolean,
  paused: boolean,
  fetchImpl?: SnapshotFetch,
): RealAtlas & { check: () => void } {
  const [state, setState] = useState<RealAtlas>({ phase: "off" });
  const view = useRef<RealView | null>(null);
  const inflight = useRef<AbortController | null>(null);

  const check = useCallback(async () => {
    if (inflight.current) return;
    const controller = new AbortController();
    inflight.current = controller;
    setState((s) =>
      s.phase === "ready" || s.phase === "unavailable"
        ? { ...s, checking: true }
        : s.phase === "off"
          ? { phase: "loading" }
          : s,
    );
    const result = await fetchSnapshot(controller.signal, fetchImpl);
    // left Real mode (or unmounted) while the read was in flight: drop it
    if (inflight.current !== controller || controller.signal.aborted) return;
    inflight.current = null;

    const step = stepReal(view.current, result, layout, Date.now());
    if (step.kind === "unavailable") {
      setState({ phase: "unavailable", failure: step.failure, attemptedAt: Date.now(), checking: false });
      return;
    }
    view.current = step.view;
    setState({ phase: "ready", checking: false, ...step.view });
  }, [layout, fetchImpl]);

  /* entering Real mode reads once; leaving it drops everything it held */
  useEffect(() => {
    if (!enabled) return;
    const start = setTimeout(() => void check(), 0);
    return () => {
      clearTimeout(start);
      inflight.current?.abort();
      inflight.current = null;
      view.current = null;
      setState({ phase: "off" });
    };
  }, [enabled, check]);

  /* read again now and then, only while it is on screen */
  useEffect(() => {
    if (!enabled || paused) return;
    const id = setInterval(() => void check(), REAL_POLL_MS);
    return () => clearInterval(id);
  }, [enabled, paused, check]);

  return { ...state, check: () => void check() };
}
