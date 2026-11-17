/**
 * Headless regression test for Real memory in the Cognitive Atlas.
 *
 * Covers the projection (category → region, Work kept as Work, explicit vs
 * shared-entity links, entity relationships never drawn as memory links),
 * missing metadata staying missing, snapshot reconciliation (observed,
 * changed, withdrawn — and a withdrawn record leaving no trace in any index),
 * failed or malformed reads never deleting anything, the read-only and
 * no-persistence boundaries, and the simulation staying untouched.
 *
 * Every fixture is invented and shaped like the backend contract
 * (services/core-api/app.py). No real memory, response or name is used.
 * Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { EndpointResult } from "@/lib/api";
import { RealNodeInspector, RealTimelineNotice } from "@/components/memory/atlas/real-panels";
import { buildBrainLayout } from "./brain-shape";
import {
  CATEGORY_REGION,
  SHARED_ENTITY_LINK_CAP,
  UNMAPPED_REGIONS,
  buildRealGraph,
  fetchSnapshot,
  projectLinks,
  projectRecord,
  reconcile,
  regionLabel,
  stepReal,
  type MemorySnapshot,
  type RealView,
  type SnapshotFetch,
} from "./real-source";
import { DEFAULT_RENDER_WEIGHT, renderWeight } from "./render";
import { createSimulation } from "./simulation";
import { createAtlasStore } from "./store";
import { buildSyntheticGraph } from "./synthetic";
import { normalizeEntity, normalizeRecord, normalizeRelationship } from "@/lib/memory/client";
import { CATEGORIES, type MemoryRecord } from "@/lib/memory/types";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const src = (...path: string[]) => readFileSync(join(process.cwd(), "src", ...path), "utf8");
const T0 = Date.parse("2026-11-16T12:00:00Z");
const iso = (daysAgo: number) => new Date(T0 - daysAgo * 86400000).toISOString();

/* ---------------------------------------------------------------- fixtures */

type Raw = Record<string, unknown>;

/** A record exactly as the backend sends one today (only invented content). */
function raw(id: string, over: Raw = {}): Raw {
  return {
    id,
    summary: `Record ${id}`,
    content: `Content of ${id}.`,
    category: "knowledge",
    kind: "unknown",
    entities: [],
    confidence: null,
    importance: null,
    pinned: false,
    tags: [],
    provenance: { kind: "file", source_account: null, label: "Curated memory file", at: null },
    created_at: null,
    updated_at: iso(40),
    last_accessed: null,
    related: [],
    ...over,
  };
}

const ACME = { id: "org_acme", type: "company", label: "Acme Test Co" };
const ROBIN = { id: "person_robin", type: "person", label: "Robin Example" };
const KITE = { id: "project_kite", type: "project", label: "Project Kite" };

const BASE: Raw[] = [
  raw("w1", { category: "work", summary: "Prefers async stand-ups", entities: [ACME] }),
  raw("c1", {
    category: "career",
    summary: "Interview scheduled",
    entities: [ACME, ROBIN],
    confidence: 0.82,
    provenance: { kind: "career_event", source_account: "mail · test", label: "Seen in a test email", at: iso(3) },
    created_at: iso(3),
    updated_at: iso(3),
  }),
  raw("p1", { category: "projects", summary: "Kite prototype", entities: [KITE, ROBIN], related: ["k1"] }),
  raw("k1", { category: "knowledge", summary: "Kite uses a test protocol", entities: [KITE] }),
  raw("pe1", { category: "people", summary: "Robin is a test contact", entities: [ROBIN] }),
];

const ENTITIES = {
  entities: [ACME, ROBIN, KITE],
  relationships: [{ id: "rel_1", from: "person_robin", to: "org_acme", kind: "works at" }],
};

/** A fake fetch that serves fixed answers and records every call. */
function fakeFetch(records: unknown, entities: unknown = ENTITIES, status = { records: 200, entities: 200 }) {
  const calls: { path: string; extra: number }[] = [];
  const impl: SnapshotFetch = async (path, ...rest) => {
    calls.push({ path, extra: rest.length > 1 ? 1 : 0 });
    const which = path === "/memory/records" ? "records" : "entities";
    const code = status[which];
    const ok = code >= 200 && code < 300;
    return { path, ok, status: code, data: ok ? (which === "records" ? records : entities) : null } as EndpointResult;
  };
  return { impl, calls };
}

