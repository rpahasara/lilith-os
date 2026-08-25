"use client";

import { type ComponentType, type ReactNode } from "react";
import { Sparkles, Mail, Users, MessageSquareText, Hash } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { Eyebrow, PanelHeader } from "@/components/ui/primitives";
import type { MeetingContext, MeetingEvent, PrepBrief } from "@/lib/meetings/types";
import { PrepLifecycle, PrepBadge } from "./prep-lifecycle";

function Section({ icon: Icon, title, children }: { icon: ComponentType<{ className?: string }>; title: string; children: ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 text-ink-faint" />
        <Eyebrow>{title}</Eyebrow>
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function MeetingIntelligence({
  event,
  context,
  brief,
  briefLoading,
}: {
  event?: MeetingEvent | null;
  context?: MeetingContext;
  brief: PrepBrief | null;
  briefLoading: boolean;
}) {
  if (!event) {
    return (
      <GlassCard className="p-5" animated={false}>
        <PanelHeader title="Meeting intelligence" />
        <p className="mt-6 py-6 text-center text-sm text-ink-faint">
          Select a meeting to see what Lilith has prepared.
        </p>
      </GlassCard>
    );
  }

  const hasContext = context && context.eventId === event.id;

  return (
    <GlassCard className="p-5" animated={false}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Eyebrow>Meeting intelligence</Eyebrow>
          <h3 className="mt-1 truncate text-base font-semibold text-ink">{event.title}</h3>
        </div>
        <PrepBadge status={event.prepStatus} />
      </div>

      {/* prep lifecycle */}
      <div className="mt-4 rounded-[var(--radius-md)] border border-white/[0.06] bg-white/[0.02] p-4">
        <PrepLifecycle status={event.prepStatus} />
      </div>

      <div className="mt-6 space-y-6">
        {/* persisted LILITH brief */}
        <Section icon={Sparkles} title="Lilith's prep brief">
          {briefLoading ? (
            <div className="space-y-2">
              <div className="h-3 w-3/4 animate-pulse rounded bg-white/[0.05]" />
              <div className="h-3 w-full animate-pulse rounded bg-white/[0.04]" />
              <div className="h-3 w-2/3 animate-pulse rounded bg-white/[0.04]" />
            </div>
          ) : brief ? (
            <div className="rounded-[var(--radius-md)] border border-violet-bright/15 bg-violet-bright/[0.04] p-3">
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-muted">
                {brief.brief}
              </p>
              <p className="mt-2 font-mono text-[10px] text-ink-faint">
                prepared from {brief.sourceCounts.gmailMessages ?? 0} threads ·{" "}
                {brief.sourceCounts.followups ?? 0} follow-ups
              </p>
            </div>
          ) : event.prepStatus === "delivered" ? (
            <p className="text-xs text-ink-faint">
              A brief was delivered, but the full text isn&apos;t stored for this meeting.
            </p>
          ) : (
            <p className="text-xs text-ink-faint">
              No brief yet — Lilith prepares one automatically ~15 minutes before the meeting.
            </p>
          )}
        </Section>

        {/* related context */}
        <Section icon={MessageSquareText} title="Related threads">
          {hasContext && context!.messages.length > 0 ? (
            <ul className="space-y-2">
              {context!.messages.slice(0, 6).map((m, i) => (
                <li key={i} className="rounded-lg bg-white/[0.02] px-2.5 py-2">
                  <p className="flex items-center gap-1.5 text-xs text-ink">
                    <Mail className="h-3 w-3 shrink-0 text-cyan-bright/70" />
                    <span className="truncate">{m.subject || "(no subject)"}</span>
                  </p>
                  <p className="mt-0.5 truncate font-mono text-[10px] text-ink-faint">
                    {m.from}
                    {m.account ? ` · ${m.account}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-faint">
              No related context gathered for this meeting yet.
            </p>
          )}
        </Section>

        {/* keywords */}
        {hasContext && context!.keywords.length > 0 && (
          <Section icon={Hash} title="Signals">
            <div className="flex flex-wrap gap-1.5">
              {context!.keywords.slice(0, 12).map((k) => (
                <span key={k} className="rounded-md bg-white/[0.04] px-2 py-0.5 text-[11px] text-ink-muted">
                  {k}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* attendees */}
        {event.attendees.length > 0 && (
          <Section icon={Users} title="Attendees">
            <ul className="space-y-1.5">
              {event.attendees.map((a, i) => (
                <li key={i} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate text-ink-muted">{a.displayName || a.emailMasked || "Guest"}</span>
                  {a.emailMasked && (
                    <span className="shrink-0 font-mono text-[10px] text-ink-faint">{a.emailMasked}</span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* related follow-ups */}
        {hasContext && context!.followups.length > 0 && (
          <Section icon={MessageSquareText} title="Related follow-ups">
            <ul className="space-y-1.5">
              {context!.followups.map((f) => (
                <li key={f.id} className="text-xs text-ink-muted">
                  {f.title}
                  {f.due && <span className="ml-1 text-ink-faint">· due {f.due}</span>}
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </GlassCard>
  );
}
