import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for the follow-up draft store — collection routes
 * (Slice 4). The browser calls same-origin `/api/lilith/drafts`; this handler
 * forwards to the private backend's `GET /os/drafts` (list) and
 * `POST /os/drafts` (create the one approval-gated write). `LILITH_API_URL` is
 * SERVER-ONLY, so the backend URL never reaches the client and there is no
 * CORS. The general `[...path]` proxy stays GET-only and read-only; this
 * dedicated route is the only place a draft write can happen.
 *
 * Backend status and body are forwarded verbatim so the client sees 400/404/
 * 409/413/422 exactly as the store reports them.
 */

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 10_000;

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

function noBackend() {
  return NextResponse.json({ error: "LILITH_API_URL is not configured" }, { status: 503 });
}

async function forward(method: "GET" | "POST", url: string, init?: { body?: string }) {
  try {
    const upstream = await fetch(url, {
      method,
      headers: { "content-type": "application/json", accept: "application/json" },
      body: init?.body,
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

export async function GET(req: NextRequest) {
  const base = baseUrl();
  if (!base) return noBackend();
  const q = new URLSearchParams();
  const sp = req.nextUrl.searchParams;
  for (const k of ["limit", "target_id", "task_id", "idempotency_key"]) {
    const v = sp.get(k);
    if (v) q.set(k, v);
  }
  const qs = q.toString();
  return forward("GET", `${base}/os/drafts${qs ? `?${qs}` : ""}`);
}

export async function POST(req: NextRequest) {
  const base = baseUrl();
  if (!base) return noBackend();
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  return forward("POST", `${base}/os/drafts`, { body: JSON.stringify(body ?? {}) });
}