function snapshotOf(rows: Raw[], at = T0): MemorySnapshot {
  return {
    takenAt: at,
    records: rows.map((r) => normalizeRecord(r)),
    entities: ENTITIES.entities.map((e) => normalizeEntity(e)),
    relationships: ENTITIES.relationships.map(normalizeRelationship),
    unidentified: 0,
  };
}

/* -------------------------------------------------------------------- test */

export async function runAtlasRealSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `atlas real: ${name}`, pass, detail: pass ? undefined : detail });
  const layout = buildBrainLayout();
  const records: MemoryRecord[] = BASE.map((r) => normalizeRecord(r));

  /* mapping ----------------------------------------------------------------- */
  check("every memory category has a region", CATEGORIES.every((c) => Boolean(CATEGORY_REGION[c])));
  check("no category is drawn in the Relationships domain",
    !Object.values(CATEGORY_REGION).includes("relationships") && UNMAPPED_REGIONS.includes("relationships"));
  const w1 = projectRecord(records[0]);
  check("Work sits in the Career field but stays Work", w1.region === "career" && w1.category === "work");
  check("Work never becomes Projects", CATEGORY_REGION.work !== "projects");
  check("the Career field is named for both categories in Real mode",
    regionLabel("career", "real") === "Career · Work" && regionLabel("career") === "Career");
  check("every projected node is marked real", records.map(projectRecord).every((n) => n.origin === "real"));

  /* missing metadata stays missing ---------------------------------------------- */
  check("no confidence is invented", w1.confidence === undefined);
  check("no importance is invented", w1.importance === undefined);
  check("no creation date is invented (file mtime stays an update date)",
    w1.createdAt === undefined && typeof w1.updatedAt === "number");
  check("no signal time is invented", w1.provenance.at === undefined);
  check("an unstated classification stays unknown", w1.kind === "unknown");
  check("a stated confidence comes through as stated", projectRecord(records[1]).confidence === 82);
  check("node size falls back to a drawing default without touching the data",
    renderWeight(w1) === DEFAULT_RENDER_WEIGHT && w1.importance === undefined);

  const graph = buildRealGraph(snapshotOf(BASE), layout);
  check("real nodes carry no growth, recall or reinforcement history",
    graph.nodes.every((n) => n.born === 0 && !n.live && n.recalls === 0 && n.reinforcements === 0 && n.reinforcedAt === undefined));
  const again = buildRealGraph(snapshotOf(BASE), layout);
  check("positions are stable for the same records",
    graph.nodes.every((n, i) => n.id === again.nodes[i].id && n.position.join() === again.nodes[i].position.join()));

  /* links --------------------------------------------------------------------- */
  const links = projectLinks(records);
  const explicit = links.filter((l) => l.basis === "explicit");
  const shared = links.filter((l) => l.basis === "shared-entity");
  check("the source's own relation becomes an explicit link",
    explicit.length === 1 && explicit[0].id === "explicit:k1|p1");
  check("a pair the source linked is not also drawn as shared-entity",
    !shared.some((l) => l.id === "shared:k1|p1"));
  check("shared-entity links name the entities they share",
    shared.some((l) => l.id === "shared:c1|w1" && l.via?.join() === "Acme Test Co") &&
      shared.some((l) => l.id === "shared:c1|p1" && l.via?.join() === "Robin Example"));
  check("entity-to-entity relationships are never drawn as memory links",
    links.every((l) => l.basis !== "synthetic") &&
      projectLinks(records).length === links.length && // independent of the entities payload
      !links.some((l) => /works at/.test(l.kind)));
  const crowd = Array.from({ length: SHARED_ENTITY_LINK_CAP + 1 }, (_, i) =>
    normalizeRecord(raw(`crowd${i}`, { entities: [{ id: "topic_x", type: "topic", label: "Common topic" }] })));
  check("an entity on too many records draws no pathways", projectLinks(crowd).length === 0);
  check("a relation to a record that is not present is not drawn",
    projectLinks([normalizeRecord(raw("lonely", { related: ["missing"] }))]).length === 0);

  /* reconciliation ------------------------------------------------------------- */
  const store = createAtlasStore(buildRealGraph(snapshotOf(BASE), layout), layout);
  const placed = store.node("c1")!.position.join();
  const next = BASE.filter((r) => r.id !== "pe1").map((r) => (r.id === "c1" ? { ...r, summary: "Interview moved" } : r));
  next.push(raw("n1", { category: "people", summary: "New test contact", entities: [ROBIN] }));
  const diff = reconcile(store.getState(), snapshotOf(next, T0 + 60_000));
  for (const e of diff.events) store.apply(e);
  const s = store.getState();
  check("a new record is reported as observed, not learned",
    diff.events.some((e) => e.type === "record.observed" && e.node.id === "n1") &&
      !diff.events.some((e) => e.type.startsWith("memory.")) && s.session.learned === 0);
  check("a changed record is updated in place",
    store.node("c1")?.title === "Interview moved" && store.node("c1")!.position.join() === placed);
  check("a record gone from a successful snapshot leaves the graph", !store.node("pe1") && !s.nodes.some((n) => n.id === "pe1"));
  check("its pathways go with it",
    !s.links.some((l) => l.source === "pe1" || l.target === "pe1") && store.linksOf("pe1").length === 0 &&
      store.between("pe1", "c1") === undefined && store.between("pe1", "p1") === undefined);
  check("nothing of its content stays in the activity log",
    !JSON.stringify(s.activity).includes("Robin is a test contact") &&
      !JSON.stringify(s).includes("Robin is a test contact"));
  check("new shared-entity links arrive after their records",
    diff.events.findIndex((e) => e.type === "link.observed") > diff.events.findIndex((e) => e.type === "record.observed"));
  check("the counters describe differences, not cognition",
    s.changes.observed === 1 && s.changes.changed === 1 && s.changes.withdrawn === 1 && s.session.recalled === 0);
  const quiet = reconcile(store.getState(), snapshotOf(next, T0 + 120_000));
  check("an unchanged snapshot produces no events", quiet.events.length === 0, String(quiet.events.length));

  /* reads -------------------------------------------------------------------- */
  const ok = fakeFetch({ records: BASE });
  const good = await fetchSnapshot(undefined, ok.impl, () => T0);
  check("a good read returns every identified record", good.ok && good.snapshot.records.length === BASE.length);
  check("reads are plain GETs of the two read-only endpoints",
    ok.calls.map((c) => c.path).sort().join() === "/memory/entities,/memory/records" && ok.calls.every((c) => c.extra === 0));

  const noId = fakeFetch({ records: [...BASE, { summary: "no id here" }, BASE[0]] });
  const partial = await fetchSnapshot(undefined, noId.impl, () => T0);
  check("records without an id are left out and counted, duplicates dropped",
    partial.ok && partial.snapshot.unidentified === 1 && partial.snapshot.records.length === BASE.length);

  const malformed = await fetchSnapshot(undefined, fakeFetch({ records: "nope" }).impl);
  check("a malformed records body is a failure", !malformed.ok && malformed.reason === "malformed");
  const refused = await fetchSnapshot(undefined, fakeFetch(null, ENTITIES, { records: 401, entities: 200 }).impl);
  check("a refused read is a failure", !refused.ok && refused.reason === "refused");
  const down = await fetchSnapshot(undefined, fakeFetch(null, ENTITIES, { records: 0, entities: 0 }).impl);
  check("an unreachable backend is a failure", !down.ok && down.reason === "unreachable");
  const unconfigured = await fetchSnapshot(undefined, fakeFetch(null, ENTITIES, { records: 503, entities: 503 }).impl);
  check("an unconfigured backend is a failure", !unconfigured.ok && unconfigured.reason === "unconfigured");
  const noEntities = await fetchSnapshot(undefined, fakeFetch({ records: BASE }, null, { records: 200, entities: 500 }).impl);
  check("a missing entities answer still yields the records", noEntities.ok && noEntities.snapshot.entities === null);

  /* steps: failure never deletes ---------------------------------------------------- */
  const first = stepReal(null, good, layout, T0);
  check("with nothing confirmed, a failure is 'unavailable' — no stand-in data",
    stepReal(null, down, layout, T0).kind === "unavailable");
  const view = first.kind === "ready" ? first.view : (null as unknown as RealView);
  const before = view.store.getState().nodes.length;
  const failed = stepReal(view, down, layout, T0 + 60_000);
  check("a failed read deletes nothing and marks the view stale",
    failed.kind === "ready" && failed.view.store.getState().nodes.length === before && failed.view.stale?.failure === "unreachable");
  const garbled = stepReal(view, malformed, layout, T0 + 60_000);
  check("a malformed read deletes nothing",
    garbled.kind === "ready" && garbled.view.store.getState().nodes.length === before);
  const empty = await fetchSnapshot(undefined, fakeFetch({ records: [] }).impl, () => T0 + 120_000);
  const cleared = stepReal(view, empty, layout, T0 + 120_000);
  check("a successful empty snapshot does remove everything",
    cleared.kind === "ready" && cleared.view.store.getState().nodes.length === 0 && cleared.view.stale === null);
  const keptEntities = stepReal(
    { ...view, entities: [{ id: "x", type: "concept", label: "Kept", memoryCount: 0 }] },
    noEntities,
    layout,
    T0,
  );
  check("a missing entities answer keeps the previous entity index",
    keptEntities.kind === "ready" && keptEntities.view.entities[0]?.label === "Kept" && keptEntities.view.entitiesStale);

  /* panels say only what the source says --------------------------------------------- */
  const panelStore = createAtlasStore(buildRealGraph(snapshotOf(BASE), layout), layout);
  const html = renderToStaticMarkup(
    createElement(RealNodeInspector, {
      node: panelStore.node("w1")!,
      store: panelStore,
      entities: snapshotOf(BASE).entities ?? [],
      relationships: snapshotOf(BASE).relationships ?? [],
      onClose: () => {},
      onSelect: () => {},
      onExplore: () => {},
    }),
  );
  check("the inspector keeps the source category and says where it is drawn",
    html.includes("Work") && html.includes("drawn in the Career · Work field"));
  check("the inspector shows no invented history",
    !/Learned|Reinforced|recalled|Last reinforced/.test(html) && html.includes("not stated"));
  check("entity relationships are shown as such, apart from memory links",
    renderToStaticMarkup(
      createElement(RealNodeInspector, {
        node: panelStore.node("c1")!,
        store: panelStore,
        entities: snapshotOf(BASE).entities ?? [],
        relationships: snapshotOf(BASE).relationships ?? [],
        onClose: () => {},
        onSelect: () => {},
        onExplore: () => {},
      }),
    ).includes("between entities") && html.includes("Share an entity · derived here"));
  check("the timeline says record dates are not learning history",
    renderToStaticMarkup(createElement(RealTimelineNotice, { nodes: panelStore.getState().nodes })).includes("not the moment Lilith learned it"));

  /* boundaries ------------------------------------------------------------------------ */
  const realFiles = {
    source: src("lib", "memory", "atlas", "real-source.ts"),
    hook: src("components", "memory", "atlas", "use-real-atlas.ts"),
    panels: src("components", "memory", "atlas", "real-panels.tsx"),
  };
  const code = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  check("Real memory never writes",
    !/method\s*:|POST|PUT|PATCH|DELETE/.test(code(realFiles.source)) &&
      !/fetchEndpoint\([^)]*,[^)]*,/.test(code(realFiles.source)));
  check("Real memory is never kept in browser storage",
    Object.values(realFiles).every((t) => !/localStorage|sessionStorage|indexedDB|caches\./.test(code(t))));
  const atlas = code(src("components", "memory", "atlas", "cognitive-atlas.tsx"));
  const writes = atlas.match(/localStorage\.setItem\([^)]*\)/g) ?? [];
  check("the Atlas stores only visual preferences",
    writes.length === 1 && /PREFS_KEY, JSON\.stringify\(\{ visuals, labels: labelsOn \}\)/.test(writes[0]), writes.join("; "));
  check("Real mode never uses demo data", !/demoDataEnabled|getMemoryData|DEMO/.test(code(realFiles.source)));
  check("Real mode never records a recall", /if \(isReal \|\| !recall\?\.done/.test(atlas));
  check("Simulation stays the default source", /useState<AtlasSource>\("simulation"\)/.test(atlas));
  check("the simulation never reads real memory",
    ["synthetic.ts", "simulation.ts"].every((f) => !/real-source|@\/lib\/api|memory\/client/.test(src("lib", "memory", "atlas", f))));
  check("the real path does not import the synthetic data",
    !/from "\.\/synthetic"|from "\.\/simulation"/.test(realFiles.source) &&
      !/from "\.\/synthetic"/.test(src("lib", "memory", "atlas", "store.ts")));

  /* simulation intact --------------------------------------------------------------------- */
  const simStore = createAtlasStore(buildSyntheticGraph(layout, T0), layout);
  const simState = simStore.getState();
  check("synthetic nodes and links are marked synthetic",
    simState.nodes.every((n) => n.origin === "synthetic") && simState.links.every((l) => l.basis === "synthetic"));
  check("synthetic nodes keep their full invented metadata",
    simState.nodes.every((n) => typeof n.confidence === "number" && typeof n.importance === "number" && typeof n.createdAt === "number"));
  const sim = createSimulation(simStore);
  sim.teach();
  check("the simulation still learns through the same store",
    simStore.getState().session.learned === 1 && simStore.getState().changes.observed === 0 &&
      simStore.getState().nodes.length === simState.nodes.length + 1);

  return out;
}
