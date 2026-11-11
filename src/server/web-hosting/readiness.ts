/**
 * Deployment-readiness checks for the private web preview (pure; no network).
 * Used by scripts/check-web-readiness.mjs and the headless self-test.
 *
 * Each check returns a list of problems; an empty list means ready. The rules
 * encode the hosting design (#420 §2 and the H1/H2 records):
 * - the web VM is separate from the Core API host, so LILITH_API_URL must be a
 *   PRIVATE, non-loopback address (a loopback Core API would treat this server
 *   as the trusted on-host router: LILITH_OS_TRUST_LOOPBACK);
 * - hosted authentication is fully configured; nothing is NEXT_PUBLIC_;
 * - the server binds 127.0.0.1:3000 only, as an unprivileged dedicated user;
 * - Cloudflare Tunnel routes exactly one hostname to it and 404s everything else.
 */
import { readEdgeAuthConfig } from "@/server/edge-auth/config";

export function parseEnvFile(text: string): { env: Record<string, string>; problems: string[] } {
  const env: Record<string, string> = {};
  const problems: string[] = [];
  text.split(/\r?\n/).forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith("#")) return;
    const m = /^([A-Z][A-Z0-9_]*)=(.*)$/.exec(line);
    if (!m) {
      problems.push(`env line ${i + 1} is not KEY=VALUE`);
      return;
    }
    let value = m[2].trim();
    if (/^(["']).*\1$/.test(value)) value = value.slice(1, -1);
    if (m[1] in env) problems.push(`env key ${m[1]} is defined twice`);
    env[m[1]] = value;
  });
  return { env, problems };
}

const PLACEHOLDER = /^<.*>$|changeme|replace[-_ ]?me|example-token|xxx+/i;

function isPrivateHost(host: string): boolean {
  if (/\.internal$/i.test(host)) return true; // GCP internal DNS (<vm>.<zone>.c.<project>.internal)
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);
  if (!m) return false;
  const [a, b] = [Number(m[1]), Number(m[2])];
  return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
}

export function checkEnv(text: string): string[] {
  const { env, problems } = parseEnvFile(text);
  for (const [k, v] of Object.entries(env)) {
    if (k.startsWith("NEXT_PUBLIC_")) problems.push(`${k}: no NEXT_PUBLIC_ variables in the server environment`);
    if (PLACEHOLDER.test(v)) problems.push(`${k}: still a placeholder`);
  }
  const cfg = readEdgeAuthConfig(env);
  if (cfg.mode !== "hosted") {
    problems.push(`hosted authentication is not valid: ${cfg.mode === "misconfigured" ? cfg.problems.join("; ") : "LILITH_HOSTED is not 1"}`);
  }
  try {
    const api = new URL(env.LILITH_API_URL ?? "");
    if (!/^https?:$/.test(api.protocol)) problems.push("LILITH_API_URL must be http(s)");
    if (!isPrivateHost(api.hostname)) {
      problems.push("LILITH_API_URL must be the Core API's PRIVATE address (RFC 1918 or *.internal), never loopback or public");
    }
  } catch {
    problems.push("LILITH_API_URL is missing or invalid");
  }
  for (const k of ["LILITH_OS_READ_TOKEN", "LILITH_OS_WRITE_TOKEN"]) {
    if ((env[k] ?? "").length < 32) problems.push(`${k} must be set (32+ characters)`);
  }
  if (env.LILITH_OS_READ_TOKEN && env.LILITH_OS_READ_TOKEN === env.LILITH_OS_WRITE_TOKEN) {
    problems.push("read and write tokens must differ");
  }
  if ("LILITH_OS_OWNER_CAPTURE_TOKEN" in env) {
    problems.push("LILITH_OS_OWNER_CAPTURE_TOKEN must not be on the web host (owner capture is not a web capability)");
  }
  if (env.HOSTNAME !== undefined && env.HOSTNAME !== "127.0.0.1") problems.push("HOSTNAME must be 127.0.0.1");
  if (env.PORT !== undefined && env.PORT !== "3000") problems.push("PORT must be 3000");
  return problems;
}

interface IngressRule {
  hostname?: string;
  service?: string;
  path?: string;
}

