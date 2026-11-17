/**
 * Headless regression test for the Cognitive Atlas boundary: the preview ships
 * in every build unless it is switched off, it stays reachable from Memory, the
 * simulation says on screen that it is synthetic, and exactly one file —
 * `real-source.ts`, the read-only Real memory projection — talks to the
 * backend. Everything else under `memory/atlas` (the synthetic data and
 * simulation included) reaches real memory only through it, if at all.
 * Real memory's own rules are tested in `real-self-test.ts`.
 *
 * Reads source: the things under test are a route convention and an import
 * boundary. Run by `npm run test:core`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { atlasPreviewEnabled } from "@/lib/memory/atlas/preview";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const src = (...path: string[]) => readFileSync(join(root, "src", ...path), "utf8");

function filesUnder(...path: string[]): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(entry.name) && !/self-test\.ts$/.test(entry.name)) out.push(full);
    }
  };
  walk(join(root, "src", ...path));
  return out;
}

/** Anything that would let the Atlas read or write real data. */
/** The one file allowed to read the backend: the read-only Real memory source. */
const REAL_READER = /lib[\\/]memory[\\/]atlas[\\/]real-source\.ts$/;
const BACKEND_ACCESS = [
  /\bfetch\s*\(/,
  /fetchEndpoint/,
  /from "@\/lib\/api"/,
  /from "@\/lib\/memory\/client"/,
  /from "@\/hooks\/use-memory"/,
  /\/api\/lilith/,
  /XMLHttpRequest|WebSocket|EventSource|sendBeacon/,
];

export function runAtlasPreviewSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `atlas: ${name}`, pass, detail: pass ? undefined : detail });

  /* the gate ----------------------------------------------------------------- */
  check("the preview is included by default, in production too",
    atlasPreviewEnabled(undefined) && atlasPreviewEnabled("") && atlasPreviewEnabled("true"));
  check("the preview is left out only when the flag is exactly \"false\"",
    !atlasPreviewEnabled("false") && atlasPreviewEnabled("0") && atlasPreviewEnabled("FALSE"));
  check("the switch does not depend on the build mode",
    !/NODE_ENV/.test(src("lib", "memory", "atlas", "preview.ts").replace(/\/\*[\s\S]*?\*\//g, "")));

  const layout = src("app", "memory", "atlas", "layout.tsx");
  check("the Atlas route is gated on the server",
    !/"use client"/.test(layout) && /if \(!atlasPreviewEnabled\(\)\) notFound\(\);/.test(layout));

  const archive = src("app", "memory", "page.tsx");
  const switches = archive.match(/<MemoryViewSwitch\b/g) ?? [];
  const gated = archive.match(/ATLAS_PREVIEW && \(\s*<div className="flex justify-end">\s*<MemoryViewSwitch\b/g) ?? [];
  check("the Archive shows the Brain / Archive / Timeline switch only when the preview is on",
    /const ATLAS_PREVIEW = atlasPreviewEnabled\(\);/.test(archive) && switches.length > 0 && gated.length === switches.length,
    `${gated.length} of ${switches.length} gated`);
  check("the switch stays reachable when Memory data is unavailable",
    /<WorkspaceUnavailable[\s\S]*?\/>\s*\{ATLAS_PREVIEW && \(/.test(archive));

  const flagReaders = filesUnder().filter((file) =>
    /process\.env\.NEXT_PUBLIC_LILITH_ATLAS_PREVIEW/.test(readFileSync(file, "utf8")));
  check("the preview flag is read in exactly one place",
    flagReaders.length === 1 && /preview\.ts$/.test(flagReaders[0]), flagReaders.join(", "));

  /* synthetic only ------------------------------------------------------------- */
  const atlasFiles = [
    ...filesUnder("lib", "memory", "atlas"),
    ...filesUnder("components", "memory", "atlas"),
    ...filesUnder("app", "memory", "atlas"),
  ];
  const offenders: string[] = [];
  for (const file of atlasFiles) {
    if (REAL_READER.test(file)) continue;
    const text = readFileSync(file, "utf8");
    for (const pattern of BACKEND_ACCESS) {
      if (pattern.test(text)) offenders.push(`${file.slice(root.length + 1)} ~ ${pattern.source}`);
    }
  }
  check("the Atlas has files to check", atlasFiles.length >= 15, String(atlasFiles.length));
  check("only the read-only Real memory source reads the backend", offenders.length === 0, offenders.join("; "));
  check("the Real memory source exists and is the only reader",
    atlasFiles.filter((f) => REAL_READER.test(f)).length === 1);

  const atlas = src("components", "memory", "atlas", "cognitive-atlas.tsx");
  check("the simulation says on screen that it is a preview on synthetic data",
    /Preview · Synthetic data/.test(atlas) && /not connected to Lilith's real memory/.test(atlas));
  check("the Atlas inspector says nothing real is read or changed",
    /Nothing real is read or changed/.test(src("components", "memory", "atlas", "atlas-inspector.tsx")));
  check("simulated recall and activity are marked as simulated",
    /Simulated recall/.test(src("components", "memory", "atlas", "recall-console.tsx")) &&
      /Simulated/.test(src("components", "memory", "atlas", "cognition-feed.tsx")));
  check("the Atlas route names itself a preview in its title",
    /Cognitive Atlas Preview/.test(src("app", "memory", "atlas", "layout.tsx")));

  return out;
}
