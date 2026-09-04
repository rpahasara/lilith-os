import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for LILITH voice synthesis (OpenAI TTS).
 *
 * The browser POSTs same-origin `/api/voice/tts` with ONLY `{ text }`; this
 * handler resolves model/voice/instructions from SERVER-ONLY env and calls
 * OpenAI's `/v1/audio/speech`, returning encoded WAV bytes. The API key
 * (`OPENAI_API_KEY`) never reaches the client, and the client cannot control the
 * model, voice, instructions, upstream URL, or key. Returns 503 when unconfigured
 * so the app degrades cleanly.
 */

export const dynamic = "force-dynamic";

const UPSTREAM = "https://api.openai.com/v1/audio/speech";
const UPSTREAM_TIMEOUT_MS = 30_000;
const MAX_TEXT = 4096;

const DEFAULT_MODEL = "gpt-4o-mini-tts";
const DEFAULT_VOICE = "marin";
const DEFAULT_INSTRUCTIONS =
  "Speak naturally, warmly, calmly, and conversationally. Keep the delivery clear and slightly playful without exaggeration.";

export async function POST(req: NextRequest) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    return NextResponse.json(
      { error: "OPENAI_API_KEY is not configured" },
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

  const model = process.env.OPENAI_TTS_MODEL || DEFAULT_MODEL;
  const voice = process.env.OPENAI_TTS_VOICE || DEFAULT_VOICE;
  const instructions = process.env.OPENAI_TTS_INSTRUCTIONS || DEFAULT_INSTRUCTIONS;

  try {
    const upstream = await fetch(UPSTREAM, {
      method: "POST",
      headers: {
        authorization: `Bearer ${key}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model,
        voice,
        input: text,
        response_format: "wav",
        instructions,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });

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
        "content-type": "audio/wav",
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
