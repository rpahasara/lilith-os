import { NextResponse, type NextRequest } from "next/server";
import { authenticateEdge, refusal } from "@/server/edge-auth/guard";

/**
 * Next.js 16 Proxy: the first authentication boundary for the hosted web
 * preview. No `matcher` is exported on purpose, so it runs on EVERY request:
 * pages, API routes, `_next` assets and `public/` files (including the avatar).
 *
 * Local mode (LILITH_HOSTED unset): passes everything through unchanged.
 * Hosted mode: requires a valid Cloudflare Access token for an allowed owner
 * email; a request that reaches this server directly (bypassing Cloudflare)
 * has no valid token and is refused. Sensitive API handlers re-verify on their
 * own (see src/server/edge-auth/guard.ts); this proxy is not the only check.
 */
export async function proxy(request: NextRequest) {
  const auth = await authenticateEdge(request.headers);
  if (!auth.ok) return refusal(auth.status, auth.code);
  return NextResponse.next();
}
