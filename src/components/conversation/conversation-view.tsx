"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConversation } from "./conversation-provider";

/**
 * The live conversation transcript, rendered in LILITH's existing visual
 * language (glass bubbles, violet accents). Shows a subtle thinking state while
 * a turn is in flight and a graceful error row with retry. Auto-scrolls to the
 * latest turn. Renders nothing in the empty state — the hero keeps its
 * greeting there.
 */
export function ConversationView() {
  const { messages, status, error, retry } = useConversation();
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status, error]);

  if (messages.length === 0 && !error) return null;

  return (
    <div className="scroll-area flex max-h-[34vh] w-full flex-col gap-2.5 overflow-y-auto px-1 py-1 lg:max-h-[240px]">
      <AnimatePresence initial={false}>
        {messages.map((m) => (
          <motion.div
            key={m.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className={cn(
              "flex",
              m.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-3.5 py-2 text-[14px] leading-relaxed",
                m.role === "user"
                  ? "border border-violet-bright/25 bg-violet-bright/[0.12] text-ink"
                  : "glass text-ink",
              )}
            >
              {m.role === "lilith" && (
                <span className="eyebrow mb-1 block text-violet-bright/80">Lilith</span>
              )}
              <p className="whitespace-pre-wrap break-words">{m.text}</p>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      {status === "sending" && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex justify-start"
        >
          <div className="glass flex items-center gap-1.5 rounded-2xl px-3.5 py-2.5">
            <Dot delay={0} />
            <Dot delay={0.15} />
            <Dot delay={0.3} />
          </div>
        </motion.div>
      )}

      {error && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between gap-3 rounded-2xl border border-rose/25 bg-rose/[0.08] px-3.5 py-2"
        >
          <span className="text-[13px] text-rose">{error}</span>
          <button
            onClick={retry}
            className="flex shrink-0 items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
          >
            <RotateCcw className="h-3 w-3" /> Retry
          </button>
        </motion.div>
      )}

      <div ref={endRef} />
    </div>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <motion.span
      className="block h-1.5 w-1.5 rounded-full bg-violet-bright"
      animate={{ opacity: [0.3, 1, 0.3] }}
      transition={{ duration: 1.1, repeat: Infinity, delay }}
    />
  );
}
