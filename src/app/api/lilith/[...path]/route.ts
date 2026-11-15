import { NextResponse, type NextRequest } from "next/server";
import { guardApiRequest } from "@/server/edge-auth/guard";
import { coreApiHeaders } from "@/lib/core-api-credentials";

/**
 * Server-side proxy to the private LILITH backend.
 *
 * The browser calls same-origin `/api/lilith/<path>` and this handler forwards
 * to `LILITH_API_URL` (a SERVER-ONLY env var — never shipped to the client).
 * That keeps the backend private (point it at a localhost SSH/IAP tunnel),
 * avoids CORS entirely, and means the tunnel URL never appears in the bundle.
 *
 * Read-only: only GET is proxied. If the backend is not configured the handler
 * returns 503 so the client can fall back to demo data.
 */

export const dynamic = "force-dynamic";

// Endpoints the frontend is allowed to reach through the proxy.
const ALLOWED = [
  "career/applications",
  "career/pipeline",
  "career/activity",
  "os/overview",
  "system/status",
  "audit/recent",
  // World Model (Slice 7). Read-only belief store; single prefix covers
  // /os/world and /os/world/{key}. Live on the backend (Slice 7 Phase B).
  "os/world",
  // Memory (endpoints not live yet — the client falls back to demo until the
  // backend ships these; allow-listing now keeps the frontend live-ready).
  "memory/overview",
  "memory/records",
  "memory/entities",
  "memory/entity",
  "memory/search",
  // Meetings (read-only). Single prefix covers /meetings/overview, /upcoming,
  // /context, /followups and the dynamic /meetings/{id}/prep. Proxy is GET-only.
  "meetings",
];

// A plain path segment: non-empty, not a dot segment, and free of separators
// (`/`, `\`), percent signs (double or ambiguous encoding), `?`, `#` and
// control characters (the URL parser strips tabs and newlines).
function isPlainSegment(s: unknown): boolean {
  return typeof s === "string" && s.length > 0 && s !== "." && s !== ".." &&
    !/[/\\%?#\u0000-\u001f\u007f]/.test(s);
}

function baseUrl() {
  const raw = process.env.LILITH_API_URL;
  return raw ? raw.replace(/\/+$/, "") : null;
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
) {
  const denied = await guardApiRequest(req, { mutating: false });
  if (denied) return denied;
  const base = baseUrl();
  if (!base) {
    return NextResponse.json(
      { error: "LILITH_API_URL is not configured" },
      { status: 503 },
    );
  }

  const { path } = await ctx.params;
  // Segments arrive already decoded, so `..%2f..%2fos%2ftasks` is one segment
  // holding slashes. Refuse every segment that could change the path once it
  // is joined and normalised into the backend URL, before the allow-list check.
  if (!Array.isArray(path) || !path.every(isPlainSegment)) {
    return NextResponse.json({ error: "path not allowed" }, { status: 403 });
  }
  const joined = path.join("/");

  if (!ALLOWED.some((p) => joined === p || joined.startsWith(`${p}/`))) {
    return NextResponse.json({ error: "path not allowed" }, { status: 403 });
  }

  const url = `${base}/${joined}${req.nextUrl.search}`;

  try {
    const upstream = await fetch(url, {
      headers: { accept: "application/json", ...coreApiHeaders() },
      cache: "no-store",
      // 10s guard so a hung tunnel doesn't stall the request forever.
      signal: AbortSignal.timeout(10_000),
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "backend unreachable" },
      { status: 502 },
    );
  }
}
