import { NextResponse, type NextRequest } from "next/server";
import { ownerCaptureAuthentication } from "@/lib/conversation/owner-capture-auth";

/**
 * Server-side proxy for First Interaction conversation evidence (F2/F5).
 *
 * GET reports whether owner-protected recording is available (it is not until
 * a genuine owner-authentication bridge exists). POST forwards
 * `{action: "open"}` and `{action: "seal" | "transcript", session}` to the
 * backend's `POST /os/conversation/evidence` ONLY for a same-origin request
 * from a server-verified owner session; otherwise it refuses before contacting
 * the backend. Opening, sealing and reading evidence never creates or accepts a
 * memory.
 *
 * The server-only `LILITH_OS_OWNER_CAPTURE_TOKEN` is SERVICE authentication
 * (this server to the backend), NOT owner authentication: it never identifies
 * the person typing, it is never sent to the browser, and it is forwarded only
 * after the owner check passes.
 */

export const dynamic = "force-dynamic";

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

function refuse(error: string, status: number) {
  return NextResponse.json({ error }, { status, headers: { "cache-control": "no-store" } });
}

export async function GET(req: NextRequest) {
  const auth = await ownerCaptureAuthentication(req);
  return NextResponse.json(
    auth.available ? { available: true } : { available: false, reason: auth.reason },
    { headers: { "cache-control": "no-store" } },
  );
}

export async function POST(req: NextRequest) {
  const auth = await ownerCaptureAuthentication(req);
  if (!auth.available) return refuse("OWNER_AUTHENTICATION_REQUIRED", 403);
  // CSRF: only same-origin JSON requests (a cross-site form cannot set this content type or origin).
  if (req.headers.get("origin") !== req.nextUrl.origin
      || !(req.headers.get("content-type") ?? "").startsWith("application/json")) {
    return refuse("CROSS_ORIGIN_REQUEST_REFUSED", 403);
  }
  const base = baseUrl();
  const capture = process.env.LILITH_OS_OWNER_CAPTURE_TOKEN;
  if (!base || !capture) return refuse("conversation evidence capture is not configured", 503);

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return refuse("invalid JSON body", 400);
  }

  const b = (body ?? {}) as Record<string, unknown>;
  const action = b.action;
  const forwarded =
    action === "open"
      ? { action }
      : (action === "seal" || action === "transcript") && typeof b.session === "string"
        ? { action, session: b.session }
        : null;
  if (!forwarded) return refuse("invalid evidence request", 400);

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
    return refuse("conversation backend unreachable", 502);
  }
}
