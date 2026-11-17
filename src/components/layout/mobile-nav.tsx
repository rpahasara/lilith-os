"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { isNavActive, nav } from "./nav";
import { cn } from "@/lib/utils";
import { user } from "@/lib/data";
import { FoxMark } from "@/components/ui/fox-mark";
import { useGlobalCommand } from "@/components/command/global-command";
import { DURATION, EASE_OUT, fade, spring } from "@/lib/motion";

/*
 * Mobile navigation (below md, 768px), where the 88px rail is hidden.
 *
 * The fox in the compact header is the menu. It opens a floating glass sheet
 * that slides in from the left over the current workspace; the sheet's own top
 * row puts a fox in the same spot, so the fox opens and closes it. The page
 * underneath stays mounted (it is only made inert and stops scrolling), so the
 * conversation, presence and command providers never remount.
 *
 * One source of truth: the destinations are `nav` and the current one is
 * `isNavActive`, exactly as the desktop rail. No route state of its own: the
 * sheet closes whenever the path changes (a link, Back, Forward), on Escape,
 * on the backdrop, on its close control, when Lilith's panel opens, and when
 * the viewport grows into the rail's range.
 */

export const MOBILE_NAV_ID = "mobile-nav";
/** The rail's breakpoint (Tailwind md). The sheet only exists below it. */
export const MOBILE_NAV_QUERY = "(max-width: 47.99rem)";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';
const SHELL = "[data-shell-root]";

/** The fox tile, shared by the header button and the sheet so they line up. */
function FoxTile() {
  return (
    <>
      <span className="absolute inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(255,255,255,0.12),transparent_48%)]" />
      <FoxMark className="relative h-7 w-7 drop-shadow-[0_0_10px_rgba(225,132,157,0.4)]" />
    </>
  );
}

const TILE =
  "glass relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-lg shadow-[0_12px_30px_-14px_rgba(201,84,115,0.8)]";

