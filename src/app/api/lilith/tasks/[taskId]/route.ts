import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for the durable Task Store — per-task routes. Forwards
 * `GET /os/tasks/{taskId}` (fetch one) and `PATCH /os/tasks/{taskId}` (update
 * with optimistic concurrency) to the private backend. Backend status/body are
 * passed through verbatim so the client sees 409 conflicts, 404, 413 and 422.
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

// Guard the path segment before it reaches the backend (mirrors the backend's
// own taskId validation) so malformed ids never leave the proxy.
const TASK_ID_RE = /^[A-Za-z0-9._:-]{1,128}$/;

async function forward(
  method: "GET" | "PATCH",
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

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ taskId: string }> },
) {
  const base = baseUrl();
  if (!base) return noBackend();
  const { taskId } = await ctx.params;
  if (!TASK_ID_RE.test(taskId)) {
    return NextResponse.json({ error: "invalid taskId" }, { status: 400 });
  }
  return forward("GET", `${base}/os/tasks/${encodeURIComponent(taskId)}`);
}

export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<{ taskId: string }> },
) {
  const base = baseUrl();
  if (!base) return noBackend();
  const { taskId } = await ctx.params;
  if (!TASK_ID_RE.test(taskId)) {
    return NextResponse.json({ error: "invalid taskId" }, { status: 400 });
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  return forward("PATCH", `${base}/os/tasks/${encodeURIComponent(taskId)}`, {
    body: JSON.stringify(body ?? {}),
  });
}
