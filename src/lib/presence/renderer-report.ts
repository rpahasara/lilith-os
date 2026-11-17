/**
 * What Lilith's presence actually rendered, as measured by the presence stage
 * on the Command Center, for anything else that wants to tell the truth about it
 * (the System workspace).
 *
 * The stage writes here when it decides what to draw (and why) and after each
 * one-second frame-rate window it already measures for its performance guard.
 * Nothing else writes, and nothing here is assumed: until the stage has rendered
 * in this tab, there is no report. A plain module store, not React state, so the
 * stage never re-renders for it.
 */

export type RenderedPresence = "avatar" | "orb" | "static" | "off";

/** Why the stage drew what it drew. */
export type PresenceRenderReason =
  | "live" // the chosen renderer is mounted
  | "preference-off" // the owner turned presence off
  | "reduced-motion" // the device asks for reduced motion: still image
  | "no-webgl" // this browser cannot create a WebGL context
  | "performance" // frame rate stayed under the guard's floor: still image until reload
  | "error"; // the renderer threw: still image

export interface PresenceRenderReport {
  rendered: RenderedPresence;
  reason: PresenceRenderReason;
  /** Frames per second over the last measured one-second window, while live. */
  fps: number | null;
  /** When the stage last reported (ISO). */
  at: string;
}

let current: PresenceRenderReport | null = null;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

export const presenceRenderReport = {
  get: (): PresenceRenderReport | null => current,
  getServer: (): PresenceRenderReport | null => null,
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  /** What the stage is drawing now, and why. Keeps the last fps while still live. */
  setRendered(rendered: RenderedPresence, reason: PresenceRenderReason, now = new Date()): void {
    const keepFps = reason === "live" && current?.reason === "live" && current.rendered === rendered;
    if (current && current.rendered === rendered && current.reason === reason) return;
    current = { rendered, reason, fps: keepFps ? current!.fps : null, at: now.toISOString() };
    emit();
  },
  /** One measured window from the stage's frame-rate guard. */
  setFps(fps: number, now = new Date()): void {
    if (!current || current.reason !== "live" || !Number.isFinite(fps)) return;
    current = { ...current, fps: Math.round(fps), at: now.toISOString() };
    emit();
  },
  /** Tests only. */
  reset(): void {
    current = null;
    emit();
  },
};
