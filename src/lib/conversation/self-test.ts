/**
 * Headless self-test for owner-protected First Interaction recording (F5).
 * Fakes only: no browser, no backend, no real conversation. Run by
 * `npm run test:core` (scripts/run-core-self-test.mjs).
 */
import type { NextRequest } from "next/server";
import {
  INITIAL_RECORDING,
  finishRecording,
  fetchRecordingAvailability,
  recordingConfirmation,
  recordingReducer,
  startRecording,
  type RecordingState,
} from "./recording";
import { GET as evidenceGet, POST as evidencePost } from "@/app/api/lilith/conversation/evidence/route";
import { POST as conversationPost } from "@/app/api/lilith/conversation/route";

interface Result {
  name: string;
  pass: boolean;
  detail?: string;
}

const SESSION = "fi-capture-" + "a".repeat(32);
const EVIDENCE = { evidenceRef: "evidence.conv." + "b".repeat(32), sha256: "c".repeat(64), turnCount: 4 };

function check(name: string, fn: () => boolean | Promise<boolean>, results: Result[]) {
  return Promise.resolve()
    .then(fn)
    .then((pass) => results.push({ name, pass }))
    .catch((e) => results.push({ name, pass: false, detail: String(e) }));
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function fakeRequest(body: unknown, headers: Record<string, string> = {}): NextRequest {
  const h = new Headers({ "content-type": "application/json", ...headers });
  return {
    headers: h,
    nextUrl: { origin: "http://localhost:3000" },
    json: async () => body,
  } as unknown as NextRequest;
}

function reduce(...actions: Parameters<typeof recordingReducer>[1][]): RecordingState {
  return actions.reduce(recordingReducer, INITIAL_RECORDING);
}

export async function runConversationSelfTest(): Promise<Result[]> {
  const results: Result[] = [];
  const available = { type: "AVAILABILITY", available: true } as const;

  await check("recording.hiddenByDefault", () => INITIAL_RECORDING.phase === "unavailable", results);
  await check("recording.unavailableIgnoresStart", () =>
    reduce({ type: "START_REQUESTED" }).phase === "unavailable", results);
  await check("recording.storedIdIsNotProof", () =>
    reduce({ type: "RESTORE", session: SESSION }).phase === "unavailable"
    && reduce(available, { type: "RESTORE", session: "lilith-os-guess" }).phase === "idle", results);
  await check("recording.startUsesServerSession", () => {
    const s = reduce(available, { type: "START_REQUESTED" }, { type: "STARTED", session: SESSION });
    return s.phase === "recording" && s.session === SESSION;
  }, results);
  await check("recording.duplicateStartIgnored", () => {
    const starting = reduce(available, { type: "START_REQUESTED" });
    return recordingReducer(starting, { type: "START_REQUESTED" }) === starting;
  }, results);
  await check("recording.invalidServerSessionRefused", () =>
    reduce(available, { type: "START_REQUESTED" }, { type: "STARTED", session: "lilith-os-1" }).phase === "idle",
  results);
  await check("recording.finishSealsAndClearsSession", () => {
    const s = reduce(available, { type: "START_REQUESTED" }, { type: "STARTED", session: SESSION },
      { type: "FINISH_REQUESTED" }, { type: "FINISHED", evidence: EVIDENCE });
    return s.phase === "finished" && s.session === null && s.evidence?.evidenceRef === EVIDENCE.evidenceRef;
  }, results);
  await check("recording.duplicateFinishIgnored", () => {
    const finishing = reduce(available, { type: "START_REQUESTED" }, { type: "STARTED", session: SESSION },
      { type: "FINISH_REQUESTED" });
    return recordingReducer(finishing, { type: "FINISH_REQUESTED" }) === finishing;
  }, results);
  await check("recording.interruptedIsTerminal", () => {
    const s = reduce(available, { type: "START_REQUESTED" }, { type: "STARTED", session: SESSION },
      { type: "FINISH_REQUESTED" }, { type: "FINISH_FAILED", code: "CAPTURE_INCOMPLETE", error: "x" });
    return s.phase === "interrupted" && s.session === null;
  }, results);
  await check("recording.networkFailureKeepsRecording", () => {
    const s = reduce(available, { type: "START_REQUESTED" }, { type: "STARTED", session: SESSION },
      { type: "FINISH_REQUESTED" }, { type: "FINISH_FAILED", code: "NETWORK", error: "x" });
    return s.phase === "recording" && s.session === SESSION;
  }, results);
  await check("recording.confirmationNeverClaimsMemory", () => {
    const text = recordingConfirmation(EVIDENCE);
    return text.includes(EVIDENCE.evidenceRef) && text.includes("This is not a memory")
      && !/memory (was |has been )?(created|saved|accepted)/i.test(text);
  }, results);

  // Client requests against a fake fetch.
  await check("client.availabilityFromServer", async () => {
    const a = await fetchRecordingAvailability(async () => json({ available: false, reason: "OWNER_AUTHENTICATION_UNAVAILABLE" }));
    const b = await fetchRecordingAvailability(async () => { throw new Error("down"); });
    return !a.available && a.reason === "OWNER_AUTHENTICATION_UNAVAILABLE" && !b.available;
  }, results);
  await check("client.startAndFinish", async () => {
    const sent: string[] = [];
    const fake = async (_u: string, init?: RequestInit) => {
      sent.push(String(init?.body));
      return JSON.parse(String(init?.body)).action === "open" ? json({ session: SESSION }) : json(EVIDENCE);
    };
    const started = await startRecording(fake);
    const sealed = await finishRecording(fake, SESSION);
    return started.value === SESSION && sealed.value?.evidenceRef === EVIDENCE.evidenceRef
      && sent[1] === JSON.stringify({ action: "seal", session: SESSION });
  }, results);
  await check("client.ownerRefusalSurfaced", async () => {
    const r = await startRecording(async () => json({ error: "OWNER_AUTHENTICATION_REQUIRED" }, 403));
    return !r.ok && r.code === "OWNER_AUTHENTICATION_REQUIRED";
  }, results);

  // Next route handlers: owner authentication is unavailable, so nothing reaches the backend.
  const realFetch = globalThis.fetch;
  const env = process.env as Record<string, string | undefined>;
  const saved = { url: env.LILITH_API_URL, token: env.LILITH_OS_OWNER_CAPTURE_TOKEN };
  const upstream: { url: string; headers: Record<string, string> }[] = [];
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    upstream.push({ url: String(url), headers: { ...(init?.headers as Record<string, string>) } });
    return json({ reply: "TEST_ONLY reply", session: "lilith-os-x" });
  }) as typeof fetch;
  env.LILITH_API_URL = "http://backend.test.invalid";
  env.LILITH_OS_OWNER_CAPTURE_TOKEN = "TEST_ONLY-service-token-never-forwarded-0123456789";
  try {
    await check("route.evidenceAvailabilityFalse", async () => {
      const body = await (await evidenceGet(fakeRequest(null))).json();
      return body.available === false && body.reason === "OWNER_AUTHENTICATION_UNAVAILABLE";
    }, results);
    await check("route.evidenceRefusedWithoutOwner", async () => {
      upstream.length = 0;
      const statuses = [];
      for (const body of [{ action: "open" }, { action: "seal", session: SESSION },
        { action: "transcript", session: SESSION }]) {
        const res = await evidencePost(fakeRequest(body, { origin: "http://localhost:3000" }));
        statuses.push(res.status);
      }
      return statuses.every((s) => s === 403) && upstream.length === 0;
    }, results);
    await check("route.captureSessionRefusedWithoutOwner", async () => {
      upstream.length = 0;
      const res = await conversationPost(fakeRequest({ message: "hi", session: SESSION },
        { origin: "http://localhost:3000" }));
      return res.status === 403 && upstream.length === 0;
    }, results);
    await check("route.ordinaryChatUnchangedNoToken", async () => {
      upstream.length = 0;
      const res = await conversationPost(fakeRequest({ message: "  hi  ", session: "lilith-os-abc" }));
      const body = await res.json();
      const sent = upstream[0];
      return res.status === 200 && body.reply === "TEST_ONLY reply" && upstream.length === 1
        && sent.url === "http://backend.test.invalid/os/conversation"
        && !Object.keys(sent.headers).some((k) => k.toLowerCase() === "x-lilith-os-owner-capture");
    }, results);
  } finally {
    globalThis.fetch = realFetch;
    env.LILITH_API_URL = saved.url;
    env.LILITH_OS_OWNER_CAPTURE_TOKEN = saved.token;
    if (saved.url === undefined) delete env.LILITH_API_URL;
    if (saved.token === undefined) delete env.LILITH_OS_OWNER_CAPTURE_TOKEN;
  }
  return results;
}
