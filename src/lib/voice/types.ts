/**
 * LILITH Voice — provider-independent type boundary.
 *
 * Nothing here touches three.js, an AudioContext, or a specific TTS vendor. A
 * TTSProvider returns portable, AudioContext-free audio (encoded bytes, a Blob,
 * or a URL); the browser playback layer (audio-playback.ts) owns decoding and
 * the AudioBuffer. Hsin depends only on these types + the speech controller,
 * never on a concrete provider.
 */

import type { VisemeCue } from "@/lib/hsin-lip-sync";

export type { VisemeCue };

/** Portable audio payload — decodable without a provider-owned AudioContext. */
export type TTSAudio =
  | { kind: "bytes"; data: ArrayBuffer; mimeType: string }
  | { kind: "blob"; blob: Blob }
  | { kind: "url"; url: string };

/** Optional coarse alignment a provider may return (for cue derivation). */
export interface WordTiming {
  word: string;
  startMs: number;
  endMs: number;
}

export interface PhonemeTiming {
  phoneme: string;
  startMs: number;
  endMs: number;
}

export interface TTSRequest {
  text: string;
  voice?: string;
  /** Abort in-flight synthesis (provider should honor it when it can). */
  signal?: AbortSignal;
}

export interface TTSResult {
  audio: TTSAudio;
  /** Known duration in seconds, if the provider reports it (else derived on decode). */
  durationSec?: number;
  /** (A) Provider-supplied viseme timeline — preferred when present. */
  cues?: VisemeCue[];
  /** (B) Word timings — used to approximate cues when no cues are given. */
  words?: WordTiming[];
  /** (C) Phoneme timings — reserved for future local alignment. */
  phonemes?: PhonemeTiming[];
  meta?: { provider: string; voice?: string };
}

/** The portable synthesis contract. Implementations must not require an AudioContext. */
export interface TTSProvider {
  readonly name: string;
  synthesize(req: TTSRequest): Promise<TTSResult>;
}

/** High-level speech controller status (for dev readout). */
export type SpeechStatus = "idle" | "loading" | "playing" | "paused";

export interface SpeechControllerSnapshot {
  status: SpeechStatus;
  provider: string | null;
  durationSec: number;
  /** Monotonic id; increments on every speak()/stop() for stale-guarding. */
  requestId: number;
}
