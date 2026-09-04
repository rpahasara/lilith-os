export type LilithViseme = "aa" | "ih" | "ou" | "ee" | "oh" | "sil";

export type VisemeCue = {
  viseme: LilithViseme;
  startMs: number;
  durationMs?: number;
  weight?: number;
};

export type SpeechPlaybackSnapshot = {
  id: number;
  status: "idle" | "playing" | "paused";
  cues: readonly VisemeCue[];
  startedAtMs: number;
  pausedAtMs: number;
  endMs: number;
  /**
   * When true, this playback is driven by an external owner (lilithSpeech /
   * real audio): the controller does NOT run its own completion timer or own
   * the elapsed clock — the audio layer is the sole completion authority, and
   * viseme sampling uses the audio-derived elapsed time instead of
   * performance.now(). Default false = legacy internal-clock behavior.
   */
  externalClock: boolean;
};

/** Options for {@link HsinLipSyncController.startSpeech}. */
export type StartSpeechOptions = {
  /** Drive completion/elapsed externally (audio-authoritative). Default false. */
  externalClock?: boolean;
};

const EMPTY_SNAPSHOT: SpeechPlaybackSnapshot = {
  id: 0,
  status: "idle",
  cues: [],
  startedAtMs: 0,
  pausedAtMs: 0,
  endMs: 0,
  externalClock: false,
};

class HsinLipSyncController {
  private snapshot = EMPTY_SNAPSHOT;
  private listeners = new Set<() => void>();
  private endTimer: ReturnType<typeof setTimeout> | null = null;

  getSnapshot = () => this.snapshot;
  getServerSnapshot = () => EMPTY_SNAPSHOT;

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  startSpeech(cues: readonly VisemeCue[], opts: StartSpeechOptions = {}) {
    const externalClock = opts.externalClock ?? false;
    const normalizedCues = cues
      .map((cue) => ({
        ...cue,
        startMs: Math.max(0, cue.startMs),
        durationMs:
          cue.durationMs == null ? undefined : Math.max(0, cue.durationMs),
        weight:
          cue.weight == null ? undefined : Math.max(0, Math.min(1, cue.weight)),
      }))
      .sort((a, b) => a.startMs - b.startMs);
    if (normalizedCues.length === 0) {
      this.stopSpeech();
      return;
    }

    this.clearEndTimer();
    const finalCue = normalizedCues[normalizedCues.length - 1];
    const endMs = finalCue.startMs + (finalCue.durationMs ?? 220);
    this.snapshot = {
      id: this.snapshot.id + 1,
      status: "playing",
      cues: normalizedCues,
      startedAtMs: performance.now(),
      pausedAtMs: 0,
      endMs,
      externalClock,
    };
    this.emit();
    // In external-clock mode the audio layer owns completion — no internal timer.
    if (!externalClock) this.scheduleEnd(endMs);
  }

  stopSpeech() {
    this.clearEndTimer();
    this.snapshot = {
      ...EMPTY_SNAPSHOT,
      id: this.snapshot.id + 1,
    };
    this.emit();
  }

  pauseSpeech() {
    if (this.snapshot.status !== "playing") return;
    this.clearEndTimer();
    // External-clock mode: lilithSpeech owns the elapsed clock, so we only flip
    // status; pausedAtMs is irrelevant to sampling here.
    this.snapshot = {
      ...this.snapshot,
      status: "paused",
      pausedAtMs: this.snapshot.externalClock
        ? this.snapshot.pausedAtMs
        : Math.min(
            this.snapshot.endMs,
            performance.now() - this.snapshot.startedAtMs,
          ),
    };
    this.emit();
  }

  resumeSpeech() {
    if (this.snapshot.status !== "paused") return;
    if (this.snapshot.externalClock) {
      // No internal timer/clock to rebase — just resume status.
      this.snapshot = { ...this.snapshot, status: "playing" };
      this.emit();
      return;
    }
    const remainingMs = Math.max(0, this.snapshot.endMs - this.snapshot.pausedAtMs);
    this.snapshot = {
      ...this.snapshot,
      status: "playing",
      startedAtMs: performance.now() - this.snapshot.pausedAtMs,
      pausedAtMs: 0,
    };
    this.emit();
    this.scheduleEnd(remainingMs);
  }

  private scheduleEnd(delayMs: number) {
    this.endTimer = setTimeout(() => this.stopSpeech(), delayMs);
  }

  private clearEndTimer() {
    if (this.endTimer != null) clearTimeout(this.endTimer);
    this.endTimer = null;
  }

  private emit() {
    this.listeners.forEach((listener) => listener());
  }
}

export const hsinLipSync = new HsinLipSyncController();

