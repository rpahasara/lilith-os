/**
 * LILITH Voice — OpenAI TTS provider (client side).
 *
 * Calls our OWN same-origin server route (`/api/voice/tts`), never OpenAI
 * directly — the API key lives only on the server. Returns portable encoded
 * audio bytes and NO alignment: OpenAI's /audio/speech gives no timing, and we
 * refuse to fabricate provider cues. The speech controller generates fallback
 * visemes AFTER decode (when the exact duration is known). No AudioContext here.
 */

import type { TTSProvider, TTSRequest, TTSResult } from "./types";

const TTS_ENDPOINT = "/api/voice/tts";

export class OpenAITTSProvider implements TTSProvider {
  readonly name = "openai";

  async synthesize(req: TTSRequest): Promise<TTSResult> {
    const res = await fetch(TTS_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "audio/wav" },
      // Only the text crosses the wire — model/voice/instructions are resolved
      // server-side from env, never client-controlled.
      body: JSON.stringify({ text: req.text }),
      cache: "no-store",
      signal: req.signal,
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        if (j?.error) detail = String(j.error);
      } catch {
        /* non-JSON error body */
      }
      throw new Error(`OpenAI TTS failed: ${detail}`);
    }

    const data = await res.arrayBuffer();
    const mimeType = res.headers.get("content-type") ?? "audio/wav";
    return {
      audio: { kind: "bytes", data, mimeType },
      // No cues/words/phonemes — controller derives fallback cues post-decode.
      meta: { provider: this.name },
    };
  }
}
