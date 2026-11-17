/**
 * Real memory for the Cognitive Atlas — a read-only projection of the
 * authorized memory read model onto the brain.
 *
 * Source: the same GET endpoints the Memory Archive reads (`/memory/records`,
 * `/memory/entities`) through the same-origin proxy. Nothing here writes,
 * nothing is stored in the browser, and nothing is filled in: a field the
 * source does not give stays absent.
 *
 * There is no memory event stream to subscribe to, so change is found by
 * comparing successive successful snapshots. A snapshot is only accepted when
 * the records endpoint answered 2xx with a records array; anything else
 * (network error, 401/403/5xx, a malformed body) is a failed check, and a
 * failed check never removes anything from the graph.
 *
 * See docs/engineering/cognitive-atlas-real-memory.md.
 */
import { fetchEndpoint, type EndpointResult } from "@/lib/api";
import { normalizeEntity, normalizeRecord, normalizeRelationship } from "@/lib/memory/client";
import type { Entity, MemoryCategory, MemoryRecord, Relationship } from "@/lib/memory/types";
import { placeNode, type BrainLayout } from "./brain-shape";
import { REGION_BY_ID } from "./regions";
import { createAtlasStore, type AtlasGraph, type AtlasStore } from "./store";
import type { AtlasEvent, AtlasLink, AtlasLinkInput, AtlasNode, AtlasNodeInput, RegionId, Vec3 } from "./types";

/* ---------------------------------------------------------------- mapping */

/**
 * Memory category → brain region. The brain's seven domains were drawn for the
 * prototype; the memory model has seven categories. Six map by name. Work has
 * no domain of its own and sits in the Career field (the frontal field of
 * roles and the decisions that shape them), while the node keeps "work" as its
 * category and every panel says so. Relationships has no category in the
 * memory model, so in Real mode it stays empty rather than borrowing records.
 */
export const CATEGORY_REGION: Record<MemoryCategory, RegionId> = {
  career: "career",
  work: "career",
  projects: "projects",
  people: "people",
  knowledge: "knowledge",
  preferences: "preferences",
  personal: "personal",
};

/** Regions that hold no category of the memory model. */
export const UNMAPPED_REGIONS: RegionId[] = ["relationships"];

/** A region's name as shown for a source. Real memory names the Career field
 *  for both categories it holds, so Work is never presented as Career. */
export function regionLabel(id: RegionId, origin: "synthetic" | "real" = "synthetic"): string {
  if (origin === "real" && id === "career") return "Career · Work";
  return REGION_BY_ID[id].label;
}

/** Above this many records one entity is not drawn as pathways (too dense to
 *  read, and the pathway buffer is finite). It is still listed on each record. */
export const SHARED_ENTITY_LINK_CAP = 24;

/* --------------------------------------------------------------- snapshot */

export interface MemorySnapshot {
  takenAt: number;
  records: MemoryRecord[];
  /** null when the entities endpoint did not answer this time. */
  entities: Entity[] | null;
  relationships: Relationship[] | null;
  /** records the source returned without a usable id (left out of the graph). */
  unidentified: number;
}

export type SnapshotFailure = "unconfigured" | "refused" | "unreachable" | "error" | "malformed";

export type SnapshotResult =
  | { ok: true; snapshot: MemorySnapshot }
  | { ok: false; reason: SnapshotFailure; status: number };

export type SnapshotFetch = (path: string, signal?: AbortSignal) => Promise<EndpointResult>;

function failure(res: EndpointResult): SnapshotFailure {
  if (res.status === 503) return "unconfigured";
  if (res.status === 401 || res.status === 403) return "refused";
  // status 0: no HTTP answer at all (network error, aborted, timed out)
  return res.status === 0 ? "unreachable" : "error";
}

/** Raw records array, or null when the body is not the shape we expect. */
function recordsArray(data: unknown): unknown[] | null {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object" && Array.isArray((data as { records?: unknown }).records)) {
    return (data as { records: unknown[] }).records;
  }
  return null;
}

