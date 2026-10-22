import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy for First Interaction conversation evidence (F2).
 *
 * Forwards `{action: "open"}` and `{action: "seal" | "transcript", session}` to
 * the backend's `POST /os/conversation/evidence`, authenticated with the
 * server-only `LILITH_OS_OWNER_CAPTURE_TOKEN`. The browser never sees the
 * credential. Opening, sealing and reading evidence never creates or accepts a
 * memory.
 *
 * The capture credential is SERVICE authentication (this server to the
 * backend), NOT owner authentication: it never identifies the person typing,
 * and captured evidence is not an authentic First Memory.
 */

export const dynamic = "force-dynamic";

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

export async function POST(req: NextRequest) {
  const base = baseUrl();
  const capture = process.env.LILITH_OS_OWNER_CAPTURE_TOKEN;
  if (!base || !capture) {
    return NextResponse.json(
      { error: "conversation evidence capture is not configured" },
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
  const action = b.action;
  const forwarded =
    action === "open"
      ? { action }
      : (action === "seal" || action === "transcript") && typeof b.session === "string"
        ? { action, session: b.session }
        : null;
  if (!forwarded) {
    return NextResponse.json({ error: "invalid evidence request" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${base}/os/conversation/evidence`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json",
        "x-lilith-os-owner-capture": capture,
      },
      body: JSON.stringify(forwarded),
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
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
    return NextResponse.json(
      { error: "conversation backend unreachable" },
      { status: 502 },
    );
  }
}
