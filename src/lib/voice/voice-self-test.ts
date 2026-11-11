/**
 * Headless regression test for the owner-facing voice toggle and the voice
 * path it drives. Fakes only: no browser audio, no TTS provider, no network.
 * Run by `npm run test:core`.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { VoiceToggleButton, VOICE_PROBLEM_TEXT, voiceProblem } from "@/components/conversation/voice-toggle";
import { hsinLipSync } from "@/lib/hsin-lip-sync";
import { ElevenLabsTTSProvider } from "./elevenlabs-tts-provider";
import { decideReplyVoicing, MAX_SPOKEN_CHARS } from "./reply-voicing";
import { LilithSpeechController } from "./speech-controller";
import type { TTSProvider, TTSRequest, TTSResult } from "./types";
import { VOICE_STORAGE_KEY, VoiceSettingsStore, type VoiceStorage } from "./voice-settings";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

function memoryStorage(initial: Record<string, string> = {}): VoiceStorage & { data: Record<string, string> } {
  const data = { ...initial };
  return { data, getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => void (data[k] = v) };
}

const throwingStorage: VoiceStorage = {
  getItem: () => { throw new Error("blocked"); },
  setItem: () => { throw new Error("blocked"); },
};

/** A provider whose synthesis the test resolves or rejects by hand. */
function manualProvider() {
  const calls: { req: TTSRequest; resolve: (r: TTSResult) => void; reject: (e: unknown) => void }[] = [];
  const provider: TTSProvider = {
    name: "fake",
    synthesize: (req) => new Promise<TTSResult>((resolve, reject) => calls.push({ req, resolve, reject })),
  };
  return { provider, calls };
}

const audioResult = (): TTSResult => ({ audio: { kind: "bytes", data: new ArrayBuffer(8), mimeType: "audio/mpeg" } });

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? sourceFiles(p) : /\.(ts|tsx)$/.test(name) ? [p] : [];
  });
}