function hasStableId(raw: unknown): boolean {
  if (!raw || typeof raw !== "object") return false;
  const r = raw as { id?: unknown; memory_id?: unknown };
  const id = r.id ?? r.memory_id;
  return (typeof id === "string" && id.trim() !== "") || typeof id === "number";
}

/** One read of the memory read model. Never throws; never writes. */
export async function fetchSnapshot(
  signal?: AbortSignal,
  fetchImpl: SnapshotFetch = fetchEndpoint,
  now: () => number = Date.now,
): Promise<SnapshotResult> {
  const [recRes, entRes] = await Promise.all([
    fetchImpl("/memory/records", signal),
    fetchImpl("/memory/entities", signal),
  ]);
  if (!recRes.ok) return { ok: false, reason: failure(recRes), status: recRes.status };
  const raw = recordsArray(recRes.data);
  if (!raw) return { ok: false, reason: "malformed", status: recRes.status };

  // A record without its own id cannot be followed between snapshots (the
  // normaliser would invent a new one each time), so it is left out and counted.
  const seen = new Set<string>();
  const records: MemoryRecord[] = [];
  let unidentified = 0;
  for (const item of raw) {
    if (!hasStableId(item)) {
      unidentified += 1;
      continue;
    }
    const record = normalizeRecord(item);
    if (seen.has(record.id)) continue;
    seen.add(record.id);
    records.push(record);
  }

  let entities: Entity[] | null = null;
  let relationships: Relationship[] | null = null;
  const ent = entRes.ok ? (entRes.data as { entities?: unknown; relationships?: unknown } | null) : null;
  if (ent && Array.isArray(ent.entities)) {
    entities = ent.entities.map(normalizeEntity);
    relationships = Array.isArray(ent.relationships) ? ent.relationships.map(normalizeRelationship) : [];
  }

  return { ok: true, snapshot: { takenAt: now(), records, entities, relationships, unidentified } };
}

/* ------------------------------------------------------------- projection */

function epoch(iso?: string): number | undefined {
  if (!iso) return undefined;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : undefined;
}

/** A record as an Atlas node input. Only fields the source gave. */
export function projectRecord(r: MemoryRecord): AtlasNodeInput {
  return {
    id: r.id,
    origin: "real",
    region: CATEGORY_REGION[r.category],
    category: r.category,
    title: r.summary.trim() || "Untitled record",
    detail: r.content,
    kind: r.kind,
    tags: [...r.tags],
    entities: r.entities.map((e) => e.label),
    entityRefs: r.entities.map((e) => ({ id: e.id, type: e.type, label: e.label })),
    provenance: {
      kind: r.provenance.kind,
      label: r.provenance.label,
      at: epoch(r.provenance.at),
      account: r.provenance.sourceAccount,
    },
    confidence: r.confidence,
    importance: r.importance,
    createdAt: epoch(r.createdAt),
    updatedAt: epoch(r.updatedAt),
  };
}

const pairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);

/**
 * Links between records. Explicit ones are the source's own `related` lists;
 * shared-entity ones are derived here and say which entities they share.
 * Both ends must be in the snapshot.
 */
