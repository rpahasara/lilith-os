/**
 * Hosted-mode configuration (server-only environment; never NEXT_PUBLIC_*).
 *
 *   LILITH_HOSTED=1                 hosted mode: every request needs Cloudflare Access
 *   LILITH_ACCESS_TEAM_DOMAIN       <team>.cloudflareaccess.com
 *   LILITH_ACCESS_AUD               Access application AUD tag (64 hex)
 *   LILITH_OWNER_EMAILS             comma-separated owner email allow-list (1-5)
 *   LILITH_PUBLIC_ORIGIN            https://<public host>, the ONLY trusted Origin
 *   LILITH_REQUIRE_HOSTED=1         set by the production systemd unit (W-SEC-1): local
 *                                   mode is refused, so a disabled or broken hosted
 *                                   setting fails closed instead of serving openly
 *
 * LILITH_HOSTED unset or "0" is local mode (existing behaviour). Any other
 * value, or hosted mode with any missing or invalid setting, is "misconfigured"
 * and every request is refused (fail closed). Hosted mode also refuses the
 * browser-direct backend setting NEXT_PUBLIC_LILITH_API_URL: the Core API stays
 * behind the server-side proxy.
 */

export type EdgeAuthConfig =
  | { mode: "local" }
  | { mode: "misconfigured"; problems: string[] }
  | {
      mode: "hosted";
      teamDomain: string;
      issuer: string;
      audience: string;
      ownerEmails: ReadonlySet<string>;
      publicOrigin: string;
    };

const TEAM = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.cloudflareaccess\.com$/;
const AUD = /^[0-9a-f]{64}$/;
const EMAIL = /^[^\s@,]+@[^\s@,]+\.[^\s@,]+$/;

type Env = Record<string, string | undefined>;

export function readEdgeAuthConfig(env: Env = process.env): EdgeAuthConfig {
  const required = env.LILITH_REQUIRE_HOSTED;
  const problems: string[] = [];
  if (required !== undefined && required !== "" && required !== "1") problems.push("LILITH_REQUIRE_HOSTED must be exactly 1 when set");
  const mustBeHosted = required !== undefined && required !== "";
  const hosted = env.LILITH_HOSTED;
  if (hosted === undefined || hosted === "" || hosted === "0") {
    if (!mustBeHosted) return { mode: "local" };
    problems.push("hosted mode is required (LILITH_REQUIRE_HOSTED): LILITH_HOSTED must be 1 with a valid Access configuration");
    return { mode: "misconfigured", problems };
  }
  if (hosted !== "1") problems.push("LILITH_HOSTED must be exactly 1 or 0");

  const teamDomain = (env.LILITH_ACCESS_TEAM_DOMAIN ?? "").trim().toLowerCase();
  if (!TEAM.test(teamDomain)) problems.push("LILITH_ACCESS_TEAM_DOMAIN must be <team>.cloudflareaccess.com");

  const audience = (env.LILITH_ACCESS_AUD ?? "").trim().toLowerCase();
  if (!AUD.test(audience)) problems.push("LILITH_ACCESS_AUD must be the 64-hex Access application AUD tag");

  const emails = (env.LILITH_OWNER_EMAILS ?? "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
  if (emails.length < 1 || emails.length > 5 || !emails.every((e) => EMAIL.test(e))) {
    problems.push("LILITH_OWNER_EMAILS must list 1-5 owner email addresses");
  }

  let publicOrigin = "";
  try {
    const raw = (env.LILITH_PUBLIC_ORIGIN ?? "").trim();
    const u = new URL(raw);
    const bare = u.protocol === "https:" && !u.username && !u.password && u.pathname === "/" && !u.search && !u.hash;
    if (bare && (raw === u.origin || raw === `${u.origin}/`)) publicOrigin = u.origin;
  } catch {
    /* invalid */
  }
  if (!publicOrigin) problems.push("LILITH_PUBLIC_ORIGIN must be a bare https origin");

  if (env.NEXT_PUBLIC_LILITH_API_URL) problems.push("NEXT_PUBLIC_LILITH_API_URL must be unset in hosted mode");

  if (problems.length) return { mode: "misconfigured", problems };
  return {
    mode: "hosted",
    teamDomain,
    issuer: `https://${teamDomain}`,
    audience,
    ownerEmails: new Set(emails),
    publicOrigin,
  };
}
