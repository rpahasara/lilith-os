/**
 * Headless regression test for the Memory Archive evidence explorer: filters
 * and facets work on what the source returned, nothing is invented where the
 * source is silent, the Archive stays read-only, and the Brain / Archive /
 * Timeline navigation is kept.
 *
 * The fixture has the shape production returns today (see
 * services/core-api/app.py): no classification, confidence on some memories
 * only, no importance, pins, links or last-accessed. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryDetailBody, MemoryReadOnlyFooter } from "@/components/memory/memory-detail";
import { MemoryExplorer } from "@/components/memory/memory-explorer";
import { MemoryRow } from "@/components/memory/memory-row";
import { normalizeRecord } from "@/lib/memory/client";
import {
  EMPTY_FILTERS,
  activeFilterCount,
  applyFilters,
  confidenceBand,
  coverage,
  entityRelations,
  facetIsUseful,
  facetNote,
  facets,
  matchesQuery,
  recordTime,
  sharedEntityRecords,
  sortRecords,
  timeBand,
} from "@/lib/memory/explorer";
import type { Entity, MemoryData, MemoryRecord, Relationship } from "@/lib/memory/types";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const NOW = Date.parse("2026-11-16T12:00:00Z");
const ago = (days: number) => new Date(NOW - days * 86400000).toISOString();
const src = (...path: string[]) => readFileSync(join(process.cwd(), "src", ...path), "utf8");

/* A payload exactly as the backend sends it today, run through the real normaliser. */
const RAW = [
  { id: "c1", summary: "Final interview confirmed", content: "Final interview confirmed.", category: "career", kind: "unknown",
    entities: [{ id: "company_1", type: "company", label: "Northwind" }, { id: "person_1", type: "person", label: "Dana Reyes" }],
    confidence: 0.95, importance: null, pinned: false, tags: ["interview"],
    provenance: { kind: "career_event", source_account: "gmail · primary", label: "Seen in a career email", at: ago(1) },
    created_at: ago(1), updated_at: ago(1), last_accessed: null, related: [] },
  { id: "c2", summary: "Recruiter asked for availability", content: "Recruiter asked for availability.", category: "career", kind: "unknown",
    entities: [{ id: "company_1", type: "company", label: "Northwind" }], confidence: 0.72, importance: null, pinned: false, tags: ["recruiter"],
    provenance: { kind: "career_event", source_account: "gmail · primary", label: "Seen in a career email", at: ago(12) },
    created_at: ago(12), updated_at: ago(12), last_accessed: null, related: [] },
  { id: "c3", summary: "Role mentioned in a newsletter", content: "Role mentioned.", category: "career", kind: "unknown",
    entities: [{ id: "company_2", type: "company", label: "Lumen Works" }], confidence: 0.45, importance: null, pinned: false, tags: [],
    provenance: { kind: "career_event", source_account: "gmail · secondary", label: "Seen in a career email", at: ago(60) },
    created_at: ago(60), updated_at: ago(60), last_accessed: null, related: [] },
  { id: "m1", summary: "Prefers written briefs", content: "Prefers written briefs.", category: "preferences", kind: "unknown",
    entities: [], confidence: null, importance: null, pinned: false, tags: [],
    provenance: { kind: "curated_memory", source_account: "hermes · memories", label: "Written to curated memory" },
    created_at: null, updated_at: null, last_accessed: null, related: [] },
];
const RECORDS: MemoryRecord[] = RAW.map(normalizeRecord);
const ENTITIES: Entity[] = [
  { id: "company_1", type: "company", label: "Northwind", memoryCount: 2 },
  { id: "company_2", type: "company", label: "Lumen Works", memoryCount: 1 },
  { id: "person_1", type: "person", label: "Dana Reyes", memoryCount: 1 },
];
const RELATIONSHIPS: Relationship[] = [{ id: "r1", from: "person_1", to: "company_1", kind: "works at" }];
const DATA: MemoryData = {
  records: RECORDS,
  entities: ENTITIES,
  relationships: RELATIONSHIPS,
  isDemo: false,
  overview: { total: 4, recentlyLearned: 1, pinned: 0, categories: 2, entities: 3, avgConfidence: 71,
    byCategory: { people: 0, projects: 0, career: 3, work: 0, personal: 0, preferences: 1, knowledge: 0 }, bySource: {}, recentActivity: [] },
};
const ids = (rs: MemoryRecord[]) => rs.map((r) => r.id).join(",");
const by = (id: string) => RECORDS.find((r) => r.id === id) as MemoryRecord;

