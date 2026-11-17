"use client";

import { type ComponentType, type ReactNode, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { DURATION, EASE_OUT, spring, springSnap } from "@/lib/motion";

export function SectionHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">{title}</p>{description && <p className="mt-1 text-xs text-ink-faint">{description}</p>}</div>{action}</div>;
}

export type FilterItem<T extends string> = { key: T; label: string; count?: number };
export function FilterTabs<T extends string>({ items, value, onChange, layoutId }: { items: FilterItem<T>[]; value: T; onChange: (value: T) => void; layoutId: string }) {
  return <div className="scroll-area flex gap-1 overflow-x-auto rounded-full border border-white/[0.06] bg-white/[0.02] p-1">{items.map((item) => { const active = item.key === value; return <button key={item.key} type="button" onClick={() => onChange(item.key)} className={cn("relative shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-colors", active ? "text-ink" : "text-ink-faint hover:text-ink-muted")}>{active && <motion.span layoutId={layoutId} className="absolute inset-0 rounded-full bg-white/10" transition={springSnap} />}<span className="relative">{item.label}{item.count != null && <span className="ml-1.5 font-mono text-micro text-ink-faint">{item.count}</span>}</span></button>; })}</div>;
}

export function EmptyState({ icon: Icon, title, description, action, className }: { icon: ComponentType<{ className?: string }>; title: string; description: string; action?: ReactNode; className?: string }) {
  return <div className={cn("flex flex-col items-center justify-center px-4 py-10 text-center", className)}><span className="grid h-10 w-10 place-items-center rounded-lg border border-white/[0.07] bg-white/[0.03]"><Icon className="h-4 w-4 text-ink-faint" /></span><p className="mt-3 text-sm font-medium text-ink-muted">{title}</p><p className="mt-1 max-w-xs text-xs leading-relaxed text-ink-faint">{description}</p>{action && <div className="mt-4">{action}</div>}</div>;
}

