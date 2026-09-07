/**
 * Shared client-side access to the LILITH backend.
 *
 * Two supported connection modes (in priority order):
 *  1. Same-origin proxy (recommended): leave NEXT_PUBLIC_LILITH_API_URL unset
 *     and set the SERVER-ONLY `LILITH_API_URL` (e.g. a localhost tunnel). The
 *     browser hits `/api/lilith/*`; the backend URL never reaches the client
 *     and there is no CORS. This keeps the backend private.
 *  2. Direct: set `NEXT_PUBLIC_LILITH_API_URL` to hit the backend straight from
 *     the browser (requires the backend to allow the origin via CORS).
 *
 * If neither yields a reachable backend, callers fall back to demo data.
 */

const DIRECT = process.env.NEXT_PUBLIC_LILITH_API_URL?.replace(/\/+$/, "");
export const API_BASE = DIRECT || "/api/lilith";
export const API_MODE: "direct" | "proxy" = DIRECT ? "direct" : "proxy";

export interface EndpointResult<T = unknown> {
  path: string;
  ok: boolean;
  status: number;
  data: T | null;
  error?: string;
}

/** An optional non-GET request (approval-gated writes). Omit for reads. */
export interface EndpointRequest {
  method?: "GET" | "POST" | "DELETE" | "PATCH";
  body?: unknown;
}

/** Fetch a single endpoint, never throwing — result carries ok/status/data. */
export async function fetchEndpoint<T = unknown>(
  path: string,
  signal?: AbortSignal,
  init?: EndpointRequest,
): Promise<EndpointResult<T>> {
  const url = `${API_BASE}${path}`;
  const method = init?.method ?? "GET";
  const hasBody = init?.body !== undefined && method !== "GET";
  try {
    const res = await fetch(url, {
      signal,
      method,
      headers: hasBody
        ? { accept: "application/json", "content-type": "application/json" }
        : { accept: "application/json" },
      body: hasBody ? JSON.stringify(init!.body) : undefined,
      cache: "no-store",
    });
    let data: T | null = null;
    try {
      data = (await res.json()) as T;
    } catch {
      data = null;
    }
    return {
      path,
      ok: res.ok,
      status: res.status,
      data: res.ok ? data : null,
      error: res.ok ? undefined : `HTTP ${res.status}`,
    };
  } catch (e) {
    return {
      path,
      ok: false,
      status: 0,
      data: null,
      error: e instanceof Error ? e.message : "network error",
    };
  }
}

export interface Diagnostics {
  mode: "live" | "demo";
  transport: "direct" | "proxy";
  endpoints: { path: string; ok: boolean; status: number; error?: string }[];
}

export function toDiagnostics(
  mode: "live" | "demo",
  results: EndpointResult[],
): Diagnostics {
  return {
    mode,
    transport: API_MODE,
    endpoints: results.map((r) => ({
      path: r.path,
      ok: r.ok,
      status: r.status,
      error: r.error,
    })),
  };
}
