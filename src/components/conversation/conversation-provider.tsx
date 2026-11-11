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
import { TurnRunner, canReuseUserMessage, type TurnOutcome } from "@/lib/conversation/turn-runner";
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
  /** true once persisted history has been restored (client only). */
  hydrated: boolean;
  /** Epoch ms the in-flight turn started, or null when idle. */
  pendingSince: number | null;
  /** Set after Stop: the unanswered turn the owner may ask again. */
  stopped: { userMessageId: string } | null;
  /** Send a message. No-op while a send is already in flight. */
  send: (text: string) => void;
  /** Stop waiting for the in-flight reply (browser-side abort only). */
  stop: () => void;
  /** Re-send the last failed or stopped turn, reusing its user message. */
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

  const [pendingSince, setPendingSince] = useState<number | null>(null);
  const [stopped, setStopped] = useState<{ userMessageId: string } | null>(null);

  // One turn at a time, with abort + stale-reply protection (see TurnRunner).
  const runner = useRef<TurnRunner | null>(null);
  if (runner.current === null) {
    runner.current = new TurnRunner((text, session, signal) => sendConversation(text, session, signal));
  }
  // The last failed or stopped turn, kept for retry.
  const lastAttempt = useRef<{ text: string; userMessageId: string } | null>(null);
  // Mirror of the transcript for synchronous checks inside callbacks.
  const messagesRef = useRef<ConversationMessage[]>([]);
  messagesRef.current = messages;

  // Unmount: abort the browser request and drop any late reply.
  useEffect(() => () => runner.current?.dispose(), []);

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

  const handleOutcome = useCallback((outcome: TurnOutcome) => {
    if (outcome.type === "dropped") return; // stopped, superseded or unmounted
    setPendingSince(null);
    setStatus("idle");
    if (outcome.type === "reply") {
      const reply = outcome.reply.reply.trim() || "…";
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "lilith", text: reply, ts: new Date().toISOString() },
      ]);
      lastAttempt.current = null;
    } else {
      setError(outcome.message);
    }
  }, []);

  /** Start a turn; reuses `userMessageId` when retrying an unanswered bubble. */
  const runTurn = useCallback(
    (text: string, reuseUserMessageId?: string) => {
      const r = runner.current!;
      if (r.isBusy()) return;
      const userMessageId = reuseUserMessageId ?? newId();
      const pending = r.start(text, activeSession, userMessageId);
      if (!pending) return;
      lastAttempt.current = { text, userMessageId };
      setError(null);
      setStopped(null);
      setStatus("sending");
      setPendingSince(r.current?.startedAt ?? Date.now());
      if (!reuseUserMessageId) {
        setMessages((prev) => [
          ...prev,
          { id: userMessageId, role: "user", text, ts: new Date().toISOString() },
        ]);
      }
      void pending.then(handleOutcome);
    },
    [activeSession, handleOutcome],
  );

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      runTurn(trimmed);
    },
    [runTurn],
  );

  const stop = useCallback(() => {
    const result = runner.current?.stop();
    if (!result) return;
    lastAttempt.current = { text: result.text, userMessageId: result.userMessageId };
    setPendingSince(null);
    setStatus("idle");
    setError(null);
    setStopped({ userMessageId: result.userMessageId });
  }, []);

  const retry = useCallback(() => {
    const attempt = lastAttempt.current;
    if (!attempt || runner.current?.isBusy()) return;
    // Reuse the unanswered bubble if it is still the last message; otherwise
    // the transcript moved on and the retry is a fresh turn.
    const reuse = canReuseUserMessage(messagesRef.current, attempt.userMessageId);
    runTurn(attempt.text, reuse ? attempt.userMessageId : undefined);
  }, [runTurn]);

  const reset = useCallback(() => {
    if (runner.current?.isBusy() || isRecordingActive(recording)) return; // finish the recording first
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
    setStopped(null);
    lastAttempt.current = null;
  }, [recording]);

  const startRecording = useCallback(() => {
    if (recordingBusy.current || runner.current?.isBusy()) return;
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
        setStopped(null);
        lastAttempt.current = null;
      })
      .finally(() => {
        recordingBusy.current = false;
      });
  }, [recording.phase]);

  const finishRecording = useCallback(() => {
    const session = recording.session;
    if (recordingBusy.current || runner.current?.isBusy() || recording.phase !== "recording" || !session) return;
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
    () => ({ messages, status, error, sessionId, hydrated, pendingSince, stopped, send, stop, retry, reset,
             recording, startRecording, finishRecording, dismissRecording }),
    [messages, status, error, sessionId, hydrated, pendingSince, stopped, send, stop, retry, reset,
     recording, startRecording, finishRecording, dismissRecording],
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
