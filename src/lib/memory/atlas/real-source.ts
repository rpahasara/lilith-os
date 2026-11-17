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

/** Drawing weights (never shown as values): source-stated links read first. */
export const EXPLICIT_STRENGTH = 0.95;
const sharedStrength = (via: number) => 0.34 + Math.min(3, via) * 0.07;

/** In a shared-entity group, about one member in this many gets one extra
 *  short pathway beyond the spanning tree, so groups read as clusters rather
 *  than single threads. */
export const EXTRA_EVERY = 4;

/**
 * Where a record sits for the purpose of choosing which pathways to draw: its
 * hashed home in its region. It depends only on the id and category, so the
 * same records always yield the same drawn pathways, whatever order they were
 * placed in.
 */
function homeOf(layout: BrainLayout, r: MemoryRecord): Vec3 {
  return placeNode(layout, CATEGORY_REGION[r.category], r.id, []);
}

const dist2 = (a: Vec3, b: Vec3) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;

/**
 * A minimum spanning tree over one group (Prim), deterministic: members in id
 * order, ties to the lower index. Pairs already drawn cost nothing, so groups
 * reuse each other's pathways instead of adding parallel ones.
 */
function spanningPairs(ids: string[], at: Vec3[], drawn: Set<string>): [number, number][] {
  const n = ids.length;
  if (n < 2) return [];
  const cost = (i: number, j: number) => (drawn.has(pairKey(ids[i], ids[j])) ? 0 : dist2(at[i], at[j]));
  const inTree = new Uint8Array(n);
  const best = new Float64Array(n).fill(Infinity);
  const from = new Int32Array(n).fill(-1);
  inTree[0] = 1;
  for (let j = 1; j < n; j++) {
    best[j] = cost(0, j);
    from[j] = 0;
  }
  const edges: [number, number][] = [];
  for (let step = 1; step < n; step++) {
    let pick = -1;
    for (let j = 1; j < n; j++) if (!inTree[j] && (pick < 0 || best[j] < best[pick])) pick = j;
    inTree[pick] = 1;
    edges.push([from[pick], pick]);
    for (let k = 1; k < n; k++) {
      if (inTree[k]) continue;
      const c = cost(pick, k);
      if (c < best[k]) {
        best[k] = c;
        from[k] = pick;
      }
    }
  }
  return edges;
}

/**
 * The pathways drawn on the brain.
 *
 * - Explicit: every relation the source states (`related`), always drawn.
 * - Shared-entity: derived here. Drawing every pair that shares an entity
 *   grows quadratically and washes the brain out, so each entity's records
 *   are joined by a spanning tree over their homes (every group stays
 *   connected through short, local pathways), plus a few extra short ones.
 *
 * Only the drawing is reduced. Every association stays available: see
 * `associationsOf` and `associationTotals`, which the inspector and the
 * counts use. A drawn shared pathway names every entity the pair shares.
 */
