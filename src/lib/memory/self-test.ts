/**
 * Deterministic self-test for the memory projection (ledger FM-09, principle P-07).
 *
 * Unknown, missing, malformed or unsupported epistemic values must stay UNKNOWN:
 * never promoted to a fact, never attributed to "manual" provenance, never
 * dropped. Recognized values pass through unchanged. No network: it exercises
 * the real normalizer and the real badge components directly.
 */
import { isValidElement, type ReactElement } from "react";
import { normalizeRecord } from "./client";
import { buildDemoMemoryData } from "./demo";
import { KIND_META, PROVENANCE_META, type MemoryRecord, type ProvenanceKind } from "./types";
import { KindTag, ProvenanceBadge } from "@/components/memory/provenance-badge";

export interface MemorySelfTestResult {
  name: string;
  pass: boolean;
  detail?: string;
}

const RECOGNIZED_PROVENANCE = (Object.keys(PROVENANCE_META) as ProvenanceKind[]).filter((k) => k !== "unknown");

/** The visible text of a rendered badge: its string children, in order. */
function text(el: unknown): string {
  if (typeof el === "string" || typeof el === "number") return String(el);
  if (Array.isArray(el)) return el.map(text).join("");
  if (isValidElement(el)) return text((el as ReactElement<{ children?: unknown }>).props.children);
  return "";
}

function record(raw: Record<string, unknown>): MemoryRecord {
  return normalizeRecord({ id: "m", summary: "s", ...raw });
}

export function runMemorySelfTest(): MemorySelfTestResult[] {
  const results: MemorySelfTestResult[] = [];
  const check = (name: string, pass: boolean, detail?: string) => results.push({ name, pass, detail });

  // 1-2. Recognized classifications are preserved exactly.
  const fact = record({ kind: "fact", provenance: { kind: "conversation" } });
  check("MEM-1 recognized fact stays fact", fact.kind === "fact", `kind=${fact.kind}`);
  const inf = record({ kind: "inference" });
  const inferred = record({ memory_kind: "inferred" });
  check("MEM-2 recognized inference stays inference",
    inf.kind === "inference" && inferred.kind === "inference", `${inf.kind}/${inferred.kind}`);

  // 3-4. Missing or unsupported kind is UNKNOWN, never a fact (negative controls).
  const missingKinds = [record({}), record({ kind: null }), record({ kind: "" })];
  check("MEM-3 missing kind is unknown, not fact",
    missingKinds.every((r) => r.kind === "unknown"), missingKinds.map((r) => r.kind).join(","));
  const unsupportedKinds = ["hypothesis", "FACT", "Fact", "observation", 1, true, { kind: "fact" }]
    .map((k) => record({ kind: k }));
  check("MEM-4 unsupported kind is unknown, not fact",
    unsupportedKinds.every((r) => r.kind === "unknown"), unsupportedKinds.map((r) => r.kind).join(","));

  // 5-6. Missing or unsupported provenance is UNKNOWN, never "manual"; the raw value stays visible.
  const missingProv = [record({}), record({ provenance: null }), record({ provenance: {} }), record({ provenance: "" })];
  check("MEM-5 missing provenance is unknown, not manual",
    missingProv.every((r) => r.provenance.kind === "unknown" && r.provenance.label === "Unknown source"),
    missingProv.map((r) => `${r.provenance.kind}:${r.provenance.label}`).join(","));
  const slack = record({ provenance: { kind: "slack" } });
  const bare = record({ source: "fax" });
  check("MEM-6 unsupported provenance is unknown, not manual, raw value kept",
    slack.provenance.kind === "unknown" && slack.provenance.label === 'Unrecognized source "slack"'
      && bare.provenance.kind === "unknown" && bare.provenance.label === 'Unrecognized source "fax"',
    `${slack.provenance.kind}:${slack.provenance.label} | ${bare.provenance.kind}:${bare.provenance.label}`);
  const labelled = record({ provenance: { kind: "slack", label: "Imported thread" } });
  check("MEM-6b a supplied label is kept, the kind still unknown",
    labelled.provenance.kind === "unknown" && labelled.provenance.label === "Imported thread",
    `${labelled.provenance.kind}:${labelled.provenance.label}`);

  // 7. Valid provenance, including manual, is preserved exactly.
  const preserved = RECOGNIZED_PROVENANCE.map((k) => [k, record({ provenance: { kind: k } }).provenance.kind]);
  check("MEM-7 recognized provenance (incl. manual) preserved exactly",
    preserved.every(([a, b]) => a === b) && record({ provenance: "manual" }).provenance.kind === "manual",
    preserved.filter(([a, b]) => a !== b).map(([a, b]) => `${a}->${b}`).join(",") || `${preserved.length} kinds`);

  // 8. Visible UI: an unknown record renders "Unknown", never "Fact"/"Inference"/"Manual".
  const unknownTag = text(KindTag({ kind: "unknown" }));
  const factTag = text(KindTag({ kind: "fact" }));
  const infTag = text(KindTag({ kind: "inference" }));
  check("MEM-8 KindTag shows Unknown for unknown, unchanged for fact/inference",
    unknownTag === "Unknown" && factTag === "Fact" && infTag === "Inference", `${unknownTag}/${factTag}/${infTag}`);
  const unknownBadge = text(ProvenanceBadge({ provenance: slack.provenance }));
  const manualBadge = text(ProvenanceBadge({ provenance: record({ provenance: { kind: "manual" } }).provenance }));
  check("MEM-8b ProvenanceBadge shows Unknown source, never Manual, for unsupported provenance",
    unknownBadge === "Unknown source" && manualBadge === "Manual", `${unknownBadge}/${manualBadge}`);
  check("MEM-8c unknown presentation is distinct and neutral",
    KIND_META.unknown.label !== KIND_META.fact.label && KIND_META.unknown.accent === "faint"
      && PROVENANCE_META.unknown.label !== PROVENANCE_META.manual.label && PROVENANCE_META.unknown.accent === "faint");

  // Unknown records are kept, not dropped.
  check("MEM-9 unknown records are not discarded",
    [record({}), slack].every((r) => r.id === "m" && r.summary === "s"));

  // Demo data stays labelled and fully classified (no accidental unknowns there).
  const demo = buildDemoMemoryData();
  check("MEM-10 demo data is flagged and uses only recognized values",
    demo.isDemo === true && demo.records.every((r) => r.kind !== "unknown" && r.provenance.kind !== "unknown"),
    `isDemo=${demo.isDemo} records=${demo.records.length}`);

  return results;
}
