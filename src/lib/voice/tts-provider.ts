/**
 * LILITH Voice — TTS providers.
 *
 * The public contract (TTSProvider) is portable and AudioContext-free. The mock
 * provider below is a dev-only stand-in that synthesizes a short, gentle test
 * tone as encoded WAV BYTES (pure math — no AudioContext) plus a deterministic
 * viseme timeline spanning the clip. It exists only to validate the pipeline
 * plumbing (audible playback, audio clock, viseme sync, lifecycle) — NOT lip-sync
 * realism, since a tone is not speech. No external/paid provider is included.
 */

import type { TTSProvider, TTSRequest, TTSResult, VisemeCue } from "./types";

export type { TTSProvider } from "./types";

const MOCK_SAMPLE_RATE = 22050;
const MOCK_CUE_MS = 150; // one viseme step per 150ms
const MOCK_VISEME_CYCLE: VisemeCue["viseme"][] = ["aa", "ih", "ou", "ee", "oh"];

/** Encode mono float samples [-1,1] as a 16-bit PCM WAV ArrayBuffer. */
function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const numSamples = samples.length;
  const dataBytes = numSamples * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  const writeStr = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  view.setUint32(40, dataBytes, true);
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, clamped * 0x7fff, true);
    offset += 2;
  }
  return buffer;
}

/** Deterministic viseme cues covering [0, durationMs). */
function buildMockCues(durationMs: number): VisemeCue[] {
  const cues: VisemeCue[] = [];
  let t = 0;
  let i = 0;
  while (t < durationMs - MOCK_CUE_MS) {
    cues.push({
      viseme: MOCK_VISEME_CYCLE[i % MOCK_VISEME_CYCLE.length],
      startMs: t,
      durationMs: MOCK_CUE_MS,
      weight: 1,
    });
    t += MOCK_CUE_MS;
    i += 1;
  }
  // Close the mouth at the end.
  cues.push({ viseme: "sil", startMs: t, durationMs: MOCK_CUE_MS, weight: 1 });
  return cues;
}

export interface MockTTSOptions {
  /** Clip length in seconds (default 1.8s, or scaled by text length). */
  durationSec?: number;
  /** Base tone frequency in Hz (default 180 — a soft, low, non-harsh tone). */
  frequency?: number;
}

/**
 * MOCK-ONLY provider. Not for production. Generates a portable WAV byte payload.
 */
export class MockTTSProvider implements TTSProvider {
  readonly name = "mock";
  private readonly opts: MockTTSOptions;

  constructor(opts: MockTTSOptions = {}) {
    this.opts = opts;
  }

  async synthesize(req: TTSRequest): Promise<TTSResult> {
    // Duration: explicit, else a gentle function of text length (0.9s–4s).
    const durationSec =
      this.opts.durationSec ??
      Math.max(0.9, Math.min(4, 0.6 + req.text.trim().length * 0.05));
    const freq = this.opts.frequency ?? 180;
    const sr = MOCK_SAMPLE_RATE;
    const n = Math.floor(durationSec * sr);
    const samples = new Float32Array(n);
    // Soft tone with a slow tremolo + short fade in/out so it is clearly audible
    // but never harsh. Amplitude kept modest (0.25).
    const fade = Math.floor(sr * 0.03);
    for (let i = 0; i < n; i++) {
      const tSec = i / sr;
      const tremolo = 0.85 + 0.15 * Math.sin(2 * Math.PI * 4 * tSec);
      let amp = 0.25 * tremolo;
      if (i < fade) amp *= i / fade;
      else if (i > n - fade) amp *= (n - i) / fade;
      samples[i] = amp * Math.sin(2 * Math.PI * freq * tSec);
    }
    const data = encodeWav(samples, sr);
    return {
      audio: { kind: "bytes", data, mimeType: "audio/wav" },
      durationSec,
      cues: buildMockCues(durationSec * 1000),
      meta: { provider: this.name, voice: req.voice },
    };
  }
}
