/**
 * The Memory Archive as an evidence explorer — the rules behind it.
 *
 * Everything here works on what the backend actually returned. Nothing is
 * inferred about a memory: a classification the source did not state stays
 * "unknown", a confidence it did not give stays absent, and a facet is only
 * offered when the data can tell memories apart by it.
 *
 * Pure functions, covered headlessly by `explorer-self-test.ts`.
 */
import {
  CATEGORIES,
  CATEGORY_META,
  KIND_META,
  PROVENANCE_META,
  type Entity,
  type EntityRef,
  type MemoryCategory,
  type MemoryKind,
  type MemoryRecord,
  type ProvenanceKind,
  type Relationship,
} from "./types";

/* ------------------------------------------------------------------ bands */

export type ConfidenceBand = "high" | "medium" | "low" | "unstated";
export type TimeBand = "week" | "month" | "older" | "undated";

export const CONFIDENCE_LABEL: Record<ConfidenceBand, string> = {
  high: "High · 85+",
  medium: "Medium · 60–84",
  low: "Low · under 60",
  unstated: "Not stated",
};

export const TIME_LABEL: Record<TimeBand, string> = {
  week: "Last 7 days",
  month: "Last 30 days",
  older: "Older",
  undated: "Undated",
};

/** Same thresholds as `confidenceTier`; absent stays absent. */
export function confidenceBand(value: number | undefined): ConfidenceBand {
  if (typeof value !== "number") return "unstated";
  if (value >= 85) return "high";
  if (value >= 60) return "medium";
  return "low";
}

/**
 * When a memory is from: when it was recorded, else when it last changed, else
 * the time of the signal it came from. Undefined when the source gave none.
 */
export function recordTime(r: MemoryRecord): string | undefined {
  return r.createdAt ?? r.updatedAt ?? r.provenance.at;
}

const DAY = 24 * 3600 * 1000;

export function timeBand(iso: string | undefined, now: number): TimeBand {
  const t = iso ? Date.parse(iso) : NaN;
  if (!Number.isFinite(t)) return "undated";
  const age = now - t;
  if (age <= 7 * DAY) return "week";
  if (age <= 30 * DAY) return "month";
  return "older";
}

/* ---------------------------------------------------------------- filters */

export interface ExplorerFilters {
  query: string;
  categories: MemoryCategory[];
  sources: ProvenanceKind[];
  kinds: MemoryKind[];
  confidence: ConfidenceBand[];
  time: TimeBand[];
  /** Only memories about this entity. */
  entityId: string | null;
}

export const EMPTY_FILTERS: ExplorerFilters = {
  query: "",
  categories: [],
  sources: [],
  kinds: [],
  confidence: [],
  time: [],
  entityId: null,
};

/** How many facet choices are narrowing the list (the query is not counted). */
export function activeFilterCount(f: ExplorerFilters): number {
  return f.categories.length + f.sources.length + f.kinds.length + f.confidence.length + f.time.length + (f.entityId ? 1 : 0);
}

/** Plain keyword match over what a memory says and where it came from. */
export function matchesQuery(r: MemoryRecord, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const hay = [
    r.summary,
    r.content,
    CATEGORY_META[r.category].label,
    KIND_META[r.kind].label,
    ...r.tags,
    ...r.entities.map((e) => e.label),
    PROVENANCE_META[r.provenance.kind].label,
    r.provenance.label,
    r.provenance.sourceAccount ?? "",
  ]
    .join(" ")
    .toLowerCase();
  return q.split(/\s+/).every((word) => hay.includes(word));
}

/** Within a facet, choices widen (OR); across facets they narrow (AND). */
export function applyFilters(records: MemoryRecord[], f: ExplorerFilters, now: number): MemoryRecord[] {
  const has = <T,>(chosen: T[], value: T) => chosen.length === 0 || chosen.includes(value);
  return records.filter(
    (r) =>
      matchesQuery(r, f.query) &&
      has(f.categories, r.category) &&
      has(f.sources, r.provenance.kind) &&
      has(f.kinds, r.kind) &&
      has(f.confidence, confidenceBand(r.confidence)) &&
      has(f.time, timeBand(recordTime(r), now)) &&
      (f.entityId === null || r.entities.some((e) => e.id === f.entityId)),
  );
}

/* ------------------------------------------------------------------ facets */

export interface FacetValue<T extends string> {
  key: T;
  label: string;
  count: number;
}

export interface Facets {
  categories: FacetValue<MemoryCategory>[];
  sources: FacetValue<ProvenanceKind>[];
  kinds: FacetValue<MemoryKind>[];
  confidence: FacetValue<ConfidenceBand>[];
  time: FacetValue<TimeBand>[];
}

function tally<T extends string>(order: readonly T[], label: (k: T) => string, values: T[]): FacetValue<T>[] {
  return order
    .map((key) => ({ key, label: label(key), count: values.filter((v) => v === key).length }))
    .filter((v) => v.count > 0);
}

