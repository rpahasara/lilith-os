/**
 * Integration Fabric V1 — Vertical Slice 6.
 *
 * A typed connector layer between capabilities and their underlying systems.
 * Capabilities describe WHAT to do (and bind declaratively to a connector +
 * operation); a Connector performs the system-specific I/O. The architecture
 * rule: Planner proposes · Policy governs · Capability describes · Connector
 * performs · Verifier proves.
 *
 * The connector receives the same injected {@link CoreTransport} the core uses,
 * so tests exercise the whole path with a fake transport and no network. This is
 * deliberately minimal — no plugin marketplace, no worker pool, no discovery
 * beyond "does this connector support this operation".
 */
import type { CoreTransport, TransportResult } from "./types";

export type ConnectorHealthState = "healthy" | "degraded" | "unavailable";

export interface ConnectorHealth {
  state: ConnectorHealthState;
  detail?: string;
}

export interface ConnectorOperation {
  id: string;
  kind: "read" | "write";
}

export interface ConnectorRequest {
  operation: string;
  /** Operation-specific input (e.g. the draft body, or a draft id). */
  input?: Record<string, unknown>;
}

export interface ConnectorResult<T = unknown> {
  ok: boolean;
  status: number;
  data: T | null;
  errorKind?: "network" | "timeout" | "5xx" | "4xx" | "malformed" | "unsupported" | "unavailable";
  error?: string;
}

export interface Connector {
  id: string;
  version: string;
  title: string;
  /** The operations this connector can perform (capability discovery). */
  operations: ConnectorOperation[];
  supports(operation: string): boolean;
  /** Probe availability. A capability requiring an unavailable connector must not run. */
  checkHealth(transport: CoreTransport, signal?: AbortSignal): Promise<ConnectorHealth>;
  /** Perform one operation's system-specific I/O. */
  execute<T = unknown>(req: ConnectorRequest, transport: CoreTransport, signal?: AbortSignal): Promise<ConnectorResult<T>>;
}

/* --------------------------------------------------------------- utilities */

function classify(res: TransportResult): ConnectorResult["errorKind"] {
  if (res.ok) return undefined;
  if (res.status === 0) return /timeout|abort/i.test(res.error ?? "") ? "timeout" : "network";
  if (res.status >= 500) return "5xx";
  if (res.status >= 400) return "4xx";
  return "network";
}

function toResult<T>(res: TransportResult): ConnectorResult<T> {
  return { ok: res.ok, status: res.status, data: res.ok ? (res.data as T) : null, errorKind: classify(res), error: res.error };
}

function makeSupports(ops: ConnectorOperation[]) {
  const set = new Set(ops.map((o) => o.id));
  return (op: string) => set.has(op);
}

/* ------------------------------------- connector: internal career store ---- */

export const INTERNAL_CAREER_STORE_ID = "internal-career-store";

const INTERNAL_STORE_OPS: ConnectorOperation[] = [
  { id: "create_draft", kind: "write" },
  { id: "get", kind: "read" },
  { id: "list", kind: "read" },
  { id: "discard", kind: "write" },
];

/**
 * The first real connector: the backend `/os/drafts` internal record store
 * (drafts + notes). It owns the endpoint shapes; capabilities no longer build
 * paths/bodies themselves. Nothing here leaves the box — no external send.
 */
export const internalCareerStoreConnector: Connector = {
  id: INTERNAL_CAREER_STORE_ID,
  version: "1.0.0",
  title: "Internal career store",
  operations: INTERNAL_STORE_OPS,
  supports: makeSupports(INTERNAL_STORE_OPS),
  async checkHealth(transport, signal) {
    const res = await transport("/drafts?limit=1", signal);
    if (res.ok) return { state: "healthy" };
    if (res.status === 0 || res.status >= 500) {
      return { state: "unavailable", detail: res.error ?? `HTTP ${res.status}` };
    }
    return { state: "degraded", detail: res.error ?? `HTTP ${res.status}` };
  },
  async execute(req, transport, signal) {
    const input = req.input ?? {};
    switch (req.operation) {
      case "create_draft":
        return toResult(await transport("/drafts", signal, { method: "POST", body: input }));
      case "get": {
        const id = String(input.draftId ?? "");
        return toResult(await transport(`/drafts/${encodeURIComponent(id)}`, signal));
      }
      case "list":
        return toResult(await transport(`/drafts${input.query ? `?${input.query}` : ""}`, signal));
      case "discard": {
        const id = String(input.draftId ?? "");
        return toResult(await transport(`/drafts/${encodeURIComponent(id)}`, signal, { method: "DELETE" }));
      }
      default:
        return { ok: false, status: 0, data: null, errorKind: "unsupported", error: `operation ${req.operation} not supported` };
    }
  },
};

/* ------------------------------------------- connector: google workspace --- */

const GOOGLE_OPS: ConnectorOperation[] = [
  { id: "send_email", kind: "write" },
  { id: "create_event", kind: "write" },
  { id: "get_availability", kind: "read" },
];

/**
 * Google Workspace — modelled as an UNAVAILABLE connector (health metadata
 * only). The known OAuth breakage is NOT repaired here (§8): this connector
 * never performs real I/O; it exists to prove the health model has a genuine
 * unavailable state and to keep Gmail/Calendar writes off the table by policy
 * and by availability. Its one bound capability (mail.send_email) is also
 * PROHIBITED, so it is refused twice over.
 */
export const googleWorkspaceConnector: Connector = {
  id: "google-workspace",
  version: "0.0.0",
  title: "Google Workspace",
  operations: GOOGLE_OPS,
  supports: makeSupports(GOOGLE_OPS),
  async checkHealth() {
    return { state: "unavailable", detail: "Google OAuth is not connected" };
  },
  async execute() {
    return { ok: false, status: 0, data: null, errorKind: "unavailable", error: "Google Workspace is not connected" };
  },
};

/* ------------------------------------------------------------- registry ---- */

export const CONNECTOR_REGISTRY: Record<string, Connector> = {
  [internalCareerStoreConnector.id]: internalCareerStoreConnector,
  [googleWorkspaceConnector.id]: googleWorkspaceConnector,
};

export function getConnector(id: string): Connector | undefined {
  return CONNECTOR_REGISTRY[id];
}

/** Capability discovery: does the registered connector support this operation? */
export function connectorSupports(connectorId: string, operation: string): boolean {
  const c = getConnector(connectorId);
  return !!c && c.supports(operation);
}

export interface ConnectorBinding {
  id: string;
  operation: string;
}

export type ConnectorResolution =
  | { ok: true; connector: Connector }
  | { ok: false; reason: string };

/**
 * Resolve a capability's declared connector binding. Fails safely (before any
 * execution) when the connector is missing or does not support the operation.
 */
export function resolveConnectorBinding(binding: ConnectorBinding | undefined): ConnectorResolution {
  if (!binding) return { ok: false, reason: "no connector binding declared" };
  const connector = getConnector(binding.id);
  if (!connector) return { ok: false, reason: `connector "${binding.id}" is not registered` };
  if (!connector.supports(binding.operation)) {
    return { ok: false, reason: `connector "${binding.id}" does not support operation "${binding.operation}"` };
  }
  return { ok: true, connector };
}