const BADGE = { green: "border-green/20 bg-green/10 text-green", cyan: "border-cyan-bright/20 bg-cyan-bright/10 text-cyan-bright", amber: "border-amber/20 bg-amber/10 text-amber", rose: "border-rose/20 bg-rose/10 text-rose", orchid: "border-orchid-bright/20 bg-orchid-bright/10 text-orchid-bright", faint: "border-white/[0.07] bg-white/[0.03] text-ink-faint" } as const;
export function StatusBadge({ label, tone = "faint" }: { label: string; tone?: keyof typeof BADGE }) { return <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-micro font-medium", BADGE[tone])}>{label}</span>; }

export function ContextAction({ icon: Icon, title, description, disabled, onClick }: { icon: ComponentType<{ className?: string }>; title: string; description?: string; disabled?: boolean; onClick?: () => void }) {
  return <button type="button" disabled={disabled} onClick={onClick} className="group flex w-full items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-3 text-left transition-colors hover:border-white/15 hover:bg-white/[0.045] disabled:cursor-not-allowed disabled:opacity-45"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-2xl bg-white/[0.05] text-ink-muted"><Icon className="h-3.5 w-3.5" /></span><span className="min-w-0 flex-1"><span className="block text-xs font-medium text-ink">{title}</span>{description && <span className="mt-0.5 block text-micro leading-relaxed text-ink-faint">{description}</span>}</span><ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></button>;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type Box = { top: number; left: number; width: number; height: number };

/** Where the drawer opens from: the control that opened it, if it is a row on the page. */
function originBox(el: Element | null): Box | null {
  if (!el || !(el instanceof HTMLElement) || el === document.body || !el.closest("main")) return null;
  const r = el.getBoundingClientRect();
  if (r.width < 40 || r.height < 24) return null;
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

/** The drawer's own box (it is `fixed inset-y-0 right-0 w-full max-w-[30rem]`). */
function drawerBox(): Box {
  const width = Math.min(window.innerWidth, 480);
  return { top: 0, left: window.innerWidth - width, width, height: window.innerHeight };
}

/**
 * The shared detail drawer. It is a modal dialog, so it behaves like one:
 * focus moves into it when it opens, Tab stays inside it, Escape closes it, and
 * focus returns to whatever opened it.
 *
 * Row to detail: when a row on the page opens it, a plate the shape of that
 * row grows into the drawer (and shrinks back into the row on close), so the
 * detail reads as the row opened up rather than a panel from nowhere. With
 * "reduce motion" on, or when there is no row to grow from, the drawer simply
 * fades in (no movement).
 */
export function DetailDrawer({ open, onClose, eyebrow, title, children, footer }: { open: boolean; onClose: () => void; eyebrow?: string; title: string; children: ReactNode; footer?: ReactNode }) {
  const panel = useRef<HTMLElement>(null);
  // callers usually pass an inline handler; keep the latest without re-running the effect
  const close = useRef(onClose);
  close.current = onClose;
  const reduce = useReducedMotion();
  // The opener is read the moment the drawer opens (before the dialog takes
  // focus), and again as it closes, so the plate meets the row where it is now.
  const opener = useRef<Element | null>(null);
  const [from, setFrom] = useState<Box | null>(null);
  const [back, setBack] = useState<Box | null>(null);
  const [wasOpen, setWasOpen] = useState(false);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      opener.current = typeof document === "undefined" ? null : document.activeElement;
      setFrom(typeof window === "undefined" ? null : originBox(opener.current));
    } else {
      setBack(typeof window === "undefined" ? null : originBox(opener.current));
    }
  }
  const morph = !reduce && from !== null;

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const raf = requestAnimationFrame(() =>
      panel.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus({ preventScroll: true }),
    );
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        close.current();
        return;
      }
      if (event.key !== "Tab" || !panel.current) return;
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const outside = !panel.current.contains(active);
      if (event.shiftKey && (active === first || outside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || outside)) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("keydown", onKey);
      opener?.focus?.({ preventScroll: true });
    };
  }, [open]);

  const target = typeof window === "undefined" ? null : drawerBox();
  const plateFrom = from && target ? { ...from, borderRadius: 16 } : null;
  const plateTo = target ? { ...target, borderRadius: 0 } : null;
  const plateBack = back ?? from;

  return <AnimatePresence>{open && <><motion.button key="scrim" type="button" tabIndex={-1} aria-label="Close detail panel" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="fixed inset-0 z-40 cursor-default bg-black/55 backdrop-blur-sm" />{morph && plateFrom && plateTo && <motion.div key="plate" aria-hidden data-drawer-plate initial={{ ...plateFrom, opacity: 1 }} animate={{ ...plateTo, opacity: [1, 1, 0], transition: { duration: DURATION.base + 0.06, ease: EASE_OUT, opacity: { duration: DURATION.base + 0.12, times: [0, 0.75, 1] } } }} exit={plateBack ? { ...plateBack, borderRadius: 16, opacity: [1, 1, 0], transition: { duration: DURATION.base, ease: EASE_OUT, opacity: { duration: DURATION.base, times: [0, 0.8, 1] } } } : { opacity: 0 }} className="pointer-events-none fixed z-50 border border-wine-bright/35 bg-[rgba(24,14,20,0.92)]" />}<motion.aside key="panel" ref={panel} {...(morph ? { initial: { opacity: 0 }, animate: { opacity: 1, transition: { duration: DURATION.fast, delay: DURATION.fast * 0.7 } }, exit: { opacity: 0, transition: { duration: DURATION.instant } } } : reduce ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } } : { initial: { x: "100%" }, animate: { x: 0 }, exit: { x: "100%" }, transition: spring })} role="dialog" aria-modal="true" aria-label={title} className="glass-strong scroll-area fixed inset-y-0 right-0 z-50 flex w-full max-w-[30rem] flex-col overflow-y-auto"><div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-white/[0.06] bg-base/75 px-6 py-5 backdrop-blur-xl"><div className="min-w-0">{eyebrow && <p className="eyebrow text-wine-bright/80">{eyebrow}</p>}<h2 className="mt-1 truncate text-xl font-semibold tracking-tight text-ink">{title}</h2></div><button type="button" data-autofocus onClick={onClose} className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/[0.06] text-ink-muted hover:text-ink" aria-label="Close"><X className="h-4 w-4" /></button></div><div className="flex-1 p-6">{children}</div>{footer && <div className="sticky bottom-0 border-t border-white/[0.06] bg-base/80 p-4 backdrop-blur-xl">{footer}</div>}</motion.aside></>}</AnimatePresence>;
}
