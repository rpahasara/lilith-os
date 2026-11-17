/**
 * Shell health — the truthful source for the global status capsule.
 *
 * The capsule used to render fixed strings ("Online", "Live", "Healthy",
 * "Private", "48ms") whatever the backend was doing. This module replaces them
 * with one measured probe: a read-only GET of `/system/status` through the
 * existing same-origin proxy, timed in the browser. Nothing here can write, and
 * no backend URL, token or provider detail is involved on the client.
 *
 * The round-trip is browser → Next proxy → backend → back, i.e. what the owner
 * actually waits on. It is NOT model latency.
 */
import { fetchEndpoint, type EndpointRequest, type EndpointResult } from "@/lib/api";
import { platformFrom, type PlatformSnapshot } from "./platform";

/** The probe's fetch seam (the real one is `fetchEndpoint`). */
export type ProbeFetch = (
  path: string,
  signal?: AbortSignal,
  init?: EndpointRequest,
) => Promise<EndpointResult>;

export type ShellHealthState = "checking" | "live" | "unconfigured" | "unreachable";

export interface ShellHealth {
  state: ShellHealthState;
  /** Measured round-trip in ms; only set when `state === "live"`. */
  latencyMs: number | null;
  /** HTTP status of the last probe (0 = network error / timeout). */
  httpStatus: number | null;
  /** ISO timestamp of the last completed probe. */
  checkedAt: string | null;
  /**
   * The platform units in the same response (System reads these). Null until a
   * live probe returns them; the probe makes no extra request for them.
   */
  platform: PlatformSnapshot | null;
}

export const INITIAL_SHELL_HEALTH: ShellHealth = {
  state: "checking",
  latencyMs: null,
  httpStatus: null,
  checkedAt: null,
  platform: null,
};

export const SHELL_HEALTH_PATH = "/system/status";
export const SHELL_HEALTH_INTERVAL_MS = 60_000;
export const SHELL_HEALTH_TIMEOUT_MS = 8_000;

/**
 * Map one probe result to a shell state. Pure, so it is covered by the
 * headless self-test.
 *  - 2xx                → live (with latency)
 *  - 503 (proxy has no LILITH_API_URL) → unconfigured: there is no backend to
 *    reach, so workspaces are unavailable (sample data is opt-in only)
 *  - anything else      → unreachable (502 tunnel down, 0 timeout, 401/403 …)
 */
export function deriveShellHealth(
  result: Pick<EndpointResult, "ok" | "status"> & { data?: unknown },
  elapsedMs: number,
  now: Date = new Date(),
): ShellHealth {
  const checkedAt = now.toISOString();
  if (result.ok) {
    return {
      state: "live",
      latencyMs: Math.max(0, Math.round(elapsedMs)),
      httpStatus: result.status,
      checkedAt,
      platform: platformFrom(result.data),
    };
  }
  return {
    state: result.status === 503 ? "unconfigured" : "unreachable",
    latencyMs: null,
    httpStatus: result.status,
    checkedAt,
    platform: null,
  };
}

/** Run one timed, read-only probe. Never throws. */
export async function probeShellHealth(
  fetchImpl: ProbeFetch = fetchEndpoint,
  clock: () => number = () => performance.now(),
): Promise<ShellHealth> {
  const started = clock();
  const result = await fetchImpl(
    SHELL_HEALTH_PATH,
    AbortSignal.timeout(SHELL_HEALTH_TIMEOUT_MS),
  );
  return deriveShellHealth(result, clock() - started);
}

/** Short, honest label for the capsule. */
export function shellHealthLabel(h: ShellHealth): string {
  switch (h.state) {
    case "checking":
      return "Checking";
    case "live":
      return "Online";
    case "unconfigured":
      return "No backend configured";
    case "unreachable":
      return "Backend unreachable";
  }
}
