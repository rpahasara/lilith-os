/**
 * Headless security regression test for H1 (private web authentication).
 * Real RSA keys and real signatures; a fake JWKS endpoint; no network, no
 * Cloudflare, no backend. Run by `npm run test:core`.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import type { NextRequest } from "next/server";
import { proxy } from "@/proxy";
import { ownerCaptureAuthentication } from "@/lib/conversation/owner-capture-auth";
import * as conversationRoute from "@/app/api/lilith/conversation/route";
import * as evidenceRoute from "@/app/api/lilith/conversation/evidence/route";
import * as draftsRoute from "@/app/api/lilith/drafts/route";
import * as draftRoute from "@/app/api/lilith/drafts/[draftId]/route";
import * as tasksRoute from "@/app/api/lilith/tasks/route";
import * as taskRoute from "@/app/api/lilith/tasks/[taskId]/route";
import * as readProxyRoute from "@/app/api/lilith/[...path]/route";
import * as ttsRoute from "@/app/api/voice/tts/route";
import * as elevenRoute from "@/app/api/voice/elevenlabs/route";
import { readEdgeAuthConfig } from "./config";
import { ACCESS_JWT_HEADER, __resetEdgeAuthForTests, authenticateEdge, guardApiRequest } from "./guard";
import { JwksCache, MIN_REFETCH_MS, REFRESH_MS, STALE_MAX_MS, certsUrl } from "./jwks";
import { verifyAccessToken } from "./jwt";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const TEAM = "lilith-test.cloudflareaccess.com";
const ISS = `https://${TEAM}`;
const AUD = "a".repeat(64);
const OWNER = "owner@example.com";
const ORIGIN = "https://os.example.com";
const HOSTED_ENV = {
  LILITH_HOSTED: "1",
  LILITH_ACCESS_TEAM_DOMAIN: TEAM,
  LILITH_ACCESS_AUD: AUD,
  LILITH_OWNER_EMAILS: `${OWNER}, second@example.com`,
  LILITH_PUBLIC_ORIGIN: ORIGIN,
};
const ENV_KEYS = [...Object.keys(HOSTED_ENV), "NEXT_PUBLIC_LILITH_API_URL", "LILITH_API_URL",
  "OPENAI_API_KEY", "ELEVENLABS_API_KEY"];

const b64url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const b64urlJson = (v: unknown) => b64url(new TextEncoder().encode(JSON.stringify(v)));

interface Signer {
  kid: string;
  jwk: JsonWebKey & { kid: string; alg: string; use: string };
  sign: (header: Record<string, unknown>, payload: Record<string, unknown>) => Promise<string>;
}

async function makeSigner(kid: string): Promise<Signer> {
  const pair = (await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  )) as CryptoKeyPair;
  const pub = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return {
    kid,
    jwk: { kty: "RSA", n: pub.n, e: pub.e, kid, alg: "RS256", use: "sig" },
    async sign(header, payload) {
      const h = b64urlJson(header);
      const p = b64urlJson(payload);
      const sig = new Uint8Array(await crypto.subtle.sign({ name: "RSASSA-PKCS1-v1_5" }, pair.privateKey,
        new TextEncoder().encode(`${h}.${p}`)));
      return `${h}.${p}.${b64url(sig)}`;
    },
  };
}

function claims(nowS: number, over: Record<string, unknown> = {}) {
  return { iss: ISS, aud: [AUD], email: OWNER, type: "app", iat: nowS - 10, nbf: nowS - 10, exp: nowS + 3600,
    sub: "user-1", ...over };
}

/** A fake JWKS endpoint whose published keys and availability the test controls. */
function fakeJwks() {
  const state = { keys: [] as unknown[], fail: false, calls: [] as { url: string; init: RequestInit }[] };
  const fetchImpl = async (url: string, init: RequestInit) => {
    state.calls.push({ url, init });
    if (state.fail) return new Response("down", { status: 503 });
    return new Response(JSON.stringify({ keys: state.keys }), { status: 200, headers: { "content-type": "application/json" } });
  };
  return { state, fetchImpl };
}

function fakeRequest(headers: Record<string, string>, body: unknown = {}, search = ""): NextRequest {
  return {
    headers: new Headers(headers),
    nextUrl: { origin: "http://localhost:3000", search, searchParams: new URLSearchParams(search) },
    json: async () => body,
  } as unknown as NextRequest;
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? sourceFiles(p) : /\.(ts|tsx)$/.test(n) ? [p] : [];
  });
}

