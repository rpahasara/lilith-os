"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { Activity, ArrowUpRight, RotateCw } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { StatusDot, WorkspaceHeader, type Accent } from "@/components/ui/primitives";
import { SectionHeader, StatusBadge } from "@/components/ui/workspace";
import { useShellHealth } from "@/components/layout/shell-health-provider";
import { setVoiceReplies } from "@/components/conversation/voice-toggle";
import { useNow } from "@/hooks/use-now";
import { shellHealthLabel, type ShellHealth } from "@/lib/system/shell-health";
import { PLATFORM_STATE_LABEL, automationSummary, type PlatformState, type PlatformUnit } from "@/lib/system/platform";
import {
  detectWebGL, usePresencePreference, useReducedMotion, writePresencePreference,
  type PresencePreference,
} from "@/lib/presence/capabilities";
import { presenceRenderReport, type PresenceRenderReport } from "@/lib/presence/renderer-report";
import { browserVoiceStorage, voiceSettings } from "@/lib/voice/voice-settings";
import { lilithSpeech } from "@/lib/voice/speech-controller";
import { cn } from "@/lib/utils";

/*
 * System: measured health of LILITH and of this device, and the preferences
 * that already work. Every value is either measured (the shell's health probe,
 * the platform units in that same response, what the presence stage reports,
 * what this browser can do) or a setting the owner chose. Nothing is a static
 * status, and nothing here starts a probe of its own.
 */

export const SYSTEM_IDENTITY = {
  icon: Activity,
  eyebrow: "Operations · System",
  title: "System",
  description: "Measured health of LILITH and of this device, and the preferences you can change. If something can't be measured, it says so.",
};

/* ------------------------------------------------------------ small parts */

function ago(iso: string | null, now: number | null): string {
  if (!iso || now === null) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

function clock(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isFinite(d.getTime()) ? d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
}

function Row({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-baseline gap-3 py-2.5">
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="min-w-0 text-xs text-ink [overflow-wrap:anywhere]">
        {children}
        {hint && <span className="mt-0.5 block text-micro leading-relaxed text-ink-faint">{hint}</span>}
      </dd>
    </div>
  );
}

const HEALTH_ACCENT: Record<ShellHealth["state"], Accent> = { checking: "orchid", live: "green", unconfigured: "amber", unreachable: "rose" };
const UNIT_TONE: Record<PlatformState, "green" | "cyan" | "amber" | "rose" | "faint"> = {
  running: "green", scheduled: "cyan", idle: "faint", failed: "rose", unknown: "amber",
};

/* ------------------------------------------------------------- connection */

function ConnectionCard() {
  const { health, refresh } = useShellHealth();
  const now = useNow(15_000);
  // "Check again" waits for the next completed probe (or gives up after 12s).
  const [waitingSince, setWaitingSince] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    if (waitingSince === undefined) return;
    if (health.checkedAt !== waitingSince) { setWaitingSince(undefined); return; }
    const t = window.setTimeout(() => setWaitingSince(undefined), 12_000);
    return () => window.clearTimeout(t);
  }, [health.checkedAt, waitingSince]);
  const checking = waitingSince !== undefined;

  const explanation =
    health.state === "unconfigured" ? "This deployment has no backend configured, so nothing can be read."
      : health.state === "unreachable" ? `The backend did not answer the last check (${health.httpStatus ? `HTTP ${health.httpStatus}` : "network error or timeout"}).`
        : health.state === "checking" ? "The first check has not finished yet."
          : "The backend answered the last check.";

  return (
    <GlassCard className="p-5" animated={false} data-system-card="connection">
      <SectionHeader
        title="Connection"
        description="Measured by the shell's own check, every minute while this tab is visible."
        action={
          <button
            type="button"
            onClick={() => { setWaitingSince(health.checkedAt); refresh(); }}
            disabled={checking}
            className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.1] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-white/20 hover:text-ink disabled:opacity-60"
          >
            <RotateCw className={cn("h-3 w-3", checking && "animate-spin")} />
            {checking ? "Checking…" : "Check again"}
          </button>
        }
      />
      <div className="mt-4 flex items-center gap-2.5" role="status" aria-live="polite" data-connection-state={health.state}>
        <StatusDot accent={HEALTH_ACCENT[health.state]} />
        <span className="text-lg font-medium text-ink">{shellHealthLabel(health)}</span>
        {health.state === "live" && health.latencyMs !== null && <span className="font-mono text-xs text-ink-muted">{health.latencyMs} ms</span>}
      </div>
      <p className="mt-1 text-xs text-ink-faint">{explanation}</p>
      <dl className="mt-3 divide-y divide-white/[0.05] border-t border-white/[0.05]">
        <Row label="Round trip" hint="Browser → web app → backend and back. Not model latency.">
          {health.state === "live" && health.latencyMs !== null ? `${health.latencyMs} ms` : "Not measured"}
        </Row>
        <Row label="Last check">{health.checkedAt ? `${ago(health.checkedAt, now)} · ${clock(health.checkedAt)}` : "Not yet"}</Row>
        <Row label="Response">{health.httpStatus === null ? "—" : health.httpStatus === 0 ? "No response" : `HTTP ${health.httpStatus}`}</Row>
      </dl>
    </GlassCard>
  );
}

