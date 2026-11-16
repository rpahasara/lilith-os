/**
 * Headless regression test for the Memory Archive: what a real memory carries
 * from the backend is what the Archive shows. The fact / inference / unknown
 * classification, the provenance ("why Lilith knows this"), the source account,
 * confidence, importance, entities, relations and timestamps all survive the
 * trip from a live payload to the card and the detail drawer.
 *
 * No browser and no backend: `fetch` is replaced for the duration of the test,
 * and the components are server-rendered. Run by `npm run test:core`.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryDetail } from "@/components/memory/memory-detail";
import { ShardCard } from "@/components/memory/shard-card";
import { isUnavailable } from "@/lib/data-mode";
import { getMemoryData } from "@/lib/memory/client";
import { KIND_META, PROVENANCE_META, type MemoryData, type MemoryRecord } from "@/lib/memory/types";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

/** A live `/memory/records` payload: one of each classification. */
const LIVE_RECORDS = [
  {
    id: "m-fact",
    summary: "Prefers written briefs",
    content: "Prefers a written brief before any meeting.",
    category: "preferences",
    kind: "fact",
    confidence: 92,
    importance: 71,
    tags: ["meetings"],
    entities: [{ id: "e-1", type: "person", label: "Owner" }],
    provenance: { kind: "conversation", label: "Said so directly", source_account: "telegram · owner", at: "2026-11-01T09:30:00Z" },
    created_at: "2026-11-01T09:30:00Z",
    updated_at: "2026-11-02T10:00:00Z",
    related: ["m-inference"],
  },
  {
    id: "m-inference",
    summary: "Probably prefers mornings",
    content: "Most briefs are requested before 10am.",
    category: "preferences",
    kind: "inference",
    confidence: 55,
    tags: [],
    entities: [],
    provenance: { kind: "inferred", label: "Derived from request times" },
    related: [],
  },
  {
    id: "m-unstated",
    summary: "A record with no stated class",
    content: "The source did not say what kind of memory this is.",
    category: "knowledge",
    tags: [],
    entities: [],
    related: [],
  },
];

async function withBackend<T>(fn: () => Promise<T>): Promise<T> {
  const real = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/memory/records") ? { records: LIVE_RECORDS } : url.includes("/memory/entities") ? { entities: [] } : {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
  try {
    return await fn();
  } finally {
    globalThis.fetch = real;
  }
}

export async function runArchiveSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `archive: ${name}`, pass, detail: pass ? undefined : detail });

  const loaded = await withBackend(() => getMemoryData(undefined, false));
  if (isUnavailable(loaded)) {
    check("a live payload loads as live data", false, "loader returned unavailable");
    return out;
  }
  const data: MemoryData = loaded;
  const byId = (id: string) => data.records.find((r) => r.id === id) as MemoryRecord;

  check("a live payload is live, not simulated", data.isDemo === false && data.diagnostics?.mode === "live");
  check("every live record is kept", data.records.length === LIVE_RECORDS.length, String(data.records.length));

  /* classification ---------------------------------------------------------- */
  check("a stated fact stays a fact", byId("m-fact")?.kind === "fact");
  check("a stated inference stays an inference", byId("m-inference")?.kind === "inference");
  check("an unstated class is unknown, never promoted to fact", byId("m-unstated")?.kind === "unknown");

  /* provenance and metadata --------------------------------------------------- */
  const fact = byId("m-fact");
  check("provenance kind, label and signal time are kept",
    fact.provenance.kind === "conversation" && fact.provenance.label === "Said so directly" && Boolean(fact.provenance.at),
    JSON.stringify(fact.provenance));
  check("missing provenance is unknown, never shown as manual", byId("m-unstated").provenance.kind === "unknown");
  check("confidence, importance, tags, entities and relations are kept",
    fact.confidence === 92 && fact.importance === 71 && fact.tags.includes("meetings") &&
      fact.entities.length === 1 && fact.related.includes("m-inference"));
  check("an absent confidence stays absent, not invented", byId("m-unstated").confidence === undefined);

  /* the card ------------------------------------------------------------------- */
  for (const record of data.records) {
    const card = renderToStaticMarkup(createElement(ShardCard, { record, onSelect: () => {} }));
    check(`the card shows the class of ${record.id}`, card.includes(KIND_META[record.kind].label), card.slice(0, 160));
    check(`the card shows the source of ${record.id}`, card.includes(PROVENANCE_META[record.provenance.kind].label));
  }

  /* the detail drawer ----------------------------------------------------------- */
  const drawer = (record: MemoryRecord) =>
    renderToStaticMarkup(
      createElement(MemoryDetail, { record, allRecords: data.records, onClose: () => {}, onSelectRelated: () => {} }),
    );
  for (const record of data.records) {
    const html = drawer(record);
    check(`the drawer shows the class of ${record.id} and what it means`,
      html.includes(KIND_META[record.kind].label) && html.includes(KIND_META[record.kind].title),
      html.slice(0, 200));
    check(`the drawer shows the source of ${record.id}`,
      html.includes("Why Lilith knows this") && html.includes(PROVENANCE_META[record.provenance.kind].label) &&
        html.includes(record.provenance.label));
  }
  const factHtml = drawer(fact);
  check("the drawer shows the source account when there is one",
    !fact.provenance.sourceAccount || factHtml.includes(fact.provenance.sourceAccount));
  check("the drawer shows confidence, importance, entities, relations and timestamps",
    /Confidence/.test(factHtml) && /Importance/.test(factHtml) && factHtml.includes("Owner") &&
      factHtml.includes("Probably prefers mornings") && /Created/.test(factHtml) && /Updated/.test(factHtml));
  check("the drawer keeps its read-only promise", /Read-only/.test(factHtml) && (factHtml.match(/disabled=""/g) ?? []).length >= 3);

  return out;
}
