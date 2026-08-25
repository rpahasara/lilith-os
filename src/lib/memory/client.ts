/**
 * Memory API client.
 *
 * Live-ready: it fetches from the LILITH backend (via the shared proxy/direct
 * layer in `@/lib/api`) and normalises to the domain types. Those `/memory/*`
 * endpoints DO NOT EXIST on the backend yet, so in practice every call falls
 * back to the isolated demo adapter and the UI shows a "Demo data" badge.
 *
 * Live and demo data are NEVER mixed: if the core records endpoint doesn't
 * respond, the whole payload comes from demo. When the backend later ships the
 * endpoints below, this module lights up with real data automatically — no UI
 * changes required.
 */
import { buildDemoMemoryData } from "./demo";
import {
  CATEGORIES,
  ENTITY_META,
  PROVENANCE_META,
  type Entity,
  type EntityRef,
  type EntityType,
  type MemoryCategory,
  type MemoryData,
  type MemoryKind,
  type MemoryOverview,
  type MemoryRecord,
  type ProvenanceKind,
  type Relationship,
} from "./types";
import { fetchEndpoint, toDiagnostics, type EndpointResult } from "@/lib/api";

const CATEGORY_SET = new Set<string>(CATEGORIES);
const ENTITY_SET = new Set<string>(Object.keys(ENTITY_META));
const PROVENANCE_SET = new Set<string>(Object.keys(PROVENANCE_META));

function str(v: unknown, fallback = ""): string {
  return v == null ? fallback : String(v);
}
function num(v: unknown): number | undefined {
  const n = typeof v === "string" ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? n : undefined;
}
/** Confidence may arrive as 0–1 or 0–100; normalise to 0–100. */
function pct(v: unknown): number | undefined {
  const n = num(v);
  if (n == null) return undefined;
  return Math.round(n <= 1 ? n * 100 : n);
}
function asCategory(v: unknown): MemoryCategory {
  return CATEGORY_SET.has(v as string) ? (v as MemoryCategory) : "knowledge";
}
function asEntityType(v: unknown): EntityType {
  return ENTITY_SET.has(v as string) ? (v as EntityType) : "concept";
}
function asProvenanceKind(v: unknown): ProvenanceKind {
  return PROVENANCE_SET.has(v as string) ? (v as ProvenanceKind) : "manual";
}
function asKind(v: unknown): MemoryKind {
  return v === "inference" || v === "inferred" ? "inference" : "fact";
}
function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function normalizeEntityRef(r: any): EntityRef {
  return {
    id: str(r.id ?? r.entity_id ?? Math.random().toString(36).slice(2)),
    type: asEntityType(r.type ?? r.entity_type),
    label: str(r.label ?? r.name ?? "Unknown"),
  };
}

function normalizeRecord(r: any): MemoryRecord {
  return {
    id: str(r.id ?? r.memory_id ?? Math.random().toString(36).slice(2)),
    summary: str(r.summary ?? r.title ?? r.content ?? "").slice(0, 240),
    content: str(r.content ?? r.body ?? r.summary ?? ""),
    category: asCategory(r.category),
    kind: asKind(r.kind ?? r.memory_kind),
    entities: arr(r.entities ?? r.entity_refs).map(normalizeEntityRef),
    // confidence is optional on purpose — file-backed memories have none.
    confidence: pct(r.confidence),
    importance: pct(r.importance),
    pinned: Boolean(r.pinned),
    tags: arr(r.tags).map((t) => str(t)),
    provenance: normalizeProvenance(r.provenance ?? r.source),
    createdAt: r.created_at ? str(r.created_at) : undefined,
    updatedAt: r.updated_at ? str(r.updated_at) : undefined,
    lastAccessed: r.last_accessed ? str(r.last_accessed) : undefined,
    related: arr(r.related ?? r.related_ids).map((x) => str(x)),
  };
}

function normalizeProvenance(raw: any) {
  const p = typeof raw === "string" ? { kind: raw } : (raw ?? {});
  const kind = asProvenanceKind(p.kind ?? p.type);
  return {
    kind,
    sourceAccount: p.source_account ? str(p.source_account) : p.account ? str(p.account) : undefined,
    label: str(p.label ?? p.reason ?? PROVENANCE_META[kind].label),
    at: p.at ? str(p.at) : p.occurred_at ? str(p.occurred_at) : undefined,
  };
}

