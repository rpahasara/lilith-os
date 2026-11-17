/**
 * What the World Model read proxy lets the browser see.
 *
 * The belief store keeps owner-context beliefs (owner-approved memories,
 * mirrored in as `entity_type = "owner"`), store-wide counts that include them,
 * and provenance that can carry record ids, message ids and account names. The
 * web app shows none of that, so the proxy decides it, before a byte reaches the
 * browser:
 *
 *   - a list request that names the owner entity type is refused (403);
 *   - a single belief that is owner context is answered exactly like an unknown
 *     key (404, the backend's own wording), so the response does not reveal it;
 *   - every other belief response is REBUILT from an allow-list: only the fields
 *     the Beliefs view needs, each type-checked; provenance keeps its source
 *     class and type, when it was observed, its confidence and a readable label
 *     for known sources; `meta` is dropped (its counts include hidden beliefs);
 *   - an error from the store becomes a generic body with the same status;
 *   - anything that cannot be validated fails closed (502), nothing forwarded.
 *
 * Narrowing only: the backend, its authority, its read gate and its API are
 * unchanged.
 */

export const OWNER_ENTITY_TYPE = "owner";

const isOwner = (value: unknown) =>
  typeof value === "string" && value.trim().toLowerCase() === OWNER_ENTITY_TYPE;

/** `os/world` asking for owner context by entity type. */
export function worldListRefused(joined: string, search: URLSearchParams): boolean {
  return joined === "os/world" && search.getAll("entity_type").some(isOwner);
}

/** A World Model path: the list or one belief. */
export function isWorldPath(joined: string): boolean {
  return joined === "os/world" || joined.startsWith("os/world/");
}

/** Readable labels for the evidence sources the backend is known to use; nothing else is labelled. */
export const SOURCE_LABELS: Readonly<Record<string, string>> = {
  "career-store": "Career pipeline record",
  "career-events": "Career activity event",
};

const LIFECYCLE = new Set(["ACTIVE", "CONFLICTED", "STALE", "SUPERSEDED"]);
const EPISTEMIC = new Set(["OBSERVED", "USER_ASSERTED", "INFERRED", "VERIFIED"]);
const TIERS = new Set(["high", "medium", "low", "unknown"]);
const SOURCE_CLASS = /^[A-Z][A-Z_]{0,39}$/;
const CODE = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const STAMP = /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?)?(?:Z|[+-]\d{2}:?\d{2})?$/;

type Json = Record<string, unknown>;
const obj = (v: unknown): v is Json => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, max = 512): v is string => typeof v === "string" && v.length > 0 && v.length <= max;
/** A timestamp, null when absent, or false when present but not a timestamp. */
const stamp = (v: unknown): string | null | false =>
  v === null || v === undefined ? null : typeof v === "string" && STAMP.test(v.trim()) ? v : false;
const unit = (v: unknown) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1;

class Unsafe extends Error {}
const need = (ok: boolean, what: string) => { if (!ok) throw new Unsafe(what); };

/** One provenance entry, keeping only what the inspector shows. */
function safeEvidence(p: unknown): Json {
  need(obj(p), "evidence");
  const e = p as Json;
  need(typeof e.source_class === "string" && SOURCE_CLASS.test(e.source_class), "evidence class");
  const out: Json = { source_class: e.source_class };
  if (typeof e.source_type === "string" && CODE.test(e.source_type)) out.source_type = e.source_type;
  const at = stamp(e.observed_at);
  if (typeof at === "string") out.observed_at = at;
  if (unit(e.confidence)) out.confidence = e.confidence;
  const label = typeof e.source_id === "string" ? SOURCE_LABELS[e.source_id] : undefined;
  if (label) out.source_label = label;
  return out;
}

/** One belief, rebuilt from the allow-list; throws if it cannot be validated. */
function safeBelief(b: unknown): Json {
  need(obj(b), "belief");
  const x = b as Json;
  need(str(x.key) && str(x.entity_type, 128) && (str(x.entity_id, 128) || typeof x.entity_id === "number") && str(x.predicate, 128), "identity");
  need(LIFECYCLE.has(x.lifecycle_state as string) && EPISTEMIC.has(x.epistemic_state as string), "state");
  need(obj(x.confidence), "confidence");
  const c = x.confidence as Json;
  need(unit(c.value) && TIERS.has(c.tier as string) && (typeof c.basis === "string" && /^[a-z0-9_+]{1,64}$/.test(c.basis)), "confidence fields");
  need(Number.isInteger(x.revision) && (x.revision as number) >= 0, "revision");
  const created = stamp(x.created_at), updated = stamp(x.updated_at), observed = stamp(x.observed_at), expires = stamp(x.expires_at);
  need(typeof created === "string" && typeof updated === "string", "created/updated");
  need(observed !== false && expires !== false, "observed/expiry");
  need(x.provenance === undefined || Array.isArray(x.provenance), "provenance");
  need(x.contradicted_by === undefined || Array.isArray(x.contradicted_by), "conflicts");
  return {
    key: x.key,
    entity_type: x.entity_type,
    entity_id: String(x.entity_id),
    predicate: x.predicate,
    value: x.value ?? null,
    lifecycle_state: x.lifecycle_state,
    epistemic_state: x.epistemic_state,
    confidence: { value: c.value, tier: c.tier, basis: c.basis },
    provenance: ((x.provenance as unknown[]) ?? []).map(safeEvidence),
    observed_at: observed,
    created_at: created,
    updated_at: updated,
    expires_at: expires,
    revision: x.revision,
    // only how many unresolved conflicts there are; the refs themselves are not needed
    contradicted_by: ((x.contradicted_by as unknown[]) ?? []).map(() => "conflict"),
  };
}

export interface SafeResponse {
  status: number;
  body: string;
}

const json = (status: number, value: unknown): SafeResponse => ({ status, body: JSON.stringify(value) });

/** The answer for a hidden belief: identical to the backend's unknown key. */
export const HIDDEN_BELIEF: SafeResponse = json(404, { detail: "no belief for key" });

/**
 * What the browser receives for a World Model path, given the store's status
 * and body. Never forwards the store's body as-is.
 */
export function sanitizeWorldResponse(joined: string, upstreamStatus: number, upstreamBody: string): SafeResponse {
  const detail = joined.startsWith("os/world/");
  if (upstreamStatus < 200 || upstreamStatus >= 300) {
    return detail && upstreamStatus === 404 ? HIDDEN_BELIEF : json(upstreamStatus, { error: "belief store unavailable" });
  }
  try {
    const parsed: unknown = JSON.parse(upstreamBody);
    if (detail) {
      need(obj(parsed), "detail");
      if (isOwner((parsed as Json).entity_type)) return HIDDEN_BELIEF;
      return json(200, safeBelief(parsed));
    }
    need(obj(parsed) && Array.isArray((parsed as Json).beliefs), "list");
    const beliefs = ((parsed as Json).beliefs as unknown[])
      .filter((b) => !(obj(b) && isOwner(b.entity_type)))
      .map(safeBelief);
    return json(200, { beliefs });
  } catch {
    return json(502, { error: "belief store response could not be validated" });
  }
}