/** The values that actually occur, with how many memories carry each. */
export function facets(records: MemoryRecord[], now: number): Facets {
  return {
    categories: tally(CATEGORIES, (k) => CATEGORY_META[k].label, records.map((r) => r.category)),
    sources: tally(
      Object.keys(PROVENANCE_META) as ProvenanceKind[],
      (k) => PROVENANCE_META[k].label,
      records.map((r) => r.provenance.kind),
    ),
    kinds: tally(["fact", "inference", "unknown"] as const, (k) => KIND_META[k].label, records.map((r) => r.kind)),
    confidence: tally(
      ["high", "medium", "low", "unstated"] as const,
      (k) => CONFIDENCE_LABEL[k],
      records.map((r) => confidenceBand(r.confidence)),
    ),
    time: tally(["week", "month", "older", "undated"] as const, (k) => TIME_LABEL[k], records.map((r) => timeBand(recordTime(r), now))),
  };
}

/** A facet is worth offering only if it can tell memories apart. */
export function facetIsUseful(values: FacetValue<string>[]): boolean {
  return values.length > 1;
}

/**
 * What to say in place of a facet that cannot filter. States what the data
 * does or does not carry; never presents a gap as a property of the memories.
 */
export function facetNote(facet: keyof Facets, values: FacetValue<string>[]): string {
  if (values.length === 0) return "Nothing to filter.";
  const only = values[0];
  if (facet === "kinds" && only.key === "unknown") return "Not stated by the source for any of these memories.";
  if (facet === "confidence" && only.key === "unstated") return "Not stated by the source for any of these memories.";
  if (facet === "time" && only.key === "undated") return "None of these memories carries a date.";
  return `The same for every memory here: ${only.label}.`;
}

/* -------------------------------------------------------------------- sort */

export type SortKey = "newest" | "confidence";

/** Stable. Memories without the sorted value keep their order at the end. */
export function sortRecords(records: MemoryRecord[], key: SortKey): MemoryRecord[] {
  const time = (r: MemoryRecord) => {
    const t = Date.parse(recordTime(r) ?? "");
    return Number.isFinite(t) ? t : -Infinity;
  };
  const conf = (r: MemoryRecord) => (typeof r.confidence === "number" ? r.confidence : -Infinity);
  const value = key === "newest" ? time : conf;
  return records
    .map((r, i) => ({ r, i }))
    .sort((a, b) => value(b.r) - value(a.r) || a.i - b.i)
    .map((x) => x.r);
}

/* ----------------------------------------------------------- relationships */

export interface SharedEntityLink {
  record: MemoryRecord;
  /** The entities both memories are about. */
  via: EntityRef[];
}

/**
 * Other memories about the same entities. This is a lookup, not a judgement:
 * two memories are listed together only because the source attached the same
 * entity to both. Memories the source linked explicitly are left out (they are
 * shown as such).
 */
export function sharedEntityRecords(record: MemoryRecord, all: MemoryRecord[]): SharedEntityLink[] {
  const mine = new Set(record.entities.map((e) => e.id));
  if (mine.size === 0) return [];
  return all
    .filter((r) => r.id !== record.id && !record.related.includes(r.id))
    .map((r) => ({ record: r, via: r.entities.filter((e) => mine.has(e.id)) }))
    .filter((link) => link.via.length > 0)
    .sort((a, b) => b.via.length - a.via.length);
}

export interface EntityRelation {
  id: string;
  /** The edge as the source names it, e.g. "works at". */
  kind: string;
  /** Whether the entity is the start or the end of the edge. */
  direction: "out" | "in";
  other: Entity;
}

/** The relationships the backend returned for one entity. */
export function entityRelations(entityId: string, entities: Entity[], relationships: Relationship[]): EntityRelation[] {
  const byId = new Map(entities.map((e) => [e.id, e]));
  const out: EntityRelation[] = [];
  for (const rel of relationships) {
    if (rel.from === entityId && byId.has(rel.to)) out.push({ id: rel.id, kind: rel.kind, direction: "out", other: byId.get(rel.to)! });
    else if (rel.to === entityId && byId.has(rel.from)) out.push({ id: rel.id, kind: rel.kind, direction: "in", other: byId.get(rel.from)! });
  }
  return out;
}

/* ---------------------------------------------------------------- coverage */

export interface Coverage {
  total: number;
  classified: number;
  withConfidence: number;
  dated: number;
  withEntities: number;
  linked: number;
}

/** How much of each kind of metadata the source actually supplied. */
export function coverage(records: MemoryRecord[]): Coverage {
  return {
    total: records.length,
    classified: records.filter((r) => r.kind !== "unknown").length,
    withConfidence: records.filter((r) => typeof r.confidence === "number").length,
    dated: records.filter((r) => recordTime(r) !== undefined).length,
    withEntities: records.filter((r) => r.entities.length > 0).length,
    linked: records.filter((r) => r.related.length > 0).length,
  };
}
