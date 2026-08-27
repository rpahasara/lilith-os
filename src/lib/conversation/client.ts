/**
 * Client for the LILITH OS conversation surface.
 *
 * Talks to the same-origin private proxy (`/api/lilith/conversation`) in the
 * default proxy mode, or directly to the backend's `/os/conversation` when a
 * public backend URL is configured. All model/provider selection happens
 * VM-side in Conversation Router V2 — the browser only ever sends text and
 * receives text.
 */
import { API_BASE, API_MODE } from "@/lib/api";
import type { ConversationReply } from "./types";

const PATH = API_MODE === "direct" ? "/os/conversation" : "/conversation";

export async function sendConversation(
  message: string,
  session: string,
  signal?: AbortSignal,
): Promise<ConversationReply> {
  const res = await fetch(`${API_BASE}${PATH}`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({ message, session }),
    cache: "no-store",
    signal,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail = data?.error ?? data?.detail;
    const msg =
      typeof detail === "string" && detail
        ? detail
        : res.status === 502 || res.status === 503
          ? "LILITH is unreachable right now."
          : res.status === 504
            ? "LILITH took too long to respond."
            : `Request failed (HTTP ${res.status}).`;
    throw new Error(msg);
  }

  return {
    reply: String(data?.reply ?? ""),
    session: String(data?.session ?? session),
    state: data?.state ? String(data.state) : undefined,
  };
}
