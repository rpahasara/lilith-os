"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, Loader2, Mic, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandInputProps {
  onFocusChange?: (focused: boolean) => void;
  onSubmit?: (text: string) => void;
  /** Fired on each keystroke — used to arm presence typing-suppression. */
  onType?: () => void;
  /** While true the input is locked and shows a working state (prevents
   *  duplicate sends). */
  loading?: boolean;
  /** Suggested actions shown under the input. Falls back to defaults. */
  suggestions?: string[];
  /** Prior submitted commands (oldest→newest) for Ctrl/↑ recall. */
  historyItems?: string[];
  /** Bump `nonce` to load `text` into the field (e.g. "Edit" from review). */
  fill?: { text: string; nonce: number };
}

const DEFAULT_SUGGESTIONS = ["Plan my day", "Summarise inbox", "Compare AWS cost", "What did I miss?"];

export function CommandInput({
  onFocusChange,
  onSubmit,
  onType,
  loading = false,
  suggestions = DEFAULT_SUGGESTIONS,
  historyItems = [],
  fill,
}: CommandInputProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // History recall cursor: -1 = live (not recalling), 0..n = index from newest.
  const [recall, setRecall] = useState(-1);

  // Ctrl+Space is the (in-app) global command entry point. Native desktop
  // global hotkeys are intentionally out of scope for V1.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.ctrlKey && e.code === "Space") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Load an "Edit"-refilled value and focus.
  useEffect(() => {
    if (!fill) return;
    setValue(fill.text);
    setRecall(-1);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [fill?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  function submit() {
    if (loading) return;
    const text = value.trim();
    if (!text) return;
    onSubmit?.(text);
    setValue("");
    setRecall(-1);
  }

  function recallStep(dir: 1 | -1) {
    if (historyItems.length === 0) return;
    // newest-first index space
    let next = recall + dir;
    if (next < -1) next = -1;
    if (next > historyItems.length - 1) next = historyItems.length - 1;
    setRecall(next);
    if (next === -1) {
      setValue("");
    } else {
      setValue(historyItems[historyItems.length - 1 - next]);
    }
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
        className="glass-strong relative flex items-center gap-3 overflow-hidden rounded-full px-2 py-2 pl-5"
      >
        <span className="pointer-events-none absolute inset-x-12 top-0 h-px bg-gradient-to-r from-transparent via-pearl/45 to-transparent" />
        {loading ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-wine-bright" />
        ) : (
          <Sparkles className="h-4 w-4 shrink-0 text-wine-bright drop-shadow-[0_0_8px_rgba(225,132,157,0.45)]" />
        )}
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setRecall(-1);
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
              return;
            }
            // Shell-style command recall when the field is empty or already recalling.
            if (e.key === "ArrowUp" && (value === "" || recall !== -1)) {
              e.preventDefault();
              recallStep(1);
            } else if (e.key === "ArrowDown" && recall !== -1) {
              e.preventDefault();
              recallStep(-1);
            } else if (e.key === "Escape" && recall !== -1) {
              e.preventDefault();
              setRecall(-1);
              setValue("");
            }
          }}
          placeholder={loading ? "Lilith is thinking…" : "Ask Lilith, or command anything…"}
          className="min-w-0 flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-faint focus:outline-none disabled:opacity-60"
        />
        <kbd className="hidden items-center gap-1 rounded-md border border-white/10 bg-black/15 px-1.5 py-0.5 font-mono text-[10px] text-ink-faint sm:flex">
          Ctrl Space
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
            "grid h-9 w-9 place-items-center rounded-full border transition-all",
            value.trim() && !loading
              ? "border-wine-bright/55 bg-gradient-to-b from-wine-bright via-wine to-wine-deep text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.4),0_8px_22px_-6px_rgba(201,79,109,0.85)]"
              : "border-white/[0.06] bg-white/[0.045] text-ink-faint",
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
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => {
              setValue(s);
              setRecall(-1);
              inputRef.current?.focus();
            }}
            className="rounded-full border border-white/[0.09] bg-black/[0.12] px-3 py-1.5 text-[11px] text-ink-muted backdrop-blur-md transition-all hover:border-wine/25 hover:bg-wine/[0.07] hover:text-ink"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
