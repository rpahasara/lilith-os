"use client";

import { Circle, Square, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { recordingConfirmation } from "@/lib/conversation/recording";
import { useConversation } from "./conversation-provider";

/**
 * Start / Finish Recording for an owner-protected First Interaction transcript,
 * in the existing chat's quiet pill style. Renders nothing unless the server
 * reports an authenticated owner session (it does not until the owner
 * authentication bridge exists). Finishing confirms the sealed evidence
 * reference and never claims a memory was created or accepted.
 */
export function RecordingControl() {
  const { recording, status, startRecording, finishRecording, dismissRecording } = useConversation();
  const { phase, evidence, error } = recording;
  if (phase === "unavailable") return null;

  const pill =
    "flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 font-mono text-[10px] uppercase " +
    "tracking-wider text-ink-faint transition-colors hover:border-white/20 hover:text-ink-muted disabled:opacity-50";

  return (
    <div className="mb-1.5 flex w-full flex-col items-end gap-1" aria-live="polite">
      {(phase === "idle" || phase === "starting") && (
        <button className={pill} onClick={startRecording} disabled={phase === "starting" || status === "sending"}>
          <Circle className="h-2.5 w-2.5" /> {phase === "starting" ? "Starting…" : "Start recording"}
        </button>
      )}
      {(phase === "recording" || phase === "finishing") && (
        <button
          className={cn(pill, "border-rose/30 text-rose")}
          onClick={finishRecording}
          disabled={phase === "finishing" || status === "sending"}
        >
          <Square className="h-2.5 w-2.5" /> {phase === "finishing" ? "Sealing…" : "Recording · Finish"}
        </button>
      )}
      {(phase === "finished" || phase === "interrupted") && (
        <div className="glass flex max-w-xl items-start gap-2 rounded-2xl px-3 py-2 text-[12px] text-ink-muted">
          <span className="break-words">
            {phase === "finished" && evidence ? recordingConfirmation(evidence) : error}
          </span>
          <button onClick={dismissRecording} aria-label="Dismiss" className="shrink-0 text-ink-faint hover:text-ink">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
      {error && (phase === "idle" || phase === "recording") && (
        <span className="text-[11px] text-rose">{error}</span>
      )}
    </div>
  );
}
