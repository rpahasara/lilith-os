"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, Command, Loader2, Mic, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandInputProps {
  onFocusChange?: (focused: boolean) => void;
  onSubmit?: (text: string) => void;
  /** Fired on each keystroke — used to arm presence typing-suppression. */
  onType?: () => void;
  /** While true the input is locked and shows a working state (prevents
   *  duplicate sends). */
  loading?: boolean;
}

const SUGGESTIONS = ["Plan my day", "Summarise inbox", "Draft a reply", "What did I miss?"];

export function CommandInput({ onFocusChange, onSubmit, onType, loading = false }: CommandInputProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);

  function submit() {
    if (loading) return;
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
            ? "rgba(219,111,138,0.5)"
            : "rgba(255,255,255,0.1)",
          boxShadow: focused
            ? "0 0 0 1px rgba(243,238,244,0.22), 0 26px 66px -28px rgba(201,79,109,0.6), 0 16px 54px -30px rgba(168,134,217,0.3)"
            : "0 26px 64px -34px rgba(0,0,0,0.9), 0 18px 52px -38px rgba(201,79,109,0.16)",
        }}
        className="glass-strong flex items-center gap-3 rounded-full px-2 py-2 pl-5"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-wine-bright" />
        ) : (
          <Sparkles className="h-4 w-4 shrink-0 text-wine-bright" />
        )}
        <input
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            onType?.();
          }}
          disabled={loading}
          onFocus={() => {
            setFocused(true);
            onFocusChange?.(true);
          }}
          onBlur={() => {
            setFocused(false);
            onFocusChange?.(false);
          }}
          onKeyDown={(e) => {
            // Enter submits; Shift+Enter is reserved for a future multiline field.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={loading ? "Lilith is thinking…" : "Ask Lilith, or command anything…"}
          className="min-w-0 flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-faint focus:outline-none disabled:opacity-60"
        />
        <kbd className="hidden items-center gap-1 rounded-md border border-white/10 px-1.5 py-0.5 font-mono text-[10px] text-ink-faint sm:flex">
          <Command className="h-3 w-3" />K
        </kbd>
        <button
          aria-label="Voice input"
          disabled={loading}
          className="grid h-9 w-9 place-items-center rounded-full text-ink-muted transition-colors hover:bg-white/5 hover:text-ink disabled:opacity-40"
        >
          <Mic className="h-4 w-4" />
        </button>
        <button
          aria-label="Send"
          onClick={submit}
          disabled={loading || !value.trim()}
          className={cn(
            "grid h-9 w-9 place-items-center rounded-full transition-all",
            value.trim() && !loading
              ? "bg-gradient-to-b from-wine-bright via-wine to-wine-deep text-white shadow-[0_8px_22px_-6px_rgba(201,79,109,0.85)]"
              : "bg-white/5 text-ink-faint",
          )}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowUp className="h-4 w-4" />
          )}
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
