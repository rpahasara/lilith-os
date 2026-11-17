/**
 * Headless regression test for P1-9 PR A (Memory → Beliefs, the World Model).
 *
 *   Privacy: owner-context beliefs are never requested, never kept if one
 *   arrives, and a single-belief read follows the list's visibility; store-wide
 *   counts are not passed on. (The proxy side is in server/edge-auth/self-test.)
 *   Provenance: only safe fields survive normalisation; ids, refs and notes do not.
 *   Presentation: readable subjects, plain-language states, values that are
 *   never raw JSON, and counts that describe exactly what is shown.
 *   Navigation: Beliefs is the fourth Memory lens, set apart by a divider, at
 *   /memory/beliefs; /world redirects there.
 *
 * Every fixture is invented. Run by `npm run test:core`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { KNOWN_ORIGINS, fetchBelief, fetchWorld, isVisibleBelief, safeProvenance, unavailable } from "@/lib/world/client";
import {
  confidenceBasis, countBeliefs, countLine, evidenceLine, filterBeliefs, formatStamp, formatValue,
  groupBySubject, humanize, NO_FILTERS,
} from "@/lib/world/present";
import type { Belief } from "@/lib/world/types";
import { MemoryViewSwitch } from "@/components/memory/memory-view-switch";
import { BeliefsView } from "@/components/memory/beliefs/beliefs-view";
import { isNavActive } from "@/components/layout/nav";
import { worldDetailHidden, worldListRefused } from "@/server/world-visibility";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const root = process.cwd();
const read = (...path: string[]) => readFileSync(join(root, ...path), "utf8");

/* -------------------------------------------------------------- fixtures */

const wire = (entityType: string, id: string, predicate: string, value: unknown, extra: Record<string, unknown> = {}) => ({
  key: `${entityType}:${id}:${predicate}`,
  entity_type: entityType,
  entity_id: id,
  predicate,
  value,
  lifecycle_state: "ACTIVE",
  epistemic_state: "OBSERVED",
  confidence: { value: 0.9, tier: "high", basis: "observed+2corrob" },
  provenance: [{
    source_class: "LIVE_CONNECTOR", source_id: "career-store", source_type: "career.application",
    correlation_id: "evt_invented_42", observed_at: "2026-03-04 10:05:00", confidence: 0.9,
    origin_ref: "job_applications/invented-7", note: "acct:someone@example.invalid",
  }],
  observed_at: "2026-03-04 10:05:00",
  created_at: "2026-03-01T08:00:00Z",
  updated_at: "2026-03-04T10:06:00Z",
  revision: 2,
  supersedes: [],
  contradicted_by: [],
  ...extra,
});

const WIRE = [
  wire("career.application", "7", "role", "Invented Platform Engineer"),
  wire("career.application", "7", "company", "Example Robotics"),
  wire("career.application", "7", "status", "applied"),
  wire("career.application", "7", "last_activity", "2026-03-04 10:05:00"),
  wire("career.application", "9", "role", "Invented Data Lead", { lifecycle_state: "CONFLICTED", contradicted_by: ["2026-03-05T00:00:00Z"], confidence: { value: 0.6, tier: "medium", basis: "conflicted_penalty" }, updated_at: "2026-02-01T00:00:00Z" }),
  wire("career.application", "9", "status", { stage: "interview", round: 2 }, { lifecycle_state: "STALE", confidence: { value: 0.7, tier: "medium", basis: "stale_penalty" }, updated_at: "2026-02-01T00:00:00Z" }),
  wire("career.application", "11", "role", "Old title", { lifecycle_state: "SUPERSEDED" }),
  wire("owner", "owner", "memory.invented.1", "A private owner memory", { epistemic_state: "USER_ASSERTED" }),
];

function stubFetch(status: number, body: unknown, seen: string[]) {
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    seen.push(String(input));
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
}

