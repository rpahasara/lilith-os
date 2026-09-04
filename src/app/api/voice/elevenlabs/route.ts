import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for LILITH voice synthesis (ElevenLabs TTS).
 *
 * The browser POSTs same-origin `/api/voice/elevenlabs` with ONLY `{ text }`;
 * this handler resolves the API key, voice id, and model id from SERVER-ONLY env
 * and calls ElevenLabs' text-to-speech endpoint, returning encoded MP3 bytes.
 * `ELEVENLABS_API_KEY` never reaches the client, and the client cannot control
 * the key, voice, model, or upstream URL. Returns 503 when unconfigured so the
 * app degrades cleanly.
 */

export const dynamic = "force-dynamic";

const UPSTREAM_BASE = "https://api.elevenlabs.io/v1/text-to-speech";
const OUTPUT_FORMAT = "mp3_44100_128"; // browser-decodable via AudioContext
const UPSTREAM_TIMEOUT_MS = 30_000;
const MAX_TEXT = 4096;

const DEFAULT_VOICE_ID = "f9x21lSfJr46lObG1WtU";
const DEFAULT_MODEL_ID = "eleven_v3";

export async function POST(req: NextRequest) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key) {
    return NextResponse.json(
      { error: "ELEVENLABS_API_KEY is not configured" },
      { status: 503 },
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const text = String((body as Record<string, unknown>)?.text ?? "").trim();
  if (!text) {
    return NextResponse.json({ error: "text is required" }, { status: 400 });
  }
  if (text.length > MAX_TEXT) {
    return NextResponse.json(
      { error: `text exceeds ${MAX_TEXT} characters` },
      { status: 400 },
    );
  }

  const voiceId = process.env.ELEVENLABS_VOICE_ID || DEFAULT_VOICE_ID;
  const modelId = process.env.ELEVENLABS_MODEL_ID || DEFAULT_MODEL_ID;

  try {
    const upstream = await fetch(
      `${UPSTREAM_BASE}/${encodeURIComponent(voiceId)}?output_format=${OUTPUT_FORMAT}`,
      {
        method: "POST",
        headers: {
          "xi-api-key": key,
          "content-type": "application/json",
          accept: "audio/mpeg",
        },
        body: JSON.stringify({ text, model_id: modelId }),
        cache: "no-store",
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      },
    );

    if (!upstream.ok) {
      // Never leak the upstream body (may echo request details) or the key.
      return NextResponse.json(
        { error: `tts upstream error (HTTP ${upstream.status})` },
        { status: 502 },
      );
    }

    const audio = await upstream.arrayBuffer();
    return new NextResponse(audio, {
      status: 200,
      headers: {
        "content-type": "audio/mpeg",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "tts backend unreachable" },
      { status: 502 },
    );
  }
}