function normalizeEntity(r: any): Entity {
  return {
    id: str(r.id ?? r.entity_id),
    type: asEntityType(r.type ?? r.entity_type),
    label: str(r.label ?? r.name ?? "Unknown"),
    subtitle: r.subtitle ? str(r.subtitle) : r.role ? str(r.role) : undefined,
    memoryCount: num(r.memory_count ?? r.memoryCount) ?? 0,
  };
}

function normalizeRelationship(r: any, i: number): Relationship {
  return {
    id: str(r.id ?? i),
    from: str(r.from ?? r.source),
    to: str(r.to ?? r.target),
    kind: str(r.kind ?? r.label ?? "related to"),
  };
}

/** Derive an overview from live records when the backend omits /memory/overview. */
function deriveOverview(records: MemoryRecord[], entityCount: number): MemoryOverview {
  const byCategory = Object.fromEntries(CATEGORIES.map((c) => [c, 0])) as Record<
    MemoryCategory,
    number
  >;
  const bySource: Partial<Record<ProvenanceKind, number>> = {};
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  let confSum = 0;
  let confN = 0;
  let pinned = 0;
  let recentlyLearned = 0;

  for (const r of records) {
    byCategory[r.category] += 1;
    bySource[r.provenance.kind] = (bySource[r.provenance.kind] ?? 0) + 1;
    if (typeof r.confidence === "number") {
      confSum += r.confidence;
      confN += 1;
    }
    if (r.pinned) pinned += 1;
    if (r.createdAt && Date.parse(r.createdAt) >= weekAgo) recentlyLearned += 1;
  }

  return {
    total: records.length,
    recentlyLearned,
    pinned,
    categories: CATEGORIES.filter((c) => byCategory[c] > 0).length,
    entities: entityCount,
    avgConfidence: confN ? Math.round(confSum / confN) : 0,
    byCategory,
    bySource,
    recentActivity: [],
  };
}

function normalizeOverview(raw: any, records: MemoryRecord[], entityCount: number): MemoryOverview {
  if (!raw || typeof raw !== "object") return deriveOverview(records, entityCount);
  const derived = deriveOverview(records, entityCount);
  return {
    total: num(raw.total) ?? derived.total,
    recentlyLearned: num(raw.recently_learned ?? raw.recentlyLearned) ?? derived.recentlyLearned,
    pinned: num(raw.pinned) ?? derived.pinned,
    categories: num(raw.categories) ?? derived.categories,
    entities: num(raw.entities) ?? derived.entities,
    avgConfidence: pct(raw.avg_confidence ?? raw.avgConfidence) ?? derived.avgConfidence,
    byCategory: derived.byCategory,
    bySource: derived.bySource,
    recentActivity: arr(raw.recent_activity ?? raw.recentActivity).map((a: any, i: number) => ({
      id: str(a.id ?? i),
      at: str(a.at ?? a.created_at ?? ""),
      text: str(a.text ?? a.summary ?? ""),
      category: asCategory(a.category),
      kind: (["learned", "updated", "reinforced"].includes(a.kind) ? a.kind : "learned") as
        | "learned"
        | "updated"
        | "reinforced",
    })),
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/**
 * Fetch everything the Memory screen needs. Never throws — resolves to usable
 * data, falling back to the demo adapter when the backend is absent (today,
 * always). Records are the backbone: without them the payload is demo.
 */
export async function getMemoryData(signal?: AbortSignal): Promise<MemoryData> {
  const paths = ["/memory/records", "/memory/entities", "/memory/overview"];

  const [recRes, entRes, ovRes] = (await Promise.all(
    paths.map((p) => fetchEndpoint(p, signal)),
  )) as EndpointResult[];
  const results = [recRes, entRes, ovRes];

  // Records are the backbone. Without them we serve demo data.
  if (!recRes.ok || recRes.data == null) {
    const demo = buildDemoMemoryData();
    demo.diagnostics = toDiagnostics("demo", results);
    return demo;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawRec: any = recRes.data;
  const records: MemoryRecord[] = arr(rawRec.records ?? rawRec).map(normalizeRecord);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawEnt: any = entRes.ok ? entRes.data : null;
  const entities: Entity[] = arr(rawEnt?.entities ?? rawEnt).map(normalizeEntity);
  const relationships: Relationship[] = arr(rawEnt?.relationships).map(normalizeRelationship);

  const overview = normalizeOverview(ovRes.ok ? ovRes.data : null, records, entities.length);

  return {
    isDemo: false,
    diagnostics: toDiagnostics("live", results),
    records,
    entities,
    relationships,
    overview,
  };
}
