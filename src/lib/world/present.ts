/**
 * Presentation of World Model beliefs for the Memory → Beliefs view.
 *
 * Pure functions: grouping beliefs into readable subjects, plain-language
 * labels for the epistemic and lifecycle axes and for confidence, readable
 * values, and counts that describe exactly the beliefs on screen. Nothing here
 * reads the network or changes a belief.
 *
 * A belief is LILITH's current interpretation of one fact about one subject
 * ("this application's status is Applied"). It is not a memory: memories are
 * records with their own provenance, beliefs are reconciled from evidence and
 * carry an epistemic state. Earlier values are not kept by the store yet, so
 * everything here describes the present interpretation only.
 */

import type { Belief, BeliefProvenance, ConfidenceTier, EpistemicState, LifecycleState } from "./types";

/* ----------------------------------------------------------------- words */

/** "career.application" → "Career application"; "last_activity" → "Last activity". */
export function humanize(code: string): string {
  const words = code.replace(/[._-]+/g, " ").trim().toLowerCase();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : code;
}

export const EPISTEMIC: Record<EpistemicState, { label: string; detail: string }> = {
  OBSERVED: { label: "Observed", detail: "Seen directly in a connected source." },
  USER_ASSERTED: { label: "Stated by you", detail: "You said this directly." },
  INFERRED: { label: "Inferred", detail: "Reasoned from other evidence. It may be wrong and never outranks evidence." },
  VERIFIED: { label: "Verified", detail: "Independently checked by the verification step." },
};

export const LIFECYCLE: Record<Exclude<LifecycleState, "SUPERSEDED">, { label: string; detail: string; tone: "green" | "amber" | "faint" }> = {
  ACTIVE: { label: "Current", detail: "LILITH's current best interpretation.", tone: "green" },
  CONFLICTED: { label: "Conflicted", detail: "Trusted sources disagree and the rules cannot settle it safely.", tone: "amber" },
  STALE: { label: "Stale", detail: "Still known, but older than its freshness window.", tone: "faint" },
};

export const TIER: Record<ConfidenceTier, string> = { high: "High", medium: "Medium", low: "Low", unknown: "Unknown" };

export const SOURCE_CLASS: Record<string, string> = {
  USER: "You",
  LIVE_CONNECTOR: "Live connector",
  TASK_RESULT: "Task result",
  VERIFICATION: "Verification",
  MEMORY: "Memory",
  INFERENCE: "Inference",
  SYSTEM: "System",
};

/** The rule behind a confidence value, in words (see the backend's confidence model). */
export function confidenceBasis(basis: string): string {
  if (basis === "conflicted_penalty") return "Lowered because sources disagree";
  if (basis === "stale_penalty") return "Lowered because the information is old";
  const m = /^([a-z_]+)\+(\d+)corrob$/.exec(basis);
  if (m) {
    const n = Number(m[2]);
    return `${humanize(m[1])}, corroborated by ${n} more ${n === 1 ? "source" : "sources"}`;
  }
  if (basis === "observed") return "Observed once";
  if (basis === "user_asserted") return "Stated by you";
  return humanize(basis);
}

/* ---------------------------------------------------------------- values */

/** The backend's timestamps: ISO, or "YYYY-MM-DD HH:MM:SS" (no zone). */
const STAMP = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?$/;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A timestamp as written, without shifting zones: "24 Aug 2026 · 19:11". */
export function formatStamp(value: string): string | null {
  const m = STAMP.exec(value.trim());
  if (!m) return null;
  const month = MONTHS[Number(m[2]) - 1];
  if (!month) return null;
  const date = `${Number(m[3])} ${month} ${m[1]}`;
  return m[4] ? `${date} · ${m[4]}:${m[5]}` : date;
}

/** Milliseconds for sorting; NaN when unparseable (Safari-safe). */
export function stampTime(value?: string): number {
  if (!value) return NaN;
  const iso = value.trim().replace(" ", "T");
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) || iso.length <= 10 ? iso : `${iso}Z`).getTime();
}

/** A belief's value in words. Objects become "Key: value · Key: value", never raw JSON. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "—";
  if (typeof value === "string") return formatStamp(value) ?? value;
  if (Array.isArray(value)) return value.length ? value.map(formatValue).join(", ") : "—";
  if (typeof value === "object") {
    const parts = Object.entries(value as Record<string, unknown>).map(([k, v]) => `${humanize(k)}: ${formatValue(v)}`);
    return parts.length ? parts.join(" · ") : "—";
  }
  return String(value);
}

/* --------------------------------------------------------------- subjects */

export interface BeliefSubject {
  /** `${entityType}:${entityId}` — stable within the store. */
  id: string;
  typeLabel: string;
  title: string;
  subtitle?: string;
  beliefs: Belief[];
  updatedAt?: string;
  conflicted: number;
  stale: number;
}

/** Predicates that name a subject, and that describe it, in order of preference. */
const NAMING = ["name", "title", "role", "label", "subject"];
const DESCRIBING = ["company", "organisation", "organization", "employer"];
/** Facts in a natural reading order; anything else follows alphabetically. */
const ORDER = ["name", "title", "role", "company", "status", "stage", "last_activity"];

