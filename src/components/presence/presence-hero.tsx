"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { History } from "lucide-react";
import { PresenceStage, usePresence } from "./presence-engine";
import { CommandInput } from "./command-input";
import { ConversationAnnouncer, ConversationView } from "@/components/conversation/conversation-view";
import { RecordingControl } from "@/components/conversation/recording-control";
import { VoiceToggle } from "@/components/conversation/voice-toggle";
import { useConversation } from "@/components/conversation/conversation-provider";
import { CommandConsole, CommandHistory, useCommand } from "@/components/command";
import { ACTIVITY_META, CHIP_ACTIVITIES } from "@/lib/presence";
import { user } from "@/lib/data";
import { greetingFor, cn } from "@/lib/utils";
import { lilithSpeech } from "@/lib/voice/speech-controller";
import { voiceSettings } from "@/lib/voice/voice-settings";
import { ElevenLabsTTSProvider } from "@/lib/voice/elevenlabs-tts-provider";
import { decideReplyVoicing } from "@/lib/voice/reply-voicing";
import { ease, settle } from "@/lib/motion";

// Same opt-in as the avatar calibration tools (default off, even in `next dev`).
const SHOW_PRESENCE_CONTROLS = process.env.NEXT_PUBLIC_PRESENCE_DEBUG === "1";

// Stable module-level production auto-speech provider (never re-created on
// render). Independent of the manual dev POC provider selection.
const productionVoiceProvider = new ElevenLabsTTSProvider();