export function projectLinks(records: MemoryRecord[], layout: BrainLayout): AtlasLinkInput[] {
  const byId = new Map(records.map((r) => [r.id, r]));
  const out = new Map<string, AtlasLinkInput>();
  const drawn = new Set<string>();

  for (const r of records) {
    for (const other of r.related) {
      if (other === r.id || !byId.has(other)) continue;
      const key = pairKey(r.id, other);
      if (drawn.has(key)) continue;
      drawn.add(key);
      const [source, target] = key.split("|");
      out.set(`explicit:${key}`, {
        id: `explicit:${key}`,
        source,
        target,
        basis: "explicit",
        kind: "linked by the source",
        strength: EXPLICIT_STRENGTH,
      });
    }
  }

  const groups = new Map<string, string[]>();
  for (const r of records) {
    for (const e of r.entities) {
      const members = groups.get(e.id) ?? [];
      if (!members.includes(r.id)) members.push(r.id);
      groups.set(e.id, members);
    }
  }

  const home = new Map<string, Vec3>();
  const homeFor = (id: string) => {
    let p = home.get(id);
    if (!p) home.set(id, (p = homeOf(layout, byId.get(id)!)));
    return p;
  };
  const sharedPairs = new Set<string>();
  const addShared = (a: string, b: string) => {
    const key = pairKey(a, b);
    if (drawn.has(key)) return;
    drawn.add(key);
    sharedPairs.add(key);
  };

  for (const entityId of [...groups.keys()].sort()) {
    const ids = [...groups.get(entityId)!].sort();
    if (ids.length < 2) continue;
    const at = ids.map(homeFor);
    const tree = spanningPairs(ids, at, drawn);
    const adjacent = new Set(tree.map(([i, j]) => pairKey(ids[i], ids[j])));
    for (const [i, j] of tree) addShared(ids[i], ids[j]);
    if (ids.length < 4) continue;
    // a few extra short pathways: the nearest member not already joined to it
    for (let i = EXTRA_EVERY - 1; i < ids.length; i += EXTRA_EVERY) {
      let near = -1;
      for (let k = 0; k < ids.length; k++) {
        if (k === i || adjacent.has(pairKey(ids[i], ids[k]))) continue;
        if (near < 0 || dist2(at[i], at[k]) < dist2(at[i], at[near])) near = k;
      }
      if (near >= 0) addShared(ids[i], ids[near]);
    }
  }

  // each drawn shared pathway names every entity the two records share
  for (const key of sharedPairs) {
    const [source, target] = key.split("|");
    const theirs = new Map(byId.get(target)!.entities.map((e) => [e.id, e.label]));
    const both = byId.get(source)!.entities.filter((e) => theirs.has(e.id));
    const unique = [...new Map(both.map((e) => [e.id, e.label])).entries()].sort((a, b) => (a[1] < b[1] ? -1 : 1));
    const via = unique.map(([, label]) => label);
    out.set(`shared:${key}`, {
      id: `shared:${key}`,
      source,
      target,
      basis: "shared-entity",
      via,
      viaIds: unique.map(([id]) => id),
      kind: `shares · ${via.join(", ")}`,
      strength: sharedStrength(via.length),
    });
  }
  return [...out.values()].sort((a, b) => (a.id! < b.id! ? -1 : 1));
}

/* ------------------------------------------------------------ associations */

export interface Associations {
  /** records the source links this one to. */
  explicit: string[];
  /** records that share at least one entity with this one, and which. */
  shared: { id: string; via: string[]; viaIds: string[] }[];
}

type Linkish = Pick<AtlasLink, "source" | "target" | "basis">;

/** Every association of one record — not only the pathways that are drawn. */
export function associationsOf(nodeId: string, nodes: readonly AtlasNode[], links: readonly Linkish[]): Associations {
  const explicit = new Set<string>();
  for (const l of links) {
    if (l.basis !== "explicit") continue;
    if (l.source === nodeId) explicit.add(l.target);
    else if (l.target === nodeId) explicit.add(l.source);
  }
  const self = nodes.find((n) => n.id === nodeId);
  const mine = new Map((self?.entityRefs ?? []).map((e) => [e.id, e.label]));
  const shared: Associations["shared"] = [];
  if (mine.size) {
    for (const n of nodes) {
      if (n.id === nodeId || explicit.has(n.id)) continue;
      const both = [...new Map((n.entityRefs ?? []).filter((e) => mine.has(e.id)).map((e) => [e.id, e.label]))];
      if (both.length) shared.push({ id: n.id, via: both.map(([, l]) => l), viaIds: both.map(([id]) => id) });
    }
    shared.sort((a, b) => b.via.length - a.via.length || (a.id < b.id ? -1 : 1));
  }
  return { explicit: [...explicit].sort(), shared };
}

/** Records carrying an entity. */
export function entityMembers(entityId: string, nodes: readonly AtlasNode[]): string[] {
  return nodes.filter((n) => n.entityRefs?.some((e) => e.id === entityId)).map((n) => n.id);
}

