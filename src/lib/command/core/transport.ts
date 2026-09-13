/**
 * Default core transport — wraps the same-origin read-only proxy in `@/lib/api`.
 * The core depends only on the {@link CoreTransport} seam, so tests inject a
 * fake and never touch the network.
 */
import { fetchEndpoint } from "@/lib/api";
import type { CoreTransport } from "./types";

export const realTransport: CoreTransport = async (path, signal, init) => {
  const res = await fetchEndpoint(path, signal, init);
  return { ok: res.ok, status: res.status, data: res.data, error: res.error };
};

export { executionId } from "./ids";
