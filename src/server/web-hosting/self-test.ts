/**
 * Headless tests for H2 (hosting package): security headers, private versioned
 * avatar delivery, and deployment-readiness rules (including the shipped
 * templates). Run by `npm run test:core`.
 */
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gzipSync } from "node:zlib";
import type { NextRequest } from "next/server";
import nextConfig from "../../../next.config";
import * as avatarRoute from "@/app/avatar/[asset]/route";
import { CONTENT_SECURITY_POLICY, PERMISSIONS_POLICY, SECURITY_HEADERS } from "./security-headers";
import {
  AVATAR_CACHE_CONTROL, AVATAR_SOURCE, acceptsGzip, avatarResponse, versionOfFile, versionedAvatarName,
} from "./avatar";
import { checkArtifact, checkCloudflared, checkEnv, checkUnit } from "./readiness";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const ROOT = process.cwd();
const read = (p: string) => readFileSync(join(ROOT, p), "utf8");

const GOOD_ENV = `
LILITH_HOSTED=1
LILITH_ACCESS_TEAM_DOMAIN=lilith-test.cloudflareaccess.com
LILITH_ACCESS_AUD=${"a".repeat(64)}
LILITH_OWNER_EMAILS=owner@example.com
LILITH_PUBLIC_ORIGIN=https://os.example.com
LILITH_API_URL=http://10.20.0.5:8765
LILITH_OS_READ_TOKEN=${"r".repeat(40)}
LILITH_OS_WRITE_TOKEN=${"w".repeat(40)}
`;
const fillTemplate = (t: string) => t
  .replace(/<TUNNEL_ID>/g, "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
  .replace(/<PUBLIC_HOSTNAME>/g, "os.example.com");

export async function runWebHostingSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `web-hosting: ${name}`, pass, detail: pass ? undefined : detail });

  /* ------------------------------------------------ security headers */
  const csp = Object.fromEntries(CONTENT_SECURITY_POLICY.split("; ").map((d) => {
    const [k, ...v] = d.split(" ");
    return [k, v];
  }));
  check("CSP: default-src, object-src none, base-uri, form-action, frame-ancestors none",
    csp["default-src"]?.join(" ") === "'self'" && csp["object-src"]?.join(" ") === "'none'" &&
    csp["base-uri"]?.join(" ") === "'self'" && csp["form-action"]?.join(" ") === "'self'" &&
    csp["frame-ancestors"]?.join(" ") === "'none'");
  check("CSP: no unsafe-eval, no wildcard or remote source anywhere",
    !/unsafe-eval|\*|https?:|wss?:/.test(CONTENT_SECURITY_POLICY), CONTENT_SECURITY_POLICY);
  check("CSP: the browser may only connect to this origin (and Three.js blob: textures)",
    csp["connect-src"]?.join(" ") === "'self' blob:" && csp["img-src"]?.join(" ") === "'self' data: blob:");
  check("CSP: no upgrade-insecure-requests (Cloudflare sets HSTS; local http keeps working)",
    !("upgrade-insecure-requests" in csp));
  const h = Object.fromEntries(SECURITY_HEADERS.map((x) => [x.key, x.value]));
  check("nosniff, no-referrer, COOP same-origin, CORP same-origin, X-Frame-Options DENY",
    h["X-Content-Type-Options"] === "nosniff" && h["Referrer-Policy"] === "no-referrer" &&
    h["Cross-Origin-Opener-Policy"] === "same-origin" && h["Cross-Origin-Resource-Policy"] === "same-origin" &&
    h["X-Frame-Options"] === "DENY");
  check("Permissions-Policy denies camera, microphone, geolocation, payment",
    ["camera=()", "microphone=()", "geolocation=()", "payment=()"].every((p) => PERMISSIONS_POLICY.includes(p)));
  const rules = await nextConfig.headers!();
  check("next.config applies the headers to every path and builds standalone",
    nextConfig.output === "standalone" && rules.length === 1 && rules[0].source === "/:path*" &&
    nextConfig.poweredByHeader === false);
  const appliedCsp = rules[0].headers.find((x) => x.key === "Content-Security-Policy");
  check("CSP is applied only to production builds (dev keeps Fast Refresh)",
    process.env.NODE_ENV === "production" ? appliedCsp?.value === CONTENT_SECURITY_POLICY : appliedCsp === undefined,
    `NODE_ENV=${process.env.NODE_ENV}`);

  /* ------------------------------------------------ avatar delivery */
  const version = versionOfFile(join(ROOT, AVATAR_SOURCE));
  const sourceSha = createHash("sha256").update(readFileSync(join(ROOT, AVATAR_SOURCE))).digest("hex");
  check("avatar version is the source file's content hash, exposed to the client build",
    /^[0-9a-f]{16}$/.test(version) && sourceSha.startsWith(version) &&
    nextConfig.env?.NEXT_PUBLIC_HSIN_AVATAR_VERSION === version);
  check("the app loads the versioned avatar URL (same bytes, original stays in public/)",
    /\/avatar\/hsin-\$\{process\.env\.NEXT_PUBLIC_HSIN_AVATAR_VERSION\}\.vrm/.test(read("src/components/presence/avatar-scene.tsx")));

  check("gzip negotiation", acceptsGzip("gzip, deflate, br") && acceptsGzip("br;q=1, gzip;q=0.5") &&
    !acceptsGzip("gzip;q=0") && !acceptsGzip("br") && !acceptsGzip(null) && acceptsGzip("*"));

  const fake = mkdtempSync(join(tmpdir(), "lilith-avatar-"));
  const raw = Buffer.from("glTF-fake-avatar-bytes".repeat(1000));
  const v = createHash("sha256").update(raw).digest("hex").slice(0, 16);
  mkdirSync(join(fake, "public/assets/avatars"), { recursive: true });
  writeFileSync(join(fake, AVATAR_SOURCE), raw);
  const ask = (over: Partial<Parameters<typeof avatarResponse>[0]> = {}) => avatarResponse({
    name: versionedAvatarName(v), version: v, method: "GET", acceptEncoding: "gzip, br", ifNoneMatch: null, root: fake, ...over,
  });
  for (const [label, name] of [["wrong version", "hsin-0000000000000000.vrm"], ["traversal", "../../etc/passwd"],
    ["original file name", "Hsin_FINAL_EXPORT_WORKING_FIXED.vrm"], ["other extension", `hsin-${v}.vrm.gz`]] as const) {
    check(`avatar: ${label} is 404`, ask({ name }).status === 404);
  }
  check("avatar: unknown/invalid build version is 404", ask({ version: undefined }).status === 404 && ask({ version: "zz" }).status === 404);
  const rawRes = ask();
  check("avatar: raw bytes when no compressed copy is packaged (local dev)",
    rawRes.status === 200 && !rawRes.headers.get("content-encoding") &&
    Buffer.from(await rawRes.arrayBuffer()).equals(raw));
  mkdirSync(join(fake, "avatar-cache"));
  writeFileSync(join(fake, "avatar-cache", `${versionedAvatarName(v)}.gz`), gzipSync(raw));
  const gz = ask();
  check("avatar: gzip copy with Content-Encoding: gzip when accepted",
    gz.status === 200 && gz.headers.get("content-encoding") === "gzip" &&
    gz.headers.get("content-type") === "model/gltf-binary" && gz.headers.get("vary") === "Accept-Encoding");
  check("avatar: private immutable caching (never a shared/edge cache), nosniff",
    gz.headers.get("cache-control") === AVATAR_CACHE_CONTROL && AVATAR_CACHE_CONTROL.startsWith("private,") &&
    !/public|s-maxage/.test(AVATAR_CACHE_CONTROL) && gz.headers.get("x-content-type-options") === "nosniff");
  check("avatar: raw when the client does not accept gzip", !ask({ acceptEncoding: "br" }).headers.get("content-encoding"));
  const tag = gz.headers.get("etag");
  check("avatar: per-encoding strong ETags", tag === `"${v}-gz"` && ask({ acceptEncoding: null }).headers.get("etag") === `"${v}"`);
  check("avatar: matching If-None-Match is 304 with no body", ask({ ifNoneMatch: tag }).status === 304 &&
    ask({ ifNoneMatch: `W/${tag}` }).status === 304 && ask({ ifNoneMatch: `"${v}"` }).status === 200);
  const head = ask({ method: "HEAD" });
  check("avatar: HEAD has headers and no body", head.status === 200 && head.body === null && !!head.headers.get("content-length"));

  const saved = { h: process.env.LILITH_HOSTED, v: process.env.NEXT_PUBLIC_HSIN_AVATAR_VERSION };
  try {
    process.env.LILITH_HOSTED = "1"; // incomplete hosted config: must fail closed
    const ctx = { params: Promise.resolve({ asset: versionedAvatarName(version) }) };
    const req = { headers: new Headers(), nextUrl: { origin: "http://localhost:3000" } } as unknown as NextRequest;
    check("avatar route re-checks authentication itself (hosted misconfigured -> 503)",
      (await avatarRoute.GET(req, ctx)).status === 503 && (await avatarRoute.HEAD(req, ctx)).status === 503);
  } finally {
    if (saved.h === undefined) delete process.env.LILITH_HOSTED;
    else process.env.LILITH_HOSTED = saved.h;
  }

  /* ------------------------------------------------ readiness: environment */
  check("readiness env: a complete hosted environment passes", checkEnv(GOOD_ENV).length === 0, checkEnv(GOOD_ENV).join("; "));
  const envCases: [string, string][] = [
    ["NEXT_PUBLIC variable", GOOD_ENV + "NEXT_PUBLIC_LILITH_API_URL=http://10.20.0.5:8765\n"],
    ["Core API on loopback (co-hosted)", GOOD_ENV.replace("http://10.20.0.5:8765", "http://127.0.0.1:8765")],
    ["Core API on localhost", GOOD_ENV.replace("http://10.20.0.5:8765", "http://localhost:8765")],
    ["Core API on a public address", GOOD_ENV.replace("http://10.20.0.5:8765", "http://34.87.1.2:8765")],
    ["short read token", GOOD_ENV.replace("r".repeat(40), "short")],
    ["identical tokens", GOOD_ENV.replace("w".repeat(40), "r".repeat(40))],
    ["owner capture token on the web host", GOOD_ENV + `LILITH_OS_OWNER_CAPTURE_TOKEN=${"c".repeat(40)}\n`],
    ["placeholder value", GOOD_ENV.replace("owner@example.com", "<owner email>")],
    ["hosted mode off", GOOD_ENV.replace("LILITH_HOSTED=1", "LILITH_HOSTED=0")],
    ["public bind", GOOD_ENV + "HOSTNAME=0.0.0.0\n"],
    ["duplicate key", GOOD_ENV + "LILITH_HOSTED=1\n"],
  ];
  for (const [label, env] of envCases) check(`readiness env rejects: ${label}`, checkEnv(env).length > 0);
  check("readiness env: GCP internal DNS name is accepted as private",
    checkEnv(GOOD_ENV.replace("10.20.0.5", "lilith-core.asia-southeast1-b.c.project.internal")).length === 0);
  check("readiness env: the shipped template is flagged until filled in", checkEnv(read("deploy/web/lilith-web.env.template")).length > 0);

  /* ------------------------------------------------ readiness: tunnel routing */
  const tunnel = fillTemplate(read("deploy/web/cloudflared.yml.template"));
  check("readiness tunnel: the shipped template (filled) passes",
    checkCloudflared(tunnel, "https://os.example.com").length === 0, checkCloudflared(tunnel, "https://os.example.com").join("; "));
  const tunnelCases: [string, string][] = [
    ["a second hostname", tunnel.replace("  - service: http_status:404", "  - hostname: admin.example.com\n    service: http://127.0.0.1:3000\n  - service: http_status:404")],
    ["a duplicate rule for the approved hostname", tunnel.replace("  - service: http_status:404", "  - hostname: os.example.com\n    service: http://127.0.0.1:3000\n  - service: http_status:404")],
    ["a route to the Core API", tunnel.replace("http://127.0.0.1:3000", "http://10.20.0.5:8765")],
    ["SSH exposure", tunnel.replace("  - service: http_status:404", "  - hostname: ssh.example.com\n    service: ssh://127.0.0.1:22\n  - service: http_status:404")],
    ["catch-all that is not 404", tunnel.replace("http_status:404", "http://127.0.0.1:3000")],
    ["missing catch-all", tunnel.replace("  - service: http_status:404\n", "")],
    ["wildcard hostname", tunnel.replace("hostname: os.example.com", "hostname: \"*.example.com\"")],
    ["hostname mismatch", tunnel.replace("os.example.com", "other.example.com")],
    ["warp-routing enabled", tunnel.replace("enabled: false", "enabled: true")],
    ["public interface", tunnel.replace("http://127.0.0.1:3000", "http://0.0.0.0:3000")],
  ];
  for (const [label, yaml] of tunnelCases) check(`readiness tunnel rejects: ${label}`, checkCloudflared(yaml, "https://os.example.com").length > 0);

  /* ------------------------------------------------ readiness: systemd unit */
  const unit = read("deploy/web/lilith-web.service");
  check("readiness unit: the shipped service passes", checkUnit(unit).length === 0, checkUnit(unit).join("; "));
  const unitCases: [string, string][] = [
    ["root user", unit.replace("User=lilith-web", "User=root")],
    ["the Core API user", unit.replace("User=lilith-web", "User=lilith")],
    ["public bind", unit.replace("HOSTNAME=127.0.0.1", "HOSTNAME=0.0.0.0")],
    ["other port", unit.replace("PORT=3000", "PORT=8765")],
    ["no NoNewPrivileges", unit.replace("NoNewPrivileges=yes", "NoNewPrivileges=no")],
    ["capabilities", unit.replace("CapabilityBoundingSet=\n", "CapabilityBoundingSet=CAP_NET_BIND_SERVICE\n")],
    ["inlined secret", unit.replace("Environment=PORT=3000", `Environment=PORT=3000\nEnvironment=LILITH_OS_WRITE_TOKEN=${"w".repeat(40)}`)],
    ["no memory limit", unit.replace("MemoryMax=512M\n", "")],
  ];
  for (const [label, text] of unitCases) check(`readiness unit rejects: ${label}`, checkUnit(text).length > 0);
  const hc = read("deploy/web/healthcheck.sh");
  check("health check treats 'served without auth' as critical and checks loopback-only binding",
    /200\)[^\n]*CRITICAL[^\n]*exit 3/.test(hc) && /EDGE_AUTH_REQUIRED/.test(hc) && /127\\\.0\\\.0\\\.1:3000/.test(hc));
  check("periodic check stops the service on an auth regression",
    /rc -eq 3[^\n]*systemctl stop lilith-web\.service/.test(read("deploy/web/lilith-web-health.service")));

  /* ------------------------------------------------ readiness: artifact */
  const goodArtifact = {
    files: ["server.js", "web-artifact.json", ".next/static/chunks/a.js", "public/favicon.ico", "avatar-cache/hsin-x.vrm.gz",
      "node_modules/next/package.json", "node_modules/react/index.js"],
    totalBytes: 150e6, nodeModulesBytes: 31e6,
  };
  check("readiness artifact: a standalone package passes", checkArtifact(goodArtifact).length === 0);
  const artifactCases: [string, Partial<typeof goodArtifact>][] = [
    ["no server.js", { files: goodArtifact.files.filter((f) => f !== "server.js") }],
    ["no static", { files: goodArtifact.files.filter((f) => !f.startsWith(".next/static")) }],
    ["packaged .env", { files: [...goodArtifact.files, ".env.local"] }],
    ["browser source map", { files: [...goodArtifact.files, ".next/static/chunks/a.js.map"] }],
    ["dev dependency", { files: [...goodArtifact.files, "node_modules/typescript/lib/tsc.js"] }],
    ["source tree", { files: [...goodArtifact.files, "src/server/edge-auth/jwt.ts"] }],
    ["full node_modules", { nodeModulesBytes: 600e6 }],
    ["no compressed avatar", { files: goodArtifact.files.filter((f) => !f.startsWith("avatar-cache/")) }],
  ];
  for (const [label, over] of artifactCases) check(`readiness artifact rejects: ${label}`, checkArtifact({ ...goodArtifact, ...over }).length > 0);

  return out;
}