/* --------------------------------------------------------------- platform */

function UnitRow({ unit, now }: { unit: PlatformUnit; now: number | null }) {
  const since = unit.state === "running" && unit.lastRun ? `since ${clock(unit.lastRun)}` : null;
  return (
    <li className="flex items-start justify-between gap-3 py-3" data-platform-unit={unit.id}>
      <div className="min-w-0">
        <p className="text-sm text-ink">{unit.name}</p>
        <p className="mt-0.5 text-micro text-ink-faint">
          {[since, unit.restarts ? `restarted ${unit.restarts} ${unit.restarts === 1 ? "time" : "times"}` : null, unit.kind === "timer" && unit.lastRun ? `last run ${ago(unit.lastRun, now)}` : null]
            .filter(Boolean).join(" · ") || "No run details reported"}
        </p>
      </div>
      <span title={unit.detail ? `systemd: ${unit.detail}` : undefined}>
        <StatusBadge label={PLATFORM_STATE_LABEL[unit.state]} tone={UNIT_TONE[unit.state]} />
      </span>
    </li>
  );
}

function PlatformCard() {
  const { health } = useShellHealth();
  const now = useNow(30_000);
  const platform = health.platform;
  const core = platform?.units.filter((u) => u.role === "platform") ?? [];
  const autos = platform ? automationSummary(platform.units) : null;

  return (
    <GlassCard className="p-5" animated={false} data-system-card="platform">
      <SectionHeader title="Platform" description="The services LILITH runs on, as the backend reports them in the same check." />
      {!platform ? (
        <p className="mt-4 text-xs leading-relaxed text-ink-muted" data-platform-state="none">
          {health.state === "live"
            ? "The backend answered but did not report its services."
            : "Shown once the backend answers. Nothing is assumed in the meantime."}
        </p>
      ) : (
        <>
          <ul className="mt-2 divide-y divide-white/[0.05]">
            {core.map((u) => <UnitRow key={u.id} unit={u} now={now} />)}
          </ul>
          {autos && autos.total > 0 && (
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-white/[0.06] bg-white/[0.02] px-3.5 py-3" data-platform-automations="">
              <p className="text-xs text-ink-muted">
                <span className="font-medium text-ink">{autos.total} automations</span>
                {(["scheduled", "running", "failed", "idle", "unknown"] as const)
                  .filter((s) => autos[s] > 0)
                  .map((s) => ` · ${autos[s]} ${PLATFORM_STATE_LABEL[s].toLowerCase()}`)
                  .join("")}
              </p>
              <Link href="/automations" className="inline-flex items-center gap-1 text-xs text-wine-bright hover:underline">
                Open Automations <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>
          )}
          <p className="mt-3 text-micro text-ink-faint">
            Reported by the backend {platform.reportedAt ? `at ${clock(platform.reportedAt)}` : "with no time"}.
            {platform.unlisted > 0 && ` ${platform.unlisted} other ${platform.unlisted === 1 ? "unit is" : "units are"} reported but not shown here.`}
          </p>
        </>
      )}
    </GlassCard>
  );
}

/* ------------------------------------------------------------ this device */

