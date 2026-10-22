/**
 * Owner-protected First Interaction recording (F5): client state machine + requests.
 *
 * The server is the only authority. A recording session id is minted by the
 * backend (`fi-capture-…`) and every action is re-checked there: an id kept in
 * localStorage is only a UI hint, never proof of who is using the browser.
 * Recording is available only when the server reports an authenticated owner
 * session; until a real owner-authentication bridge exists it never does, so
 * the controls stay hidden and nothing can be recorded.
 *
 * Recording a transcript is not a memory: the confirmation names the sealed
 * evidence reference and says so.
 */

export type RecordingPhase =
  | "unavailable"
  | "idle"
  | "starting"
  | "recording"
  | "finishing"
  | "finished"
  | "interrupted";

export interface SealedEvidence {
  evidenceRef: string;
  sha256: string;
  turnCount: number;
}

export interface RecordingState {
  phase: RecordingPhase;
  /** Server-minted capture session; only meaningful while recording/finishing. */
  session: string | null;
  evidence: SealedEvidence | null;
  error: string | null;
  /** Why recording is unavailable (server-reported). */
  reason: string | null;
}

export type RecordingAction =
  | { type: "AVAILABILITY"; available: boolean; reason?: string | null }
  | { type: "RESTORE"; session: string }
  | { type: "START_REQUESTED" }
  | { type: "STARTED"; session: string }
  | { type: "START_FAILED"; error: string }
  | { type: "FINISH_REQUESTED" }
  | { type: "FINISHED"; evidence: SealedEvidence }
  | { type: "FINISH_FAILED"; code: string; error: string }
  | { type: "DISMISS" };

export const INITIAL_RECORDING: RecordingState = {
  phase: "unavailable",
  session: null,
  evidence: null,
  error: null,
  reason: "OWNER_AUTHENTICATION_UNAVAILABLE",
};

const CAPTURE_SESSION = /^fi-capture-[0-9a-f]{32}$/;
/** Server refusals after which the current recording can never be finished. */
const TERMINAL = new Set([
  "CAPTURE_INCOMPLETE",
  "CAPTURE_SESSION_SEALED",
  "CAPTURE_SESSION_UNKNOWN",
  "CAPTURE_SESSION_NOT_OPEN",
  "CAPTURE_PRIVACY_HELD",
  "CAPTURE_PRIVACY_FORGOTTEN",
]);

export function recordingReducer(state: RecordingState, action: RecordingAction): RecordingState {
  switch (action.type) {
    case "AVAILABILITY":
      if (!action.available) {
        return { ...INITIAL_RECORDING, reason: action.reason ?? "OWNER_AUTHENTICATION_UNAVAILABLE" };
      }
      return state.phase === "unavailable" ? { ...state, phase: "idle", reason: null } : state;
    case "RESTORE":
      // A stored id only resumes the UI; the server re-checks it on the next send or finish.
      if (state.phase !== "idle" || !CAPTURE_SESSION.test(action.session)) return state;
      return { ...state, phase: "recording", session: action.session, error: null };
    case "START_REQUESTED":
      if (!["idle", "finished", "interrupted"].includes(state.phase)) return state; // duplicate / pending
      return { ...state, phase: "starting", session: null, evidence: null, error: null };
    case "STARTED":
      if (state.phase !== "starting" || !CAPTURE_SESSION.test(action.session)) {
        return state.phase === "starting"
          ? { ...state, phase: "idle", error: "The server returned an invalid recording session." }
          : state;
      }
      return { ...state, phase: "recording", session: action.session };
    case "START_FAILED":
      return state.phase === "starting" ? { ...state, phase: "idle", error: action.error } : state;
    case "FINISH_REQUESTED":
      return state.phase === "recording" ? { ...state, phase: "finishing", error: null } : state;
    case "FINISHED":
      if (state.phase !== "finishing") return state;
      return { ...state, phase: "finished", session: null, evidence: action.evidence };
    case "FINISH_FAILED":
      if (state.phase !== "finishing") return state;
      return TERMINAL.has(action.code)
        ? { ...state, phase: "interrupted", session: null, error: action.error }
        : { ...state, phase: "recording", error: action.error }; // e.g. network: the owner may try again
    case "DISMISS":
      if (!["finished", "interrupted"].includes(state.phase)) return state;
      return { ...state, phase: "idle", session: null, evidence: null, error: null };
  }
}

