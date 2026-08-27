import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for the LILITH OS conversation surface.
 *
 * The browser POSTs same-origin `/api/lilith/conversation`; this handler
 * forwards to the private backend's `POST /os/conversation` (the narrowly
 * scoped conversation relay on the FastAPI service, which fronts the trusted
 * localhost `lilith_os` gateway console → Conversation Router V2). Same as the
 * read-only GET proxy, `LILITH_API_URL` is a SERVER-ONLY env var: the backend
 * URL never reaches the client, there is no CORS, and no provider keys or
 * model/provider details are ever exposed to the browser.
 *
 * This is the ONLY mutating path exposed through the proxy, and it carries a
 * single field (the message text) plus a stable session id — never command
 * execution or agent internals.
 */

export const dynamic = "force-dynamic";

// Conversation turns can be slow (technical turns run tools on the VM). Allow a
// generous ceiling below the backend console's own reply timeout (~180s).
const UPSTREAM_TIMEOUT_MS = 178_000;

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

export async function POST(req: NextRequest) {
  const base = baseUrl();
  if (!base) {
    return NextResponse.json(
      { error: "LILITH_API_URL is not configured" },
      { status: 503 },
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const b = (body ?? {}) as Record<string, unknown>;
  const message = String(b.message ?? "").trim();
  const session = (String(b.session ?? "lilith-os").trim() || "lilith-os").slice(0, 200);
  if (!message) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${base}/os/conversation`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({ message, session }),
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
    return NextResponse.json(
      { error: "conversation backend unreachable" },
      { status: 502 },
    );
  }
}