const RENDER_WORDS: Record<PresenceRenderReport["reason"], string> = {
  live: "",
  "preference-off": "Off, as set in Preferences",
  "reduced-motion": "Still image: this device asks for reduced motion",
  "no-webgl": "Still image: this browser cannot use WebGL",
  performance: "Still image: the frame rate stayed too low (reload to try again)",
  error: "Still image: the renderer failed",
};

export function presenceLine(report: PresenceRenderReport | null): { text: string; tone: "green" | "amber" | "faint" } {
  if (!report) return { text: "Not measured yet in this tab", tone: "faint" };
  if (report.reason === "live") return { text: `${report.rendered === "avatar" ? "Avatar" : "Orb"}, live${report.fps !== null ? ` · ${report.fps} fps` : ""}`, tone: "green" };
  return { text: RENDER_WORDS[report.reason], tone: report.reason === "preference-off" ? "faint" : "amber" };
}

function useStorageWorks(): boolean | null {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    try {
      const k = "lilith-os:storage-check";
      window.localStorage.setItem(k, "1");
      const back = window.localStorage.getItem(k) === "1";
      window.localStorage.removeItem(k);
      setOk(back);
    } catch {
      setOk(false);
    }
  }, []);
  return ok;
}

function DeviceCard() {
  const report = useSyncExternalStore(presenceRenderReport.subscribe, presenceRenderReport.get, presenceRenderReport.getServer);
  const speech = useSyncExternalStore(lilithSpeech.subscribe, lilithSpeech.getSnapshot, lilithSpeech.getServerSnapshot);
  const reduced = useReducedMotion();
  const storage = useStorageWorks();
  const now = useNow(30_000);
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => setWebgl(detectWebGL()), []);
  const presence = presenceLine(report);

  const voice =
    speech.lastResult === "ok" ? "The last reply was spoken"
      : speech.lastResult === "unavailable" ? "Voice wasn't available for the last reply"
        : speech.lastResult === "blocked" ? "The browser blocked audio for the last reply"
          : "Not tried in this tab";

  return (
    <GlassCard className="p-5" animated={false} data-system-card="device">
      <SectionHeader title="This device" description="Measured in this browser, now." />
      <dl className="mt-2 divide-y divide-white/[0.05]">
        <Row
          label="Lilith's presence"
          hint={report ? `Measured on the Command Center ${ago(report.at, now)}.` : "It is measured on the Command Center; open it once and come back."}
        >
          <span data-presence-report={report ? `${report.rendered}:${report.reason}` : "none"}>
            <StatusBadge label={presence.text} tone={presence.tone} />
          </span>
        </Row>
        <Row label="WebGL">{webgl === null ? "Checking…" : webgl ? "Available" : "Not available"}</Row>
        <Row label="Reduced motion" hint="Set by your device. LILITH follows it.">{reduced ? "On" : "Off"}</Row>
        <Row label="Spoken replies">{voice}</Row>
        <Row label="Saved preferences" hint={storage === false ? "Choices apply until you reload." : undefined}>
          {storage === null ? "Checking…" : storage ? "Kept in this browser" : "This browser won't keep them"}
        </Row>
      </dl>
    </GlassCard>
  );
}

/* ------------------------------------------------------------ preferences */

const PRESENCE_OPTIONS: { value: PresencePreference; label: string; detail: string }[] = [
  { value: "full", label: "Avatar", detail: "Lilith in full on the Command Center." },
  { value: "orb", label: "Orb", detail: "A lighter, abstract presence." },
  { value: "off", label: "Off", detail: "No presence on the Command Center." },
];

