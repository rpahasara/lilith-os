"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  EVENT_MAP,
  IDLE_SIGNAL,
  applyMapping,
  initialEngineState,
  readRendererOverride,
  resolveSignal,
  subscribePresence,
  type EngineState,
  type EventMapping,
  type PresenceEvent,
  type PresenceSignal,
  type RendererKind,
} from "@/lib/presence";

/**
 * The Presence orchestrator.
 *
 * It owns the engine state (steady + transient layers), subscribes to the
 * semantic event bus, and turns events into a resolved {@link PresenceSignal}
 * that renderers consume. It also enforces the interruption model: priority,
 * transient hold/restore, per-event cooldowns, and suppression of ambient
 * interruptions while the user is actively typing.
 *
 * No three.js, no animation clips, no personality tables live here — those are
 * in `@/lib/presence` (mapping/reducer) and in each renderer. This file is the
 * seam between "an event happened" and "a signal to render".
 */

/** How long after a keystroke ambient events stay suppressed. */
const TYPING_SUPPRESS_MS = 1500;

interface PresenceContextValue {
  /** The signal a renderer should show right now. */
  signal: PresenceSignal;
  /** Which renderer is active (orb today; avatar/edge later). */
  rendererKind: RendererKind;
  setRendererKind: (kind: RendererKind) => void;
  /** Emit a semantic presence event (also available module-wide via the bus). */
  emit: (event: PresenceEvent) => void;
  /**
   * Directly set a signal patch — for manual controls / debugging. Bypasses
   * cooldown + suppression. `holdMs` makes it a transient reaction.
   */
  override: (patch: Partial<PresenceSignal>, holdMs?: number) => void;
}

const PresenceContext = createContext<PresenceContextValue | null>(null);

function signalsEqual(a: PresenceSignal, b: PresenceSignal): boolean {
  return (
    a.activity === b.activity &&
    a.emotion === b.emotion &&
    a.attention === b.attention &&
    a.placement === b.placement &&
    a.intensity === b.intensity &&
    a.speaking === b.speaking &&
    a.importance === b.importance
  );
}

export function PresenceProvider({
  children,
  defaultRenderer = "orb",
}: {
  children: ReactNode;
  defaultRenderer?: RendererKind;
}) {
  const [signal, setSignal] = useState<PresenceSignal>(IDLE_SIGNAL);
  const [rendererKind, setRendererKind] = useState<RendererKind>(defaultRenderer);

  // Engine state + scheduling live in refs so `emit` is stable and never stale.
  const engine = useRef<EngineState>(initialEngineState());
  const lastFired = useRef<Map<string, number>>(new Map());
  const typingUntil = useRef(0);
  const expiryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const commit = useCallback((now: number) => {
    // Drop an expired transient so the engine state stays tidy.
    const t = engine.current.transient;
    if (t && t.until <= now) {
      engine.current = { steady: engine.current.steady, transient: null };
    }
    const resolved = resolveSignal(engine.current, now);
    setSignal((prev) => (signalsEqual(prev, resolved) ? prev : resolved));
  }, []);

  const scheduleExpiry = useCallback(() => {
    if (expiryTimer.current) {
      clearTimeout(expiryTimer.current);
      expiryTimer.current = null;
    }
    const t = engine.current.transient;
    if (!t) return;
    const delay = Math.max(0, t.until - Date.now()) + 16;
    expiryTimer.current = setTimeout(() => {
      commit(Date.now());
      scheduleExpiry();
    }, delay);
  }, [commit]);

  const run = useCallback(
    (mapping: EventMapping, now: number, gated: boolean) => {
      engine.current = applyMapping(engine.current, mapping, now);
      commit(now);
      scheduleExpiry();
      void gated;
    },
    [commit, scheduleExpiry],
  );

  const emit = useCallback(
    (event: PresenceEvent) => {
      const now = event.at ?? Date.now();

      // Typing only arms suppression; it never changes the visible signal.
      if (event.type === "conversation.typing") {
        typingUntil.current = now + TYPING_SUPPRESS_MS;
        return;
      }

      const mapping = EVENT_MAP[event.type];
      if (!mapping) return;

      // Suppress ambient (external, sub-urgent) events while the user types.
      if (
        mapping.external &&
        mapping.importance !== "urgent" &&
        now < typingUntil.current
      ) {
        return;
      }

      // Cooldown — only consumed on an event that actually fires.
      if (mapping.cooldownMs) {
        const key = mapping.cooldownKey ?? event.type;
        const last = lastFired.current.get(key) ?? 0;
        if (now - last < mapping.cooldownMs) return;
        lastFired.current.set(key, now);
      }

      run(mapping, now, true);
    },
    [run],
  );

  const override = useCallback(
    (patch: Partial<PresenceSignal>, holdMs?: number) => {
      run({ patch, importance: "normal", holdMs }, Date.now(), false);
    },
    [run],
  );

  // Subscribe the orchestrator to the module-wide bus.
  useEffect(() => subscribePresence(emit), [emit]);

  // Dev-only preview: honor a stored renderer override on boot, and expose a
  // console helper (`window.__lilithPresence`). Never present in production and
  // adds no UI. Toggle with e.g. `__lilithPresence.setRendererKind("avatar")`.
  useEffect(() => {
    const rendererOverride = readRendererOverride();
    const queryRenderer =
      process.env.NODE_ENV !== "production" && typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("renderer")
        : null;
    if (
      queryRenderer === "orb" ||
      queryRenderer === "avatar" ||
      queryRenderer === "edge" ||
      queryRenderer === "voice"
    ) {
      setRendererKind(queryRenderer);
    } else if (rendererOverride) {
      setRendererKind(rendererOverride);
    }
    if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
      (window as unknown as Record<string, unknown>).__lilithPresence = {
        setRendererKind,
        emit,
        override,
      };
    }
  }, [emit, override]);

  // Clean up the expiry timer on unmount.
  useEffect(() => {
    return () => {
      if (expiryTimer.current) clearTimeout(expiryTimer.current);
    };
  }, []);

  const value = useMemo(
    () => ({ signal, rendererKind, setRendererKind, emit, override }),
    [signal, rendererKind, emit, override],
  );

  return (
    <PresenceContext.Provider value={value}>{children}</PresenceContext.Provider>
  );
}

export function usePresence() {
  const ctx = useContext(PresenceContext);
  if (!ctx) throw new Error("usePresence must be used within a PresenceProvider");
  return ctx;
}

// Renderer selection + fallbacks live in presence-stage; re-export so existing
// consumers keep importing `PresenceStage` from the engine module.
export { PresenceStage } from "./presence-stage";
