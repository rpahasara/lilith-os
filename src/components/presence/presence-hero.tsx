"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PresenceStage, usePresence } from "./presence-engine";
import { CommandInput } from "./command-input";
import { ConversationView } from "@/components/conversation/conversation-view";
import { useConversation } from "@/components/conversation/conversation-provider";
import { ACTIVITY_META, CHIP_ACTIVITIES } from "@/lib/presence";
import { user } from "@/lib/data";
import { greetingFor, cn } from "@/lib/utils";
import { StatusDot } from "@/components/ui/primitives";
import { lilithSpeech } from "@/lib/voice/speech-controller";
import { voiceSettings } from "@/lib/voice/voice-settings";
import { ElevenLabsTTSProvider } from "@/lib/voice/elevenlabs-tts-provider";

// Stable module-level production auto-speech provider (never re-created on
// render). Independent of the manual dev POC provider selection.
const productionVoiceProvider = new ElevenLabsTTSProvider();

export function PresenceHero() {
  const { signal, emit, override } = usePresence();
  const { messages, status, error, send, reset } = useConversation();
  const [greeting, setGreeting] = useState("Good evening");

  const hasConversation = messages.length > 0 || !!error;
  const isSending = status === "sending";
  const activity = signal.activity;

  useEffect(() => {
    setGreeting(greetingFor(new Date()));
  }, []);

  // Drive the presence from the real conversation lifecycle — via semantic
  // events, not by poking the renderer. The engine maps these to signals.
  const lastLilith = [...messages].reverse().find((m) => m.role === "lilith");
  const handledReplyId = useRef<string | null>(null);
  // Tracks whether we've asserted a real-speaking presence override for the
  // current audio, so we only settle back to idle after having spoken.
  const spokePresence = useRef(false);

  // Live production-voice playback status (audio lifecycle authority).
  const voiceStatus = useSyncExternalStore(
    lilithSpeech.subscribe,
    () => lilithSpeech.getSnapshot().status,
    () => lilithSpeech.getServerSnapshot().status,
  );

  useEffect(() => {
    if (isSending) emit({ type: "conversation.response_started" });
  }, [isSending, emit]);

  // Handle each finalized LILITH reply exactly once (dedupe by stable UUID id,
  // marked BEFORE any async so StrictMode/effect re-entry can't double-speak).
  useEffect(() => {
    if (!lastLilith || lastLilith.id === handledReplyId.current) return;
    const id = lastLilith.id;
    const text = lastLilith.text;
    handledReplyId.current = id;

    // AUTO SPEAK OFF (default): unchanged — the canned 2.6s speaking transient.
    if (!voiceSettings.getSnapshot().autoSpeak) {
      emit({ type: "conversation.response_complete" });
      return;
    }

    // AUTO SPEAK ON: real audio owns the speaking lifecycle. On failure (or an
    // unconfigured provider) fall back ONCE to the canned transient so the
    // avatar still reacts and never sticks. No automatic retry of the same id.
    let cancelled = false;
    void lilithSpeech.speak({ text }, productionVoiceProvider).then((ok) => {
      if (cancelled) return;
      if (!ok && handledReplyId.current === id) {
        emit({ type: "conversation.response_complete" });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [lastLilith, emit]);

  // Real-audio presence ownership (only while AUTO SPEAK is on): the audio
  // lifecycle is the sole authority for real speaking. Loading = thinking (not
  // speaking); playing/paused = speaking; return to idle settles once.
  useEffect(() => {
    if (!voiceSettings.getSnapshot().autoSpeak) return;
    if (voiceStatus === "loading") {
      override({ activity: "thinking", emotion: "focused", attention: "locked" });
    } else if (voiceStatus === "playing" || voiceStatus === "paused") {
      spokePresence.current = true;
      override({
        activity: "speaking",
        emotion: "pleased",
        attention: "engaged",
        speaking: true,
      });
    } else if (voiceStatus === "idle" && spokePresence.current) {
      spokePresence.current = false;
      override({
        activity: "idle",
        emotion: "neutral",
        attention: "ambient",
        speaking: false,
      });
    }
  }, [voiceStatus, override]);

  // Stop any speech cleanly when this surface unmounts / route changes.
  useEffect(() => {
    return () => {
      lilithSpeech.stop();
    };
  }, []);

  useEffect(() => {
    if (error) emit({ type: "conversation.error" });
  }, [error, emit]);

  function handleFocus(focused: boolean) {
    // Don't yank her out of an active thinking/speaking beat.
    if (isSending || activity === "thinking" || activity === "speaking") return;
    emit({
      type: focused ? "conversation.input_focus" : "conversation.input_blur",
    });
  }

  function handleSubmit(text: string) {
    // User's new turn interrupts any in-progress speech immediately: stop audio
    // and clear visemes. Suppress the settle-to-idle override so response_started
    // / sending can move presence cleanly into thinking.
    spokePresence.current = false;
    lilithSpeech.stop();
    emit({ type: "conversation.user_message" });
    send(text);
  }

  return (
    <div className="relative flex h-full flex-col items-center justify-between py-2">
      {/* greeting */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.7 }}
        className="text-center"
      >
        <p className="eyebrow mb-2 flex items-center justify-center gap-2">
          <StatusDot accent="violet" /> Lilith · online
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-[2.5rem]">
          {greeting}, <span className="text-violet-bright">{user.name}</span>.
        </h1>
      </motion.div>

      {/* presence stage — pluggable renderer (orb today, avatar later). No
          grounded reflection: the bust-up should read as an integrated presence,
          not a figure standing on a stage floor. */}
      <div className="relative my-2 aspect-square w-full max-w-[460px] flex-1">
        <PresenceStage />
      </div>

      {/* conversation region: live transcript once talking, else the idle hint + state chips */}
      <div className="mb-4 flex w-full flex-col items-center gap-3">
        {hasConversation ? (
          <div className="flex w-full flex-col items-center gap-1.5">
            <button
              onClick={reset}
              className="self-end rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-ink-faint transition-colors hover:text-ink-muted"
            >
              Clear
            </button>
            <ConversationView />
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-center">
            <AnimatePresence mode="wait">
              <motion.p
                key={activity}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.4 }}
                className="max-w-md text-[15px] text-ink-muted"
              >
                {ACTIVITY_META[activity].hint}
              </motion.p>
            </AnimatePresence>

            <div className="flex items-center gap-1.5">
              {CHIP_ACTIVITIES.map((a) => (
                <button
                  key={a}
                  onClick={() => override({ activity: a })}
                  className={cn(
                    "rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition-all",
                    activity === a
                      ? "bg-white/10 text-ink"
                      : "text-ink-faint hover:text-ink-muted",
                  )}
                >
                  {ACTIVITY_META[a].label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* command input — the primary conversation surface */}
      <div className="w-full max-w-xl">
        <CommandInput
          onFocusChange={handleFocus}
          onSubmit={handleSubmit}
          onType={() => emit({ type: "conversation.typing" })}
          loading={isSending}
        />
      </div>
    </div>
  );
}