export function projectLinks(records: MemoryRecord[]): AtlasLinkInput[] {
  const ids = new Set(records.map((r) => r.id));
  const out = new Map<string, AtlasLinkInput>();

  for (const r of records) {
    for (const other of r.related) {
      if (other === r.id || !ids.has(other)) continue;
      const key = pairKey(r.id, other);
      const [source, target] = key.split("|");
      out.set(`explicit:${key}`, {
        id: `explicit:${key}`,
        source,
        target,
        basis: "explicit",
        kind: "linked by the source",
        strength: 0.85,
      });
    }
  }

  const byEntity = new Map<string, { label: string; records: string[] }>();
  for (const r of records) {
    for (const e of r.entities) {
      const entry = byEntity.get(e.id) ?? { label: e.label, records: [] };
      if (!entry.records.includes(r.id)) entry.records.push(r.id);
      byEntity.set(e.id, entry);
    }
  }
  const shared = new Map<string, Set<string>>();
  for (const { label, records: members } of byEntity.values()) {
    if (members.length < 2 || members.length > SHARED_ENTITY_LINK_CAP) continue;
    const sorted = [...members].sort();
    for (let i = 0; i < sorted.length; i++) {
      for (let j = i + 1; j < sorted.length; j++) {
        const key = pairKey(sorted[i], sorted[j]);
        if (out.has(`explicit:${key}`)) continue;
        const via = shared.get(key) ?? new Set<string>();
        via.add(label);
        shared.set(key, via);
      }
    }
  }
  for (const [key, viaSet] of shared) {
    const via = [...viaSet].sort();
    const [source, target] = key.split("|");
    out.set(`shared:${key}`, {
      id: `shared:${key}`,
      source,
      target,
      basis: "shared-entity",
      via,
      kind: `shares · ${via.join(", ")}`,
      // a drawing weight: more shared entities draw a slightly brighter path
      strength: 0.4 + Math.min(3, via.length) * 0.1,
    });
  }
  return [...out.values()].sort((a, b) => (a.id! < b.id! ? -1 : 1));
}

/** The first graph for a store. Every node is present from the start. */
export function buildRealGraph(snapshot: MemorySnapshot, layout: BrainLayout): AtlasGraph {
  const inputs = snapshot.records.map(projectRecord).sort((a, b) => (a.id < b.id ? -1 : 1));
  const taken: Vec3[] = [];
  const nodes: AtlasNode[] = inputs.map((input) => {
    const position = placeNode(layout, input.region, input.id, taken);
    taken.push(position);
    // born 0: no growth history is implied — the read model has none
    return { ...input, position, born: 0, live: false, reinforcements: 0, recalls: 0 };
  });
  const present = new Set(nodes.map((n) => n.id));
  const links: AtlasLink[] = projectLinks(snapshot.records)
    .filter((l) => present.has(l.source) && present.has(l.target))
    .map((l): AtlasLink => ({ ...l, id: l.id!, basis: l.basis ?? "explicit", born: 0, live: false }));
  return { nodes, links, origin: snapshot.takenAt - 1, now: snapshot.takenAt };
}

/* ---------------------------------------------------------- reconciliation */

/** What a node says, for change detection. Position and session state excluded. */
export function fingerprint(n: AtlasNodeInput | AtlasNode): string {
  return JSON.stringify([
    n.region, n.category, n.title, n.detail, n.kind, n.tags, n.entityRefs,
    n.provenance.kind, n.provenance.label, n.provenance.at, n.provenance.account,
    n.confidence, n.importance, n.createdAt, n.updatedAt,
  ]);
}

export interface Diff {
  events: AtlasEvent[];
  summary: { observed: number; changed: number; withdrawn: number; linksObserved: number; linksWithdrawn: number };
}

/**
 * Events that take a graph showing `current` to one showing `next`. Only call
 * this with a successful snapshot: anything absent from it is treated as gone.
 */
