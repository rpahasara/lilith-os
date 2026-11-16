"use client";

import { useEffect, useId, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Ellipsis,
  FlaskConical,
  Focus,
  Pause,
  Play,
  Plus,
  RotateCcw,
  SlidersHorizontal,
  Tag,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ visuals */

export interface AtlasVisuals {
  /** slow automatic sway around the profile view. */
  orbit: boolean;
  /** ambient association pathways. */
  pathways: boolean;
  glow: "soft" | "balanced" | "vivid";
  /** how much the environment is dimmed behind the brain. */
  backdrop: "light" | "balanced" | "deep";
}

export const DEFAULT_VISUALS: AtlasVisuals = {
  orbit: true,
  pathways: true,
  glow: "balanced",
  backdrop: "balanced",
};

export const GLOW_GAIN: Record<AtlasVisuals["glow"], number> = { soft: 0.78, balanced: 1, vivid: 1.22 };

/** Shadow pool behind the brain — alpha at the centre, mid and outer ring. */
export const BACKDROP_SHADE: Record<AtlasVisuals["backdrop"], [number, number, number]> = {
  light: [0.84, 0.62, 0.26],
  balanced: [0.93, 0.78, 0.42],
  deep: [0.97, 0.88, 0.6],
};

/* --------------------------------------------------------------- primitives */

const TOUCH = "[@media(pointer:coarse)]:h-10 [@media(pointer:coarse)]:w-10";

function Tooltip({ label, hint, shortcut, align }: { label: string; hint?: string; shortcut?: string; align: "start" | "center" }) {
  return (
    <span
      aria-hidden
      className={cn(
        "pointer-events-none absolute bottom-[calc(100%+12px)] z-30 flex w-max max-w-[220px] flex-col gap-0.5 rounded-lg border border-white/[0.1] bg-[rgba(14,9,15,0.92)] px-2.5 py-1.5 text-left opacity-0 shadow-[0_14px_30px_-16px_rgba(0,0,0,0.95)] backdrop-blur-xl transition-opacity duration-150",
        // appear after a beat on hover, at once on keyboard focus; never on touch
        "group-hover/dock:opacity-100 group-hover/dock:delay-300 group-focus-visible/dock:opacity-100 [@media(hover:none)]:hidden",
        align === "start" ? "left-0" : "left-1/2 -translate-x-1/2",
      )}
    >
      <span className="flex items-center gap-2 text-[11px] font-medium text-ink">
        {label}
        {shortcut && (
          <kbd className="rounded border border-white/[0.14] bg-white/[0.06] px-1 font-mono text-[9px] font-normal text-ink-muted">
            {shortcut}
          </kbd>
        )}
      </span>
      {hint && <span className="text-[10px] leading-snug text-ink-faint">{hint}</span>}
    </span>
  );
}

function DockButton({
  icon: Icon,
  label,
  hint,
  shortcut,
  active,
  pressed,
  disabled,
  expanded,
  controls,
  tipAlign = "center",
  quietTip,
  onClick,
  buttonRef,
}: {
  icon: LucideIcon;
  label: string;
  hint?: string;
  shortcut?: string;
  /** lit: the thing this button governs is on. */
  active?: boolean;
  /** toggle semantics for assistive tech; omit for plain actions. */
  pressed?: boolean;
  disabled?: boolean;
  expanded?: boolean;
  controls?: string;
  tipAlign?: "start" | "center";
  quietTip?: boolean;
  onClick: () => void;
  buttonRef?: React.Ref<HTMLButtonElement>;
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      aria-expanded={expanded}
      aria-controls={controls}
      aria-haspopup={controls ? "dialog" : undefined}
      disabled={disabled}
      onClick={onClick}
      // the global focus ring squares corners; keep these round
      style={{ borderRadius: 9999 }}
      className={cn(
        "group/dock relative grid h-9 w-9 shrink-0 place-items-center transition-[color,background-color] duration-200 disabled:cursor-not-allowed disabled:opacity-35",
        TOUCH,
        active ? "bg-white/[0.07] text-wine-bright" : "text-ink-muted hover:bg-white/[0.06] hover:text-ink",
      )}
    >
      <Icon className="h-4 w-4" strokeWidth={active ? 2 : 1.75} />
      {/* a thin mark under an active control — state without a heavy fill */}
      <span
        aria-hidden
        className={cn(
          "absolute bottom-1 h-0.5 rounded-full bg-wine-bright transition-all duration-300 [@media(pointer:coarse)]:bottom-1.5",
          active ? "w-3 opacity-90" : "w-0 opacity-0",
        )}
      />
      {!quietTip && <Tooltip label={label} hint={hint} shortcut={shortcut} align={tipAlign} />}
    </button>
  );
}

function Divider() {
  // dropped on phone-width screens so six full-size touch targets still fit
  return <span aria-hidden className="mx-0.5 h-4 w-px shrink-0 bg-white/[0.1] max-[420px]:hidden" />;
}

function Switch({ label, hint, checked, disabled, onChange }: { label: string; hint?: string; checked: boolean; disabled?: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className="group/sw flex min-h-9 w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.045] disabled:cursor-not-allowed disabled:opacity-45 [@media(pointer:coarse)]:min-h-11"
    >
      <span className="min-w-0">
        <span className="block text-xs text-ink">{label}</span>
        {hint && <span className="block text-[10px] leading-snug text-ink-faint">{hint}</span>}
      </span>
      <span
        aria-hidden
        className={cn(
          "relative h-4 w-7 shrink-0 rounded-full border transition-colors duration-200",
          checked ? "border-wine/50 bg-wine/45" : "border-white/[0.12] bg-white/[0.05]",
        )}
      >
        <span
          className={cn(
            "absolute top-[1px] h-3 w-3 rounded-full transition-all duration-200",
            checked ? "left-[13px] bg-pearl" : "left-[1px] bg-ink-faint",
          )}
        />
      </span>
    </button>
  );
}

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { key: T; label: string }[]; onChange: (value: T) => void }) {
  return (
    <div className="px-2 py-1.5">
      <p className="mb-1.5 text-xs text-ink">{label}</p>
      <div role="radiogroup" aria-label={label} className="flex rounded-full border border-white/[0.08] bg-white/[0.03] p-0.5">
        {options.map((option) => {
          const on = option.key === value;
          return (
            <button
              key={option.key}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(option.key)}
              style={{ borderRadius: 9999 }}
              className={cn(
                "min-h-7 flex-1 px-2 text-[11px] transition-colors duration-200 [@media(pointer:coarse)]:min-h-10",
                on ? "bg-white/[0.1] text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]" : "text-ink-faint hover:text-ink-muted",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MenuAction({ icon: Icon, label, hint, disabled, onClick }: { icon: LucideIcon; label: string; hint?: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex min-h-9 w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.045] disabled:cursor-not-allowed disabled:opacity-45 [@media(pointer:coarse)]:min-h-11"
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
      <span className="min-w-0 flex-1">
        <span className="block text-xs text-ink">{label}</span>
        {hint && <span className="block text-[10px] leading-snug text-ink-faint">{hint}</span>}
      </span>
    </button>
  );
}

/* --------------------------------------------------------------------- dock */

export interface AtlasDockProps {
  view: "brain" | "timeline";
  /** whether the brain is in motion (false: paused, or held for reduced motion). */
  motion: boolean;
  /** the system asks for reduced motion and the viewer has not overridden it. */
  heldForReducedMotion: boolean;
  onMotion: () => void;
  onReset: () => void;
  labels: boolean;
  onLabels: () => void;
  activity: boolean;
  onActivity: () => void;
  domains: boolean;
  onDomains: () => void;
  visuals: AtlasVisuals;
  onVisuals: (patch: Partial<AtlasVisuals>) => void;
  simulating: boolean;
  onSimulating: () => void;
  /** pooled synthetic memories not yet "learned". */
  remaining: number;
  onTeach: () => void;
  onReplay: () => void;
  /** which menu is open — owned by the parent so shortcuts and Escape can reach it. */
  menu: "visuals" | "more" | null;
  onMenu: (menu: "visuals" | "more" | null) => void;
  className?: string;
}

/**
 * The control dock — one compact glass capsule. Five things are always a tap
 * away (motion, camera, labels, activity, visuals); everything else lives in
 * the overflow menu so the brain keeps the page.
 */
export function AtlasDock(props: AtlasDockProps) {
  const { menu, onMenu, visuals, onVisuals } = props;
  const container = useRef<HTMLDivElement>(null);
  const visualsButton = useRef<HTMLButtonElement>(null);
  const moreButton = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const wasOpen = useRef<"visuals" | "more" | null>(null);

  // close on an outside press; return focus to the trigger when a menu closes
  useEffect(() => {
    if (menu) {
      const onPress = (e: PointerEvent) => {
        if (!container.current?.contains(e.target as Node)) onMenu(null);
      };
      document.addEventListener("pointerdown", onPress);
      panel.current?.querySelector<HTMLElement>("button:not([disabled])")?.focus({ preventScroll: true });
      wasOpen.current = menu;
      return () => document.removeEventListener("pointerdown", onPress);
    }
    if (wasOpen.current && container.current?.contains(document.activeElement)) {
      (wasOpen.current === "visuals" ? visualsButton : moreButton).current?.focus({ preventScroll: true });
    }
    wasOpen.current = null;
  }, [menu, onMenu]);

  const motionLabel = props.motion ? "Pause motion" : "Resume motion";
  const feed = props.view === "timeline" ? "Growth log" : "Activity feed";

  return (
    <div ref={container} className={cn("relative", props.className)}>
      <AnimatePresence>
        {menu && (
          <motion.div
            key={menu}
            ref={panel}
            id={menuId}
            role="dialog"
            aria-label={menu === "visuals" ? "Visual settings" : "More controls"}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.stopPropagation();
                onMenu(null);
              }
            }}
            // denser than the usual glass: this text sits directly over the brain
            className="absolute bottom-[calc(100%+10px)] left-0 z-30 w-[268px] max-w-[calc(100vw-7.5rem)] origin-bottom-left rounded-[var(--radius-lg)] border border-white/[0.12] bg-[rgba(14,9,15,0.88)] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.1),0_26px_56px_-28px_rgba(0,0,0,0.95)] backdrop-blur-2xl"
          >
            {menu === "visuals" ? (
              <>
                <p className="eyebrow px-2 pb-1.5 pt-1">Visual settings</p>
                <Switch
                  label="Auto-orbit"
                  hint={props.motion ? "A slow sway around the profile view" : "Resumes when motion is resumed"}
                  checked={visuals.orbit}
                  onChange={() => onVisuals({ orbit: !visuals.orbit })}
                />
                <Switch
                  label="Pathways"
                  hint="Ambient associations between memories"
                  checked={visuals.pathways}
                  onChange={() => onVisuals({ pathways: !visuals.pathways })}
                />
                <Segmented
                  label="Glow"
                  value={visuals.glow}
                  onChange={(glow) => onVisuals({ glow })}
                  options={[
                    { key: "soft", label: "Soft" },
                    { key: "balanced", label: "Balanced" },
                    { key: "vivid", label: "Vivid" },
                  ]}
                />
                <Segmented
                  label="Backdrop"
                  value={visuals.backdrop}
                  onChange={(backdrop) => onVisuals({ backdrop })}
                  options={[
                    { key: "light", label: "Light" },
                    { key: "balanced", label: "Balanced" },
                    { key: "deep", label: "Deep" },
                  ]}
                />
                <div className="mt-1 flex justify-end border-t border-white/[0.06] px-2 pt-2">
                  <button
                    type="button"
                    onClick={() => onVisuals(DEFAULT_VISUALS)}
                    className="rounded-md px-1.5 py-1 text-[11px] text-ink-faint transition-colors hover:text-ink"
                  >
                    Reset to defaults
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="eyebrow px-2 pb-1.5 pt-1">More</p>
                <Switch
                  label="Domain list"
                  hint="All seven domains with their sizes"
                  checked={props.domains}
                  onChange={props.onDomains}
                />
                <div className="my-1 border-t border-white/[0.06]" />
                <p className="flex items-center gap-1.5 px-2 pb-0.5 pt-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-amber">
                  <FlaskConical className="h-3 w-3" />
                  Simulation
                </p>
                <Switch
                  label="Simulated activity"
                  hint="Synthetic learning, linking and reinforcement"
                  checked={props.simulating}
                  disabled={props.view !== "brain"}
                  onChange={props.onSimulating}
                />
                <MenuAction
                  icon={Plus}
                  label="Learn a memory now"
                  hint={props.remaining ? `${props.remaining} synthetic memories left in the pool` : "The synthetic pool is spent"}
                  disabled={props.view !== "brain" || props.remaining === 0}
                  onClick={props.onTeach}
                />
                <MenuAction
                  icon={RotateCcw}
                  label="Replay assembly"
                  hint="Watch the brain form again"
                  onClick={() => {
                    props.onReplay();
                    onMenu(null);
                  }}
                />
                <div className="mt-1 border-t border-white/[0.06] px-2 pb-1 pt-2">
                  <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint">Keyboard</p>
                  <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-2.5 gap-y-1 text-[10px] text-ink-muted">
                    {[
                      ["Space", "Pause / resume motion"],
                      ["R", "Reset view"],
                      ["L · A · D", "Labels · activity · domains"],
                      ["← → ↑ ↓", "Orbit"],
                      ["+ −", "Zoom"],
                      ["Esc", "Step back"],
                    ].map(([keys, what]) => (
                      <div key={keys} className="contents">
                        <dt className="font-mono text-ink-faint">{keys}</dt>
                        <dd>{what}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div
        role="toolbar"
        aria-label="Atlas controls"
        className="flex items-center gap-0.5 rounded-full border border-white/[0.09] bg-[rgba(12,8,13,0.5)] p-1 max-[420px]:gap-0 shadow-[inset_0_1px_0_rgba(255,255,255,0.07),0_18px_40px_-24px_rgba(0,0,0,0.95)] backdrop-blur-xl"
      >
        <DockButton
          icon={props.motion ? Pause : Play}
          label={motionLabel}
          hint={props.heldForReducedMotion ? "Held still for your system's reduced-motion setting" : undefined}
          shortcut="Space"
          pressed={!props.motion}
          tipAlign="start"
          quietTip={Boolean(menu)}
          onClick={props.onMotion}
        />
        <DockButton icon={Focus} label="Reset view" shortcut="R" quietTip={Boolean(menu)} onClick={props.onReset} />
        <Divider />
        <DockButton
          icon={Tag}
          label="Domain labels"
          shortcut="L"
          active={props.labels}
          pressed={props.labels}
          quietTip={Boolean(menu)}
          onClick={props.onLabels}
        />
        <DockButton
          icon={Activity}
          label={feed}
          hint={props.view === "brain" ? "Simulated — not real memory activity" : undefined}
          shortcut="A"
          active={props.activity}
          pressed={props.activity}
          quietTip={Boolean(menu)}
          onClick={props.onActivity}
        />
        <DockButton
          buttonRef={visualsButton}
          icon={SlidersHorizontal}
          label="Visual settings"
          active={menu === "visuals"}
          expanded={menu === "visuals"}
          controls={menuId}
          quietTip={Boolean(menu)}
          onClick={() => onMenu(menu === "visuals" ? null : "visuals")}
        />
        <Divider />
        <DockButton
          buttonRef={moreButton}
          icon={Ellipsis}
          label="More controls"
          active={menu === "more" || props.domains}
          expanded={menu === "more"}
          controls={menuId}
          quietTip={Boolean(menu)}
          onClick={() => onMenu(menu === "more" ? null : "more")}
        />
      </div>
    </div>
  );
}
