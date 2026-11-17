/**
 * Headless regression test for the data-mode rule: a workspace that cannot
 * reach the backend is `unavailable`, and sample data appears only by explicit
 * opt-in. Also holds the Command Center to claims it can back.
 *
 * No browser and no backend: `fetch` is replaced for the duration of the test.
 * Run by `npm run test:core`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { getAutomationsData } from "@/lib/automations/client";
import { getCareerData } from "@/lib/career/client";
import { matchRealIntent } from "@/lib/command/core/intents";
import { DEMO_SUGGESTIONS, REAL_SUGGESTIONS, defaultSuggestions } from "@/lib/command/suggestions";
import {
  demoCommandsEnabled,
  demoDataEnabled,
  isUnavailable,
  simulationAllowed,
  unavailableReason,
  type Loaded,
} from "@/lib/data-mode";
import { getMeetingsData } from "@/lib/meetings/client";
import { getMemoryData } from "@/lib/memory/client";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

type Loader = (signal?: AbortSignal, demo?: boolean) => Promise<Loaded<{ isDemo: boolean }>>;

const LOADERS: Record<string, Loader> = {
  career: getCareerData,
  automations: getAutomationsData,
  meetings: getMeetingsData,
  memory: getMemoryData,
};

/** Run `fn` with every backend request answered by `respond`. */
async function withBackend<T>(respond: () => Response | Promise<Response>, fn: () => Promise<T>): Promise<T> {
  const real = globalThis.fetch;
  globalThis.fetch = (async () => respond()) as typeof fetch;
  try {
    return await fn();
  } finally {
    globalThis.fetch = real;
  }
}

const status = (code: number) => () => new Response("{}", { status: code });
const offline = () => Promise.reject(new TypeError("fetch failed"));

function source(...path: string[]): string {
  return readFileSync(join(process.cwd(), "src", ...path), "utf8");
}

export async function runDataModeSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `data-mode: ${name}`, pass, detail: pass ? undefined : detail });

  /* the opt-in ------------------------------------------------------------- */
  check("sample data is off unless the flag is exactly \"true\"",
    !demoDataEnabled(undefined, "development") && !demoDataEnabled("", "development") &&
      !demoDataEnabled("false", "development") && !demoDataEnabled("1", "development") &&
      !demoDataEnabled("TRUE", "development") && demoDataEnabled("true", "development"));

  /* the production guard ----------------------------------------------------- */
  check("a production build never enables sample data, whatever the flag says",
    !demoDataEnabled("true", "production") && !simulationAllowed("production") &&
      simulationAllowed("development") && simulationAllowed(undefined));
  check("a production build never enables the scripted demo commands",
    !demoCommandsEnabled("true", "production") && demoCommandsEnabled("true", "development") &&
      !demoCommandsEnabled("false", "development") && !demoCommandsEnabled(undefined, "development"));
  {
    // The flags are read in exactly one place, so the guard cannot be bypassed.
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (/\.(ts|tsx)$/.test(entry.name) && !/self-test\.ts$/.test(entry.name)) {
          const text = readFileSync(full, "utf8");
          if (/process\.env\.NEXT_PUBLIC_LILITH_(DEMO_DATA|ENABLE_DEMO_COMMANDS)/.test(text)) offenders.push(full);
        }
      }
    };
    walk(join(process.cwd(), "src"));
    check("the demo flags are read only by the data-mode module",
      offenders.length === 1 && /data-mode\.ts$/.test(offenders[0]), offenders.join(", "));
  }

  /* every workspace, every way the backend can be absent --------------------- */
  const absences: Record<string, () => Response | Promise<Response>> = {
    "bad gateway (502)": status(502),
    "no backend configured (503)": status(503),
    "network failure": offline,
  };
  for (const [workspace, load] of Object.entries(LOADERS)) {
    for (const [how, respond] of Object.entries(absences)) {
      const result = await withBackend(respond, () => load(undefined, false));
      check(`${workspace}: ${how} is unavailable, never sample data`,
        isUnavailable(result) && result.diagnostics.mode === "unavailable" &&
          result.diagnostics.endpoints.every((e) => !e.ok),
        JSON.stringify(result).slice(0, 160));
    }
    const sample = await withBackend(status(502), () => load(undefined, true));
    check(`${workspace}: with the opt-in, sample data is returned and flagged`,
      !isUnavailable(sample) && sample.isDemo === true,
      JSON.stringify(sample).slice(0, 120));
  }

  const empty = await withBackend(status(200), () => getAutomationsData(undefined, false));
  check("automations: a backend that answers with no units is live and empty",
    !isUnavailable(empty) && empty.isDemo === false && empty.units.length === 0,
    JSON.stringify(empty).slice(0, 160));

  /* what the unavailable state tells the owner ------------------------------ */
  const unconfigured = await withBackend(status(503), () => getCareerData(undefined, false));
  const unreachable = await withBackend(offline, () => getCareerData(undefined, false));
  check("a 503 from every endpoint reads as \"no backend configured\"",
    isUnavailable(unconfigured) && /No backend is configured/.test(unavailableReason(unconfigured.diagnostics)));
  check("a network failure reads as \"not reachable\"",
    isUnavailable(unreachable) && /not reachable/.test(unavailableReason(unreachable.diagnostics)));

  /* the pages -------------------------------------------------------------- */
  for (const workspace of Object.keys(LOADERS)) {
    const page = source("app", workspace, "page.tsx");
    check(`${workspace} page renders the unavailable state and marks sample data`,
      /<WorkspaceUnavailable/.test(page) && /data\.isDemo && <DemoBanner \/>/.test(page));
    check(`${workspace} page never builds sample data itself`, !/buildDemo/.test(page));
    const client = source("lib", workspace, "client.ts");
    const guard = client.indexOf("if (!demo) return unavailable(results);");
    const build = client.search(/buildDemo\w+\(\)/);
    check(`${workspace} client refuses before it reaches the sample data`,
      guard > 0 && build > guard, `guard@${guard} build@${build}`);
  }

  /* claims on the Command Center -------------------------------------------- */
  check("every default suggestion maps to a real intent",
    REAL_SUGGESTIONS.every((s) => matchRealIntent(s) !== null),
    REAL_SUGGESTIONS.filter((s) => matchRealIntent(s) === null).join(", "));
  check("demo suggestions appear only when demo commands are enabled",
    defaultSuggestions(false).length === REAL_SUGGESTIONS.length &&
      defaultSuggestions(false).every((s) => !DEMO_SUGGESTIONS.includes(s as (typeof DEMO_SUGGESTIONS)[number])) &&
      DEMO_SUGGESTIONS.every((s) => defaultSuggestions(true).includes(s)));

  const hero = source("components", "presence", "presence-hero.tsx");
  check("the hero makes no static \"Presence online\" claim", !/Presence online/.test(hero));
  check("manual presence chips sit behind the presence debug flag",
    /SHOW_PRESENCE_CONTROLS && \(/.test(hero) &&
      /NEXT_PUBLIC_PRESENCE_DEBUG === "1"/.test(hero));
  check("Automations does not call sample data \"live\"",
    !/—\s*live/i.test(source("components", "automations", "automations-header.tsx")));
  check("no internal slice or baseline labels in the UI",
    !/eyebrow="Slice/.test(source("app", "world", "page.tsx")) &&
      !/value="Home V2|status="Module-owned"/.test(source("app", "system", "page.tsx") + source("components", "system", "system-workspace.tsx")));

  return out;
}