export async function runVoiceSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `voice: ${name}`, pass, detail: pass ? undefined : detail });

  /* ------------------------------------------------ settings store */
  {
    const s = new VoiceSettingsStore();
    check("voice is OFF by default (client and server)", !s.getSnapshot().autoSpeak && !s.getServerSnapshot().autoSpeak);
  }
  for (const [stored, expected] of [["on", true], ["off", false], ["true", false], ["1", false], ["", false]] as const) {
    const s = new VoiceSettingsStore();
    s.hydrate(memoryStorage({ [VOICE_STORAGE_KEY]: stored }));
    check(`remembered value "${stored}" restores ${expected ? "ON" : "OFF"}`, s.getSnapshot().autoSpeak === expected);
  }
  {
    const s = new VoiceSettingsStore();
    s.hydrate(null);
    const t = new VoiceSettingsStore();
    t.hydrate(throwingStorage);
    check("no or unreadable storage stays OFF without throwing", !s.getSnapshot().autoSpeak && !t.getSnapshot().autoSpeak);
  }
  {
    const s = new VoiceSettingsStore();
    const store = memoryStorage();
    s.hydrate(store);
    let notified = 0;
    s.subscribe(() => notified++);
    s.setAutoSpeak(true);
    s.setAutoSpeak(true);
    const persistedOn = store.data[VOICE_STORAGE_KEY];
    s.setAutoSpeak(false);
    check("explicit owner choice persists and notifies only on change",
      persistedOn === "on" && store.data[VOICE_STORAGE_KEY] === "off" && notified === 2, `${persistedOn} ${notified}`);
    s.setAutoSpeak(true);
    s.hydrate(memoryStorage({ [VOICE_STORAGE_KEY]: "off" }));
    check("hydrate runs once: a remount cannot override this session's choice", s.getSnapshot().autoSpeak);
  }
  {
    const s = new VoiceSettingsStore();
    s.hydrate(throwingStorage);
    s.setAutoSpeak(true);
    check("blocked storage: the choice still applies for the page", s.getSnapshot().autoSpeak);
  }

  /* ------------------------------------------------ which replies are voiced */
  const base = { replyId: "r2", handledReplyId: "r1", awaitingReply: true, autoSpeak: true, text: "Hello!" };
  check("new reply to this page's turn with voice ON is spoken", decideReplyVoicing(base) === "speak");
  check("voice OFF plays only the canned beat (no TTS call)", decideReplyVoicing({ ...base, autoSpeak: false }) === "transient");
  check("restored or re-shown history is never spoken or re-animated",
    decideReplyVoicing({ ...base, awaitingReply: false }) === "skip" &&
    decideReplyVoicing({ ...base, awaitingReply: false, autoSpeak: false }) === "skip");
  check("an already handled reply is never spoken twice", decideReplyVoicing({ ...base, handledReplyId: "r2" }) === "skip");
  check("empty, placeholder or over-long replies are not sent to TTS",
    decideReplyVoicing({ ...base, text: "  " }) === "transient" &&
    decideReplyVoicing({ ...base, text: "…" }) === "transient" &&
    decideReplyVoicing({ ...base, text: "x".repeat(MAX_SPOKEN_CHARS + 1) }) === "transient");

  /* ------------------------------------------------ speech controller */
  {
    const c = new LilithSpeechController();
    const failing: TTSProvider = { name: "fake", synthesize: async () => { throw new Error("ELEVENLABS_API_KEY is not configured"); } };
    const ok = await c.speak({ text: "hi" }, failing);
    const snap = c.getSnapshot();
    check("TTS unavailable: speak reports failure, stays idle, mouth closed",
      !ok && snap.status === "idle" && snap.lastResult === "unavailable" && hsinLipSync.getSnapshot().status === "idle",
      JSON.stringify(snap));
  }
  {
    const c = new LilithSpeechController();
    const m = manualProvider();
    const pending = c.speak({ text: "hello" }, m.provider);
    const signal = m.calls[0].req.signal;
    c.stop();
    m.calls[0].resolve(audioResult());
    const ok = await pending;
    check("stop during synthesis aborts the TTS request and discards its audio",
      !!signal && signal.aborted && !ok && c.getSnapshot().status === "idle" && c.getSnapshot().lastResult === null,
      JSON.stringify(c.getSnapshot()));
    check("only the reply text is handed to the provider", JSON.stringify(Object.keys(m.calls[0].req).sort()) === '["signal","text"]' &&
      m.calls[0].req.text === "hello");
  }
  {
    const c = new LilithSpeechController();
    const m = manualProvider();
    const first = c.speak({ text: "one" }, m.provider);
    const second = c.speak({ text: "two" }, m.provider);
    check("a newer reply supersedes and aborts the older synthesis", !!m.calls[0].req.signal?.aborted && !m.calls[1].req.signal?.aborted);
    c.stop();
    m.calls.forEach((x) => x.resolve(audioResult()));
    check("superseded speech never plays", !(await first) && !(await second));
  }
  {
    hsinLipSync.startSpeech([{ viseme: "aa", startMs: 0, durationMs: 400 }, { viseme: "oh", startMs: 400, durationMs: 400 }]);
    const wasPlaying = hsinLipSync.getSnapshot().status === "playing";
    new LilithSpeechController().stop();
    check("switching voice OFF (controller stop) clears Hsin's visemes",
      wasPlaying && hsinLipSync.getSnapshot().status === "idle" && hsinLipSync.getSnapshot().cues.length === 0);
  }
  {
    // Browser autoplay policy: the AudioContext stays suspended.
    const g = globalThis as unknown as { window?: unknown };
    const hadWindow = "window" in g;
    const prevWindow = g.window;
    class SuspendedContext {
      state = "suspended";
      async resume() {}
      async decodeAudioData() { return { duration: 1 } as unknown as AudioBuffer; }
    }
    g.window = { AudioContext: SuspendedContext };
    try {
      const c = new LilithSpeechController();
      const ok = await c.speak({ text: "hi" }, { name: "fake", synthesize: async () => audioResult() });
      check("audio locked by the browser: no silent mouth animation, reported as blocked",
        !ok && c.getSnapshot().status === "idle" && c.getSnapshot().lastResult === "blocked" &&
        hsinLipSync.getSnapshot().status === "idle", JSON.stringify(c.getSnapshot()));
    } finally {
      if (hadWindow) g.window = prevWindow;
      else delete g.window;
    }
  }

  /* ------------------------------------------------ provider privacy */
  {
    const g = globalThis as unknown as { fetch: typeof fetch };
    const realFetch = g.fetch;
    const seen: { url: string; body: string; hasSignal: boolean }[] = [];
    g.fetch = (async (url: string, init?: RequestInit) => {
      seen.push({ url: String(url), body: String(init?.body), hasSignal: !!init?.signal });
      return new Response(new Uint8Array([1, 2, 3]), { status: 200, headers: { "content-type": "audio/mpeg" } });
    }) as typeof fetch;
    try {
      const ac = new AbortController();
      await new ElevenLabsTTSProvider().synthesize({ text: "Only this reply.", signal: ac.signal });
      check("ElevenLabs path: same-origin route, body is only the reply text, abortable",
        seen.length === 1 && seen[0].url === "/api/voice/elevenlabs" &&
        seen[0].body === JSON.stringify({ text: "Only this reply." }) && seen[0].hasSignal, JSON.stringify(seen));
      g.fetch = (async () => new Response(JSON.stringify({ error: "ELEVENLABS_API_KEY is not configured" }), { status: 503 })) as typeof fetch;
      let threw = false;
      try { await new ElevenLabsTTSProvider().synthesize({ text: "x" }); } catch { threw = true; }
      check("unconfigured TTS (503) surfaces as a provider failure", threw);
    } finally {
      g.fetch = realFetch;
    }
  }

  /* ------------------------------------------------ toggle UI */
  check("failure notice only for attempts after the owner turned voice on",
    voiceProblem({ lastResult: "unavailable", requestId: 5 }, 5) === null &&
    voiceProblem({ lastResult: "unavailable", requestId: 6 }, 5) === "unavailable" &&
    voiceProblem({ lastResult: "ok", requestId: 6 }, 5) === null);

  const noop = () => {};
  const offHtml = renderToStaticMarkup(createElement(VoiceToggleButton, { on: false, problem: null, speaking: false, onToggle: noop }));
  const onHtml = renderToStaticMarkup(createElement(VoiceToggleButton, { on: true, problem: null, speaking: true, onToggle: noop }));
  const problemHtml = renderToStaticMarkup(createElement(VoiceToggleButton, { on: true, problem: "unavailable", speaking: false, onToggle: noop }));
  const offTag = offHtml.match(/<button[^>]*>/)?.[0] ?? "";
  check("toggle is a labelled, keyboard-operable switch that reports OFF",
    /type="button"/.test(offTag) && /role="switch"/.test(offTag) && /aria-checked="false"/.test(offTag) &&
    /aria-label="Speak replies aloud"/.test(offTag) && !/disabled/.test(offTag) && /Voice (<!-- -->)?off</.test(offHtml), offTag);
  check("toggle reports ON when on", /aria-checked="true"/.test(onHtml) && /Voice (<!-- -->)?on</.test(onHtml));
  check("unavailable TTS is shown as a status, replies stay text",
    /role="status"/.test(problemHtml) && problemHtml.includes(VOICE_PROBLEM_TEXT.unavailable.replace(/'/g, "&#x27;")));

  /* ------------------------------------------------ one voice state */
  const root = join(process.cwd(), "src");
  const offenders = sourceFiles(root).filter((p) => {
    const src = readFileSync(p, "utf8");
    return /\[\s*autoSpeak\s*,\s*setAutoSpeak\s*\]\s*=\s*useState/.test(src) ||
      (/class\s+\w*VoiceSettings\w*/.test(src) && !p.endsWith(join("voice", "voice-settings.ts")));
  });
  check("there is exactly one voice settings store", offenders.length === 0, offenders.join(", "));

  return out;
}
