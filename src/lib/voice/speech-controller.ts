/**
 * LILITH Voice — speech playback controller (`lilithSpeech`).
 *
 * The single higher-level owner that synchronizes AUDIO PLAYBACK with the
 * existing hsinLipSync viseme stack. Audio is the sole completion authority:
 * hsinLipSync is driven in external-clock mode (no internal end timer), and the
 * audio layer's natural `onended` is what stops it. Viseme sampling reads
 * `elapsedMs()` (audio-clock derived) — see avatar-scene's sampler.
 *
 * Lifecycle: speak() → synthesize → decode → start audio + hsinLipSync
 * (externalClock) → progress on the audio clock → natural end → stopSpeech()
 * (mouth closes) → Speaking Motion ramps out via the existing isSpeaking gate.
 *
 * Every async step is guarded by a monotonic requestId so a stale synthesize
 * resolve, or a superseded clip's teardown, can never affect newer playback or
 * leave the mouth stuck open.
 */

import { hsinLipSync } from "@/lib/hsin-lip-sync";
import {
  decodeAudio,
  ensureAudioContext,
  WebAudioPlayback,
} from "./audio-playback";
import { MockTTSProvider } from "./tts-provider";
import type {
  SpeechControllerSnapshot,
  SpeechStatus,
  TTSProvider,
  TTSRequest,
  VisemeCue,
} from "./types";

function resolveCues(cues: VisemeCue[] | undefined): VisemeCue[] {
  // (A) provider cues preferred. (B) word-derived and (C) phoneme alignment are
  // future seams; for now, absent cues => empty (audio still plays, mouth stays
  // closed) rather than a bad guess.
  return cues && cues.length > 0 ? cues : [];
}

class LilithSpeechController {
  private provider: TTSProvider = new MockTTSProvider();
  private playback: WebAudioPlayback | null = null;

  private requestId = 0;
  private status: SpeechStatus = "idle";
  private providerName: string | null = null;
  private durationSec = 0;

  private listeners = new Set<() => void>();
  private snapshot: SpeechControllerSnapshot = {
    status: "idle",
    provider: null,
    durationSec: 0,
    requestId: 0,
  };

  /** Swap the active provider (dev/config). */
  setProvider(provider: TTSProvider): void {
    this.provider = provider;
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  getSnapshot = (): SpeechControllerSnapshot => this.snapshot;
  getServerSnapshot = (): SpeechControllerSnapshot => this.snapshot;

  /** Audio-authoritative elapsed time (ms). Drives external-clock viseme sampling. */
  elapsedMs(): number {
    return this.playback ? this.playback.elapsedSec() * 1000 : 0;
  }

  isActive(): boolean {
    return this.status === "playing" || this.status === "paused";
  }

  /**
   * Speak the given text. Cleanly replaces any current speech. Returns when
   * playback has started (or been superseded/failed).
   */
  async speak(req: TTSRequest): Promise<void> {
    // New request owns everything from here; invalidates prior async work.
    const myId = ++this.requestId;
    this.teardownPlayback();
    hsinLipSync.stopSpeech();
    this.setState("loading", this.provider.name, 0);

    let result;
    try {
      result = await this.provider.synthesize(req);
    } catch {
      if (myId === this.requestId) this.hardReset();
      return;
    }
    if (myId !== this.requestId) return; // superseded during synthesis

    let ctx: AudioContext;
    let buffer: AudioBuffer;
    try {
      ctx = await ensureAudioContext();
      buffer = await decodeAudio(ctx, result.audio);
    } catch {
      if (myId === this.requestId) this.hardReset();
      return;
    }
    if (myId !== this.requestId) return; // superseded during decode

    const playback = new WebAudioPlayback(ctx, buffer);
    playback.setOnEnded(() => {
      if (myId !== this.requestId) return; // stale natural-end, ignore
      this.handleNaturalEnd();
    });
    this.playback = playback;
    this.durationSec = result.durationSec ?? playback.durationSec;

    // Start audio and visemes together; audio is the completion authority.
    hsinLipSync.startSpeech(resolveCues(result.cues), { externalClock: true });
    playback.play();
    this.setState("playing", result.meta?.provider ?? this.provider.name, this.durationSec);
  }

  stop(): void {
    // Invalidate any in-flight/stale callbacks, then tear down.
    this.requestId++;
    this.hardReset();
  }

  pause(): void {
    if (this.status !== "playing" || !this.playback) return;
    this.playback.pause();
    hsinLipSync.pauseSpeech();
    this.setState("paused", this.providerName, this.durationSec);
  }

  resume(): void {
    if (this.status !== "paused" || !this.playback) return;
    this.playback.resume();
    hsinLipSync.resumeSpeech();
    this.setState("playing", this.providerName, this.durationSec);
  }

  private handleNaturalEnd(): void {
    this.teardownPlayback();
    hsinLipSync.stopSpeech();
    this.setState("idle", null, 0);
  }

  private hardReset(): void {
    this.teardownPlayback();
    hsinLipSync.stopSpeech();
    this.setState("idle", null, 0);
  }

  private teardownPlayback(): void {
    if (this.playback) {
      this.playback.stop();
      this.playback = null;
    }
  }

  private setState(
    status: SpeechStatus,
    provider: string | null,
    durationSec: number,
  ): void {
    this.status = status;
    this.providerName = provider;
    this.durationSec = durationSec;
    this.snapshot = {
      status,
      provider,
      durationSec,
      requestId: this.requestId,
    };
    this.listeners.forEach((l) => l());
  }
}

export const lilithSpeech = new LilithSpeechController();
