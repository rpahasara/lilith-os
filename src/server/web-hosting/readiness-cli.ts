/**
 * Readiness CLI. Bundled at packaging time into the release artifact as a
 * single dependency-free file, `bin/check-readiness.mjs` (Node built-ins
 * only), so the destination host can verify an installation without the
 * repository or any development dependency.
 *
 *   node bin/check-readiness.mjs --artifact <release dir> --env <env file> \
 *        --cloudflared <config.yml> --unit <lilith-web.service>
 *
 * Any option may be omitted to skip that check. Exits non-zero on any problem.
 */
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";
import { checkArtifact, checkCloudflared, checkEnv, checkUnit, parseEnvFile } from "./readiness";
import { isLfsPointer, looksLikeGlb } from "./avatar";

function argMap(argv: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[i + 1] ?? "";
  return out;
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    const s = statSync(p);
    return s.isDirectory() ? walk(p) : [p];
  });
}

/** CLI output goes to stdout directly (this is a command-line tool, not app logging). */
function say(line: string): void {
  process.stdout.write(`${line}\n`);
}

export function main(argv: string[] = process.argv.slice(2), here = dirname(fileURLToPath(import.meta.url))): number {
  const args = argMap(argv);
  const report: [string, string[]][] = [];
  const section = (name: string, problems: string[]) => {
    report.push([name, problems]);
    say(`${problems.length ? "FAIL" : "PASS"} ${name}`);
    for (const p of problems) say(`     - ${p}`);
  };

  let envText: string | null = null;
  if (args.env) {
    envText = readFileSync(args.env, "utf8");
    const problems = checkEnv(envText);
    if (process.platform !== "win32") {
      const mode = statSync(args.env).mode & 0o777;
      if (mode & 0o007) problems.push(`env file is world-accessible (mode ${mode.toString(8)}); use 0640 or 0600`);
    }
    section("server-only environment and hosted authentication", problems);
  }
  if (args.cloudflared) {
    const origin = envText ? parseEnvFile(envText).env.LILITH_PUBLIC_ORIGIN ?? "" : args.origin ?? "";
    section("Cloudflare Tunnel routing", checkCloudflared(readFileSync(args.cloudflared, "utf8"), origin));
  }
  if (args.unit) section("systemd service hardening and binding", checkUnit(readFileSync(args.unit, "utf8")));
  if (args.artifact) {
    const dir = resolve(args.artifact);
    const all = existsSync(dir) ? walk(dir) : [];
    const files = all.map((f) => relative(dir, f).split(sep).join("/"));
    const size = (pred: (f: string) => boolean) => all.filter((_, i) => pred(files[i])).reduce((n, f) => n + statSync(f).size, 0);
    const problems = checkArtifact({ files, totalBytes: size(() => true), nodeModulesBytes: size((f) => f.startsWith("node_modules/")) });
    const manifestPath = join(dir, "web-artifact.json");
    if (existsSync(manifestPath)) {
      const m = JSON.parse(readFileSync(manifestPath, "utf8"));
      const gzPath = join(dir, "avatar-cache", `hsin-${m.avatar.version}.vrm.gz`);
      const srcPath = join(dir, m.avatar.source);
      const sha = (b: Buffer) => createHash("sha256").update(b).digest("hex");
      if (!existsSync(gzPath) || !existsSync(srcPath)) problems.push("packaged avatar files are missing");
      else {
        const avatarBytes = readFileSync(srcPath);
        if (!looksLikeGlb(avatarBytes)) {
          problems.push(isLfsPointer(avatarBytes)
            ? "packaged avatar is a Git LFS pointer, not the model (release built without `git lfs pull`)"
            : "packaged avatar is not a valid binary glTF (GLB/VRM)");
        }
        if (sha(avatarBytes) !== m.avatar.sha256) problems.push("packaged avatar does not match the manifest hash");
        if (sha(gunzipSync(readFileSync(gzPath))) !== m.avatar.sha256) problems.push("compressed avatar does not decompress to the original");
      }
    }
    const scanner = args.scanner || join(here, "scan-prod-bundle.mjs");
    if (!existsSync(scanner)) problems.push(`client bundle scanner not found (${scanner})`);
    else {
      try {
        execFileSync(process.execPath, [scanner, "--demo", "--static", join(dir, ".next/static")], { stdio: "pipe" });
      } catch (e) {
        const out = String((e as { stdout?: Buffer }).stdout ?? (e as Error).message).trim().split("\n").slice(-3).join(" | ");
        problems.push(`client bundle scan failed: ${out}`);
      }
    }
    section("standalone artifact", problems);
  }

  const failed = report.filter(([, p]) => p.length).length;
  say(failed ? `\nNOT READY: ${failed} check(s) failed` : `\nREADY: ${report.length} check(s) passed`);
  return failed ? 1 : 0;
}
