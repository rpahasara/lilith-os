import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for the durable Cognitive Core Task Store — collection
 * routes. The browser calls same-origin `/api/lilith/tasks`; this handler
 * forwards to the private backend's `GET /os/tasks` (history) and
 * `POST /os/tasks` (create). Like the other proxies, `LILITH_API_URL` is a
 * SERVER-ONLY env var, so the backend URL never reaches the client and there
 * is no CORS. The general `[...path]` proxy stays GET-only and read-only; the
 * task store's writes live behind this dedicated, narrowly-scoped route.
 *
 * The backend status and body are forwarded verbatim so the client can react
 * to 409 (revision conflict / illegal transition), 404, 413 and 422.
 */

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 10_000;

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

function noBackend() {
  return NextResponse.json(
    { error: "LILITH_API_URL is not configured" },
    { status: 503 },
  );
}

async function forward(
  method: "GET" | "POST",
  url: string,
  init?: { body?: string },
) {
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
        "content-type":
          upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ error: "task store unreachable" }, { status: 502 });
  }
}

export async function GET(req: NextRequest) {
  const base = baseUrl();
  if (!base) return noBackend();
  // Forward only the safe list filters (never arbitrary query passthrough).
  const q = new URLSearchParams();
  const sp = req.nextUrl.searchParams;
  for (const k of ["limit", "status", "kind"]) {
    const v = sp.get(k);
    if (v) q.set(k, v);
  }
  const qs = q.toString();
  return forward("GET", `${base}/os/tasks${qs ? `?${qs}` : ""}`);
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
  return forward("POST", `${base}/os/tasks`, { body: JSON.stringify(body ?? {}) });
}