export function MobileNav() {
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const { open: commandOpen } = useGlobalCommand();

  useEffect(() => setMounted(true), []);
  const close = useCallback(() => setOpen(false), []);

  // Any navigation closes it: a link here, Back/Forward, or anything else.
  const [shownPath, setShownPath] = useState(pathname);
  if (pathname !== shownPath) {
    setShownPath(pathname);
    if (open) setOpen(false);
  }

  // Lilith's panel takes over the screen; never leave both open.
  useEffect(() => {
    if (commandOpen) setOpen(false);
  }, [commandOpen]);

  // Growing into the rail's range (rotation, resize) retires the sheet.
  useEffect(() => {
    if (!open) return;
    const mq = window.matchMedia(MOBILE_NAV_QUERY);
    const onChange = () => { if (!mq.matches) setOpen(false); };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [open]);

  // Modal while open: the shell behind is inert and does not scroll, Tab stays
  // in the sheet, Escape closes, and focus goes back to the fox afterwards.
  useEffect(() => {
    if (!open) return;
    const shell = document.querySelector<HTMLElement>(SHELL);
    const main = document.getElementById("main");
    const overflow = main?.style.overflow ?? "";
    if (shell) shell.inert = true;
    if (main) main.style.overflow = "hidden";
    const settle = requestAnimationFrame(() => {
      const target = sheet.current?.querySelector<HTMLElement>('[aria-current="page"]') ?? sheet.current?.querySelector<HTMLElement>(FOCUSABLE);
      target?.focus({ preventScroll: true });
    });
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key !== "Tab" || !sheet.current) return;
      const items = [...sheet.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (!sheet.current.contains(active)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(settle);
      document.removeEventListener("keydown", onKey);
      if (shell) shell.inert = false;
      if (main) main.style.overflow = overflow;
      // Lilith's panel manages its own focus; otherwise return to the fox, or
      // to the page if the fox is gone (the viewport grew into the rail).
      if (document.querySelector("[data-global-command-panel]")) return;
      if (trigger.current && trigger.current.offsetParent !== null) trigger.current.focus();
      else main?.focus({ preventScroll: true });
    };
  }, [open]);

  return (
    <>
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={MOBILE_NAV_ID}
        data-mobile-nav-trigger=""
        className={cn(TILE, "md:hidden")}
      >
        <FoxTile />
      </button>

      {mounted &&
        createPortal(
          <AnimatePresence>
            {open && (
              <div key="mobile-nav" className="md:hidden">
                <motion.div
                  aria-hidden
                  onClick={close}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={fade}
                  data-mobile-nav-backdrop=""
                  className="fixed inset-0 z-50 bg-[radial-gradient(120%_80%_at_0%_0%,rgba(74,18,36,0.38),transparent_60%),rgba(5,3,6,0.55)]"
                />
                <motion.div
                  ref={sheet}
                  id={MOBILE_NAV_ID}
                  role="dialog"
                  aria-modal="true"
                  aria-label="Navigation"
                  data-mobile-nav=""
                  initial={{ x: "-108%", opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  exit={{ x: "-108%", opacity: 0, transition: { duration: DURATION.fast, ease: EASE_OUT } }}
                  transition={spring}
                  className="glass-strong fixed bottom-[max(0.5rem,env(safe-area-inset-bottom))] left-[max(0.5rem,env(safe-area-inset-left))] top-[max(0.5rem,env(safe-area-inset-top))] z-50 flex w-[min(18.5rem,calc(100vw-3.5rem))] flex-col overflow-hidden rounded-[1.25rem] shadow-[0_40px_120px_-40px_rgba(0,0,0,0.95),0_24px_80px_-48px_rgba(201,84,115,0.55)]"
                >
                  <span className="pointer-events-none absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-pearl/40 to-transparent" />

                  {/* top row: the fox sits where the header's fox is, and closes */}
                  <div className="flex h-12 shrink-0 items-center gap-3 px-2">
                    <button type="button" onClick={close} aria-label="Close navigation" className={TILE}>
                      <FoxTile />
                    </button>
                    <span className="flex-1 font-mono text-micro uppercase tracking-[0.24em] text-ink-muted">Lilith</span>
                    <button
                      type="button"
                      onClick={close}
                      aria-label="Close navigation"
                      className="grid h-10 w-10 place-items-center rounded-full text-ink-faint transition-colors hover:bg-white/[0.04] hover:text-ink"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  <p className="eyebrow mt-5 px-5">Workspaces</p>
                  <nav aria-label="Primary workspaces" className="scroll-area mt-2 min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 pb-2">
                    <ul className="space-y-1">
                      {nav.map((item, i) => {
                        const active = isNavActive(pathname, item.href);
                        const Icon = item.icon;
                        return (
                          <motion.li
                            key={item.href}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: DURATION.base, ease: EASE_OUT, delay: 0.04 + i * 0.025 }}
                          >
                            <Link
                              href={item.href}
                              onClick={close}
                              aria-current={active ? "page" : undefined}
                              className="group relative flex min-h-12 items-center gap-3 rounded-xl px-3 py-1.5"
                            >
                              {active && (
                                <>
                                  <span className="glass absolute inset-0 rounded-xl shadow-[0_12px_28px_-18px_rgba(201,84,115,0.9)] ring-1 ring-wine/20" />
                                  <span aria-hidden className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-wine-bright shadow-[0_0_10px_rgba(225,132,157,0.7)]" />
                                </>
                              )}
                              <span
                                className={cn(
                                  "relative grid h-9 w-9 shrink-0 place-items-center rounded-xl transition-colors",
                                  active ? "text-wine-bright" : "text-ink-faint group-hover:text-ink",
                                )}
                              >
                                <Icon className="h-[18px] w-[18px]" strokeWidth={active ? 2.2 : 1.8} />
                              </span>
                              <span
                                className={cn(
                                  "relative flex-1 text-sm transition-colors",
                                  active ? "font-medium text-ink" : "text-ink-muted group-hover:text-ink",
                                )}
                              >
                                {item.label}
                              </span>
                            </Link>
                          </motion.li>
                        );
                      })}
                    </ul>
                  </nav>

                  {/* owner, display only — the same identity the rail shows */}
                  <div className="flex shrink-0 items-center gap-3 border-t border-white/[0.06] px-4 py-3">
                    <span aria-hidden className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-wine-deep to-wine-bright text-xs font-semibold text-white ring-1 ring-white/15">
                      {user.name.charAt(0)}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-medium text-ink">{user.name}</span>
                      <span className="block font-mono text-micro text-ink-faint">{user.plan}</span>
                    </span>
                  </div>
                </motion.div>
              </div>
            )}
          </AnimatePresence>,
          document.body,
        )}
    </>
  );
}
