/**
 * Headless regression test for the conversation request lifecycle (Stop,
 * stale replies, errors, unmount, repeated submissions) and its accessibility
 * semantics. Fakes only: no browser, no backend. Run by `npm run test:core`.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ConversationTranscript, LiveAnnouncement } from "@/components/conversation/conversation-view";
import { CommandInput } from "@/components/presence/command-input";
import type { ConversationMessage, ConversationReply } from "./types";
import {
  STOP_NOTICE,
  TurnRunner,
  canReuseUserMessage,
  elapsedLabel,
  lastReplyId,
  nextAnnouncement,
  type TurnOutcome,
} from "./turn-runner";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

interface Pending {
  text: string;
  signal: AbortSignal;
  resolve: (r: ConversationReply) => void;
  reject: (e: unknown) => void;
}

/** A fake backend whose replies the test resolves by hand. */
function fakeBackend() {
  const calls: Pending[] = [];
  const send = (text: string, _session: string, signal: AbortSignal) =>
    new Promise<ConversationReply>((resolve, reject) => {
      calls.push({ text, signal, resolve, reject });
    });
  return { calls, send };
}

const reply = (text: string): ConversationReply => ({ reply: text, session: "s" });
const abortError = () => Object.assign(new Error("The operation was aborted."), { name: "AbortError" });
const tick = () => new Promise((r) => setTimeout(r, 0));

function msg(id: string, role: "user" | "lilith", text = id): ConversationMessage {
  return { id, role, text, ts: "2026-11-11T00:00:00.000Z" };
}