export async function runEdgeAuthSelfTest(): Promise<Result[]> {
  const out: Result[] = [];
  const check = (name: string, pass: boolean, detail?: string) =>
    out.push({ name: `edge-auth: ${name}`, pass, detail: pass ? undefined : detail });

  const savedEnv = Object.fromEntries(ENV_KEYS.map((k) => [k, process.env[k]]));
  const setEnv = (env: Record<string, string | undefined>) => {
    for (const k of ENV_KEYS) delete process.env[k];
    for (const [k, v] of Object.entries(env)) if (v !== undefined) process.env[k] = v;
  };

  try {
    const k1 = await makeSigner("kid-1");
    const k2 = await makeSigner("kid-2");
    const attacker = await makeSigner("kid-1"); // same kid, different key
    let t = Date.UTC(2026, 10, 12, 12, 0, 0);
    const nowS = () => Math.floor(t / 1000);
    const policy = { issuer: ISS, audience: AUD, ownerEmails: new Set([OWNER]) };
    const hdr = (kid = "kid-1") => ({ alg: "RS256", typ: "JWT", kid });

    /* ------------------------------------------------ token verification */
    {
      const jw = fakeJwks();
      jw.state.keys = [k1.jwk];
      const cache = new JwksCache(TEAM, jw.fetchImpl, () => t);
      const verify = (tok: string | null) => verifyAccessToken(tok, policy, cache, t);
      const good = await k1.sign(hdr(), claims(nowS()));
      const ok = await verify(good);
      check("a valid owner token verifies", ok.ok && ok.email === OWNER, JSON.stringify(ok));
      check("keys are fetched only from the team's documented JWKS URL, with no redirects",
        jw.state.calls.length === 1 && jw.state.calls[0].url === `${ISS}/cdn-cgi/access/certs` &&
        jw.state.calls[0].init.redirect === "error" && certsUrl(TEAM) === `${ISS}/cdn-cgi/access/certs`);

      const cases: [string, Promise<string> | string, string][] = [
        ["forged signature (attacker key, same kid)", attacker.sign(hdr(), claims(nowS())), "signature"],
        ["tampered payload", (async () => { const [h, , s] = good.split("."); return `${h}.${b64urlJson(claims(nowS(), { email: "evil@example.com" }))}.${s}`; })(), "signature"],
        ["alg none", `${b64urlJson({ alg: "none", kid: "kid-1" })}.${b64urlJson(claims(nowS()))}.x`, "alg"],
        ["alg HS256", k1.sign({ alg: "HS256", kid: "kid-1" }, claims(nowS())), "alg"],
        ["embedded jwk header", k1.sign({ ...hdr(), jwk: attacker.jwk }, claims(nowS())), "header-jwk"],
        ["jku header", k1.sign({ ...hdr(), jku: "https://evil.example.com/keys" }, claims(nowS())), "header-jku"],
        ["crit header", k1.sign({ ...hdr(), crit: ["exp"] }, claims(nowS())), "header-crit"],
        ["missing kid", k1.sign({ alg: "RS256" }, claims(nowS())), "kid"],
        ["wrong issuer", k1.sign(hdr(), claims(nowS(), { iss: "https://evil.cloudflareaccess.com" })), "iss"],
        ["wrong audience", k1.sign(hdr(), claims(nowS(), { aud: ["b".repeat(64)] })), "aud"],
        ["empty audience list", k1.sign(hdr(), claims(nowS(), { aud: [] })), "aud"],
        ["expired", k1.sign(hdr(), claims(nowS(), { exp: nowS() - 1 })), "exp"],
        ["expires exactly now", k1.sign(hdr(), claims(nowS(), { exp: nowS() })), "exp"],
        ["missing exp", k1.sign(hdr(), (({ exp: _e, ...rest }) => rest)(claims(nowS()))), "exp"],
        ["not yet valid (nbf)", k1.sign(hdr(), claims(nowS(), { nbf: nowS() + 120 })), "nbf"],
        ["issued in the future (iat)", k1.sign(hdr(), claims(nowS(), { iat: nowS() + 120 })), "iat"],
        ["non-app token type", k1.sign(hdr(), claims(nowS(), { type: "org" })), "type"],
        ["wrong identity", k1.sign(hdr(), claims(nowS(), { email: "someone@example.com" })), "identity"],
        ["service token without email", k1.sign(hdr(), (({ email: _m, ...rest }) => rest)(claims(nowS()))), "identity"],
        ["two segments", "a.b", "malformed"],
        ["bad characters", "a.b.c d", "malformed"],
        ["non-JSON header", `${b64url(new TextEncoder().encode("not json"))}.${b64urlJson(claims(nowS()))}.sig`, "malformed"],
        ["oversized token", "a".repeat(9000), "too-long"],
        ["empty", "", "missing"],
      ];
      for (const [name, tokenP, reason] of cases) {
        const r = await verify(await tokenP);
        check(`rejects ${name}`, !r.ok && r.reason === reason, JSON.stringify(r));
      }
      const upper = await verify(await k1.sign(hdr(), claims(nowS(), { email: "Owner@Example.COM" })));
      check("owner email match is case-insensitive", upper.ok);
    }

    /* ------------------------------------------------ key rotation and JWKS failures */
    {
      const jw = fakeJwks();
      jw.state.keys = [k1.jwk];
      const cache = new JwksCache(TEAM, jw.fetchImpl, () => t);
      const verify = (tok: string) => verifyAccessToken(tok, policy, cache, t);
      await verify(await k1.sign(hdr(), claims(nowS())));
      const rotated = await k2.sign(hdr("kid-2"), claims(nowS()));
      const before = await verify(rotated);
      check("an unpublished kid is unverifiable", !before.ok && before.reason === "unverifiable");
      jw.state.keys = [k1.jwk, k2.jwk];
      const calls = jw.state.calls.length;
      const limited = await verify(rotated);
      check("unknown-kid refetch is rate-limited", !limited.ok && jw.state.calls.length === calls);
      t += MIN_REFETCH_MS;
      const after = await verify(rotated);
      check("after rotation the new key is fetched and verifies", after.ok && jw.state.calls.length === calls + 1);
      const forgedKids = jw.state.calls.length;
      for (let i = 0; i < 20; i++) await verify(await k1.sign(hdr(`forged-${i}`), claims(nowS())));
      check("forged kids cannot hammer the JWKS endpoint", jw.state.calls.length <= forgedKids + 1,
        `${jw.state.calls.length - forgedKids} fetches`);
      jw.state.fail = true;
      t += REFRESH_MS + MIN_REFETCH_MS;
      check("JWKS outage: recently fetched keys keep working", (await verify(await k1.sign(hdr(), claims(nowS())))).ok);
      t += STALE_MAX_MS;
      const stale = await verify(await k1.sign(hdr(), claims(nowS())));
      check("JWKS outage beyond the stale limit fails closed", !stale.ok && stale.reason === "unverifiable");
      jw.state.fail = false;
      jw.state.keys = [{ kty: "RSA", kid: "short", n: "AQAB", e: "AQAB" }, { kty: "EC", kid: "ec" }];
      const fresh = new JwksCache(TEAM, jw.fetchImpl, () => t);
      const weak = await verifyAccessToken(await k1.sign(hdr("short"), claims(nowS())), policy, fresh, t);
      check("weak or non-RSA published keys are ignored", !weak.ok && weak.reason === "unverifiable");
      const bad = new JwksCache(TEAM, async () => new Response("<html>", { status: 200 }), () => t);
      const r = await verifyAccessToken(await k1.sign(hdr(), claims(nowS())), policy, bad, t);
      check("a non-JSON JWKS response is unverifiable", !r.ok && r.reason === "unverifiable");
    }

    /* ------------------------------------------------ hosted configuration */
    {
      check("local mode when LILITH_HOSTED is unset or 0",
        readEdgeAuthConfig({}).mode === "local" && readEdgeAuthConfig({ LILITH_HOSTED: "0" }).mode === "local");
      check("valid hosted configuration", readEdgeAuthConfig(HOSTED_ENV).mode === "hosted");
      const bad: [string, Record<string, string | undefined>][] = [
        ["LILITH_HOSTED=true", { ...HOSTED_ENV, LILITH_HOSTED: "true" }],
        ["missing team domain", { ...HOSTED_ENV, LILITH_ACCESS_TEAM_DOMAIN: undefined }],
        ["non-Cloudflare team domain", { ...HOSTED_ENV, LILITH_ACCESS_TEAM_DOMAIN: "evil.example.com" }],
        ["look-alike team domain", { ...HOSTED_ENV, LILITH_ACCESS_TEAM_DOMAIN: "x.cloudflareaccess.com.evil.com" }],
        ["missing audience", { ...HOSTED_ENV, LILITH_ACCESS_AUD: undefined }],
        ["malformed audience", { ...HOSTED_ENV, LILITH_ACCESS_AUD: "abc" }],
        ["missing owner emails", { ...HOSTED_ENV, LILITH_OWNER_EMAILS: undefined }],
        ["malformed owner email", { ...HOSTED_ENV, LILITH_OWNER_EMAILS: "not-an-email" }],
        ["missing public origin", { ...HOSTED_ENV, LILITH_PUBLIC_ORIGIN: undefined }],
        ["http public origin", { ...HOSTED_ENV, LILITH_PUBLIC_ORIGIN: "http://os.example.com" }],
        ["public origin with a path", { ...HOSTED_ENV, LILITH_PUBLIC_ORIGIN: "https://os.example.com/app" }],
        ["browser-direct backend in hosted mode", { ...HOSTED_ENV, NEXT_PUBLIC_LILITH_API_URL: "http://10.0.0.2:8765" }],
      ];
      for (const [name, env] of bad) check(`hosted misconfiguration fails closed: ${name}`, readEdgeAuthConfig(env).mode === "misconfigured");
      for (const k of Object.keys(HOSTED_ENV)) check(`${k} is server-only (not NEXT_PUBLIC_)`, !k.startsWith("NEXT_PUBLIC_"));
    }

    /* ------------------------------------------------ proxy boundary */
    const jw = fakeJwks();
    jw.state.keys = [k1.jwk];
    __resetEdgeAuthForTests(jw.fetchImpl);
    const live = () => Math.floor(Date.now() / 1000);
    const owner = await k1.sign(hdr(), claims(live()));
    const stranger = await k1.sign(hdr(), claims(live(), { email: "stranger@example.com" }));

    setEnv({});
    check("local mode: the proxy passes everything through",
      (await proxy(fakeRequest({}))).headers.get("x-middleware-next") === "1");
    const localAuth = await authenticateEdge(new Headers());
    check("local mode: no edge identity is asserted", localAuth.ok && localAuth.mode === "local" && localAuth.email === null);

    setEnv({ ...HOSTED_ENV, LILITH_ACCESS_AUD: undefined });
    check("hosted misconfiguration: the proxy refuses with 503", (await proxy(fakeRequest({}))).status === 503);

    setEnv(HOSTED_ENV);
    const p = async (h: Record<string, string>) => (await proxy(fakeRequest(h))).status;
    check("hosted: direct-origin access without a Cloudflare token is refused (401)", (await p({})) === 401);
    check("hosted: a forged token is refused", (await p({ [ACCESS_JWT_HEADER]: await attacker.sign(hdr(), claims(live())) })) === 401);
    check("hosted: a non-owner identity is refused (403)", (await p({ [ACCESS_JWT_HEADER]: stranger })) === 403);
    check("hosted: a token in the cookie alone is not accepted",
      (await p({ cookie: `CF_Authorization=${owner}` })) === 401);
    check("hosted: the owner passes the proxy",
      (await proxy(fakeRequest({ [ACCESS_JWT_HEADER]: owner }))).headers.get("x-middleware-next") === "1");
    const proxySrc = readFileSync(join(process.cwd(), "src/proxy.ts"), "utf8");
    check("the proxy exports no matcher (covers pages, API routes and public assets)",
      !/export\s+const\s+config/.test(proxySrc) && !/matcher/.test(proxySrc.replace(/^\s*\*.*$/gm, "")));

    /* ------------------------------------------------ handlers re-verify independently */
    const draftCtx = { params: Promise.resolve({ draftId: "d1" }) };
    const taskCtx = { params: Promise.resolve({ taskId: "t1" }) };
    const pathCtx = { params: Promise.resolve({ path: ["system", "status"] }) };
    const handlers: [string, (r: NextRequest) => Promise<Response>, boolean][] = [
      ["conversation POST", (r) => conversationRoute.POST(r), true],
      ["evidence GET", (r) => evidenceRoute.GET(r), false],
      ["evidence POST", (r) => evidenceRoute.POST(r), true],
      ["drafts GET", (r) => draftsRoute.GET(r), false],
      ["drafts POST", (r) => draftsRoute.POST(r), true],
      ["draft GET", (r) => draftRoute.GET(r, draftCtx), false],
      ["draft DELETE", (r) => draftRoute.DELETE(r, draftCtx), true],
      ["tasks GET", (r) => tasksRoute.GET(r), false],
      ["tasks POST", (r) => tasksRoute.POST(r), true],
      ["task GET", (r) => taskRoute.GET(r, taskCtx), false],
      ["task PATCH", (r) => taskRoute.PATCH(r, taskCtx), true],
      ["read proxy GET", (r) => readProxyRoute.GET(r, pathCtx), false],
      ["TTS POST", (r) => ttsRoute.POST(r), true],
      ["ElevenLabs POST", (r) => elevenRoute.POST(r), true],
    ];
    const json = { "content-type": "application/json" };
    for (const [name, handler, mutating] of handlers) {
      const noToken = await handler(fakeRequest({ ...json, origin: ORIGIN }, { message: "hi", text: "hi" }));
      check(`${name}: refused without a token even if the proxy is bypassed`, noToken.status === 401, String(noToken.status));
      const wrongId = await handler(fakeRequest({ ...json, origin: ORIGIN, [ACCESS_JWT_HEADER]: stranger }, { message: "hi" }));
      check(`${name}: refused for a non-owner identity`, wrongId.status === 403, String(wrongId.status));
      if (mutating) {
        for (const [label, headers, status] of [
          ["cross-origin", { ...json, origin: "https://evil.example.com" }, 403],
          ["missing Origin", { ...json }, 403],
          ["Origin null", { ...json, origin: "null" }, 403],
          ["forwarded-host spoof", { ...json, origin: "https://evil.example.com", "x-forwarded-host": "os.example.com", host: "os.example.com" }, 403],
          ["cross-site fetch metadata", { ...json, origin: ORIGIN, "sec-fetch-site": "cross-site" }, 403],
        ] as const) {
          const r = await handler(fakeRequest({ ...headers, [ACCESS_JWT_HEADER]: owner }, { message: "hi" }));
          check(`${name}: ${label} refused`, r.status === status, String(r.status));
        }
      }
      // Owner, same origin, JSON: the guard passes and the handler proceeds (backend/keys unset → 503,
      // or the owner-capture gate → 403 for evidence POST).
      const passed = await handler(fakeRequest({ ...json, origin: ORIGIN, [ACCESS_JWT_HEADER]: owner }, { message: "hi", text: "hi" }));
      check(`${name}: the owner passes the guard`, ![401, 415].includes(passed.status) &&
        !(passed.status === 403 && name !== "evidence POST"), String(passed.status));
    }
    for (const [name, handler] of [["conversation POST", conversationRoute.POST], ["TTS POST", ttsRoute.POST], ["tasks POST", tasksRoute.POST]] as const) {
      for (const ct of ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x", "application/json-patch+json"]) {
        const r = await (handler as (q: NextRequest) => Promise<Response>)(
          fakeRequest({ "content-type": ct, origin: ORIGIN, [ACCESS_JWT_HEADER]: owner }, { message: "hi" }));
        check(`${name}: content-type ${ct.split(";")[0]} refused (415)`, r.status === 415, String(r.status));
      }
    }
    check("read proxy stays GET-only (no state-changing export)",
      !("POST" in readProxyRoute) && !("PUT" in readProxyRoute) && !("PATCH" in readProxyRoute) && !("DELETE" in readProxyRoute));

    /* ------------------------------------------------ owner authority is untouched */
    const ownerReq = fakeRequest({ ...json, origin: ORIGIN, [ACCESS_JWT_HEADER]: owner }, { action: "open" });
    const capture = await ownerCaptureAuthentication(ownerReq);
    check("Cloudflare login does NOT satisfy owner-capture authentication", !capture.available);
    const evidence = await evidenceRoute.POST(ownerReq);
    const evidenceBody = await evidence.json().catch(() => ({}));
    check("a signed-in owner still cannot open evidence capture (owner authority required)",
      evidence.status === 403 && evidenceBody.error === "OWNER_AUTHENTICATION_REQUIRED", JSON.stringify(evidenceBody));
    const authSrc = readFileSync(join(process.cwd(), "src/lib/conversation/owner-capture-auth.ts"), "utf8");
    check("owner-capture authentication does not consult the edge identity", !/edge-auth|cf-access|guardApiRequest/i.test(authSrc));
    const proxyAllow = readFileSync(join(process.cwd(), "src/app/api/lilith/[...path]/route.ts"), "utf8");
    check("no web route forwards memory approval, erasure, canonical or signing endpoints",
      !/approve|forget|erase|canonical|sign|privacy|owner_proof|memory\/(write|admit|action)/i.test(
        (proxyAllow.match(/const ALLOWED = \[[\s\S]*?\];/) ?? [""])[0].replace(/\/\/.*$/gm, "")));

    /* ------------------------------------------------ no browser-readable credentials */
    const root = join(process.cwd(), "src");
    const leaks = sourceFiles(root).filter((f) => {
      const src = readFileSync(f, "utf8");
      return /NEXT_PUBLIC_[A-Z_]*(TOKEN|KEY|SECRET|AUD|EMAIL|TEAM)/.test(src) ||
        (/["']use client["']/.test(src) && /@\/server\//.test(src));
    });
    check("no browser-readable credential variables; no client module imports server auth code", leaks.length === 0, leaks.join(", "));
  } finally {
    setEnv(savedEnv);
    __resetEdgeAuthForTests(null);
  }
  return out;
}
