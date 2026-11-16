"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { cn } from "@/lib/utils";
import { browserVoiceStorage, voiceSettings } from "@/lib/voice/voice-settings";
import { lilithSpeech } from "@/lib/voice/speech-controller";
import { ensureAudioContext } from "@/lib/voice/audio-playback";
import type { SpeechControllerSnapshot } from "@/lib/voice/types";

/**
 * Owner-facing "speak replies" switch. It reads and writes the single shared
 * `voiceSettings` store (the same one the debug panel uses) and talks to the
 * production `lilithSpeech` controller. It does not keep any voice state of
 * its own.
 *
 * - OFF by default. Turning it on is an explicit owner click, which also
 *   unlocks browser audio under that gesture.
 * - Turning it OFF stops any current audio at once (the controller closes
 *   Hsin's mouth; presence-hero settles her presence).
 * - Enabling it never replays earlier replies: only the next new reply to a
 *   turn the owner sends is spoken.
 * - If voice could not play (TTS not configured, or audio blocked), the switch
 *   stays on but says so, and replies stay text.
 */
export function VoiceToggle() {
  useEffect(() => {
    voiceSettings.hydrate(browserVoiceStorage());
  }, []);

  const on = useSyncExternalStore(
    voiceSettings.subscribe,
    () => voiceSettings.getSnapshot().autoSpeak,
    () => voiceSettings.getServerSnapshot().autoSpeak,
  );
  const speech = useSyncExternalStore(
    lilithSpeech.subscribe,
    lilithSpeech.getSnapshot,
    lilithSpeech.getServerSnapshot,
  );

  // Only report a failure from a speak attempt made after the owner last
  // turned voice on, never a stale one from before.
  const sinceRequest = useRef(speech.requestId);

  function toggle() {
    if (on) {
      voiceSettings.setAutoSpeak(false);
      lilithSpeech.stop();
      return;
    }
    sinceRequest.current = lilithSpeech.getSnapshot().requestId;
    voiceSettings.setAutoSpeak(true);
    // Unlock audio inside this click (browser autoplay policy). Plays nothing.
    void ensureAudioContext().catch(() => {});
  }

  return (
    <VoiceToggleButton
      on={on}
      problem={on ? voiceProblem(speech, sinceRequest.current) : null}
      speaking={speech.status === "playing" || speech.status === "paused"}
      onToggle={toggle}
    />
  );
}

/** Which failure, if any, to show for speech attempts after `sinceRequestId`. */
export function voiceProblem(
  speech: Pick<SpeechControllerSnapshot, "lastResult" | "requestId">,
  sinceRequestId: number,
): "unavailable" | "blocked" | null {
  if (speech.requestId <= sinceRequestId) return null;
  return speech.lastResult === "unavailable" || speech.lastResult === "blocked" ? speech.lastResult : null;
}

export const VOICE_PROBLEM_TEXT = {
  unavailable: "Voice isn't available right now. Replies stay as text.",
  blocked: "Your browser blocked audio. Replies stay as text.",
} as const;

/** Presentational switch (pure props; server-rendered by the self-test). */
export function VoiceToggleButton({
  on,
  problem,
  speaking,
  onToggle,
}: {
  on: boolean;
  problem: "unavailable" | "blocked" | null;
  speaking: boolean;
  onToggle: () => void;
}) {
  const Icon = on ? Volume2 : VolumeX;
  return (
    <div className="flex items-center justify-end gap-2">
      {problem && (
        <span role="status" className="text-micro text-amber/90" data-voice-problem={problem}>
          {VOICE_PROBLEM_TEXT[problem]}
        </span>
      )}
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label="Speak replies aloud"
        title={on ? "Voice on: new replies are spoken. Click to turn off." : "Voice off: replies are text only. Click to turn on."}
        onClick={onToggle}
        data-voice-toggle={on ? "on" : "off"}
        data-voice-speaking={speaking ? "true" : "false"}
        className={cn(
          "flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-micro uppercase tracking-wider transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wine-bright",
          on
            ? "border-wine/25 bg-wine/[0.12] text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
            : "border-transparent text-ink-faint hover:border-white/10 hover:bg-white/[0.035] hover:text-ink-muted",
        )}
      >
        <Icon className={cn("h-3 w-3", on && speaking && "text-wine-bright")} aria-hidden />
        Voice {on ? "on" : "off"}
      </button>
    </div>
  );
}
