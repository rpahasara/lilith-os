import type { NextRequest } from "next/server";

/**
 * SERVER-ONLY seam (route handlers only): is the person using this browser the
 * authenticated owner, for First Interaction recording?
 *
 * No live owner-authentication mechanism exists yet. The existing WebAuthn
 * owner-proof engine (Core API `owner_proof`) verifies assertions over a
 * single memory action; there is no owner credential registration, no login
 * challenge and no owner browser session, and the Core API relay must not
 * import that package. So this always reports UNAVAILABLE and recording stays
 * inaccessible. It must never be satisfied by the server-held capture token
 * (`LILITH_OS_OWNER_CAPTURE_TOKEN` is service authentication between this
 * server and the Core API), a localStorage value, a header the browser sets,
 * or anything else the browser controls.
 *
 * The genuine bridge, when it exists, returns `{ available: true, owner }` only
 * for a request carrying a server-verified owner session (HttpOnly, Secure,
 * SameSite=Strict cookie bound to a WebAuthn owner assertion for this origin),
 * and the capture session must then be bound server-side to that owner.
 */

export type OwnerCaptureAuthentication =
  | { available: false; reason: "OWNER_AUTHENTICATION_UNAVAILABLE" }
  | { available: true; owner: string };

export async function ownerCaptureAuthentication(
  _req: NextRequest,
): Promise<OwnerCaptureAuthentication> {
  return { available: false, reason: "OWNER_AUTHENTICATION_UNAVAILABLE" };
}
