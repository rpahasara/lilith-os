/**
 * Security headers for every response (applied by next.config.ts in production).
 *
 * CSP notes, verified against the running app:
 * - script-src needs 'unsafe-inline': the App Router streams React Server
 *   Component payloads as inline <script> tags, and the Command Center pages
 *   are statically rendered, so per-request nonces are not available without
 *   making every page dynamic. No 'unsafe-eval', and no external script origin.
 * - img-src/connect-src allow blob: because GLTFLoader and three-vrm turn the
 *   avatar's embedded textures into blob: URLs.
 * - connect-src is otherwise 'self': the browser only ever talks to this
 *   origin (Core API and TTS providers are reached server-side), so injected
 *   code cannot exfiltrate to another host.
 * - No upgrade-insecure-requests: it would break local http `next start`;
 *   Cloudflare terminates TLS and sets HSTS for the hosted origin.
 * - Cloudflare Access sign-in happens on Cloudflare's own pages before a
 *   request reaches this app, so it needs nothing from this policy.
 */

export const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self' blob:",
  "media-src 'self' blob:",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "frame-src 'none'",
  "manifest-src 'self'",
].join("; ");

export const PERMISSIONS_POLICY = [
  "camera=()",
  "microphone=()", // no speech input yet; widen only when voice input ships
  "geolocation=()",
  "payment=()",
  "usb=()",
  "serial=()",
  "hid=()",
  "bluetooth=()",
  "midi=()",
  "display-capture=()",
  "publickey-credentials-get=(self)",
  "autoplay=(self)",
  "fullscreen=(self)",
].join(", ");

export const SECURITY_HEADERS: ReadonlyArray<{ key: string; value: string }> = [
  { key: "Content-Security-Policy", value: CONTENT_SECURITY_POLICY },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: PERMISSIONS_POLICY },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  { key: "X-Frame-Options", value: "DENY" },
];
