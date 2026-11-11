/**
 * Which finished LILITH reply may be voiced, and how.
 *
 *  - "skip": this reply was already handled, or it was not a reply to a turn
 *    the owner sent from this page (restored history after a reload, or the
 *    transcript re-shown after navigating back). It is never spoken or
 *    re-animated, so enabling voice or returning to Home never replays history.
 *  - "speak": voice is on, so synthesize THIS reply only, via the existing
 *    production path (only its text is sent to our own server route).
 *  - "transient": voice is off, or there is nothing speakable, so play the
 *    short canned speaking beat with no TTS call.
 */
export type ReplyVoicing = "skip" | "speak" | "transient";

/** Upper bound accepted by the server TTS route; longer replies stay text. */
export const MAX_SPOKEN_CHARS = 4096;

export function decideReplyVoicing(input: {
  replyId: string;
  handledReplyId: string | null;
  /** true only while a turn sent from this page is awaiting its reply. */
  awaitingReply: boolean;
  autoSpeak: boolean;
  text: string;
}): ReplyVoicing {
  if (input.replyId === input.handledReplyId) return "skip";
  if (!input.awaitingReply) return "skip";
  if (!input.autoSpeak) return "transient";
  const t = input.text.trim();
  if (!t || t === "…" || t.length > MAX_SPOKEN_CHARS) return "transient";
  return "speak";
}
