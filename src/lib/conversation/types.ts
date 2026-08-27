/** A single turn in the LILITH OS conversation transcript. */
export interface ConversationMessage {
  id: string;
  role: "user" | "lilith";
  text: string;
  /** ISO timestamp. */
  ts: string;
  /** Set on a lilith message that represents a failed turn (for retry UI). */
  error?: boolean;
}

export type ConversationStatus = "idle" | "sending";

export interface ConversationReply {
  reply: string;
  session: string;
  state?: string;
}
