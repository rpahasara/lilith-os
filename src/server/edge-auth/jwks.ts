/**
 * Cloudflare Access signing-key cache (JWKS).
 *
 * Keys come only from the team's documented endpoint,
 * `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`, built from a
 * validated team domain (never from the token). Fetches are bounded (timeout,
 * size, no redirects) and deduplicated.
 *
 * Rotation: Cloudflare publishes the current and previous keys. An unknown
 * `kid` triggers at most one refetch per MIN_REFETCH_MS, so forged kids cannot
 * be used to hammer the endpoint. Keys are refreshed every REFRESH_MS; if a
 * refresh fails, previously fetched keys stay usable for STALE_MAX_MS, after
 * which verification fails closed.
 */

export const REFRESH_MS = 10 * 60_000;
export const MIN_REFETCH_MS = 30_000;
export const STALE_MAX_MS = 24 * 3600_000;
const FETCH_TIMEOUT_MS = 5_000;
const MAX_JWKS_BYTES = 64 * 1024;
const MIN_MODULUS_B64URL_CHARS = 342; // 2048-bit RSA modulus

export type FetchLike = (url: string, init: RequestInit) => Promise<Response>;

export function certsUrl(teamDomain: string): string {
  return `https://${teamDomain}/cdn-cgi/access/certs`;
}

interface CachedKeys {
  keys: Map<string, CryptoKey>;
  fetchedAt: number;
}

export class JwksCache {
  private cached: CachedKeys | null = null;
  private lastAttempt = -Infinity;
  private inflight: Promise<void> | null = null;

  constructor(
    private readonly teamDomain: string,
    private readonly fetchImpl: FetchLike = (url, init) => globalThis.fetch(url, init),
    private readonly now: () => number = () => Date.now(),
  ) {}

  /** The verification key for `kid`, or null when it cannot be established. */
  async key(kid: string): Promise<CryptoKey | null> {
    const t = this.now();
    const fresh = this.cached && t - this.cached.fetchedAt < REFRESH_MS;
    if (!fresh) await this.refresh();
    let key = this.usable()?.get(kid) ?? null;
    if (!key) {
      await this.refresh(); // possible rotation: refetch, rate-limited
      key = this.usable()?.get(kid) ?? null;
    }
    return key;
  }

  private usable(): Map<string, CryptoKey> | null {
    if (!this.cached) return null;
    return this.now() - this.cached.fetchedAt <= STALE_MAX_MS ? this.cached.keys : null;
  }

  /** Every fetch, scheduled or rotation-driven, is limited to one per MIN_REFETCH_MS. */
  private async refresh(): Promise<void> {
    if (this.inflight) return this.inflight;
    if (this.now() - this.lastAttempt < MIN_REFETCH_MS) return;
    this.lastAttempt = this.now();
    this.inflight = this.load()
      .then((keys) => {
        if (keys.size > 0) this.cached = { keys, fetchedAt: this.now() };
      })
      .catch(() => {
        /* keep previous keys until STALE_MAX_MS; verification fails closed after */
      })
      .finally(() => {
        this.inflight = null;
      });
    return this.inflight;
  }

  private async load(): Promise<Map<string, CryptoKey>> {
    const res = await this.fetchImpl(certsUrl(this.teamDomain), {
      method: "GET",
      headers: { accept: "application/json" },
      redirect: "error",
      cache: "no-store",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
    if (!res.ok) throw new Error(`JWKS HTTP ${res.status}`);
    const text = await res.text();
    if (text.length > MAX_JWKS_BYTES) throw new Error("JWKS too large");
    const body = JSON.parse(text) as { keys?: unknown };
    if (!Array.isArray(body.keys)) throw new Error("JWKS has no keys");
    const keys = new Map<string, CryptoKey>();
    for (const raw of body.keys.slice(0, 16)) {
      const k = raw as Record<string, unknown>;
      if (
        k.kty !== "RSA" ||
        (k.alg !== undefined && k.alg !== "RS256") ||
        (k.use !== undefined && k.use !== "sig") ||
        typeof k.kid !== "string" || k.kid.length === 0 || k.kid.length > 128 ||
        typeof k.n !== "string" || k.n.length < MIN_MODULUS_B64URL_CHARS ||
        typeof k.e !== "string"
      ) {
        continue;
      }
      try {
        const key = await crypto.subtle.importKey(
          "jwk",
          { kty: "RSA", n: k.n, e: k.e, alg: "RS256", ext: true },
          { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
          false,
          ["verify"],
        );
        keys.set(k.kid, key);
      } catch {
        /* skip a malformed key */
      }
    }
    return keys;
  }
}