export function reconcile(
  current: { nodes: readonly AtlasNode[]; links: readonly AtlasLink[] },
  next: MemorySnapshot,
): Diff {
  const at = next.takenAt;
  const nextNodes = new Map(next.records.map((r) => [r.id, projectRecord(r)]));
  const nextLinks = new Map(projectLinks(next.records).map((l) => [l.id!, l]));
  const have = new Map(current.nodes.map((n) => [n.id, n]));
  const haveLinks = new Map(current.links.map((l) => [l.id, l]));
  const events: AtlasEvent[] = [];
  const summary = { observed: 0, changed: 0, withdrawn: 0, linksObserved: 0, linksWithdrawn: 0 };

  // 1. links that are gone while both ends stay (a withdrawn record takes its own)
  for (const link of current.links) {
    if (nextLinks.has(link.id)) continue;
    if (!nextNodes.has(link.source) || !nextNodes.has(link.target)) continue;
    events.push({ type: "link.withdrawn", at, linkId: link.id });
    summary.linksWithdrawn += 1;
  }
  // 2. records that are gone
  for (const node of current.nodes) {
    if (nextNodes.has(node.id)) continue;
    events.push({ type: "record.withdrawn", at, nodeId: node.id });
    summary.withdrawn += 1;
  }
  // 3. records that changed
  for (const [id, input] of nextNodes) {
    const old = have.get(id);
    if (old && fingerprint(old) !== fingerprint(input)) {
      events.push({ type: "record.changed", at, node: input });
      summary.changed += 1;
    }
  }
  // 4. records that are new (sorted, so placement is stable)
  for (const [id, input] of [...nextNodes].sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (have.has(id)) continue;
    events.push({ type: "record.observed", at, node: input, links: [] });
    summary.observed += 1;
  }
  // 5. links that are new (after every node they need exists)
  for (const [id, link] of nextLinks) {
    if (haveLinks.has(id)) continue;
    events.push({ type: "link.observed", at, link });
    summary.linksObserved += 1;
  }
  return { events, summary };
}

/* ------------------------------------------------------------------- steps */

/** Everything Real mode knows, between checks. Held in memory only. */
export interface RealView {
  store: AtlasStore;
  entities: Entity[];
  relationships: Relationship[];
  /** the entities endpoint did not answer on the latest successful read. */
  entitiesStale: boolean;
  /** records the source returned without an id (not drawn). */
  unidentified: number;
  firstAt: number;
  lastGoodAt: number;
  /** set when the latest check failed; the graph is the last good one. */
  stale: { failure: SnapshotFailure; at: number } | null;
}

export type RealStep =
  | { kind: "ready"; view: RealView; diff?: Diff["summary"] }
  | { kind: "unavailable"; failure: SnapshotFailure };

/**
 * Take one check's result into the view.
 *  - first success: build the graph whole;
 *  - later success: apply only the differences (gone is gone, everywhere);
 *  - failure: change nothing that was confirmed — mark it stale, or report
 *    unavailable when nothing has been confirmed yet.
 */
export function stepReal(prev: RealView | null, result: SnapshotResult, layout: BrainLayout, at: number): RealStep {
  if (!result.ok) {
    return prev
      ? { kind: "ready", view: { ...prev, stale: { failure: result.reason, at } } }
      : { kind: "unavailable", failure: result.reason };
  }
  const snap = result.snapshot;
  if (!prev) {
    return {
      kind: "ready",
      view: {
        store: createAtlasStore(buildRealGraph(snap, layout), layout),
        entities: snap.entities ?? [],
        relationships: snap.relationships ?? [],
        entitiesStale: snap.entities === null,
        unidentified: snap.unidentified,
        firstAt: snap.takenAt,
        lastGoodAt: snap.takenAt,
        stale: null,
      },
    };
  }
  const { events, summary } = reconcile(prev.store.getState(), snap);
  for (const event of events) prev.store.apply(event);
  return {
    kind: "ready",
    diff: summary,
    view: {
      ...prev,
      // a missing entities answer keeps the previous index rather than emptying it
      entities: snap.entities ?? prev.entities,
      relationships: snap.relationships ?? prev.relationships,
      entitiesStale: snap.entities === null,
      unidentified: snap.unidentified,
      lastGoodAt: snap.takenAt,
      stale: null,
    },
  };
}

/** Plain words for a failed check. */
export const FAILURE_LINE: Record<SnapshotFailure, string> = {
  unconfigured: "The backend is not configured or is unavailable.",
  refused: "The backend refused the request.",
  unreachable: "The backend did not answer.",
  error: "The backend answered with an error.",
  malformed: "The backend answered with something that is not a list of records.",
};
