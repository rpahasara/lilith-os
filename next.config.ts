import type { NextConfig } from "next";
import { SECURITY_HEADERS } from "./src/server/web-hosting/security-headers";
import { AVATAR_SOURCE, versionOfFile } from "./src/server/web-hosting/avatar";

// Content version of the Hsin avatar (first 16 hex of its SHA-256). The app
// loads /avatar/hsin-<version>.vrm, which can therefore be cached as immutable.
// Computed when the config loads (build / dev start); not a secret.
const avatarVersion = versionOfFile(AVATAR_SOURCE);

// The CSP is production-only: `next dev` needs 'unsafe-eval' for Fast Refresh.
const headers =
  process.env.NODE_ENV === "production"
    ? SECURITY_HEADERS
    : SECURITY_HEADERS.filter((h) => h.key !== "Content-Security-Policy");

const nextConfig: NextConfig = {
  // Self-contained server (.next/standalone) with only the traced runtime
  // dependencies; scripts/package-web.mjs adds .next/static, public/ and the
  // compressed avatar to form the deployable artifact.
  output: "standalone",
  // React Compiler is disabled: react-three-fiber relies heavily on mutable
  // refs inside useFrame, and we want fully predictable render behaviour for
  // the 3D presence scene. Re-enable later once the scene is stable.
  reactCompiler: false,
  transpilePackages: ["three"],
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_HSIN_AVATAR_VERSION: avatarVersion,
  },
  async headers() {
    return [{ source: "/:path*", headers: [...headers] }];
  },
};

export default nextConfig;
