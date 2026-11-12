/**
 * Web authentication boundary (H1). Used by BOTH `src/proxy.ts` (every request)
 * and each sensitive API route handler (independently, so privileged handlers
 * never rely on the proxy alone).
 *
 * Local mode (LILITH_HOSTED unset): no edge authentication, existing behaviour.
 * Hosted mode: a valid Cloudflare Access application token for an allowed owner
 * email is required on every request; misconfiguration refuses everything.
 *
 * Scope: this proves "the configured owner signed in through Cloudflare
 * Access". It is NOT owner authority. It never satisfies
 * ownerCaptureAuthentication and never authorizes memory approvals, erasure,
 * canonical writes or relationship signing; those stay with their own
 * authorities.
 */
import type { NextRequest } from "next/server";
import { readEdgeAuthConfig, type EdgeAuthConfig } from "./config";
import { JwksCache, type FetchLike } from "./jwks";
import { verifyAccessToken } from "./jwt";

export const ACCESS_JWT_HEADER = "cf-access-jwt-assertion";

export type EdgeAuthResult =
  | { ok: true; mode: "local"; email: null }
  | { ok: true; mode: "hosted"; email: string }
  | { ok: false; status: 401 | 403 | 503; code: string; reason?: string };

let caches = new Map<string, JwksCache>();
let fetchOverride: FetchLike | null = null;

function cacheFor(teamDomain: string): JwksCache {
  let cache = caches.get(teamDomain);
  if (!cache) {
    cache = new JwksCache(teamDomain, (url, init) => (fetchOverride ?? globalThis.fetch)(url, init));
    caches.set(teamDomain, cache);
  }
  return cache;
}

/** TEST-ONLY: reset key caches and optionally fake the JWKS fetch. */
export function __resetEdgeAuthForTests(fetchImpl: FetchLike | null = null): void {
  caches = new Map();
  fetchOverride = fetchImpl;
}

export async function authenticateEdge(
  headers: Headers,
  config: EdgeAuthConfig = readEdgeAuthConfig(),
  nowMs: number = Date.now(),
): Promise<EdgeAuthResult> {
  if (config.mode === "local") return { ok: true, mode: "local", email: null };
  if (config.mode === "misconfigured") return { ok: false, status: 503, code: "HOSTED_AUTH_MISCONFIGURED" };
  const token = headers.get(ACCESS_JWT_HEADER);
  if (!token) return { ok: false, status: 401, code: "EDGE_AUTH_REQUIRED", reason: "missing" };
  const result = await verifyAccessToken(
    token.trim(),
    { issuer: config.issuer, audience: config.audience, ownerEmails: config.ownerEmails },
    cacheFor(config.teamDomain),
    nowMs,
  );
  if (result.ok) return { ok: true, mode: "hosted", email: result.email };
  if (result.reason === "identity") return { ok: false, status: 403, code: "EDGE_IDENTITY_NOT_ALLOWED", reason: "identity" };
  return { ok: false, status: 401, code: "EDGE_AUTH_INVALID", reason: result.reason };
}

export function refusal(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: code }), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function isJson(contentType: string | null): boolean {
  if (!contentType) return false;
  return contentType.split(";")[0].trim().toLowerCase() === "application/json";
}

export interface GuardOptions {
  /** State-changing request: requires a trusted Origin. */
  mutating: boolean;
  /** Carries a body: requires `Content-Type: application/json`. */
  json?: boolean;
}

/**
 * Independent per-handler check. Returns a refusal Response, or null to proceed.
 * Origin trust never uses Host or X-Forwarded-* headers: in hosted mode the only
 * trusted origin is LILITH_PUBLIC_ORIGIN; locally it is the request's own origin.
 */
export async function guardApiRequest(
  req: NextRequest,
  options: GuardOptions,
  config: EdgeAuthConfig = readEdgeAuthConfig(),
): Promise<Response | null> {
  const auth = await authenticateEdge(req.headers, config);
  if (!auth.ok) return refusal(auth.status, auth.code);
  if (options.mutating) {
    const origin = req.headers.get("origin");
    const fetchSite = req.headers.get("sec-fetch-site");
    if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
      return refusal(403, "CROSS_ORIGIN_REQUEST_REFUSED");
    }
    if (config.mode === "hosted") {
      if (origin !== config.publicOrigin) return refusal(403, "CROSS_ORIGIN_REQUEST_REFUSED");
    } else if (origin !== null && origin !== req.nextUrl.origin) {
      return refusal(403, "CROSS_ORIGIN_REQUEST_REFUSED");
    }
  }
  if (options.json && !isJson(req.headers.get("content-type"))) {
    return refusal(415, "JSON_CONTENT_TYPE_REQUIRED");
  }
  return null;
}
