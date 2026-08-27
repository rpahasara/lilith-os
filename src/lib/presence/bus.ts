/**
 * A tiny typed pub/sub for presence events.
 *
 * Any module — a hook, a provider, a plain function — can `emitPresenceEvent`
 * without prop-drilling or touching React context. The orchestrator
 * (`PresenceProvider`) subscribes once and turns events into signals. This is
 * the single seam between "something happened in the app" and "Lilith reacts".
 *
 * Events are semantic only: no payloads, PII, tokens, or backend data cross
 * this boundary (see {@link PresenceEvent}).
 */

import type { PresenceEvent } from "./types";

type Handler = (event: PresenceEvent) => void;

const handlers = new Set<Handler>();

/** Emit a presence event to every current subscriber. */
export function emitPresenceEvent(event: PresenceEvent): void {
  // Copy to a stable list so a handler that (un)subscribes mid-dispatch is safe.
  for (const h of [...handlers]) {
    try {
      h(event);
    } catch {
      /* a broken subscriber must never break the emitter */
    }
  }
}

/** Subscribe to presence events. Returns an unsubscribe function. */
export function subscribePresence(handler: Handler): () => void {
  handlers.add(handler);
  return () => {
    handlers.delete(handler);
  };
}
