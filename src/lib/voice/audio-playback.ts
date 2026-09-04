/**
 * LILITH Voice — browser audio playback layer.
 *
 * Owns the AudioContext, decoding, and AudioBufferSourceNode mechanics. This is
 * the ONLY place an AudioContext/AudioBuffer lives; providers stay portable.
 *
 * Because an AudioBufferSourceNode is one-shot (it cannot be paused/resumed),
 * pause() records the elapsed offset and stops the node, and resume() creates a
 * NEW node started at that offset — continuing the same logical timeline. The
 * authoritative elapsed time is audio-clock derived:
 *
 *   playing: completedOffset + (audioContext.currentTime - currentStartTime)
 *   paused : completedOffset
 *
 * No setTimeout is used for position or completion — natural completion is the
 * node's own `onended`, filtered so manual stop/pause/replace never fire it.
 */

import type { TTSAudio } from "./types";

let sharedContext: AudioContext | null = null;

/** Lazily create/resume the shared AudioContext (must be called from a gesture). */
export async function ensureAudioContext(): Promise<AudioContext> {
  if (!sharedContext) {
    const Ctor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctor) throw new Error("Web Audio API is not available in this browser.");
    sharedContext = new Ctor();
  }
  if (sharedContext.state === "suspended") {
    try {
      await sharedContext.resume();
    } catch {
      /* resume may reject without a gesture; caller surfaces silence */
    }
  }
  return sharedContext;
}

/** Decode a portable TTSAudio payload into an AudioBuffer. */
export async function decodeAudio(
  ctx: AudioContext,
  audio: TTSAudio,
): Promise<AudioBuffer> {
  let bytes: ArrayBuffer;
  if (audio.kind === "bytes") {
    bytes = audio.data;
  } else if (audio.kind === "blob") {
    bytes = await audio.blob.arrayBuffer();
  } else {
    const res = await fetch(audio.url);
    bytes = await res.arrayBuffer();
  }
  // decodeAudioData detaches the buffer; pass a copy so the source stays reusable.
  return ctx.decodeAudioData(bytes.slice(0));
}

/**
 * A single decoded clip's playback session. Create one per speak().
 */
export class WebAudioPlayback {
  private readonly ctx: AudioContext;
  private readonly buffer: AudioBuffer;
  private readonly gain: GainNode;
  private source: AudioBufferSourceNode | null = null;

  private completedOffset = 0; // seconds already played across pause/resume
  private currentStartTime = 0; // ctx.currentTime when the live source started
  private playing = false;
  private disposed = false;
  /** Set when we intentionally stop the node (pause/stop/replace) so its
   *  `onended` is not mistaken for natural completion. */
  private suppressEnded = false;

  private onNaturalEnd: (() => void) | null = null;

  constructor(ctx: AudioContext, buffer: AudioBuffer) {
    this.ctx = ctx;
    this.buffer = buffer;
    this.gain = ctx.createGain();
    this.gain.connect(ctx.destination);
  }

  get durationSec(): number {
    return this.buffer.duration;
  }

  /** Register the natural-completion callback (fires once, only on real end). */
  setOnEnded(cb: () => void): void {
    this.onNaturalEnd = cb;
  }

  elapsedSec(): number {
    if (this.playing) {
      return Math.min(
        this.buffer.duration,
        this.completedOffset + (this.ctx.currentTime - this.currentStartTime),
      );
    }
    return this.completedOffset;
  }

  /** Start (or restart after pause) from the saved offset. */
  play(): void {
    if (this.disposed || this.playing) return;
    const offset = Math.min(this.completedOffset, this.buffer.duration);
    const source = this.ctx.createBufferSource();
    source.buffer = this.buffer;
    source.connect(this.gain);
    source.onended = () => {
      if (this.suppressEnded) {
        // consume the flag; this ended came from a manual stop/pause/replace
        this.suppressEnded = false;
        return;
      }
      // Only the live source's own natural completion counts — ignore any stale
      // or duplicate ended from a source we've already moved past.
      if (this.disposed || this.source !== source) return;
      this.playing = false;
      this.completedOffset = this.buffer.duration;
      this.source = null;
      this.onNaturalEnd?.();
    };
    this.source = source;
    this.currentStartTime = this.ctx.currentTime;
    this.playing = true;
    source.start(0, offset);
  }

  pause(): void {
    if (this.disposed || !this.playing || !this.source) return;
    this.completedOffset = this.elapsedSec();
    this.playing = false;
    this.suppressEnded = true;
    try {
      this.source.stop();
    } catch {
      /* already stopped */
    }
    this.source.disconnect();
    this.source = null;
  }

  resume(): void {
    if (this.disposed || this.playing) return;
    if (this.completedOffset >= this.buffer.duration) return;
    this.play();
  }

  /** Stop immediately and release. Safe to call multiple times. */
  stop(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.playing = false;
    if (this.source) {
      this.suppressEnded = true;
      try {
        this.source.stop();
      } catch {
        /* already stopped */
      }
      this.source.disconnect();
      this.source = null;
    }
    try {
      this.gain.disconnect();
    } catch {
      /* ignore */
    }
    this.onNaturalEnd = null;
  }
}