export function parseIngress(yaml: string): { rules: IngressRule[]; warpRouting: boolean } {
  const rules: IngressRule[] = [];
  let inIngress = false;
  let warpRouting = false;
  let inWarp = false;
  for (const raw of yaml.split(/\r?\n/)) {
    const line = raw.replace(/\s+#.*$/, "");
    if (!line.trim() || line.trim().startsWith("#")) continue;
    if (/^\S/.test(line)) {
      inIngress = /^ingress:\s*$/.test(line);
      inWarp = /^warp-routing:\s*$/.test(line);
      continue;
    }
    if (inWarp && /^\s+enabled:\s*true\s*$/i.test(line)) warpRouting = true;
    if (!inIngress) continue;
    const item = /^\s*-\s+(\w+):\s*(.+?)\s*$/.exec(line);
    const field = /^\s+(\w+):\s*(.+?)\s*$/.exec(line);
    if (item) rules.push({ [item[1]]: item[2] } as IngressRule);
    else if (field && rules.length && ["hostname", "service", "path"].includes(field[1])) {
      (rules[rules.length - 1] as Record<string, string>)[field[1]] = field[2];
    }
  }
  return { rules, warpRouting };
}

export function checkCloudflared(yaml: string, publicOrigin: string): string[] {
  const problems: string[] = [];
  const { rules, warpRouting } = parseIngress(yaml);
  if (warpRouting) problems.push("warp-routing must stay disabled (it would expose the private network)");
  let host = "";
  try {
    host = new URL(publicOrigin).hostname;
  } catch {
    problems.push("public origin is invalid");
  }
  const named = rules.filter((r) => r.hostname !== undefined);
  if (named.length !== 1) problems.push(`exactly one hostname rule is allowed (found ${named.length})`);
  for (const r of named) {
    if (r.hostname !== host) problems.push(`hostname ${r.hostname} is not the approved public host ${host}`);
    if (/[*]/.test(r.hostname ?? "")) problems.push("wildcard hostnames are not allowed");
    if (r.path !== undefined) problems.push("path-scoped rules are not allowed");
    if (!/^http:\/\/(127\.0\.0\.1|localhost):3000\/?$/.test(r.service ?? "")) {
      problems.push(`the hostname must route only to http://127.0.0.1:3000 (found ${r.service})`);
    }
  }
  const last = rules[rules.length - 1];
  if (!last || last.hostname !== undefined || last.service !== "http_status:404") {
    problems.push("the final (catch-all) rule must be service: http_status:404");
  }
  const services = rules.map((r) => r.service ?? "");
  if (services.some((s) => /:8765\b|ssh:|rdp:|tcp:|unix:|hello_world|bastion|socks/i.test(s))) {
    problems.push("no rule may reach the Core API, SSH, raw TCP or other services");
  }
  if (rules.length !== 2) problems.push(`expected exactly 2 ingress rules (found ${rules.length})`);
  return problems;
}

function directive(unit: string, key: string): string[] {
  return unit.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.startsWith(`${key}=`)).map((l) => l.slice(key.length + 1));
}

export function checkUnit(unit: string): string[] {
  const problems: string[] = [];
  const user = directive(unit, "User")[0];
  if (!user) problems.push("User= is required");
  else if (["root", "lilith", "lilith-authority-dev", "lilith-memory-broker"].includes(user)) {
    problems.push(`User=${user} is not allowed: use a dedicated unprivileged web user`);
  }
  const envs = directive(unit, "Environment").join(" ");
  if (!/\bHOSTNAME=127\.0\.0\.1\b/.test(envs)) problems.push("Environment=HOSTNAME=127.0.0.1 is required");
  if (!/\bPORT=3000\b/.test(envs)) problems.push("Environment=PORT=3000 is required");
  if (!/\bNODE_ENV=production\b/.test(envs)) problems.push("Environment=NODE_ENV=production is required");
  const want: Record<string, string> = {
    NoNewPrivileges: "yes", ProtectSystem: "strict", ProtectHome: "yes", PrivateTmp: "yes", PrivateDevices: "yes",
    ProtectKernelTunables: "yes", ProtectKernelModules: "yes", ProtectControlGroups: "yes", RestrictSUIDSGID: "yes",
    LockPersonality: "yes", Restart: "on-failure",
  };
  for (const [k, v] of Object.entries(want)) {
    if (directive(unit, k)[0] !== v) problems.push(`${k}=${v} is required`);
  }
  if (directive(unit, "CapabilityBoundingSet")[0] !== "") problems.push("CapabilityBoundingSet= (empty) is required");
  if (!directive(unit, "MemoryMax")[0]) problems.push("MemoryMax= is required");
  if (!directive(unit, "EnvironmentFile")[0]) problems.push("EnvironmentFile= is required (secrets stay out of the unit)");
  if (/LILITH_OS_(READ|WRITE)_TOKEN|_API_KEY/.test(envs)) problems.push("secrets must not be inlined in the unit");
  return problems;
}

export interface ArtifactListing {
  files: string[]; // relative POSIX paths
  totalBytes: number;
  nodeModulesBytes: number;
}

export function checkArtifact(listing: ArtifactListing): string[] {
  const problems: string[] = [];
  const has = (p: string) => listing.files.includes(p);
  const under = (prefix: string) => listing.files.some((f) => f.startsWith(prefix));
  if (!has("server.js")) problems.push("server.js is missing (not a standalone build)");
  if (!under(".next/static/")) problems.push(".next/static is missing");
  if (!under("public/")) problems.push("public/ is missing");
  if (!has("web-artifact.json")) problems.push("web-artifact.json manifest is missing");
  if (!under("avatar-cache/")) problems.push("the compressed avatar is missing");
  for (const f of ["bin/check-readiness.mjs", "bin/scan-prod-bundle.mjs", "bin/healthcheck.sh", "bin/install-release.sh",
    "bin/rollback.sh", "deploy/lilith-web.service", "deploy/lilith-web-health.service", "deploy/lilith-web-health.timer",
    "deploy/cloudflared.yml.template", "deploy/lilith-web.env.template", "INSTALL.md"]) {
    if (!has(f)) problems.push(`install kit file missing: ${f}`);
  }
  for (const f of listing.files) {
    const base = f.split("/").pop() ?? "";
    if (/^\.env/.test(base)) problems.push(`${f}: environment files must not be packaged`);
    if (f.startsWith(".next/static/") && f.endsWith(".map")) problems.push(`${f}: no browser source maps`);
    if (/^node_modules\/(typescript|esbuild|eslint|tailwindcss|@types|@tailwindcss|babel-plugin-react-compiler)\//.test(f)) {
      problems.push(`${f}: development dependency packaged`);
    }
    if (/^(src|scripts|services|integrations|docs|\.git)\//.test(f)) problems.push(`${f}: source tree packaged`);
  }
  if (listing.nodeModulesBytes > 80 * 1024 * 1024) problems.push("node_modules exceeds 80 MB (full install packaged?)");
  return problems;
}
