"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PresenceStage, usePresence } from "./presence-engine";
import { CommandInput } from "./command-input";
import { ConversationView } from "@/components/conversation/conversation-view";
import { useConversation } from "@/components/conversation/conversation-provider";
import { PRESENCE, type PresenceState } from "@/lib/presence";
import { user } from "@/lib/data";
import { greetingFor, cn } from "@/lib/utils";
import { StatusDot } from "@/components/ui/primitives";

const CHIP_STATES: PresenceState[] = ["idle", "listening", "thinking", "speaking"];

export function PresenceHero() {
  const { state, setState } = usePresence();
  const { messages, status, error, send } = useConversation();
  const [greeting, setGreeting] = useState("Good evening");

  const hasConversation = messages.length > 0 || !!error;
  const isSending = status === "sending";

  useEffect(() => {
    setGreeting(greetingFor(new Date()));
  }, []);

  // Drive the presence orb from the real conversation lifecycle.
  const lastLilith = [...messages].reverse().find((m) => m.role === "lilith");
  const seenReply = useRef<string | null>(null);

  useEffect(() => {
    if (isSending) setState("thinking");
  }, [isSending, setState]);

  useEffect(() => {
    if (lastLilith && lastLilith.id !== seenReply.current) {
      seenReply.current = lastLilith.id;
      setState("speaking", 2600);
    }
  }, [lastLilith, setState]);

  useEffect(() => {
    if (error) setState("idle");
  }, [error, setState]);

  function handleFocus(focused: boolean) {
    if (isSending || state === "thinking" || state === "speaking") return;
    setState(focused ? "listening" : "idle");
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
                key={state}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.4 }}
                className="max-w-md text-[15px] text-ink-muted"
              >
                {PRESENCE[state].hint}
              </motion.p>
            </AnimatePresence>

            <div className="flex items-center gap-1.5">
              {CHIP_STATES.map((s) => (
                <button
                  key={s}
                  onClick={() => setState(s)}
                  className={cn(
                    "rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition-all",
                    state === s
                      ? "bg-white/10 text-ink"
                      : "text-ink-faint hover:text-ink-muted",
                  )}
                >
                  {PRESENCE[s].label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* command input — the primary conversation surface */}
      <div className="w-full max-w-xl">
        <CommandInput onFocusChange={handleFocus} onSubmit={send} loading={isSending} />
      </div>
    </div>
  );
}
