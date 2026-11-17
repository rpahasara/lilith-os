/**
 * What the World Model read proxy lets the browser see.
 *
 * The belief store keeps owner-context beliefs (owner-approved memories,
 * mirrored in as `entity_type = "owner"`). `GET /os/world` leaves them out
 * unless a caller asks for that entity type explicitly; `GET /os/world/{key}`
 * returns any key it is given. The web app never shows owner context, so the
 * proxy applies the listing rule to both, in the narrowing direction only:
 *
 *   - a list request that names the owner entity type is refused (403);
 *   - a single belief that turns out to be owner context is answered exactly
 *     like an unknown key (404, the backend's own wording), so the response
 *     does not reveal that it exists.
 *
 * Nothing is widened and the backend is untouched: its authority, its read
 * gate and its own defaults stay as they are.
 */

export const OWNER_ENTITY_TYPE = "owner";

const isOwner = (value: unknown) =>
  typeof value === "string" && value.trim().toLowerCase() === OWNER_ENTITY_TYPE;

/** `os/world` asking for owner context by entity type. */
export function worldListRefused(joined: string, search: URLSearchParams): boolean {
  return joined === "os/world" && search.getAll("entity_type").some(isOwner);
}

/** `os/world/<key>`: a single belief. */
export function isWorldDetail(joined: string): boolean {
  return joined.startsWith("os/world/");
}

/** The single-belief response is owner context, which the list never shows. */
export function worldDetailHidden(body: string): boolean {
  try {
    const parsed: unknown = JSON.parse(body);
    return typeof parsed === "object" && parsed !== null && isOwner((parsed as { entity_type?: unknown }).entity_type);
  } catch {
    return false;
  }
}

/** The answer for a hidden belief: identical to the backend's unknown key. */
export const HIDDEN_BELIEF_BODY = JSON.stringify({ detail: "no belief for key" });
