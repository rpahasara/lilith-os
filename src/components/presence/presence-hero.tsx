"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PresenceStage, usePresence } from "./presence-engine";
import { CommandInput } from "./command-input";
import { PRESENCE, type PresenceState } from "@/lib/presence";
import { user } from "@/lib/data";
import { greetingFor, cn } from "@/lib/utils";
import { StatusDot } from "@/components/ui/primitives";

const CHIP_STATES: PresenceState[] = ["idle", "listening", "thinking", "speaking"];

export function PresenceHero() {
  const { state, setState } = usePresence();
  const [greeting, setGreeting] = useState("Good evening");
  const [line, setLine] = useState<string>("I've reviewed your day. Here's what matters.");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    setGreeting(greetingFor(new Date()));
    return () => timers.current.forEach(clearTimeout);
  }, []);

  function clearTimers() {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }

  function handleSubmit(text: string) {
    clearTimers();
    setState("thinking");
    setLine(`Working on “${text}”…`);
    timers.current.push(
      setTimeout(() => {
        setState("speaking");
        setLine("Done. I've drafted a plan and surfaced the key context.");
      }, 1600),
    );
    timers.current.push(
      setTimeout(() => {
        setState("idle");
        setLine("Anything else on your mind?");
      }, 4600),
    );
  }

  function handleFocus(focused: boolean) {
    if (state === "thinking" || state === "speaking") return;
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

      {/* dynamic line + state chips */}
      <div className="mb-4 flex flex-col items-center gap-3 text-center">
        <AnimatePresence mode="wait">
          <motion.p
            key={line}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.4 }}
            className="max-w-md text-[15px] text-ink-muted"
          >
            {line}
          </motion.p>
        </AnimatePresence>

        <div className="flex items-center gap-1.5">
          {CHIP_STATES.map((s) => (
            <button
              key={s}
              onClick={() => {
                clearTimers();
                setState(s);
                setLine(PRESENCE[s].hint);
              }}
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

      {/* command input */}
      <div className="w-full max-w-xl">
        <CommandInput onFocusChange={handleFocus} onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