/** The finished-recording confirmation. Never claims a memory was created or accepted. */
export function recordingConfirmation(evidence: SealedEvidence): string {
  return (
    `Transcript recorded and sealed (${evidence.turnCount} turns, evidence ${evidence.evidenceRef}). ` +
    "This is not a memory: nothing has been admitted or accepted."
  );
}

export function isRecordingActive(state: RecordingState): boolean {
  return state.phase === "recording" || state.phase === "finishing";
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface RecordingResult<T> {
  ok: boolean;
  value?: T;
  code?: string;
  error?: string;
}

const EVIDENCE_PATH = "/api/lilith/conversation/evidence";

async function call<T>(fetchImpl: FetchLike, init: RequestInit): Promise<RecordingResult<T>> {
  let res: Response;
  try {
    res = await fetchImpl(EVIDENCE_PATH, { cache: "no-store", ...init });
  } catch {
    return { ok: false, code: "NETWORK", error: "LILITH is unreachable right now." };
  }
  let data: Record<string, unknown> | null = null;
  try {
    data = (await res.json()) as Record<string, unknown>;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail ?? data?.error;
    const code = typeof detail === "string" ? detail : `HTTP_${res.status}`;
    return { ok: false, code, error: recordingErrorText(code) };
  }
  return { ok: true, value: (data ?? {}) as T };
}

export function recordingErrorText(code: string): string {
  switch (code) {
    case "OWNER_AUTHENTICATION_REQUIRED":
    case "OWNER_AUTHENTICATION_UNAVAILABLE":
      return "Recording needs an authenticated owner session.";
    case "CAPTURE_INCOMPLETE":
      return "This recording was interrupted and cannot be finished. Start a new one.";
    case "CAPTURE_TOO_SHORT":
      return "Say at least one thing before finishing the recording.";
    case "CAPTURE_PRIVACY_HELD":
    case "CAPTURE_PRIVACY_FORGOTTEN":
      return "Recording is blocked by a privacy request.";
    default:
      return "The recording request failed.";
  }
}

export async function fetchRecordingAvailability(
  fetchImpl: FetchLike,
): Promise<{ available: boolean; reason: string | null }> {
  const result = await call<{ available?: unknown; reason?: unknown }>(fetchImpl, { method: "GET" });
  if (!result.ok) return { available: false, reason: result.code ?? "UNAVAILABLE" };
  return {
    available: result.value?.available === true,
    reason: typeof result.value?.reason === "string" ? result.value.reason : null,
  };
}

function post<T>(fetchImpl: FetchLike, body: Record<string, string>) {
  return call<T>(fetchImpl, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(body),
  });
}

export async function startRecording(fetchImpl: FetchLike): Promise<RecordingResult<string>> {
  const result = await post<{ session?: unknown }>(fetchImpl, { action: "open" });
  if (!result.ok) return { ok: false, code: result.code, error: result.error };
  const session = result.value?.session;
  return typeof session === "string" ? { ok: true, value: session } : { ok: false, code: "INVALID_RESPONSE",
    error: "The server returned an invalid recording session." };
}

export async function finishRecording(
  fetchImpl: FetchLike,
  session: string,
): Promise<RecordingResult<SealedEvidence>> {
  const result = await post<Record<string, unknown>>(fetchImpl, { action: "seal", session });
  if (!result.ok) return { ok: false, code: result.code, error: result.error };
  const v = result.value ?? {};
  if (typeof v.evidenceRef !== "string" || typeof v.sha256 !== "string" || typeof v.turnCount !== "number") {
    return { ok: false, code: "INVALID_RESPONSE", error: "The server returned an invalid sealed transcript." };
  }
  return { ok: true, value: { evidenceRef: v.evidenceRef, sha256: v.sha256, turnCount: v.turnCount } };
}
