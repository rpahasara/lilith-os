/**
 * Headless runner for the Cognitive Core self-test (all slices, incl. Slice 4
 * approval-gated write), the memory projection self-test (FM-09) and the
 * owner-protected recording self-test (F5). Bundles
 * the TypeScript with esbuild (resolving the `@/` path alias) and runs it under
 * Node — no browser, no live backend (the transport + task/draft stores are all
 * in-memory fakes).
 *
 *   node scripts/run-core-self-test.mjs
 *
 * Exits non-zero if any scenario fails.
 */
import { build } from "esbuild";
import { pathToFileURL } from "node:url";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(process.cwd());
const out = join(mkdtempSync(join(tmpdir(), "lilith-selftest-")), "bundle.mjs");

await build({
  stdin: {
    contents: `
      import { runCoreSelfTest } from "@/lib/command/core/self-test";
      import { runMemorySelfTest } from "@/lib/memory/self-test";
      import { runConversationSelfTest } from "@/lib/conversation/self-test";
      const results = [...(await runCoreSelfTest()), ...runMemorySelfTest(), ...(await runConversationSelfTest())];
      const failed = results.filter((r) => !r.pass);
      for (const r of results) {
        console.log((r.pass ? "PASS" : "FAIL").padEnd(5) + r.name.padEnd(38) + (r.detail ?? ""));
      }
      console.log("\\n" + (results.length - failed.length) + "/" + results.length + " passed");
      if (failed.length) {
        console.log("FAILURES: " + failed.map((f) => f.name).join(", "));
      }
      globalThis.__lilithExit = failed.length ? 1 : 0;
    `,
    resolveDir: root,
    loader: "ts",
    sourcefile: "self-test-entry.ts",
  },
  bundle: true,
  platform: "node",
  format: "esm",
  target: "node18",
  alias: { "@": join(root, "src"), "next/server": join(root, "scripts", "self-test-next-server-shim.mjs") },
  outfile: out,
  logLevel: "warning",
});

await import(pathToFileURL(out).href);
process.exit(globalThis.__lilithExit ?? 0);
