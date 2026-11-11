/**
 * Scan the production CLIENT bundle (.next/static) for development-only
 * diagnostics that must never ship. Run after `npm run build`:
 *
 *   npm run build && npm run scan:bundle            # dev-only diagnostics
 *   npm run build && npm run scan:bundle -- --demo  # + fabricated home data
 *
 * Exits non-zero, listing each marker and the chunk it was found in. The
 * markers are the fixed prefixes of the development-only Hsin/presence
 * diagnostics (see src/lib/diagnostics.ts); their call sites are guarded by
 * `if (DEV_DIAGNOSTICS)`, so the minifier must have removed them.
 */
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

const STATIC_DIR = join(process.cwd(), ".next", "static");

export const DEV_LOG_MARKERS = [
  "[Hsin LookAt]",
  "[Hsin VRMA idle]",
  "[Hsin ambient idle]",
  "[Hsin arm IK]",
  "[Hsin arm anatomy view]",
  "[Hsin blink]",
  "[Hsin hand inspect]",
  "[Hsin hand override] tracks=", // the bare tag is also a (functional) clip name
  "[Hsin material fallback]",
  "[Hsin neutral geometry]",
  "[Hsin normalized rest test]",
  "[Hsin pose diagnostic]",
  "[Hsin presentation state]",
  "[Hsin rare motion]",
  "[Hsin spring diagnostic]",
  "[Hsin spring init test]",
  "[Hsin visemes]",
  "WebGL context restored",
  "[HSIN_CANONICAL_NEUTRAL]",
  "[Lilith perf guard]",
  // Server-only web authentication internals (src/server/edge-auth): must never reach the browser.
  "cdn-cgi/access/certs",
  "cf-access-jwt-assertion",
  "LILITH_ACCESS_AUD",
  "LILITH_OWNER_EMAILS",
  "LILITH_ACCESS_TEAM_DOMAIN",
  "HOSTED_AUTH_MISCONFIGURED",
];

/**
 * With `--demo`: fabricated "owner day" facts from src/lib/data.ts that the
 * Command Center used to present as live (see #422). They must not ship in the
 * client bundle at all. (Workspace demo adapters, which are labelled as demo,
 * are intentionally not listed.)
 */
export const DEMO_DATA_MARKERS = [
  "Product Strategy Sync",
  "Deep Focus Room",
  "Project Nova review due",
  "Recommended 2h",
  "2 high priority",
  "Summarised 14 unread threads",
  "Learned 6 new facts about Project Nova",
];

const CHECK_DEMO = process.argv.includes("--demo");
const MARKERS = CHECK_DEMO ? [...DEV_LOG_MARKERS, ...DEMO_DATA_MARKERS] : DEV_LOG_MARKERS;

function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : p.endsWith(".js") ? [p] : [];
  });
}

if (!existsSync(STATIC_DIR)) {
  console.error("No .next/static found. Run `npm run build` first.");
  process.exit(2);
}

const chunks = files(STATIC_DIR);
const found = [];
for (const file of chunks) {
  const src = readFileSync(file, "utf8");
  for (const marker of MARKERS) if (src.includes(marker)) found.push({ marker, file });
}

console.log(`scanned ${chunks.length} client chunks for ${MARKERS.length} markers (dev logs${CHECK_DEMO ? " + demo data" : ""})`);
if (found.length) {
  for (const f of found) console.log(`FOUND ${f.marker}  in ${f.file}`);
  process.exit(1);
}
console.log(`PASS no development-only diagnostics${CHECK_DEMO ? " or fabricated home data" : ""} in the production client bundle`);
