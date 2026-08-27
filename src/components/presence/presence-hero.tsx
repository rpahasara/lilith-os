"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PresenceStage, usePresence } from "./presence-engine";
import { CommandInput } from "./command-input";
import { ConversationView } from "@/components/conversation/conversation-view";
import { useConversation } from "@/components/conversation/conversation-provider";
import { ACTIVITY_META, CHIP_ACTIVITIES } from "@/lib/presence";
import { user } from "@/lib/data";
import { greetingFor, cn } from "@/lib/utils";
import { StatusDot } from "@/components/ui/primitives";

export function PresenceHero() {
  const { signal, emit, override } = usePresence();
  const { messages, status, error, send } = useConversation();
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
  const seenReply = useRef<string | null>(null);

  useEffect(() => {
    if (isSending) emit({ type: "conversation.response_started" });
  }, [isSending, emit]);

  useEffect(() => {
    if (lastLilith && lastLilith.id !== seenReply.current) {
      seenReply.current = lastLilith.id;
      emit({ type: "conversation.response_complete" });
    }
  }, [lastLilith, emit]);

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

      {/* presence stage — pluggable renderer (orb today, avatar later) */}
      <div className="relative my-2 aspect-square w-full max-w-[420px] flex-1">
        <PresenceStage />
        {/* reflection floor */}
        <div className="pointer-events-none absolute bottom-6 left-1/2 h-8 w-40 -translate-x-1/2 rounded-[100%] bg-violet-bright/20 blur-2xl" />
      </div>

      {/* conversation region: live transcript once talking, else the idle hint + state chips */}
      <div className="mb-4 flex w-full flex-col items-center gap-3">
        {hasConversation ? (
          <ConversationView />
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
