/**
 * Readiness check from a repository checkout (build/release environment).
 * The same CLI ships inside every release artifact as `bin/check-readiness.mjs`
 * (dependency-free), which is what you run on the web VM; see deploy/web/INSTALL.md.
 *
 *   node scripts/check-web-readiness.mjs --artifact dist/lilith-web [--env ...] [--cloudflared ...] [--unit ...]
 */
import { build } from "esbuild";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const root = resolve(process.cwd());
const outfile = join(mkdtempSync(join(tmpdir(), "lilith-readiness-")), "check-readiness.mjs");
await build({
  entryPoints: [join(root, "src/server/web-hosting/readiness-cli.ts")],
  bundle: true, platform: "node", format: "esm", target: "node20", outfile, logLevel: "warning",
  alias: { "@": join(root, "src") },
});
const { main } = await import(pathToFileURL(outfile).href);
const argv = process.argv.slice(2);
if (!argv.includes("--scanner")) argv.push("--scanner", join(root, "scripts/scan-prod-bundle.mjs"));
process.exit(main(argv));
