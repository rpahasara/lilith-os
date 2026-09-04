/**
 * LILITH Voice — provider-neutral fallback viseme generator.
 *
 * Used when a TTS provider returns no alignment (e.g. OpenAI /audio/speech). It
 * is invoked by the speech controller AFTER the audio is decoded, so it receives
 * the EXACT decoded duration — cues are laid out to fit that timeline rather than
 * an estimate, and the audio clock stays authoritative.
 *
 * This is deliberately rough: it produces visually believable mouth motion, not
 * phoneme-accurate lip-sync. Every cue weight is <= 1, so the renderer (which
 * multiplies by the validated HSIN viseme maxima) never exceeds those maxima; no
 * cue extends past `durationSec`.
 */

import type { VisemeCue } from "@/lib/hsin-lip-sync";

export interface FallbackVisemeInput {
  text: string;
  durationSec: number;
}

type Vowel = "aa" | "ee" | "ih" | "oh" | "ou";

/** Rough vowel → viseme map (only the supported viseme set is used). */
function vowelViseme(ch: string): Vowel | null {
  switch (ch) {
    case "a":
      return "aa";
    case "e":
      return "ee";
    case "i":
    case "y":
      return "ih";
    case "o":
      return "oh";
    case "u":
    case "w":
      return "ou";
    default:
      return null;
  }
}

const SIL_MS = 90; // short mouth-close at clause/sentence boundaries
const MIN_CUE_MS = 70; // don't emit imperceptibly short cues
const MAX_VOWELS_PER_WORD = 3;

interface Token {
  word: string;
  /** Trailing punctuation that should introduce a short silence after the word. */
  breaksAfter: boolean;
}

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  // Words = letter/digit/apostrophe runs; punctuation between them may break.
  const re = /([\p{L}\p{N}']+)([^\p{L}\p{N}']*)/gu;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const word = m[1];
    const gap = m[2] ?? "";
    if (!word) continue;
    tokens.push({ word, breaksAfter: /[.,!?;:—–]/.test(gap) });
  }
  return tokens;
}

/** Extract up to MAX_VOWELS_PER_WORD viseme shapes for a word (never empty). */
function wordVisemes(word: string): Vowel[] {
  const out: Vowel[] = [];
  for (const ch of word.toLowerCase()) {
    const v = vowelViseme(ch);
    if (v) {
      out.push(v);
      if (out.length >= MAX_VOWELS_PER_WORD) break;
    }
  }
  // Consonant-only / no-vowel words get a single neutral opening.
  if (out.length === 0) out.push("aa");
  return out;
}

export function generateFallbackVisemes(input: FallbackVisemeInput): VisemeCue[] {
  const durationMs = Math.max(0, input.durationSec * 1000);
  if (durationMs <= 0) return [];
  const tokens = tokenize(input.text);
  if (tokens.length === 0) {
    // No words but we have audio: hold a single soft opening then close.
    const open = Math.max(MIN_CUE_MS, durationMs - SIL_MS);
    return [
      { viseme: "aa", startMs: 0, durationMs: open, weight: 0.85 },
      { viseme: "sil", startMs: open, durationMs: Math.min(SIL_MS, durationMs - open), weight: 1 },
    ];
  }

  // Reserve silence for each clause break plus a final close.
  const breakCount = tokens.filter((t) => t.breaksAfter).length + 1;
  const reservedSil = Math.min(durationMs * 0.5, breakCount * SIL_MS);
  const speechMs = Math.max(0, durationMs - reservedSil);

  // Distribute speech time by word length (min weight 1 char).
  const weights = tokens.map((t) => Math.max(1, t.word.length));
  const totalWeight = weights.reduce((a, b) => a + b, 0);

  const cues: VisemeCue[] = [];
  let t = 0;
  tokens.forEach((token, i) => {
    const wordMs = (weights[i] / totalWeight) * speechMs;
    const shapes = wordVisemes(token.word);
    const per = wordMs / shapes.length;
    shapes.forEach((v) => {
      if (per >= 1) {
        cues.push({
          viseme: v,
          startMs: t,
          durationMs: Math.max(MIN_CUE_MS, per),
          weight: 1,
        });
      }
      t += per;
    });
    if (token.breaksAfter) {
      cues.push({ viseme: "sil", startMs: t, durationMs: SIL_MS, weight: 1 });
      t += SIL_MS;
    }
  });

  // Always end closed, clamped strictly inside the decoded duration.
  const silStart = Math.min(t, Math.max(0, durationMs - SIL_MS));
  cues.push({
    viseme: "sil",
    startMs: silStart,
    durationMs: Math.max(0, durationMs - silStart),
    weight: 1,
  });

  // Final safety clamp: no cue may begin at/after the decoded duration.
  return cues.filter((c) => c.startMs < durationMs);
}
