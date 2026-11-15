/**
 * Cloudflare Access application-token (JWT) verification.
 *
 * Accepts only RS256 tokens signed by a key from the team JWKS, with the
 * expected issuer and application audience, unexpired, and carrying an
 * explicitly allowed owner email. Header-embedded keys (`jwk`, `jku`, `x5u`,
 * `x5c`) and critical extensions are refused, so a token cannot supply its own
 * verification key. Every failure is a rejection; there is no "soft" pass.
 */
import type { JwksCache } from "./jwks";

export const MAX_TOKEN_CHARS = 8192;
const LEEWAY_S = 30; // only for nbf/iat clock skew; exp is strict

export interface AccessTokenPolicy {
  issuer: string; // https://<team>.cloudflareaccess.com
  audience: string; // Access application AUD tag
  ownerEmails: ReadonlySet<string>; // lower-case
}

export type VerifyResult =
  | { ok: true; email: string }
  | { ok: false; reason: string };

const B64URL = /^[A-Za-z0-9_-]+$/;

function b64urlBytes(part: string): Uint8Array {
  const pad = part.length % 4 === 0 ? "" : "=".repeat(4 - (part.length % 4));
  const bin = atob(part.replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlJson(part: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(b64urlBytes(part)));
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export async function verifyAccessToken(
  token: string | null | undefined,
  policy: AccessTokenPolicy,
  jwks: JwksCache,
  nowMs: number = Date.now(),
): Promise<VerifyResult> {
  if (typeof token !== "string" || token.length === 0) return { ok: false, reason: "missing" };
  if (token.length > MAX_TOKEN_CHARS) return { ok: false, reason: "too-long" };
  const parts = token.split(".");
  if (parts.length !== 3 || !parts.every((p) => B64URL.test(p))) return { ok: false, reason: "malformed" };
  const [h, p, s] = parts;

  const header = b64urlJson(h);
  const payload = b64urlJson(p);
  if (!header || !payload) return { ok: false, reason: "malformed" };
  if (header.alg !== "RS256") return { ok: false, reason: "alg" };
  if (header.typ !== undefined && header.typ !== "JWT") return { ok: false, reason: "typ" };
  for (const forbidden of ["jwk", "jku", "x5u", "x5c", "crit"]) {
    if (forbidden in header) return { ok: false, reason: `header-${forbidden}` };
  }
  if (typeof header.kid !== "string" || header.kid.length === 0 || header.kid.length > 128) {
    return { ok: false, reason: "kid" };
  }

  const key = await jwks.key(header.kid);
  if (!key) return { ok: false, reason: "unverifiable" };
  let signature: Uint8Array;
  try {
    signature = b64urlBytes(s);
  } catch {
    return { ok: false, reason: "malformed" };
  }
  const valid = await crypto.subtle.verify(
    { name: "RSASSA-PKCS1-v1_5" },
    key,
    signature as BufferSource,
    new TextEncoder().encode(`${h}.${p}`) as BufferSource,
  );
  if (!valid) return { ok: false, reason: "signature" };

  // Claims are checked only after the signature is proven.
  const now = Math.floor(nowMs / 1000);
  if (payload.iss !== policy.issuer) return { ok: false, reason: "iss" };
  const aud = payload.aud;
  const audOk = typeof aud === "string" ? aud === policy.audience
    : Array.isArray(aud) && aud.length > 0 && aud.length <= 8 && aud.includes(policy.audience);
  if (!audOk) return { ok: false, reason: "aud" };
  if (typeof payload.exp !== "number" || !Number.isFinite(payload.exp) || now >= payload.exp) {
    return { ok: false, reason: "exp" };
  }
  if (payload.nbf !== undefined && (typeof payload.nbf !== "number" || payload.nbf > now + LEEWAY_S)) {
    return { ok: false, reason: "nbf" };
  }
  if (payload.iat !== undefined && (typeof payload.iat !== "number" || payload.iat > now + LEEWAY_S)) {
    return { ok: false, reason: "iat" };
  }
  if (payload.type !== undefined && payload.type !== "app") return { ok: false, reason: "type" };
  const email = typeof payload.email === "string" ? payload.email.trim().toLowerCase() : "";
  if (!email || !policy.ownerEmails.has(email)) return { ok: false, reason: "identity" };
  return { ok: true, email };
}
