/**
 * LILITH Voice — dev-gated voice settings (in-memory).
 *
 * A tiny external store for cross-subtree voice settings that the debug panel
 * writes and other components (e.g. presence-hero's auto-speech effect) read.
 * Not persisted yet — resets on reload. Kept separate from lilithSpeech so the
 * production auto-speech decision does not entangle the playback controller.
 */

export interface VoiceSettingsSnapshot {
  /** When true, finished LILITH replies are auto-spoken via the production
   *  provider (ElevenLabs). Default false = no production behavior change. */
  autoSpeak: boolean;
}

class VoiceSettingsStore {
  private snapshot: VoiceSettingsSnapshot = { autoSpeak: false };
  private listeners = new Set<() => void>();

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  getSnapshot = (): VoiceSettingsSnapshot => this.snapshot;
  getServerSnapshot = (): VoiceSettingsSnapshot => this.snapshot;

  setAutoSpeak(on: boolean): void {
    if (on === this.snapshot.autoSpeak) return;
    this.snapshot = { ...this.snapshot, autoSpeak: on };
    this.listeners.forEach((l) => l());
  }
}

export const voiceSettings = new VoiceSettingsStore();
