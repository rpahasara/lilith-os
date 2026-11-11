/**
 * Hsin avatar delivery (server-only).
 *
 * The original VRM in public/ stays the single source of truth and is never
 * modified. The app loads it from a versioned URL, /avatar/hsin-<version>.vrm,
 * where <version> is the first 16 hex of the file's SHA-256, computed at build
 * time. Because the URL changes whenever the bytes change, the response can be
 * cached as immutable.
 *
 * Caching is `private`: the browser of the signed-in owner caches it, but no
 * shared cache (including Cloudflare's edge) may store it, so the avatar is
 * never served to anyone who has not passed Cloudflare Access + the app's own
 * check. Packaging (scripts/package-web.mjs) adds a gzip copy next to the server
 * (avatar-cache/hsin-<version>.vrm.gz, about 31% of the original); it is served
 * with Content-Encoding: gzip to clients that accept it.
 */
import { createHash } from "node:crypto";
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { Readable } from "node:stream";

export const AVATAR_SOURCE = "public/assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm";
export const AVATAR_CACHE_DIR = "avatar-cache";
export const AVATAR_CONTENT_TYPE = "model/gltf-binary";
export const AVATAR_CACHE_CONTROL = "private, max-age=31536000, immutable";
const VERSION = /^[0-9a-f]{16}$/;

/** First 16 hex of the SHA-256 of a file. Build/packaging time only (reads the whole file). */
export function versionOfFile(path: string): string {
  const hash = createHash("sha256");
  hash.update(readFileSync(path));
  return hash.digest("hex").slice(0, 16);
}

export function versionedAvatarName(version: string): string {
  return `hsin-${version}.vrm`;
}

export function acceptsGzip(acceptEncoding: string | null): boolean {
  if (!acceptEncoding) return false;
  return acceptEncoding.split(",").some((part) => {
    const [name, ...params] = part.trim().toLowerCase().split(";");
    if (name !== "gzip" && name !== "*") return false;
    const q = params.map((p) => p.trim()).find((p) => p.startsWith("q="));
    return q === undefined || Number(q.slice(2)) > 0;
  });
}

export interface AvatarRequest {
  name: string;
  version: string | undefined;
  method: "GET" | "HEAD";
  acceptEncoding: string | null;
  ifNoneMatch: string | null;
  root?: string; // server working directory (standalone root when packaged)
}

/** Build the avatar response. Pure apart from reading the files it serves. */
export function avatarResponse(req: AvatarRequest): Response {
  const root = req.root ?? process.cwd();
  if (!req.version || !VERSION.test(req.version) || req.name !== versionedAvatarName(req.version)) {
    return new Response("Not found", { status: 404, headers: { "cache-control": "no-store" } });
  }
  const gzipPath = join(root, AVATAR_CACHE_DIR, `${versionedAvatarName(req.version)}.gz`);
  const rawPath = join(root, AVATAR_SOURCE);
  const gzip = acceptsGzip(req.acceptEncoding) && existsSync(gzipPath);
  const path = gzip ? gzipPath : rawPath;
  if (!existsSync(path)) {
    return new Response("Not found", { status: 404, headers: { "cache-control": "no-store" } });
  }
  const etag = `"${req.version}${gzip ? "-gz" : ""}"`;
  const headers: Record<string, string> = {
    "content-type": AVATAR_CONTENT_TYPE,
    "cache-control": AVATAR_CACHE_CONTROL,
    etag,
    vary: "Accept-Encoding",
    "x-content-type-options": "nosniff",
  };
  if (gzip) headers["content-encoding"] = "gzip";
  const matches = (req.ifNoneMatch ?? "").split(",").map((t) => t.trim().replace(/^W\//, "")).includes(etag);
  if (matches) return new Response(null, { status: 304, headers });
  headers["content-length"] = String(statSync(path).size);
  if (req.method === "HEAD") return new Response(null, { status: 200, headers });
  const body = Readable.toWeb(createReadStream(path)) as unknown as ReadableStream<Uint8Array>;
  return new Response(body, { status: 200, headers });
}