export async function runBeliefsP19SelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `p1-9a: ${name}`, pass, detail: pass ? undefined : detail });

  /* privacy: the read client --------------------------------------------------------- */
  const realFetch = globalThis.fetch;
  const seen: string[] = [];
  let beliefs: Belief[] = [];
  try {
    stubFetch(200, { beliefs: WIRE, meta: { total: 99, by_epistemic: { USER_ASSERTED: 11 }, last_reconciled_at: "2030-01-01" } }, seen);
    const live = await fetchWorld();
    beliefs = live.available ? live.beliefs : [];
    check("owner-context and superseded beliefs never reach the view",
      live.available && beliefs.length === 6 && beliefs.every((b) => b.entity.entityType !== "owner" && b.lifecycleState !== "SUPERSEDED"),
      beliefs.map((b) => b.key).join());
    check("store-wide counts are not passed on (they include hidden beliefs)", live.available && !("meta" in live && live.meta));
    seen.length = 0;
    await fetchWorld({ entityType: "owner" });
    await fetchWorld({ entityType: " Owner " });
    check("the client never asks for owner context", seen.every((u) => !/entity_type=/.test(u)), seen.join());

    stubFetch(200, WIRE[7], seen);
    const owner = await fetchBelief("owner:owner:memory.invented.1");
    check("a single owner-context belief reads exactly like an unknown key", !owner.available && owner.reason === "endpoint-not-live");
    stubFetch(200, WIRE[6], seen);
    const superseded = await fetchBelief("career.application:11:role");
    check("a single superseded belief is not shown either", !superseded.available);
    stubFetch(200, WIRE[0], seen);
    const one = await fetchBelief("career.application:7:role");
    check("a visible belief is read in full", one.available && one.beliefs[0]?.value === "Invented Platform Engineer");
    stubFetch(401, { detail: "nope" }, seen);
    const refused = await fetchBelief("career.application:7:role");
    check("a refused read is named as refused", !refused.available && refused.reason === "not-authorized");
  } finally {
    globalThis.fetch = realFetch;
  }
  check("visibility rule", !isVisibleBelief({ entity: { entityType: "OWNER", entityId: "x" }, lifecycleState: "ACTIVE" }) &&
    !isVisibleBelief({ entity: { entityType: "career.application", entityId: "1" }, lifecycleState: "SUPERSEDED" }) &&
    isVisibleBelief({ entity: { entityType: "career.application", entityId: "1" }, lifecycleState: "STALE" }));
  check("the proxy rule refuses owner lists and hides owner details",
    worldListRefused("os/world", new URLSearchParams("entity_type=owner")) && !worldListRefused("os/world", new URLSearchParams("entity_type=career.application")) &&
      worldDetailHidden(JSON.stringify({ entity_type: "owner" })) && !worldDetailHidden(JSON.stringify({ entity_type: "career.application" })) && !worldDetailHidden("not json"));
  const messages = [503, 401, 404, 502, 0, 500].map((status) => unavailable({ path: "/os/world", ok: false, status, data: null }).detail);
  check("unavailable reasons are honest and name no internals", messages.every((m) => !/Slice|LILITH_API_URL|tunnel|VM\b/.test(m)), messages.join(" | "));

  /* provenance ------------------------------------------------------------------------- */
  const p = safeProvenance(WIRE[0].provenance[0]);
  check("evidence keeps no source id, correlation id, origin ref or note",
    p.sourceId === undefined && p.correlationId === undefined && p.originRef === undefined && p.note === undefined, JSON.stringify(p));
  check("known sources get a readable origin; unknown ones get none",
    p.origin === KNOWN_ORIGINS["career-store"] && safeProvenance({ source_class: "SYSTEM", source_id: "mystery-42" }).origin === undefined);
  const line = evidenceLine(p);
  check("an evidence line is words, not identifiers",
    line.source === "Career pipeline record" && line.kind === "Career application" && line.when === "4 Mar 2026 · 10:05" && line.confidence === "0.90",
    JSON.stringify(line));
  const shown = JSON.stringify(beliefs);
  check("nothing sensitive from the fixture survives into the beliefs", !/someone@example|invented-7|evt_invented_42|acct:/.test(shown));

  /* presentation ----------------------------------------------------------------------- */
  check("codes read as words", humanize("career.application") === "Career application" && humanize("last_activity") === "Last activity");
  check("confidence rules read as words",
    confidenceBasis("observed+2corrob") === "Observed, corroborated by 2 more sources" && confidenceBasis("observed+1corrob").endsWith("1 more source") &&
      confidenceBasis("conflicted_penalty") === "Lowered because sources disagree" && confidenceBasis("stale_penalty") === "Lowered because the information is old" &&
      confidenceBasis("observed") === "Observed once");
  check("timestamps are shown as written, without shifting zones",
    formatStamp("2026-03-04 10:05:00") === "4 Mar 2026 · 10:05" && formatStamp("2026-03-04T10:06:00Z") === "4 Mar 2026 · 10:06" && formatStamp("2026-03-04") === "4 Mar 2026" && formatStamp("soon") === null);
  check("values are never raw JSON", formatValue({ stage: "interview", round: 2 }) === "Stage: interview · Round: 2" && formatValue(true) === "Yes" && formatValue(null) === "—" && formatValue(["a", "b"]) === "a, b");
  const subjects = groupBySubject(beliefs);
  check("beliefs are grouped by readable subject, a conflict first",
    subjects.length === 2 && subjects[0].title === "Invented Data Lead" && subjects[0].conflicted === 1 &&
      subjects[1].title === "Invented Platform Engineer" && subjects[1].subtitle === "Example Robotics", subjects.map((s) => s.title).join());
  check("facts read in a natural order", subjects[1].beliefs.map((b) => b.predicate).join() === "role,company,status,last_activity");
  check("a subject without a name still reads", groupBySubject([{ ...beliefs[2] }])[0].title === "Career application 7");
  const counts = countBeliefs(beliefs);
  check("counts describe exactly the beliefs shown",
    counts.beliefs === 6 && counts.subjects === 2 && counts.lifecycle.ACTIVE === 4 && counts.lifecycle.CONFLICTED === 1 && counts.lifecycle.STALE === 1 && counts.epistemic.OBSERVED === 6);
  check("count line", countLine(6, 2) === "6 beliefs about 2 subjects" && countLine(1, 1) === "1 belief about 1 subject");
  check("filters: lifecycle", filterBeliefs(beliefs, { ...NO_FILTERS, lifecycle: "CONFLICTED" }).length === 1);
  check("filters: search matches subjects and values",
    filterBeliefs(beliefs, { ...NO_FILTERS, query: "robotics" }).length === 4 && filterBeliefs(beliefs, { ...NO_FILTERS, query: "interview" }).length === 1);

  /* the view --------------------------------------------------------------------------- */
  const view = read("src", "components", "memory", "beliefs", "beliefs-view.tsx");
  check("the view shows no store-wide count", !/meta\b|\.total|byEpistemic|byLifecycle|lastReconciledAt/.test(view));
  // (a belief's key is used as a React list key and for the detail read, never as text)
  check("the view never renders ids, refs or notes",
    !/sourceId|correlationId|originRef|\.note\b/.test(view) && !/>\s*\{[\w?.]*\.(key|entityId)\}/.test(view) && !/\{[\w?.]*\.(key|entityId)\}\s*</.test(view));
  check("the view is read-only", !/method: "(POST|PUT|PATCH|DELETE)"|fetchEndpoint\(/.test(view));
  check("the inspector is the shared dialog and re-reads under the same rules", /<DetailDrawer/.test(view) && /fetchBelief\(open\.key/.test(view));
  check("an unavailable store is the shared honest state with a retry", /<WorkspaceUnavailable/.test(view) && /onRetry=/.test(view));
  check("owner context is mentioned without a number", /Private owner context is not shown here\./.test(view));
  const loading = renderToStaticMarkup(createElement(BeliefsView));
  check("first render: the header, the Beliefs lens and a reading state", /Beliefs/.test(loading) && /Reading the belief store/.test(loading) && /aria-current="page"[^>]*>[\s\S]*?Beliefs/.test(loading));

  /* navigation ------------------------------------------------------------------------- */
  const sw = renderToStaticMarkup(createElement(MemoryViewSwitch, { active: "beliefs" }));
  const order = [...sw.matchAll(/>(Brain|Archive|Timeline|Beliefs)</g)].map((m) => m[1]).join();
  check("Beliefs is the fourth lens, after Brain, Archive and Timeline", order === "Brain,Archive,Timeline,Beliefs", order);
  check("a divider sets Beliefs apart from the memory lenses", /data-memory-divider=""[^>]*>[\s\S]*?href="\/memory\/beliefs"/.test(sw) && (sw.match(/data-memory-divider/g) ?? []).length === 1);
  check("the Beliefs lens links to /memory/beliefs and marks itself current", /href="\/memory\/beliefs"[^>]*aria-current="page"|aria-current="page"[^>]*href="\/memory\/beliefs"/.test(sw));
  check("Beliefs is part of Memory in the rail and the mobile sheet", isNavActive("/memory/beliefs", "/memory") && !isNavActive("/memory/beliefs", "/"));
  check("/world bookmarks redirect permanently to /memory/beliefs", /permanentRedirect\("\/memory\/beliefs"\)/.test(read("src", "app", "world", "page.tsx")));
  check("/memory/beliefs has its own title", /title: \{ absolute: "Beliefs · Lilith OS" \}/.test(read("src", "app", "memory", "beliefs", "layout.tsx")));
  check("the World Model is not connected to the Atlas", !/lib\/world|beliefs-view/.test(read("src", "components", "memory", "atlas", "cognitive-atlas.tsx")));

  return out;
}
