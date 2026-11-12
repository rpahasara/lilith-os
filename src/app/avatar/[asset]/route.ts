import type { NextRequest } from "next/server";
import { guardApiRequest } from "@/server/edge-auth/guard";
import { avatarResponse } from "@/server/web-hosting/avatar";

/**
 * Versioned, private Hsin avatar: /avatar/hsin-<version>.vrm.
 * Re-checks the web authentication itself (the proxy is not the only gate) and
 * serves the packaged gzip copy when the client accepts it. See
 * src/server/web-hosting/avatar.ts for the caching and integrity rules.
 */

export const dynamic = "force-dynamic";

async function handle(req: NextRequest, ctx: { params: Promise<{ asset: string }> }, method: "GET" | "HEAD") {
  const denied = await guardApiRequest(req, { mutating: false });
  if (denied) return denied;
  const { asset } = await ctx.params;
  return avatarResponse({
    name: asset,
    version: process.env.NEXT_PUBLIC_HSIN_AVATAR_VERSION,
    method,
    acceptEncoding: req.headers.get("accept-encoding"),
    ifNoneMatch: req.headers.get("if-none-match"),
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ asset: string }> }) {
  return handle(req, ctx, "GET");
}

export async function HEAD(req: NextRequest, ctx: { params: Promise<{ asset: string }> }) {
  return handle(req, ctx, "HEAD");
}
