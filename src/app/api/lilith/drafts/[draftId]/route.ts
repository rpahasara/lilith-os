import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for a single follow-up draft (Slice 4): read-back (`GET`)
 * for the verifier, and discard (`DELETE`) for reversibility. The draftId is
 * validated against the same charset the backend accepts before it is
 * forwarded. Backend status/body are passed through verbatim (404 etc.).
 */

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 10_000;
const DRAFT_ID_RE = /^[A-Za-z0-9._:-]{1,128}$/;

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

function noBackend() {
  return NextResponse.json({ error: "LILITH_API_URL is not configured" }, { status: 503 });
}

async function forward(method: "GET" | "DELETE", url: string) {
  try {
    const upstream = await fetch(url, {
      method,
      headers: { accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ error: "draft store unreachable" }, { status: 502 });
  }
}

export async function GET(_req: NextRequest, ctx: { params: Promise<{ draftId: string }> }) {
  const base = baseUrl();
  if (!base) return noBackend();
  const { draftId } = await ctx.params;
  if (!DRAFT_ID_RE.test(draftId ?? "")) {
    return NextResponse.json({ error: "invalid draftId" }, { status: 400 });
  }
  return forward("GET", `${base}/os/drafts/${encodeURIComponent(draftId)}`);
}

export async function DELETE(_req: NextRequest, ctx: { params: Promise<{ draftId: string }> }) {
  const base = baseUrl();
  if (!base) return noBackend();
  const { draftId } = await ctx.params;
  if (!DRAFT_ID_RE.test(draftId ?? "")) {
    return NextResponse.json({ error: "invalid draftId" }, { status: 400 });
  }
  return forward("DELETE", `${base}/os/drafts/${encodeURIComponent(draftId)}`);
}
