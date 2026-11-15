"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConversationMessage } from "@/lib/conversation/types";
import {
  STOP_NOTICE,
  elapsedLabel,
  lastReplyId,
  nextAnnouncement,
} from "@/lib/conversation/turn-runner";
import { useConversation } from "./conversation-provider";

/**
 * The live conversation transcript, rendered in LILITH's existing visual
 * language (glass bubbles, violet accents). Shows a subtle thinking state while
 * a turn is in flight (with measured elapsed time after 10 s), a graceful error
 * row with retry, and a truthful notice after Stop. Auto-scrolls to the latest
 * turn. Renders nothing in the empty state; the hero keeps its greeting there.
 *
 * Screen readers: the transcript is a `role="log"` landmark for browsing, with
 * its own live announcements switched off. New LILITH replies are announced
 * exactly once by <ConversationAnnouncer>, which stays mounted even when this
 * view is hidden.
 */
export function ConversationView() {
  const { messages, status, error, retry, pendingSince, stopped } = useConversation();
  const now = useTicker(status === "sending" ? 1000 : null);
  const elapsed =
    status === "sending" && pendingSince != null && now != null ? elapsedLabel(now - pendingSince) : null;

  return (
    <ConversationTranscript
      messages={messages}
      sending={status === "sending"}
      elapsed={elapsed}
      error={error}
      stopped={!!stopped}
      onRetry={retry}
    />
  );
}

/** Presentational transcript (pure props; server-rendered by the self-test). */
export function ConversationTranscript({
  messages,
  sending,
  elapsed,
  error,
  stopped,
  onRetry,
}: {
  messages: ConversationMessage[];
  sending: boolean;
  elapsed: string | null;
  error: string | null;
  stopped: boolean;
  onRetry: () => void;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, error, stopped]);

  if (messages.length === 0 && !error && !stopped) return null;

  return (
    <div className="scroll-area flex max-h-[34vh] w-full flex-col gap-2.5 overflow-y-auto px-1 py-1 lg:max-h-[240px]">
      {/* Browsable history. Announcements come from <ConversationAnnouncer>,
          so this log is aria-live="off" to avoid reading replies twice. */}
      <div
        role="log"
        aria-live="off"
        aria-label="Conversation with LILITH"
        data-conversation-log=""
        className="flex flex-col gap-2.5"
      >
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-3.5 py-2 text-[14px] leading-relaxed",
                  m.role === "user"
                    ? "border border-violet-bright/25 bg-violet-bright/[0.12] text-ink"
                    : "glass text-ink",
                )}
              >
                {m.role === "lilith" ? (
                  <span className="eyebrow mb-1 block text-violet-bright/80">Lilith</span>
                ) : (
                  <span className="sr-only">You: </span>
                )}
                <p className="whitespace-pre-wrap break-words">{m.text}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {sending && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex justify-start"
          data-conversation-pending=""
        >
          <div className="glass flex items-center gap-1.5 rounded-2xl px-3.5 py-2.5">
            <span className="sr-only">LILITH is replying.</span>
            <Dot delay={0} />
            <Dot delay={0.15} />
            <Dot delay={0.3} />
            {elapsed && (
              // Measured wall-clock time since the request left this browser.
              // Not model progress, and not announced every second.
              <span aria-hidden className="ml-1.5 font-mono text-[10px] text-ink-faint" data-conversation-elapsed="">
                Waiting for a reply · {elapsed}
              </span>
            )}
          </div>
        </motion.div>
      )}

      {stopped && !sending && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          role="status"
          data-conversation-stopped=""
          className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-3.5 py-2"
        >
          <span className="text-[12px] leading-snug text-ink-muted">{STOP_NOTICE}</span>
          <button
            type="button"
            onClick={onRetry}
            className="flex shrink-0 items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
          >
            <RotateCcw className="h-3 w-3" /> Ask again
          </button>
        </motion.div>
      )}

      {error && !sending && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          role="alert"
          data-conversation-error=""
          className="flex items-center justify-between gap-3 rounded-2xl border border-rose/25 bg-rose/[0.08] px-3.5 py-2"
        >
          <span className="text-[13px] text-rose">{error}</span>
          <button
            type="button"
            onClick={onRetry}
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

/**
 * Always-mounted polite live region: announces each new LILITH reply exactly
 * once. History restored from storage is the baseline and is never read out.
 */
export function ConversationAnnouncer() {
  const { messages, hydrated } = useConversation();
  const announced = useRef<string | null | undefined>(undefined);
  const [current, setCurrent] = useState<{ id: string; text: string } | null>(null);

  useEffect(() => {
    if (!hydrated) return;
    if (announced.current === undefined) {
      announced.current = lastReplyId(messages); // baseline: restored history
      return;
    }
    const next = nextAnnouncement(messages, announced.current);
    if (!next) return;
    announced.current = next.id;
    setCurrent(next);
  }, [messages, hydrated]);

  return <LiveAnnouncement announcement={current} />;
}

/** Presentational live region (server-rendered by the self-test). */
export function LiveAnnouncement({ announcement }: { announcement: { id: string; text: string } | null }) {
  return (
    <div className="sr-only" aria-live="polite" aria-atomic="true" data-conversation-announcer="">
      {/* A fresh node per reply, so identical consecutive replies are still announced. */}
      {announcement && <p key={announcement.id}>LILITH: {announcement.text}</p>}
    </div>
  );
}

/** Wall-clock ticker; null `intervalMs` = stopped. */
function useTicker(intervalMs: number | null): number | null {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    if (intervalMs == null) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return intervalMs == null ? null : now;
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