export function runExplorerSelfTest(): Result[] {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `archive-explorer: ${name}`, pass, detail: pass ? undefined : detail });

  /* nothing invented ------------------------------------------------------------ */
  check("an unstated classification stays unknown through the loader", RECORDS.every((r) => r.kind === "unknown"));
  check("an absent confidence stays absent", by("m1").confidence === undefined && confidenceBand(undefined) === "unstated");
  check("confidence bands follow the stated value only",
    confidenceBand(95) === "high" && confidenceBand(85) === "high" && confidenceBand(72) === "medium" && confidenceBand(45) === "low" && confidenceBand(0) === "low");
  check("a memory with no date is undated, not dated now",
    recordTime(by("m1")) === undefined && timeBand(undefined, NOW) === "undated" && timeBand("not a date", NOW) === "undated");
  check("time bands are measured from the memory's own date",
    timeBand(ago(1), NOW) === "week" && timeBand(ago(12), NOW) === "month" && timeBand(ago(60), NOW) === "older");

  /* facets ------------------------------------------------------------------------- */
  const f = facets(RECORDS, NOW);
  check("facets list only values that occur, with counts",
    f.sources.map((s) => `${s.key}:${s.count}`).join() === "career_event:3,curated_memory:1" &&
      f.categories.map((c) => c.key).join() === "career,preferences" &&
      f.confidence.map((c) => `${c.key}:${c.count}`).join() === "high:1,medium:1,low:1,unstated:1" &&
      f.time.map((t) => `${t.key}:${t.count}`).join() === "week:1,month:1,older:1,undated:1");
  check("classification is not offered as a filter when the source never states it",
    f.kinds.length === 1 && f.kinds[0].key === "unknown" && !facetIsUseful(f.kinds) && facetIsUseful(f.sources));
  check("the gap is described as the source's, not as a property of the memories",
    facetNote("kinds", f.kinds) === "Not stated by the source for any of these memories." &&
      !/fact|inference/i.test(facetNote("kinds", f.kinds)));
  const mixed = facets([{ ...by("c1"), kind: "fact" }, { ...by("c2"), kind: "inference" }, by("c3")], NOW);
  check("classification becomes a filter once the source states it", facetIsUseful(mixed.kinds) && mixed.kinds.map((k) => k.key).join() === "fact,inference,unknown");

  /* filters ------------------------------------------------------------------------- */
  const run = (patch: Partial<typeof EMPTY_FILTERS>) => ids(applyFilters(RECORDS, { ...EMPTY_FILTERS, ...patch }, NOW));
  check("no filter shows everything", run({}) === "c1,c2,c3,m1" && activeFilterCount(EMPTY_FILTERS) === 0);
  check("source filter", run({ sources: ["curated_memory"] }) === "m1");
  check("confidence filter, including 'not stated'", run({ confidence: ["high"] }) === "c1" && run({ confidence: ["unstated"] }) === "m1");
  check("choices in one facet widen", run({ confidence: ["high", "low"] }) === "c1,c3");
  check("facets narrow each other", run({ sources: ["career_event"], time: ["week", "month"] }) === "c1,c2" && run({ sources: ["curated_memory"], confidence: ["high"] }) === "");
  check("time filter, including undated", run({ time: ["undated"] }) === "m1" && run({ time: ["older"] }) === "c3");
  check("entity filter", run({ entityId: "company_1" }) === "c1,c2" && run({ entityId: "person_1" }) === "c1");
  check("category filter", run({ categories: ["preferences"] }) === "m1");
  check("the filter count ignores the search text", activeFilterCount({ ...EMPTY_FILTERS, query: "x", sources: ["career_event"], entityId: "e" }) === 2);

  /* search ---------------------------------------------------------------------------- */
  check("search covers the text, entities, tags, source and account",
    matchesQuery(by("c1"), "interview") && matchesQuery(by("c1"), "dana") && matchesQuery(by("c3"), "secondary") &&
      matchesQuery(by("m1"), "curated") && matchesQuery(by("c2"), "RECRUITER"));
  check("every word must match", matchesQuery(by("c1"), "northwind interview") && !matchesQuery(by("c2"), "northwind interview"));
  check("an empty search matches everything", matchesQuery(by("m1"), "  "));
  check("search and filters combine", run({ query: "northwind", confidence: ["medium"] }) === "c2");

  /* sort -------------------------------------------------------------------------------- */
  check("newest first, undated last", ids(sortRecords(RECORDS, "newest")) === "c1,c2,c3,m1");
  check("by confidence, unstated last", ids(sortRecords([by("m1"), by("c3"), by("c1"), by("c2")], "confidence")) === "c1,c2,c3,m1");
  check("sorting does not reorder the input", ids(RECORDS) === "c1,c2,c3,m1");

  /* connections --------------------------------------------------------------------------- */
  const shared = sharedEntityRecords(by("c1"), RECORDS);
  check("connected memories are those the source tagged with the same entity",
    shared.length === 1 && shared[0].record.id === "c2" && shared[0].via.map((e) => e.label).join() === "Northwind");
  check("a memory without entities has no derived connections", sharedEntityRecords(by("m1"), RECORDS).length === 0);
  const rel = entityRelations("company_1", ENTITIES, RELATIONSHIPS);
  check("entity relationships come from the backend's edges, with direction",
    rel.length === 1 && rel[0].kind === "works at" && rel[0].direction === "in" && rel[0].other.label === "Dana Reyes" &&
      entityRelations("person_1", ENTITIES, RELATIONSHIPS)[0].direction === "out" && entityRelations("company_2", ENTITIES, RELATIONSHIPS).length === 0);
  const cov = coverage(RECORDS);
  check("coverage counts what the source supplied",
    cov.total === 4 && cov.classified === 0 && cov.withConfidence === 3 && cov.dated === 3 && cov.withEntities === 3 && cov.linked === 0);

  /* the row ---------------------------------------------------------------------------------- */
  const row = (r: MemoryRecord) => renderToStaticMarkup(createElement(MemoryRow, { record: r, selected: false, tabIndex: 0, onSelect: () => {} }));
  check("a row is an option with its source, confidence and date",
    /role="option"/.test(row(by("c1"))) && /aria-selected="false"/.test(row(by("c1"))) && /Career event/.test(row(by("c1"))) &&
      /data-row-confidence="95"/.test(row(by("c1"))) && />95%</.test(row(by("c1"))));
  check("a row never shows a classification the source did not state",
    RECORDS.every((r) => /aria-label="Classification not stated"/.test(row(r)) && !/>Fact<|>Inference</.test(row(r))));
  check("a row shows a dash, not a number, for an unstated confidence",
    /data-row-confidence="unstated"/.test(row(by("m1"))) && /aria-label="Confidence not stated"/.test(row(by("m1"))) && !/\d+%/.test(row(by("m1"))));
  check("an undated row says so", /aria-label="Undated"/.test(row(by("m1"))));
  check("a stated fact is shown as one", />Fact</.test(row({ ...by("c1"), kind: "fact" })));

  /* the detail --------------------------------------------------------------------------------- */
  const detail = (r: MemoryRecord) => renderToStaticMarkup(createElement(MemoryDetailBody, {
    record: r, allRecords: RECORDS, entities: ENTITIES, relationships: RELATIONSHIPS, onSelectRelated: () => {}, onFilterEntity: () => {} }));
  const d1 = detail(by("c1"));
  check("the detail keeps provenance: kind, account, reason and signal time",
    /Why Lilith knows this/.test(d1) && /Career event/.test(d1) && /gmail · primary/.test(d1) && /Seen in a career email/.test(d1) && /signal ·/.test(d1));
  check("the detail states the kind of claim and what it means",
    /data-kind="unknown"/.test(d1) && /Classification not stated by the source/.test(d1));
  check("the detail shows entities with the backend's relationships", /Northwind/.test(d1) && /Dana Reyes/.test(d1) && /works at/.test(d1));
  check("the detail lists connected memories and says why", /Recruiter asked for availability/.test(d1) && /Also about Northwind/.test(d1));
  check("the detail keeps the timestamps and says which are not recorded", /Recorded/.test(d1) && /Updated/.test(d1) && /Last accessed/.test(d1) && /Not recorded/.test(d1));
  const dm = detail(by("m1"));
  check("an unstated confidence is said, not drawn as a meter",
    /Not stated by the source\./.test(dm) && !/\d+%/.test(dm) && /The source attached no entities/.test(dm));
  check("importance is not shown when the source gives none", !/Importance/.test(d1) && /Importance/.test(detail({ ...by("c1"), importance: 70 })));
  check("each entity can narrow the list, by name", /aria-label="Show only memories about Northwind"/.test(d1));

  /* read-only ------------------------------------------------------------------------------------ */
  const footer = renderToStaticMarkup(createElement(MemoryReadOnlyFooter));
  check("the read-only stance is stated and the write actions stay disabled",
    /Read-only/.test(footer) && (footer.match(/disabled=""/g) ?? []).length === 3 && /Forget/.test(footer));
  const code = ["components/memory/memory-explorer.tsx", "components/memory/memory-row.tsx", "components/memory/memory-detail.tsx", "lib/memory/explorer.ts"]
    .map((p) => src(...p.split("/"))).join("\n");
  check("the explorer makes no request and stores nothing", !/\bfetch\s*\(|fetchEndpoint|localStorage|sessionStorage|method:\s*"(POST|PUT|PATCH|DELETE)"/.test(code));
  check("the explorer has no enabled write control", !/onPin|onEdit|onForget|onDelete/.test(code));

  /* the whole explorer ------------------------------------------------------------------------------ */
  const page = renderToStaticMarkup(createElement(MemoryExplorer, { data: DATA }));
  check("search comes first, as a labelled search", /role="search"/.test(page) && /aria-label="Search Lilith&#x27;s memory"/.test(page) &&
    page.indexOf('role="search"') < page.indexOf('role="listbox"'));
  check("the list is a labelled listbox with one tab stop",
    /role="listbox"/.test(page) && /aria-label="Memories"/.test(page) && (page.match(/data-memory-row=/g) ?? []).length === 4 &&
      (page.match(/role="option"[^>]*tabindex="0"/g) ?? []).length === 1);
  check("the result count is announced", /role="status"[^>]*aria-live="polite"[^>]*data-result-count="4"/.test(page));
  check("refining is a disclosure, closed by default", /aria-expanded="false"/.test(page) && !/data-facet=/.test(page));
  check("with production's data the page shows no fact or inference label", !/>Fact<|>Inference</.test(page));

  /* navigation and the Atlas -------------------------------------------------------------------------- */
  const route = src("app", "memory", "page.tsx");
  check("the memory switch is kept, also when Memory is unavailable",
    (route.match(/<MemoryViewSwitch active="archive" \/>/g) ?? []).length === 2);
  check("the Archive does not reach into the Atlas, or the Atlas into it",
    !/memory\/atlas\/(synthetic|store|simulation)/.test(code + route) && !/memory-explorer|lib\/memory\/explorer/.test(src("components", "memory", "atlas", "cognitive-atlas.tsx")));

  return out;
}
