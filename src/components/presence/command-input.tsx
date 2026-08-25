"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, Command, Mic, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandInputProps {
  onFocusChange?: (focused: boolean) => void;
  onSubmit?: (text: string) => void;
}

const SUGGESTIONS = ["Plan my day", "Summarise inbox", "Draft a reply", "What did I miss?"];

export function CommandInput({ onFocusChange, onSubmit }: CommandInputProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);

  function submit() {
    const text = value.trim();
    if (!text) return;
    onSubmit?.(text);
    setValue("");
  }

  return (
    <div className="w-full">
      <motion.div
        animate={{
          borderColor: focused
            ? "rgba(167,139,250,0.5)"
            : "rgba(255,255,255,0.1)",
          boxShadow: focused
            ? "0 0 0 1px rgba(167,139,250,0.25), 0 20px 60px -30px rgba(139,92,246,0.8)"
            : "0 20px 50px -30px rgba(0,0,0,0.9)",
        }}
        className="glass-strong flex items-center gap-3 rounded-full px-2 py-2 pl-5"
      >
        <Sparkles className="h-4 w-4 shrink-0 text-violet-bright" />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => {
            setFocused(true);
            onFocusChange?.(true);
          }}
          onBlur={() => {
            setFocused(false);
            onFocusChange?.(false);
          }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Ask Lilith, or command anything…"
          className="min-w-0 flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
        />
        <kbd className="hidden items-center gap-1 rounded-md border border-white/10 px-1.5 py-0.5 font-mono text-[10px] text-ink-faint sm:flex">
          <Command className="h-3 w-3" />K
        </kbd>
        <button
          aria-label="Voice input"
          className="grid h-9 w-9 place-items-center rounded-full text-ink-muted transition-colors hover:bg-white/5 hover:text-ink"
        >
          <Mic className="h-4 w-4" />
        </button>
        <button
          aria-label="Send"
          onClick={submit}
          className={cn(
            "grid h-9 w-9 place-items-center rounded-full transition-all",
            value.trim()
              ? "bg-gradient-to-b from-violet-bright to-violet-deep text-white shadow-[0_8px_20px_-6px_rgba(139,92,246,0.8)]"
              : "bg-white/5 text-ink-faint",
          )}
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </motion.div>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => setValue(s)}
            className="rounded-full border border-white/[0.07] bg-white/[0.02] px-3 py-1 text-xs text-ink-muted transition-colors hover:border-white/15 hover:text-ink"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
