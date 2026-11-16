"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useCommand } from "@/components/command/command-provider";
import { useConversation } from "@/components/conversation/conversation-provider";
import { useShellHealth } from "@/components/layout/shell-health-provider";
import { isTerminal } from "@/lib/command/types";
import { presenceAnnouncement, shellPresence, type ShellPresenceState } from "@/lib/presence/shell-presence";
import { cn } from "@/lib/utils";
import { lilithSpeech } from "@/lib/voice/speech-controller";

/**
 * Lilith's presence, read from the sources the shell can verify (see
 * `lib/presence/shell-presence`). Deliberately does not use the avatar's
 * presence engine.
 */
export function useShellPresence(): ShellPresenceState {
  const { health } = useShellHealth();
  const { status } = useConversation();
  const { tasks } = useCommand();
  const voice = useSyncExternalStore(
    lilithSpeech.subscribe,
    () => lilithSpeech.getSnapshot().status,
    () => lilithSpeech.getServerSnapshot().status,
  );

  return shellPresence({
    health: health.state,
    sending: status === "sending",
    taskStatuses: tasks.map((t) => t.status).filter((s) => !isTerminal(s)),
    voice,
    // Speech input does not exist yet, so there is nothing to report.
    listening: false,
  });
}

/**
 * The mark itself: a small ember with a ring. Decorative (the state is given
 * in words wherever the mark is used); its motion is CSS only and is stilled
 * by the reduced-motion rule in the stylesheet.
 */
export function PresenceMark({ state, className }: { state: ShellPresenceState; className?: string }) {
  return (
    <span aria-hidden data-presence={state} className={cn("presence-mark", className)}>
      <span className="presence-mark__ring" />
      <span className="presence-mark__core" />
    </span>
  );
}

/**
 * Tells assistive technology about the presence changes that matter (lost,
 * back, approval needed). Mount once.
 */
export function PresenceAnnouncer({ state }: { state: ShellPresenceState }) {
  const prev = useRef<ShellPresenceState | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const next = presenceAnnouncement(prev.current, state);
    prev.current = state;
    if (next) setMessage(next);
  }, [state]);

  return (
    <span className="sr-only" role="status" aria-live="polite" data-presence-announcer="">
      {message}
    </span>
  );
}
