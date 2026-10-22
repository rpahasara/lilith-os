"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { sendConversation } from "@/lib/conversation/client";
import {
  INITIAL_RECORDING,
  fetchRecordingAvailability,
  finishRecording as requestFinish,
  isRecordingActive,
  recordingReducer,
  startRecording as requestStart,
  type RecordingState,
} from "@/lib/conversation/recording";
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
// UI hint only (resume after a refresh); the server re-checks the session on every action.
const RECORDING_KEY = "lilith-os:recording-session";
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
  /** Owner-protected First Interaction recording (hidden unless the server reports it available). */
  recording: RecordingState;
  startRecording: () => void;
  finishRecording: () => void;
  dismissRecording: () => void;
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
  const [recording, dispatchRecording] = useReducer(recordingReducer, INITIAL_RECORDING);
  // Guards duplicate Start/Finish clicks while a recording request is pending.
  const recordingBusy = useRef(false);

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

  // Recording availability comes from the server (owner session), never from local state.
  useEffect(() => {
    let cancelled = false;
    void fetchRecordingAvailability(fetch).then(({ available, reason }) => {
      if (cancelled) return;
      dispatchRecording({ type: "AVAILABILITY", available, reason });
      try {
        const stored = window.localStorage.getItem(RECORDING_KEY);
        if (!available) window.localStorage.removeItem(RECORDING_KEY);
        else if (stored) dispatchRecording({ type: "RESTORE", session: stored });
      } catch {
        /* storage unavailable */
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // While recording, every turn goes to the server-minted capture session.
  const activeSession = isRecordingActive(recording) && recording.session ? recording.session : sessionId;

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
        const res = await sendConversation(text, activeSession);
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
    [activeSession],
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
    if (inFlight.current || isRecordingActive(recording)) return; // finish the recording first
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
  }, [recording]);

  const startRecording = useCallback(() => {
    if (recordingBusy.current || inFlight.current) return;
    if (!["idle", "finished", "interrupted"].includes(recording.phase)) return;
    recordingBusy.current = true;
    dispatchRecording({ type: "START_REQUESTED" });
    void requestStart(fetch)
      .then((result) => {
        if (!result.ok || !result.value) {
          dispatchRecording({ type: "START_FAILED", error: result.error ?? "The recording request failed." });
          return;
        }
        dispatchRecording({ type: "STARTED", session: result.value });
        try {
          window.localStorage.setItem(RECORDING_KEY, result.value);
        } catch {
          /* ignore */
        }
        setMessages([]); // a recording is its own conversation
        setError(null);
      })
      .finally(() => {
        recordingBusy.current = false;
      });
  }, [recording.phase]);

  const finishRecording = useCallback(() => {
    const session = recording.session;
    if (recordingBusy.current || inFlight.current || recording.phase !== "recording" || !session) return;
    recordingBusy.current = true;
    dispatchRecording({ type: "FINISH_REQUESTED" });
    void requestFinish(fetch, session)
      .then((result) => {
        if (result.ok && result.value) {
          dispatchRecording({ type: "FINISHED", evidence: result.value });
        } else {
          dispatchRecording({ type: "FINISH_FAILED", code: result.code ?? "UNKNOWN",
                              error: result.error ?? "The recording request failed." });
          if (result.code === "NETWORK") return; // still recording on the server; the owner may retry
        }
        try {
          window.localStorage.removeItem(RECORDING_KEY);
        } catch {
          /* ignore */
        }
        // Ordinary chat resumes in a fresh session, never the capture session.
        const sid = makeSessionId();
        try {
          window.localStorage.setItem(SESSION_KEY, sid);
        } catch {
          /* ignore */
        }
        setSessionId(sid);
      })
      .finally(() => {
        recordingBusy.current = false;
      });
  }, [recording.phase, recording.session]);

  const dismissRecording = useCallback(() => dispatchRecording({ type: "DISMISS" }), []);

  const value = useMemo(
    () => ({ messages, status, error, sessionId, send, retry, reset, recording, startRecording, finishRecording,
             dismissRecording }),
    [messages, status, error, sessionId, send, retry, reset, recording, startRecording, finishRecording,
     dismissRecording],
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
