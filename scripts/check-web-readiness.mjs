/**
 * Deployment-readiness check for the private web preview. Offline: reads files,
 * never contacts a host.
 *
 *   node scripts/check-web-readiness.mjs \
 *     --artifact dist/lilith-web \
 *     --env /etc/lilith-web/env \
 *     --cloudflared /etc/cloudflared/config.yml \
 *     --unit /etc/systemd/system/lilith-web.service
 *
 * Any option may be omitted to skip that check. Exits non-zero on any problem.
 * The rules live in src/server/web-hosting/readiness.ts (unit-tested).
 */
import { build } from "esbuild";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, readdirSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { gunzipSync } from "node:zlib";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const root = resolve(process.cwd());
const bundle = join(mkdtempSync(join(tmpdir(), "lilith-readiness-")), "readiness.mjs");
await build({
  entryPoints: [join(root, "src/server/web-hosting/readiness.ts")],
  bundle: true, platform: "node", format: "esm", target: "node18", outfile: bundle, logLevel: "warning",
  alias: { "@": join(root, "src") },
});
const r = await import(pathToFileURL(bundle).href);

const report = [];
const section = (name, problems) => {
  report.push([name, problems]);
  console.log(`${problems.length ? "FAIL" : "PASS"} ${name}`);
  for (const p of problems) console.log(`     - ${p}`);
};

let envText = null;
if (args.env) {
  envText = readFileSync(args.env, "utf8");
  const problems = r.checkEnv(envText);
  if (process.platform !== "win32") {
    const mode = statSync(args.env).mode & 0o777;
    if (mode & 0o007) problems.push(`env file is world-accessible (mode ${mode.toString(8)}); use 0640 or 0600`);
  }
  section("server-only environment and hosted authentication", problems);
}
if (args.cloudflared) {
  const origin = envText ? r.parseEnvFile(envText).env.LILITH_PUBLIC_ORIGIN ?? "" : args.origin ?? "";
  section("Cloudflare Tunnel routing", r.checkCloudflared(readFileSync(args.cloudflared, "utf8"), origin));
}
if (args.unit) section("systemd service hardening and binding", r.checkUnit(readFileSync(args.unit, "utf8")));
if (args.artifact) {
  const dir = resolve(args.artifact);
  const walk = (d) => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]));
  const all = existsSync(dir) ? walk(dir) : [];
  const files = all.map((f) => relative(dir, f).split(sep).join("/"));
  const size = (pred) => all.filter((f, i) => pred(files[i])).reduce((n, f) => n + statSync(f).size, 0);
  const problems = r.checkArtifact({ files, totalBytes: size(() => true), nodeModulesBytes: size((f) => f.startsWith("node_modules/")) });
  if (existsSync(join(dir, "web-artifact.json"))) {
    const m = JSON.parse(readFileSync(join(dir, "web-artifact.json"), "utf8"));
    const gzPath = join(dir, "avatar-cache", `hsin-${m.avatar.version}.vrm.gz`);
    const srcPath = join(dir, m.avatar.source);
    if (!existsSync(gzPath) || !existsSync(srcPath)) problems.push("packaged avatar files are missing");
    else {
      const sha = (b) => createHash("sha256").update(b).digest("hex");
      if (sha(readFileSync(srcPath)) !== m.avatar.sha256) problems.push("packaged avatar does not match the manifest hash");
      if (sha(gunzipSync(readFileSync(gzPath))) !== m.avatar.sha256) problems.push("compressed avatar does not decompress to the original");
    }
  }
  // Client bundle must not contain dev diagnostics, fabricated data or server-only auth internals.
  const { execFileSync } = await import("node:child_process");
  try {
    execFileSync(process.execPath, [join(root, "scripts/scan-prod-bundle.mjs"), "--demo", "--static", join(dir, ".next/static")], { stdio: "pipe" });
  } catch (e) {
    problems.push(`client bundle scan failed: ${String(e.stdout ?? e.message).trim().split("\n").slice(-3).join(" | ")}`);
  }
  section("standalone artifact", problems);
}

const failed = report.filter(([, p]) => p.length).length;
console.log(failed ? `\nNOT READY: ${failed} check(s) failed` : `\nREADY: ${report.length} check(s) passed`);
process.exit(failed ? 1 : 0);
