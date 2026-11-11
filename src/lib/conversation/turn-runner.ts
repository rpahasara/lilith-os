/**
 * Browser-side lifecycle of one conversation turn: send, stop, stale replies.
 *
 * One turn is in flight at a time. Each turn gets its own AbortController and
 * a generation number. A turn settles exactly once, and only while it is still
 * the current generation. Once it is stopped, superseded or disposed (on
 * unmount), its late reply or error is dropped and never reaches the transcript.
 *
 * Stopping is a BROWSER-side action only: it aborts this page's HTTP request.
 * It does not cancel anything on the backend. The LILITH turn may still finish
 * server-side, and no approval-gated action is affected (those run through the
 * Command Core, not this path). UI copy must say so (see STOP_NOTICE).
 */
import type { ConversationMessage, ConversationReply } from "./types";

export type SendFn = (
  text: string,
  session: string,
  signal: AbortSignal,
) => Promise<ConversationReply>;

export type TurnOutcome =
  | { type: "reply"; turnId: number; userMessageId: string; reply: ConversationReply }
  | { type: "error"; turnId: number; userMessageId: string; message: string }
  /** Stopped, superseded or disposed: the result was dropped. */
  | { type: "dropped"; turnId: number; userMessageId: string };

export interface ActiveTurn {
  turnId: number;
  userMessageId: string;
  text: string;
  startedAt: number;
}

export interface StopResult {
  userMessageId: string;
  text: string;
  elapsedMs: number;
}

/** Shown after Stop. It never claims the backend turn was cancelled. */
export const STOP_NOTICE =
  "Stopped waiting. This only stops the request in your browser: LILITH may still finish this turn on the server, and that reply won't be shown here.";

/** Elapsed feedback starts after this long. Before that the usual dots suffice. */
export const ELAPSED_AFTER_MS = 10_000;

export class TurnRunner {
  private generation = 0;
  private controller: AbortController | null = null;
  private active: ActiveTurn | null = null;

  constructor(
    private readonly send: SendFn,
    private readonly clock: () => number = () => Date.now(),
  ) {}

  get current(): ActiveTurn | null {
    return this.active;
  }

  isBusy(): boolean {
    return this.active !== null;
  }

  /**
   * Start a turn. Returns null (and sends nothing) while another turn is in
   * flight. Otherwise resolves with exactly one outcome for this turn.
   */
  start(text: string, session: string, userMessageId: string): Promise<TurnOutcome> | null {
    if (this.active) return null;
    const turnId = ++this.generation;
    const controller = new AbortController();
    this.controller = controller;
    this.active = { turnId, userMessageId, text, startedAt: this.clock() };

    const settle = (outcome: TurnOutcome): TurnOutcome => {
      if (turnId !== this.generation) return { type: "dropped", turnId, userMessageId };
      this.active = null;
      this.controller = null;
      return outcome;
    };

    let pending: Promise<ConversationReply>;
    try {
      pending = this.send(text, session, controller.signal);
    } catch (e) {
      pending = Promise.reject(e);
    }
    return pending.then(
      (reply) => settle({ type: "reply", turnId, userMessageId, reply }),
      (e: unknown) =>
        settle({
          type: "error",
          turnId,
          userMessageId,
          message: e instanceof Error && e.message ? e.message : "Something went wrong.",
        }),
    );
  }

  /** Stop waiting for the current turn (browser-side abort). */
  stop(): StopResult | null {
    const turn = this.active;
    if (!turn) return null;
    this.invalidate();
    return {
      userMessageId: turn.userMessageId,
      text: turn.text,
      elapsedMs: Math.max(0, this.clock() - turn.startedAt),
    };
  }

  /** Unmount: abort and drop whatever is in flight. Safe to call repeatedly. */
  dispose(): void {
    this.invalidate();
  }

  private invalidate() {
    this.generation++;
    this.controller?.abort();
    this.controller = null;
    this.active = null;
  }
}

/** "12s", "1m 05s", or null before ELAPSED_AFTER_MS. Measured time only. */
export function elapsedLabel(ms: number): string | null {
  if (!(ms >= ELAPSED_AFTER_MS)) return null;
  const total = Math.floor(ms / 1000);
  if (total < 60) return `${total}s`;
  const m = Math.floor(total / 60);
  return `${m}m ${String(total % 60).padStart(2, "0")}s`;
}

/**
 * Retry or "ask again" reuses the unanswered user bubble when it is still the
 * last message, so a retry never duplicates the user's turn.
 */
export function canReuseUserMessage(messages: ConversationMessage[], userMessageId: string): boolean {
  const last = messages[messages.length - 1];
  return !!last && last.role === "user" && last.id === userMessageId;
}

/** The id of the newest LILITH reply, or null. */
export function lastReplyId(messages: ConversationMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "lilith") return messages[i].id;
  }
  return null;
}

/**
 * What the live region should announce: the newest LILITH reply, once. Returns
 * null when there is none or it was already announced (or was the baseline at
 * hydration, so restored history is never read out).
 */
export function nextAnnouncement(
  messages: ConversationMessage[],
  lastAnnouncedId: string | null,
): { id: string; text: string } | null {
  const id = lastReplyId(messages);
  if (!id || id === lastAnnouncedId) return null;
  const msg = messages.find((m) => m.id === id)!;
  return { id, text: msg.text };
}