const stringValue = (beliefs: Belief[], predicate: string) => {
  const v = beliefs.find((b) => b.predicate === predicate)?.value;
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
};

function factOrder(a: Belief, b: Belief): number {
  const ia = ORDER.indexOf(a.predicate), ib = ORDER.indexOf(b.predicate);
  if (ia !== ib) return (ia < 0 ? ORDER.length : ia) - (ib < 0 ? ORDER.length : ib);
  return a.predicate.localeCompare(b.predicate);
}

/**
 * Beliefs grouped by the subject they describe. Subjects that need attention
 * (a conflict) come first, then the most recently reconciled.
 */
export function groupBySubject(beliefs: Belief[]): BeliefSubject[] {
  const groups = new Map<string, Belief[]>();
  for (const b of beliefs) {
    const id = `${b.entity.entityType}:${b.entity.entityId}`;
    groups.set(id, [...(groups.get(id) ?? []), b]);
  }
  const subjects = [...groups.entries()].map(([id, list]): BeliefSubject => {
    const sorted = [...list].sort(factOrder);
    const { entityType, entityId } = sorted[0].entity;
    const typeLabel = humanize(entityType);
    const named = NAMING.map((p) => stringValue(sorted, p)).find(Boolean);
    const described = DESCRIBING.map((p) => stringValue(sorted, p)).find(Boolean);
    const updated = sorted.reduce<string | undefined>((latest, b) =>
      !latest || stampTime(b.updatedAt) > stampTime(latest) ? b.updatedAt : latest, undefined);
    return {
      id,
      typeLabel,
      title: named ?? `${typeLabel} ${entityId}`,
      subtitle: described,
      beliefs: sorted,
      updatedAt: updated,
      conflicted: sorted.filter((b) => b.lifecycleState === "CONFLICTED").length,
      stale: sorted.filter((b) => b.lifecycleState === "STALE").length,
    };
  });
  return subjects.sort((a, b) =>
    (b.conflicted > 0 ? 1 : 0) - (a.conflicted > 0 ? 1 : 0) ||
    (stampTime(b.updatedAt) || 0) - (stampTime(a.updatedAt) || 0) ||
    a.title.localeCompare(b.title));
}

/* ------------------------------------------------------- counts and filters */

export type LifecycleFilter = "all" | "ACTIVE" | "CONFLICTED" | "STALE";
export type EpistemicFilter = "all" | EpistemicState;

export interface BeliefFilters {
  lifecycle: LifecycleFilter;
  epistemic: EpistemicFilter;
  query: string;
}

export const NO_FILTERS: BeliefFilters = { lifecycle: "all", epistemic: "all", query: "" };

/** Counts of exactly these beliefs: nothing hidden, nothing store-wide. */
export function countBeliefs(beliefs: Belief[]) {
  const lifecycle: Record<LifecycleFilter, number> = { all: beliefs.length, ACTIVE: 0, CONFLICTED: 0, STALE: 0 };
  const epistemic: Partial<Record<EpistemicState, number>> = {};
  for (const b of beliefs) {
    if (b.lifecycleState !== "SUPERSEDED") lifecycle[b.lifecycleState] += 1;
    epistemic[b.epistemicState] = (epistemic[b.epistemicState] ?? 0) + 1;
  }
  const subjects = new Set(beliefs.map((b) => `${b.entity.entityType}:${b.entity.entityId}`)).size;
  return { beliefs: beliefs.length, subjects, lifecycle, epistemic };
}

/** Beliefs passing the filters. The text query matches subjects, facts and values. */
export function filterBeliefs(beliefs: Belief[], f: BeliefFilters): Belief[] {
  const q = f.query.trim().toLowerCase();
  const subjectText = q
    ? new Map(groupBySubject(beliefs).map((s) => [s.id, `${s.title} ${s.subtitle ?? ""} ${s.typeLabel}`.toLowerCase()]))
    : null;
  return beliefs.filter((b) => {
    if (f.lifecycle !== "all" && b.lifecycleState !== f.lifecycle) return false;
    if (f.epistemic !== "all" && b.epistemicState !== f.epistemic) return false;
    if (!q) return true;
    const own = `${humanize(b.predicate)} ${formatValue(b.value)}`.toLowerCase();
    return own.includes(q) || (subjectText?.get(`${b.entity.entityType}:${b.entity.entityId}`) ?? "").includes(q);
  });
}

/** "31 beliefs about 8 subjects" — always the numbers on screen. */
export function countLine(beliefs: number, subjects: number): string {
  return `${beliefs} ${beliefs === 1 ? "belief" : "beliefs"} about ${subjects} ${subjects === 1 ? "subject" : "subjects"}`;
}

/* -------------------------------------------------------------- evidence */

/** One evidence row in words; never ids, refs or free text. */
export function evidenceLine(p: BeliefProvenance): { source: string; kind?: string; when?: string; confidence?: string } {
  return {
    source: p.origin ?? SOURCE_CLASS[p.sourceClass] ?? humanize(p.sourceClass ?? "source"),
    kind: p.sourceType ? humanize(p.sourceType) : undefined,
    when: p.observedAt ? formatStamp(p.observedAt) ?? undefined : undefined,
    confidence: typeof p.confidence === "number" ? p.confidence.toFixed(2) : undefined,
  };
}
