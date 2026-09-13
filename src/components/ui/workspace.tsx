"use client";

import { type ComponentType, type ReactNode, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, X } from "lucide-react";
import { cn } from "@/lib/utils";

export function SectionHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">{title}</p>{description && <p className="mt-1 text-xs text-ink-faint">{description}</p>}</div>{action}</div>;
}

export type FilterItem<T extends string> = { key: T; label: string; count?: number };
export function FilterTabs<T extends string>({ items, value, onChange, layoutId }: { items: FilterItem<T>[]; value: T; onChange: (value: T) => void; layoutId: string }) {
  return <div className="scroll-area flex gap-1 overflow-x-auto rounded-full border border-white/[0.06] bg-white/[0.02] p-1">{items.map((item) => { const active = item.key === value; return <button key={item.key} type="button" onClick={() => onChange(item.key)} className={cn("relative shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-colors", active ? "text-ink" : "text-ink-faint hover:text-ink-muted")}>{active && <motion.span layoutId={layoutId} className="absolute inset-0 rounded-full bg-white/10" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}<span className="relative">{item.label}{item.count != null && <span className="ml-1.5 font-mono text-[10px] text-ink-faint">{item.count}</span>}</span></button>; })}</div>;
}

export function EmptyState({ icon: Icon, title, description, action, className }: { icon: ComponentType<{ className?: string }>; title: string; description: string; action?: ReactNode; className?: string }) {
  return <div className={cn("flex flex-col items-center justify-center px-4 py-10 text-center", className)}><span className="grid h-10 w-10 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.03]"><Icon className="h-4 w-4 text-ink-faint" /></span><p className="mt-3 text-sm font-medium text-ink-muted">{title}</p><p className="mt-1 max-w-xs text-xs leading-relaxed text-ink-faint">{description}</p>{action && <div className="mt-4">{action}</div>}</div>;
}

const BADGE = { green: "border-green/20 bg-green/10 text-green", cyan: "border-cyan-bright/20 bg-cyan-bright/10 text-cyan-bright", amber: "border-amber/20 bg-amber/10 text-amber", rose: "border-rose/20 bg-rose/10 text-rose", violet: "border-violet-bright/20 bg-violet-bright/10 text-violet-bright", faint: "border-white/[0.07] bg-white/[0.03] text-ink-faint" } as const;
export function StatusBadge({ label, tone = "faint" }: { label: string; tone?: keyof typeof BADGE }) { return <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium", BADGE[tone])}>{label}</span>; }

export function ContextAction({ icon: Icon, title, description, disabled, onClick }: { icon: ComponentType<{ className?: string }>; title: string; description?: string; disabled?: boolean; onClick?: () => void }) {
  return <button type="button" disabled={disabled} onClick={onClick} className="group flex w-full items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 text-left transition-colors hover:border-white/15 hover:bg-white/[0.045] disabled:cursor-not-allowed disabled:opacity-45"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-white/[0.05] text-ink-muted"><Icon className="h-3.5 w-3.5" /></span><span className="min-w-0 flex-1"><span className="block text-xs font-medium text-ink">{title}</span>{description && <span className="mt-0.5 block text-[10px] leading-relaxed text-ink-faint">{description}</span>}</span><ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></button>;
}

export function DetailDrawer({ open, onClose, eyebrow, title, children, footer }: { open: boolean; onClose: () => void; eyebrow?: string; title: string; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => { if (!open) return; const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose(); window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [open, onClose]);
  return <AnimatePresence>{open && <><motion.button type="button" aria-label="Close detail panel" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="fixed inset-0 z-40 cursor-default bg-black/55 backdrop-blur-sm" /><motion.aside initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 320, damping: 34 }} role="dialog" aria-modal="true" aria-label={title} className="glass-strong scroll-area fixed inset-y-0 right-0 z-50 flex w-full max-w-[30rem] flex-col overflow-y-auto"><div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-white/[0.06] bg-base/75 px-6 py-5 backdrop-blur-xl"><div className="min-w-0">{eyebrow && <p className="eyebrow text-wine-bright/80">{eyebrow}</p>}<h2 className="mt-1 truncate text-xl font-semibold tracking-tight text-ink">{title}</h2></div><button type="button" onClick={onClose} className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/[0.06] text-ink-muted hover:text-ink" aria-label="Close"><X className="h-4 w-4" /></button></div><div className="flex-1 p-6">{children}</div>{footer && <div className="sticky bottom-0 border-t border-white/[0.06] bg-base/80 p-4 backdrop-blur-xl">{footer}</div>}</motion.aside></>}</AnimatePresence>;
}
