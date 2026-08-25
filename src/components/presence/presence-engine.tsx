"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { PRESENCE, type PresenceState } from "@/lib/presence";
import { PresenceOrb } from "./presence-orb";

/**
 * The Presence Engine decouples Lilith's *state* (idle / listening / thinking /
 * speaking) from how she is *rendered*. The renderer is pluggable, so the same
 * state can drive an orb today and a live 3D avatar, a voice waveform, a
 * screen-edge peek, or a floating desktop presence later — without touching the
 * screens that consume it.
 */
export type PresenceMode = "orb" | "avatar" | "voice" | "edge" | "floating";

export interface PresenceRendererProps {
  state: PresenceState;
}

/** Registry of available presence renderers. Add new modes here. */
const RENDERERS: Partial<Record<PresenceMode, (p: PresenceRendererProps) => ReactNode>> = {
  orb: ({ state }) => <PresenceOrb state={state} />,
  // avatar: ({ state }) => <AvatarPresence state={state} />,   // future
  // voice:  ({ state }) => <VoicePresence state={state} />,    // future
};

interface PresenceContextValue {
  state: PresenceState;
  mode: PresenceMode;
  /** Set a state; optionally auto-revert to idle after `holdMs`. */
  setState: (next: PresenceState, holdMs?: number) => void;
  setMode: (mode: PresenceMode) => void;
}

const PresenceContext = createContext<PresenceContextValue | null>(null);

export function PresenceProvider({
  children,
  defaultMode = "orb",
}: {
  children: ReactNode;
  defaultMode?: PresenceMode;
}) {
  const [state, setStateRaw] = useState<PresenceState>("idle");
  const [mode, setMode] = useState<PresenceMode>(defaultMode);
  const revert = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setState = useCallback((next: PresenceState, holdMs?: number) => {
    if (revert.current) clearTimeout(revert.current);
    setStateRaw(next);
    if (holdMs) {
      revert.current = setTimeout(() => setStateRaw("idle"), holdMs);
    }
  }, []);

  const value = useMemo(
    () => ({ state, mode, setState, setMode }),
    [state, mode, setState],
  );

  return (
    <PresenceContext.Provider value={value}>
      {children}
    </PresenceContext.Provider>
  );
}

export function usePresence() {
  const ctx = useContext(PresenceContext);
  if (!ctx) throw new Error("usePresence must be used within a PresenceProvider");
  return ctx;
}

/** Renders the active presence renderer for the current mode. Fills its box. */
export function PresenceStage() {
  const { state, mode } = usePresence();
  const render = RENDERERS[mode] ?? RENDERERS.orb!;
  return (
    <div className="relative h-full w-full" data-presence-mode={mode}>
      {render({ state })}
    </div>
  );
}

/** Re-export for consumers that only need the profile metadata. */
export { PRESENCE };
