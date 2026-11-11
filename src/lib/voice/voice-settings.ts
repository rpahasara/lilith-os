/**
 * LILITH Voice — the single voice settings store.
 *
 * A tiny external store that the owner-facing voice toggle, the dev debug
 * panel and presence-hero's auto-speech effect all share. There is no second
 * voice state anywhere.
 *
 * `autoSpeak` defaults to OFF. It only becomes true through an explicit owner
 * action (`setAutoSpeak(true)` from the toggle or the debug panel). The owner's
 * choice is remembered in this browser's localStorage. A remembered "on" never
 * plays anything by itself: only a NEW reply to a turn the owner sends on the
 * page is spoken (see `reply-voicing.ts`). Browsers additionally keep audio
 * locked until the owner interacts with the page, and the speech controller
 * refuses to animate speech it cannot actually play.
 *
 * Kept separate from lilithSpeech so the auto-speech decision does not
 * entangle the playback controller.
 */

export interface VoiceSettingsSnapshot {
  /** When true, NEW finished LILITH replies are spoken via the production
   *  provider (ElevenLabs). Default false. */
  autoSpeak: boolean;
}

/** Minimal storage seam (window.localStorage in the browser; a fake in tests). */
export interface VoiceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const VOICE_STORAGE_KEY = "lilith-os:voice";
const OFF: VoiceSettingsSnapshot = { autoSpeak: false };

export class VoiceSettingsStore {
  private snapshot: VoiceSettingsSnapshot = OFF;
  private listeners = new Set<() => void>();
  private storage: VoiceStorage | null = null;
  private hydrated = false;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  getSnapshot = (): VoiceSettingsSnapshot => this.snapshot;
  /** Server render is always OFF (no storage on the server, no mismatch). */
  getServerSnapshot = (): VoiceSettingsSnapshot => OFF;

  /**
   * Restore the owner's remembered choice (client only, once on mount). Only
   * the exact value "on" enables voice; anything else, or unreadable storage,
   * stays OFF.
   */
  hydrate(storage: VoiceStorage | null): void {
    // Once per page: a remount must not override a choice made this session
    // (e.g. when storage is blocked and nothing was persisted).
    if (this.hydrated) return;
    this.hydrated = true;
    this.storage = storage;
    let stored: string | null = null;
    try {
      stored = storage?.getItem(VOICE_STORAGE_KEY) ?? null;
    } catch {
      stored = null;
    }
    this.apply(stored === "on");
  }

  /** Explicit owner action. Persists the choice when storage is available. */
  setAutoSpeak(on: boolean): void {
    try {
      this.storage?.setItem(VOICE_STORAGE_KEY, on ? "on" : "off");
    } catch {
      /* storage full or blocked: the choice still applies for this page */
    }
    this.apply(on);
  }

  private apply(on: boolean): void {
    if (on === this.snapshot.autoSpeak) return;
    this.snapshot = { ...this.snapshot, autoSpeak: on };
    this.listeners.forEach((l) => l());
  }
}

export const voiceSettings = new VoiceSettingsStore();

/** Browser localStorage, or null where it is unavailable (private mode, SSR). */
export function browserVoiceStorage(): VoiceStorage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}