export async function runTurnSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `conversation-turn: ${name}`, pass, detail: pass ? undefined : detail });

  /* ------------------------------------------------ lifecycle */
  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const p = r.start("hello", "s", "u1")!;
    const second = r.start("hello again", "s", "u2");
    check("repeated submission while in flight is refused (one request)", second === null && b.calls.length === 1);
    b.calls[0].resolve(reply("hi"));
    const o = await p;
    check("reply settles once and frees the runner",
      o.type === "reply" && o.reply.reply === "hi" && o.userMessageId === "u1" && !r.isBusy(), JSON.stringify(o));
  }

  {
    const b = fakeBackend();
    let t = 1000;
    const r = new TurnRunner(b.send, () => t);
    const p = r.start("slow", "s", "u1")!;
    t += 12_500;
    const stopped = r.stop();
    check("stop returns the unanswered turn and measured elapsed time",
      stopped?.userMessageId === "u1" && stopped.text === "slow" && stopped.elapsedMs === 12_500, JSON.stringify(stopped));
    check("stop aborts the browser request", b.calls[0].signal.aborted);
    check("stop frees the runner immediately", !r.isBusy() && r.current === null);
    b.calls[0].resolve(reply("late"));
    const o = await p;
    check("a reply that arrives after Stop is dropped", o.type === "dropped", JSON.stringify(o));
  }

  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const p = r.start("x", "s", "u1")!;
    r.stop();
    b.calls[0].reject(abortError());
    const o = await p;
    check("the AbortError from Stop is not reported as an error", o.type === "dropped", JSON.stringify(o));
  }

  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const first = r.start("one", "s", "u1")!;
    r.stop();
    const second = r.start("two", "s", "u2")!;
    b.calls[1].resolve(reply("answer two"));
    b.calls[0].resolve(reply("stale answer one"));
    const [o1, o2] = await Promise.all([first, second]);
    check("stale reply from a stopped turn never lands on the next turn",
      o1.type === "dropped" && o2.type === "reply" && o2.reply.reply === "answer two" && o2.userMessageId === "u2",
      JSON.stringify([o1, o2]));
  }

  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const settled: TurnOutcome[] = [];
    const promises: Promise<TurnOutcome>[] = [];
    for (let i = 0; i < 5; i++) {
      promises.push(r.start(`try ${i}`, "s", "u1")!.then((o) => (settled.push(o), o)));
      if (i < 4) r.stop();
    }
    b.calls.forEach((c, i) => c.resolve(reply(`reply ${i}`)));
    await Promise.all(promises);
    const delivered = settled.filter((o) => o.type === "reply");
    check("rapid Stop/Retry x5 delivers exactly one reply (the last)",
      b.calls.length === 5 && delivered.length === 1 && delivered[0].type === "reply" &&
      delivered[0].reply.reply === "reply 4" && b.calls.slice(0, 4).every((c) => c.signal.aborted),
      JSON.stringify(settled));
  }

  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const p = r.start("x", "s", "u1")!;
    b.calls[0].reject(new Error("LILITH is unreachable right now."));
    const o = await p;
    check("network error surfaces its message and frees the runner",
      o.type === "error" && o.message === "LILITH is unreachable right now." && !r.isBusy(), JSON.stringify(o));
    const again = r.start("x", "s", "u1");
    check("after an error a retry can start", again !== null && b.calls.length === 2);
    b.calls[1].resolve(reply("ok"));
    check("retry after error delivers", (await again!).type === "reply");
  }

  {
    const r = new TurnRunner(() => { throw new Error("boom"); });
    const o = await r.start("x", "s", "u1")!;
    check("a synchronous send failure becomes an error outcome", o.type === "error" && !r.isBusy(), JSON.stringify(o));
  }

  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const p = r.start("x", "s", "u1")!;
    r.dispose();
    r.dispose();
    b.calls[0].resolve(reply("after unmount"));
    const o = await p;
    check("unmount aborts and drops the in-flight reply (dispose is idempotent)",
      o.type === "dropped" && b.calls[0].signal.aborted, JSON.stringify(o));
    check("stop while idle is a no-op", r.stop() === null);
  }

  {
    const b = fakeBackend();
    const r = new TurnRunner(b.send);
    const p = r.start("x", "s", "u1")!;
    b.calls[0].resolve(reply("hi"));
    await p;
    await tick();
    check("stop after the reply landed does nothing", r.stop() === null);
  }

  /* ------------------------------------------------ helpers */
  check("elapsed: nothing before 10 s", elapsedLabel(9_999) === null && elapsedLabel(Number.NaN) === null);
  check("elapsed: measured seconds and minutes",
    elapsedLabel(10_000) === "10s" && elapsedLabel(59_900) === "59s" && elapsedLabel(65_000) === "1m 05s");

  const transcript = [msg("u1", "user"), msg("l1", "lilith"), msg("u2", "user")];
  check("retry reuses the unanswered user bubble when it is last",
    canReuseUserMessage(transcript, "u2") && !canReuseUserMessage(transcript, "u1") &&
    !canReuseUserMessage([...transcript, msg("l2", "lilith")], "u2"));

  check("announcement: restored history baseline is never re-announced",
    nextAnnouncement(transcript, lastReplyId(transcript)) === null);
  const withNew = [...transcript, msg("l2", "lilith", "new reply")];
  const ann = nextAnnouncement(withNew, "l1");
  check("announcement: a new reply is announced once",
    ann?.id === "l2" && ann.text === "new reply" && nextAnnouncement(withNew, "l2") === null, JSON.stringify(ann));
  check("announcement: user messages are never announced",
    nextAnnouncement([...withNew, msg("u3", "user")], "l2") === null);

  check("Stop notice is truthful: browser-only, may still finish server-side, claims no cancellation",
    /only stops the request in your browser/.test(STOP_NOTICE) && /may still finish/.test(STOP_NOTICE) &&
    !/\b(cancel(l?ed)?|undone|reverted|rolled back|aborted on the server)\b/i.test(STOP_NOTICE));

  /* ------------------------------------------------ rendered semantics */
  const noop = () => {};
  const render = (props: Partial<Parameters<typeof ConversationTranscript>[0]>) =>
    renderToStaticMarkup(createElement(ConversationTranscript, {
      messages: transcript, sending: false, elapsed: null, error: null, stopped: false, onRetry: noop, ...props,
    }));

  const idle = render({});
  check("transcript is a labelled role=log with its own live region off (no double reads)",
    /role="log"/.test(idle) && /aria-live="off"/.test(idle) && /aria-label="Conversation with LILITH"/.test(idle));
  check("user bubbles carry a screen-reader speaker label", /<span class="sr-only">You: <\/span>/.test(idle));

  const early = render({ sending: true, elapsed: null });
  const late = render({ sending: true, elapsed: "12s" });
  check("pending turn: no elapsed text before 10 s", /LILITH is replying/.test(early) && !/Waiting for a reply/.test(early));
  check("pending turn: measured elapsed after 10 s, hidden from the live region",
    /aria-hidden="true"[^>]*data-conversation-elapsed=""[^>]*>Waiting for a reply · <!-- -->12s/.test(late) ||
    /data-conversation-elapsed=""[\s\S]*?Waiting for a reply · (<!-- -->)?12s/.test(late), late);
  check("pending turn: no invented progress or backend status",
    !/\b(\d+%|tokens?|model|step \d|generating|processing on|queued)\b/i.test(late));

  const stoppedHtml = render({ stopped: true });
  check("after Stop: status notice with the truthful copy and Ask again",
    /role="status"/.test(stoppedHtml) && stoppedHtml.includes(STOP_NOTICE.replace(/'/g, "&#x27;")) &&
    /Ask again/.test(stoppedHtml));
  check("after Stop: history is preserved", (stoppedHtml.match(/class="whitespace-pre-wrap/g) ?? []).length === 3);

  const errorHtml = render({ error: "LILITH took too long to respond." });
  check("error row is an alert with Retry", /role="alert"/.test(errorHtml) && /Retry/.test(errorHtml));
  check("error/stop rows are hidden while a new turn is sending",
    !/role="alert"/.test(render({ error: "x", sending: true })) && !/role="status"/.test(render({ stopped: true, sending: true })));

  const live = renderToStaticMarkup(createElement(LiveAnnouncement, { announcement: { id: "l2", text: "hello" } }));
  const silent = renderToStaticMarkup(createElement(LiveAnnouncement, { announcement: null }));
  check("announcer is a polite atomic live region that reads the reply",
    /aria-live="polite"/.test(live) && /aria-atomic="true"/.test(live) && /LILITH: (<!-- -->)?hello/.test(live) &&
    !/<p/.test(silent));

  const loadingInput = renderToStaticMarkup(createElement(CommandInput, { loading: true, onStop: noop }));
  const loadingNoStop = renderToStaticMarkup(createElement(CommandInput, { loading: true }));
  const idleInput = renderToStaticMarkup(createElement(CommandInput, { loading: false, onStop: noop }));
  const stopTag = loadingInput.match(/<button[^>]*data-command-stop=""[^>]*>/)?.[0] ?? "";
  check("while sending: an enabled, labelled Stop button replaces Send",
    !!stopTag && !/\sdisabled=""/.test(stopTag) && /aria-label="Stop waiting for reply"/.test(stopTag) &&
    !/aria-label="Send"/.test(loadingInput), stopTag);
  check("no Stop button when idle or when no stop handler is wired",
    !/data-command-stop/.test(idleInput) && !/data-command-stop/.test(loadingNoStop) && /aria-label="Send"/.test(idleInput));

  return out;
}
