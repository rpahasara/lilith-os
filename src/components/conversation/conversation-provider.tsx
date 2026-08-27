"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { sendConversation } from "@/lib/conversation/client";
import type { ConversationMessage, ConversationStatus } from "@/lib/conversation/types";

/**
 * Holds the live LILITH OS conversation: the transcript, the send lifecycle,
 * and a stable dedicated session identity so follow-ups retain context on the
 * backend (one long-lived `lilith_os` gateway session, like Discord/Telegram).
 *
 * Recent messages + the session id are persisted to localStorage so the
 * conversation survives navigation between workspaces and page reloads within
 * the same browser. State is hydrated on the client only (no SSR mismatch).
 */

const SESSION_KEY = "lilith-os:session-id";
const MESSAGES_KEY = "lilith-os:messages";
const MAX_PERSISTED = 60;

interface ConversationContextValue {
  messages: ConversationMessage[];
  status: ConversationStatus;
  error: string | null;
  sessionId: string;
  /** Send a message. No-op while a send is already in flight. */
  send: (text: string) => void;
  /** Retry the last message that failed. */
  retry: () => void;
  /** Clear the transcript and start a fresh backend session. */
  reset: () => void;
}

const ConversationContext = createContext<ConversationContextValue | null>(null);

function makeSessionId(): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `lilith-os-${rand}`;
}

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState<ConversationStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>("lilith-os");
  const [hydrated, setHydrated] = useState(false);

  // Guards against duplicate concurrent sends even across rapid calls.
  const inFlight = useRef(false);
  // Last user text, kept for retry.
  const lastAttempt = useRef<string | null>(null);

  // Hydrate from localStorage (client only).
  useEffect(() => {
    try {
      let sid = window.localStorage.getItem(SESSION_KEY);
      if (!sid) {
        sid = makeSessionId();
        window.localStorage.setItem(SESSION_KEY, sid);
      }
      setSessionId(sid);
      const raw = window.localStorage.getItem(MESSAGES_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) setMessages(parsed.slice(-MAX_PERSISTED));
      }
    } catch {
      /* storage unavailable — run in-memory */
    }
    setHydrated(true);
  }, []);

  // Persist transcript.
  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(
        MESSAGES_KEY,
        JSON.stringify(messages.slice(-MAX_PERSISTED)),
      );
    } catch {
      /* ignore quota / unavailable */
    }
  }, [messages, hydrated]);

  const runSend = useCallback(
    async (text: string) => {
      if (inFlight.current) return;
      inFlight.current = true;
      lastAttempt.current = text;
      setError(null);
      setStatus("sending");

      const userMsg: ConversationMessage = {
        id: newId(),
        role: "user",
        text,
        ts: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const res = await sendConversation(text, sessionId);
        const reply = res.reply.trim() || "…";
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "lilith",
            text: reply,
            ts: new Date().toISOString(),
          },
        ]);
        lastAttempt.current = null;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      } finally {
        inFlight.current = false;
        setStatus("idle");
      }
    },
    [sessionId],
  );

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || inFlight.current) return;
      void runSend(trimmed);
    },
    [runSend],
  );

  const retry = useCallback(() => {
    const text = lastAttempt.current;
    if (!text || inFlight.current) return;
    void runSend(text);
  }, [runSend]);

  const reset = useCallback(() => {
    if (inFlight.current) return;
    const sid = makeSessionId();
    try {
      window.localStorage.setItem(SESSION_KEY, sid);
      window.localStorage.removeItem(MESSAGES_KEY);
    } catch {
      /* ignore */
    }
    setSessionId(sid);
    setMessages([]);
    setError(null);
  }, []);

  const value = useMemo(
    () => ({ messages, status, error, sessionId, send, retry, reset }),
    [messages, status, error, sessionId, send, retry, reset],
  );

  return (
    <ConversationContext.Provider value={value}>
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation() {
  const ctx = useContext(ConversationContext);
  if (!ctx) {
    throw new Error("useConversation must be used within a ConversationProvider");
  }
  return ctx;
}