function PreferencesCard() {
  const presence = usePresencePreference();
  const [unsaved, setUnsaved] = useState(false);
  const reduced = useReducedMotion();
  useEffect(() => { voiceSettings.hydrate(browserVoiceStorage()); }, []);
  const speak = useSyncExternalStore(voiceSettings.subscribe, () => voiceSettings.getSnapshot().autoSpeak, () => voiceSettings.getServerSnapshot().autoSpeak);
  const group = useRef<HTMLDivElement>(null);

  const choose = (value: PresencePreference) => setUnsaved(!writePresencePreference(value));
  // Arrow keys move between the options, as in any radio group.
  const onKey = (e: React.KeyboardEvent) => {
    const i = PRESENCE_OPTIONS.findIndex((o) => o.value === presence);
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = PRESENCE_OPTIONS[(i + step + PRESENCE_OPTIONS.length) % PRESENCE_OPTIONS.length];
    choose(next.value);
    group.current?.querySelector<HTMLElement>(`[data-value="${next.value}"]`)?.focus();
  };

  return (
    <GlassCard className="p-5" animated={false} data-system-card="preferences">
      <SectionHeader title="Preferences" description="Kept in this browser. They change what you see, not what LILITH knows." />

      <div className="mt-4">
        <p id="pref-presence" className="text-xs font-medium text-ink">Lilith&apos;s presence</p>
        <div ref={group} role="radiogroup" aria-labelledby="pref-presence" onKeyDown={onKey} className="mt-2 grid gap-2">
          {PRESENCE_OPTIONS.map((o) => {
            const on = presence === o.value;
            return (
              <button
                key={o.value}
                type="button"
                role="radio"
                aria-checked={on}
                tabIndex={on ? 0 : -1}
                data-value={o.value}
                onClick={() => choose(o.value)}
                className={cn(
                  "flex items-start gap-3 rounded-2xl border px-3.5 py-2.5 text-left transition-colors",
                  on ? "border-wine-bright/35 bg-wine/10" : "border-white/[0.06] bg-white/[0.02] hover:border-white/12",
                )}
              >
                <span aria-hidden className={cn("mt-0.5 grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full border", on ? "border-wine-bright" : "border-white/25")}>
                  {on && <span className="h-1.5 w-1.5 rounded-full bg-wine-bright" />}
                </span>
                <span className="min-w-0">
                  <span className="block text-xs font-medium text-ink">{o.label}</span>
                  <span className="block text-micro leading-relaxed text-ink-faint">{o.detail}</span>
                </span>
              </button>
            );
          })}
        </div>
        {unsaved && <p role="status" className="mt-2 text-micro text-amber">This browser won&apos;t keep it; it applies until you reload.</p>}
      </div>

      <div className="mt-5 flex items-start justify-between gap-4 border-t border-white/[0.06] pt-4">
        <div className="min-w-0">
          <p id="pref-voice" className="text-xs font-medium text-ink">Speak replies</p>
          <p className="mt-0.5 text-micro leading-relaxed text-ink-faint">Read Lilith&apos;s new replies aloud. The same switch as on the Command Center.</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={speak}
          aria-labelledby="pref-voice"
          onClick={() => setVoiceReplies(!speak)}
          className={cn("relative h-6 w-11 shrink-0 rounded-full border transition-colors", speak ? "border-wine-bright/50 bg-wine/40" : "border-white/15 bg-white/[0.06]")}
        >
          <span aria-hidden className={cn("absolute top-0.5 h-[18px] w-[18px] rounded-full bg-pearl shadow transition-[left]", speak ? "left-[22px]" : "left-0.5")} />
        </button>
      </div>

      <div className="mt-5 border-t border-white/[0.06] pt-4">
        <p className="text-xs font-medium text-ink">Motion</p>
        <p className="mt-0.5 text-micro leading-relaxed text-ink-faint">
          Follows your device: reduced motion is <span className="text-ink-muted">{reduced ? "on" : "off"}</span>. Change it in your device&apos;s accessibility settings.
        </p>
      </div>
    </GlassCard>
  );
}

/* ------------------------------------------------------------------ about */

function AboutCard() {
  const version = process.env.NEXT_PUBLIC_LILITH_VERSION || "—";
  return (
    <GlassCard className="p-5" animated={false} data-system-card="about">
      <SectionHeader title="About" />
      <dl className="mt-2 divide-y divide-white/[0.05]">
        <Row label="Application">LILITH OS</Row>
        <Row label="Version">{version}</Row>
        <Row label="Build">{process.env.NODE_ENV === "production" ? "Production" : "Development"}</Row>
      </dl>
    </GlassCard>
  );
}

/* ------------------------------------------------------------------- page */

export function SystemWorkspace() {
  return (
    <>
      <WorkspaceHeader {...SYSTEM_IDENTITY} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <ConnectionCard />
          <PlatformCard />
          <DeviceCard />
        </div>
        <div className="space-y-4">
          <PreferencesCard />
          <AboutCard />
        </div>
      </div>
    </>
  );
}