export function PresenceHero() {
  const { signal, emit, override } = usePresence();
  const { messages, status, error, reset, stop, stopped } = useConversation();
  const { submit, activeTask, history, historyOpen, setHistoryOpen, recentInputs } = useCommand();
  const [greeting, setGreeting] = useState("Good evening");
  const [editFill, setEditFill] = useState<{ text: string; nonce: number } | undefined>();

  const hasConversation = messages.length > 0 || !!error || !!stopped;
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
  // True while voice owns presence (loading = thinking, playing = speaking).
  const voicePresence = useRef(false);
  // True only while a turn sent from THIS page awaits its reply. Restored or
  // re-shown history never sets it, so it is never spoken or re-animated.
  const awaitingReply = useRef(false);

  // The single shared voice setting (owner toggle / debug panel).
  const autoSpeak = useSyncExternalStore(
    voiceSettings.subscribe,
    () => voiceSettings.getSnapshot().autoSpeak,
    () => voiceSettings.getServerSnapshot().autoSpeak,
  );

  // Live production-voice playback status (audio lifecycle authority).
  const voiceStatus = useSyncExternalStore(
    lilithSpeech.subscribe,
    () => lilithSpeech.getSnapshot().status,
    () => lilithSpeech.getServerSnapshot().status,
  );

  useEffect(() => {
    if (!isSending) return;
    awaitingReply.current = true;
    emit({ type: "conversation.response_started" });
  }, [isSending, emit]);

  // Handle each finalized LILITH reply exactly once (dedupe by stable UUID id,
  // marked BEFORE any async so StrictMode/effect re-entry can't double-speak).
  useEffect(() => {
    if (!lastLilith) return;
    const id = lastLilith.id;
    const text = lastLilith.text;
    const decision = decideReplyVoicing({
      replyId: id,
      handledReplyId: handledReplyId.current,
      awaitingReply: awaitingReply.current,
      autoSpeak: voiceSettings.getSnapshot().autoSpeak,
      text,
    });
    handledReplyId.current = id;
    if (decision === "skip") return; // already handled, or history: never replayed
    awaitingReply.current = false;

    // AUTO SPEAK OFF (default), or nothing speakable: the canned 2.6s
    // speaking transient, with no TTS call.
    if (decision === "transient") {
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
    if (!autoSpeak) return;
    if (voiceStatus === "loading") {
      voicePresence.current = true;
      override({ activity: "thinking", emotion: "focused", attention: "locked" });
    } else if (voiceStatus === "playing" || voiceStatus === "paused") {
      voicePresence.current = true;
      spokePresence.current = true;
      override({
        activity: "speaking",
        emotion: "pleased",
        attention: "engaged",
        speaking: true,
      });
    } else if (voiceStatus === "idle" && spokePresence.current) {
      spokePresence.current = false;
      voicePresence.current = false;
      override({
        activity: "idle",
        emotion: "neutral",
        attention: "ambient",
        speaking: false,
      });
    }
  }, [voiceStatus, autoSpeak, override]);

  // Voice switched OFF: stop any audio now (the controller also closes the
  // mouth) and, if voice was driving presence, settle Hsin to idle so she is
  // never left mid-"speaking".
  useEffect(() => {
    if (autoSpeak) return;
    lilithSpeech.stop();
    if (voicePresence.current) {
      voicePresence.current = false;
      spokePresence.current = false;
      override({ activity: "idle", emotion: "neutral", attention: "ambient", speaking: false });
    }
  }, [autoSpeak, override]);

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

  function handleStop() {
    // Browser-side only: stop waiting for the reply. Hsin leaves the thinking
    // beat and settles; no completion/speaking transient, since nothing came back.
    stop();
    override({ activity: "idle", emotion: "neutral", attention: "ambient", speaking: false });
  }

  function handleSubmit(text: string) {
    // User's new turn interrupts any in-progress speech immediately: stop audio
    // and clear visemes. Suppress the settle-to-idle override so response_started
    // / sending can move presence cleanly into thinking.
    spokePresence.current = false;
    lilithSpeech.stop();
    emit({ type: "conversation.user_message" });
    // The Command System decides: recognised commands enter the lifecycle,
    // plain conversation goes to the real backend (unchanged path).
    submit(text, { context: { surface: "home" } });
  }

  return (
    // Below xl the hero fills the column and is a size container, so the avatar
    // viewport can cap itself at the column width (presence-profiles STAGE_FIT).
    <div className="relative flex h-full flex-col items-center justify-between pb-1 pt-2 max-xl:@container">
      {/* greeting */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...ease, delay: 0.2 }}
        className="text-center"
      >
        <h1 className="text-3xl font-medium tracking-[-0.045em] text-ink [text-shadow:0_2px_28px_rgba(0,0,0,0.72)] sm:text-[2.6rem]">
          {greeting}, <span className="bg-gradient-to-r from-pearl via-wine-bright to-orchid-bright bg-clip-text font-semibold text-transparent">{user.name}</span>.
        </h1>
      </motion.div>

      {/* presence stage — pluggable renderer (orb today, avatar later). No
          grounded reflection: the bust-up should read as an integrated presence,
          not a figure standing on a stage floor. */}
      <div className="relative my-1 aspect-square w-full min-h-0 max-w-[460px] flex-1 lg:max-w-[360px] xl:max-w-[460px]">
        <PresenceStage />
      </div>

      {/* conversation / command region: an active command takes the surface,
          else the live transcript, else the idle hint + state chips */}
      <div className="mb-3 flex w-full flex-col items-center gap-2">
        {activeTask ? (
          <div className="flex w-full max-w-xl flex-col items-center gap-1.5">
            <HistoryTrigger count={history.length} onOpen={() => setHistoryOpen(true)} />
            <CommandConsole onEditRequest={(text) => setEditFill({ text, nonce: Date.now() })} />
          </div>
        ) : hasConversation ? (
          <div className="flex w-full flex-col items-center gap-1.5">
            <div className="flex w-full items-center justify-end gap-1">
              <HistoryTrigger count={history.length} onOpen={() => setHistoryOpen(true)} />
              <button
                onClick={reset}
                className="rounded-full px-2.5 py-1 font-mono text-micro uppercase tracking-wider text-ink-faint transition-colors hover:text-ink-muted"
              >
                Clear
              </button>
            </div>
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
                transition={settle}
                className="max-w-md text-lead leading-relaxed text-ink-muted [text-shadow:0_2px_18px_rgba(0,0,0,0.7)]"
              >
                {ACTIVITY_META[activity].hint}
              </motion.p>
            </AnimatePresence>

            {/* Manual presence overrides are a calibration tool, not status:
                shown only with the presence debug flag. */}
            {SHOW_PRESENCE_CONTROLS && (
            <div className="flex items-center gap-1.5" data-presence-controls>
              {CHIP_ACTIVITIES.map((a) => (
                <button
                  key={a}
                  onClick={() => override({ activity: a })}
                  className={cn(
                    "rounded-full border px-2.5 py-1 font-mono text-micro uppercase tracking-[0.14em] transition-all",
                    activity === a
                      ? "border-wine/25 bg-wine/[0.12] text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
                      : "border-transparent text-ink-faint hover:border-white/10 hover:bg-white/[0.035] hover:text-ink-muted",
                  )}
                >
                  {ACTIVITY_META[a].label}
                </button>
              ))}
            </div>
            )}

            {history.length > 0 && (
              <HistoryTrigger count={history.length} onOpen={() => setHistoryOpen(true)} />
            )}
          </div>
        )}
      </div>

      {/* command input — the primary conversation + command surface */}
      <div className="w-full max-w-xl">
        <div className="mb-1.5">
          <VoiceToggle />
        </div>
        <RecordingControl />
        <CommandInput
          onFocusChange={handleFocus}
          onSubmit={handleSubmit}
          onType={() => emit({ type: "conversation.typing" })}
          loading={isSending}
          onStop={handleStop}
          historyItems={recentInputs}
          fill={editFill}
        />
      </div>

      {/* screen-reader announcement of each new reply (always mounted) */}
      <ConversationAnnouncer />

      {/* command history drawer (fixed overlay) */}
      <CommandHistory />
    </div>
  );
}

function HistoryTrigger({ count, onOpen }: { count: number; onOpen: () => void }) {
  if (count === 0) return null;
  return (
    <button
      onClick={onOpen}
      className="flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-micro uppercase tracking-wider text-ink-faint transition-colors hover:text-ink-muted"
    >
      <History className="h-3 w-3" /> History · {count}
    </button>
  );
}