/**
 * How many associations exist in total (explicit links plus every pair that
 * shares an entity, each pair once), and per region (a pair counts for each
 * region it touches). Compared with the drawn pathways for honest counts.
 */
export function associationTotals(
  nodes: readonly AtlasNode[],
  links: readonly Linkish[],
): { total: number; byRegion: Map<RegionId, number> } {
  const index = new Map(nodes.map((n, i) => [n.id, i]));
  const n = nodes.length;
  const seen = new Set<number>();
  const byRegion = new Map<RegionId, number>();
  const count = (i: number, j: number) => {
    const key = i < j ? i * n + j : j * n + i;
    if (seen.has(key)) return;
    seen.add(key);
    const a = nodes[i].region;
    const b = nodes[j].region;
    byRegion.set(a, (byRegion.get(a) ?? 0) + 1);
    if (b !== a) byRegion.set(b, (byRegion.get(b) ?? 0) + 1);
  };
  for (const l of links) {
    if (l.basis !== "explicit") continue;
    const i = index.get(l.source);
    const j = index.get(l.target);
    if (i !== undefined && j !== undefined) count(i, j);
  }
  const groups = new Map<string, number[]>();
  nodes.forEach((node, i) => {
    for (const e of new Set((node.entityRefs ?? []).map((r) => r.id))) {
      const members = groups.get(e);
      if (members) members.push(i);
      else groups.set(e, [i]);
    }
  });
  for (const members of groups.values()) {
    for (let x = 0; x < members.length; x++) for (let y = x + 1; y < members.length; y++) count(members[x], members[y]);
  }
  return { total: seen.size, byRegion };
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
  const links: AtlasLink[] = projectLinks(snapshot.records, layout)
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

/** Same pathway, but naming different shared entities (or a different basis). */
const relabelled = (a: AtlasLink, b: AtlasLinkInput) =>
  a.basis !== b.basis || (a.viaIds ?? []).join("|") !== (b.viaIds ?? []).join("|");

/**
 * Events that take a graph showing `current` to one showing `next`. Only call
 * this with a successful snapshot: anything absent from it is treated as gone.
 *
 * Changes to source-stated links are reported. Changes to drawn shared-entity
 * pathways are `quiet`: they follow from records being observed, changed or
 * withdrawn (which are reported) or from the drawing being re-simplified, and
 * are not, by themselves, something the source said.
 */
export function reconcile(
  current: { nodes: readonly AtlasNode[]; links: readonly AtlasLink[] },
  next: MemorySnapshot,
  layout: BrainLayout,
): Diff {
  const at = next.takenAt;
  const nextNodes = new Map(next.records.map((r) => [r.id, projectRecord(r)]));
  const nextLinks = new Map(projectLinks(next.records, layout).map((l) => [l.id!, l]));
  const have = new Map(current.nodes.map((n) => [n.id, n]));
  const haveLinks = new Map(current.links.map((l) => [l.id, l]));
  const events: AtlasEvent[] = [];
  const summary = { observed: 0, changed: 0, withdrawn: 0, linksObserved: 0, linksWithdrawn: 0 };

  // 1. links that are gone (or relabelled) while both ends stay; a withdrawn
  //    record takes its own links with it
  for (const link of current.links) {
    const replacement = nextLinks.get(link.id);
    if (replacement && !relabelled(link, replacement)) continue;
    if (!nextNodes.has(link.source) || !nextNodes.has(link.target)) continue;
    const quiet = link.basis !== "explicit";
    events.push({ type: "link.withdrawn", at, linkId: link.id, quiet });
    if (replacement) haveLinks.delete(link.id); // re-added below with its new names
    if (!quiet && !replacement) summary.linksWithdrawn += 1;
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
    const quiet = link.basis !== "explicit";
    events.push({ type: "link.observed", at, link, quiet });
    if (!quiet) summary.linksObserved += 1;
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
  const { events, summary } = reconcile(prev.store.getState(), snap, layout);
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
