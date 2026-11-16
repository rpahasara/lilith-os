/**
 * Headless self-test for the shell health probe (status capsule). Fakes only:
 * no browser, no backend. Run by `npm run test:core`.
 */
import type { EndpointResult } from "@/lib/api";
import {
  SHELL_HEALTH_PATH,
  deriveShellHealth,
  probeShellHealth,
  shellHealthLabel,
} from "./shell-health";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const NOW = new Date("2026-11-11T12:00:00.000Z");

function res(ok: boolean, status: number): EndpointResult {
  return { path: SHELL_HEALTH_PATH, ok, status, data: null };
}

export async function runShellHealthSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `shell-health: ${name}`, pass, detail: pass ? undefined : detail });

  const live = deriveShellHealth(res(true, 200), 41.6, NOW);
  check("2xx is live with rounded latency",
    live.state === "live" && live.latencyMs === 42 && live.checkedAt === NOW.toISOString(),
    JSON.stringify(live));

  const unconfigured = deriveShellHealth(res(false, 503), 5, NOW);
  check("503 (proxy unconfigured) is unconfigured, no latency",
    unconfigured.state === "unconfigured" && unconfigured.latencyMs === null, JSON.stringify(unconfigured));

  for (const status of [0, 401, 403, 404, 500, 502, 504]) {
    const h = deriveShellHealth(res(false, status), 5, NOW);
    check(`HTTP ${status} is unreachable, no latency`,
      h.state === "unreachable" && h.latencyMs === null && h.httpStatus === status,
      JSON.stringify(h));
  }

  check("negative elapsed clamps to 0",
    deriveShellHealth(res(true, 200), -3, NOW).latencyMs === 0);

  check("labels never claim more than measured",
    shellHealthLabel({ state: "unconfigured", latencyMs: null, httpStatus: 503, checkedAt: null }) === "No backend configured" &&
    shellHealthLabel({ state: "unreachable", latencyMs: null, httpStatus: 0, checkedAt: null }) === "Backend unreachable" &&
    shellHealthLabel({ state: "checking", latencyMs: null, httpStatus: null, checkedAt: null }) === "Checking");

  // probe: read-only GET of the status path, timed by the injected clock.
  let seenPath = "";
  let seenInit: unknown = "unset";
  let t = 1000;
  const probed = await probeShellHealth(
    async (path, _signal, init) => {
      seenPath = path;
      seenInit = init;
      t += 120;
      return res(true, 200);
    },
    () => t,
  );
  check("probe hits /system/status as a plain GET",
    seenPath === SHELL_HEALTH_PATH && seenInit === undefined,
    `${seenPath} ${JSON.stringify(seenInit)}`);
  check("probe measures elapsed with the injected clock",
    probed.state === "live" && probed.latencyMs === 120, JSON.stringify(probed));

  const failed = await probeShellHealth(async () => res(false, 0), () => 0);
  check("probe network failure is unreachable", failed.state === "unreachable");

  return out;
}
