"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, History, X } from "lucide-react";
import { useConversation } from "@/components/conversation/conversation-provider";
import { ConversationAnnouncer, ConversationView } from "@/components/conversation/conversation-view";
import { useShellHealth } from "@/components/layout/shell-health-provider";
import { CommandInput } from "@/components/presence/command-input";
import { PresenceAnnouncer, PresenceMark, useShellPresence } from "@/components/presence/presence-mark";
import { PRESENCE_DETAIL, PRESENCE_LABEL, presenceShowsLabel } from "@/lib/presence/shell-presence";
import { InlineNotice, LoadingRegion, Skeleton } from "@/components/ui/feedback";
import {
  GLOBAL_INPUT_ID,
  GLOBAL_PANEL_ID,
  HERO_INPUT_ID,
  SURFACE_LINE,
  activationFor,
  canSend,
  hasUnseenReply,
  isCommandCenter,
  isCommandShortcut,
  latestReplyId,
  surfaceFor,
  surfaceState,
  type SurfaceState,
} from "@/lib/command/global-surface";
import { isRecordingActive } from "@/lib/conversation/recording";
import { fade, spring } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { CommandConsole } from "./command-console";
import { CommandHistory } from "./command-history";
import { useCommand } from "./command-provider";

/**
 * Lilith, from every page.
 *
 * A launcher in the top bar and a panel that opens over the current workspace.
 * It is a second window onto the one conversation and the one command store
 * that already live in the shell: the same `submit`, the same transcript, the
 * same backend session. Nothing is duplicated, so what is said here is there on
 * the Command Center, and the other way round.
 *
 * On the Command Center itself the hero is already that window, so the launcher
 * and Ctrl+Space focus the hero input and no panel opens.
 *
 * The panel does not drive the avatar: the Command Center owns the avatar's
 * reactions and voice, and picks an in-flight turn up when it is opened.
 *
 * Deliberately not here (owner decisions, 2026-11-16):
 *  - Voice. The panel is text-first; replies are spoken only on the Command
 *    Center. Nothing here plays audio.
 *  - Clearing. Clearing the transcript, starting a new conversation and
 *    forgetting stored information are three different operations with
 *    different Privacy and FORGET consequences; none is offered here until
 *    their semantics are defined.
 *  - Object context. A turn carries the page it was launched from and nothing
 *    else. Lilith is not told what is selected or shown on that page, and the
 *    panel does not suggest that she is.
 */

interface GlobalCommandValue {
  open: boolean;
  /** Click or shortcut: focus the hero input, or open / focus the panel. */
  activate: () => void;
  close: () => void;
  /** A reply arrived that has not been shown yet. */
  unseen: boolean;
  state: SurfaceState;
  launcherRef: RefObject<HTMLButtonElement | null>;
}

const GlobalCommandContext = createContext<GlobalCommandValue | null>(null);

export function useGlobalCommand(): GlobalCommandValue {
  const ctx = useContext(GlobalCommandContext);
  if (!ctx) throw new Error("useGlobalCommand must be used within a GlobalCommandProvider");
  return ctx;
}

function focusById(id: string) {
  const el = document.getElementById(id) as HTMLInputElement | null;
  el?.focus();
}

export function GlobalCommandProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { messages, hydrated, status, error, stopped } = useConversation();
  const { health } = useShellHealth();
  const [open, setOpen] = useState(false);
  const launcherRef = useRef<HTMLButtonElement | null>(null);
  const onHome = isCommandCenter(pathname);

  const state = surfaceState({
    hydrated,
    sending: status === "sending",
    error,
    stopped: !!stopped,
    health: health.state,
  });

  const close = useCallback(() => setOpen(false), []);
  const activate = useCallback(() => {
    const action = activationFor(pathname, open);
    if (action === "focus-hero") focusById(HERO_INPUT_ID);
    else if (action === "focus-panel") focusById(GLOBAL_INPUT_ID);
    else setOpen(true);
  }, [pathname, open]);

  // The Command Center is the full surface; a panel over it would be a second
  // copy of what is already on screen.
  useEffect(() => {
    if (onHome) setOpen(false);
  }, [onHome]);

  // Ctrl+Space, app-wide. On the Command Center the hero input owns it.
  useEffect(() => {
    if (onHome) return;
    function onKey(e: KeyboardEvent) {
      if (!isCommandShortcut(e)) return;
      e.preventDefault();
      activate();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onHome, activate]);

  // "Seen" tracking for the launcher's new-reply mark. Restored history is the
  // baseline; anything visible (panel open, or the Command Center) is seen.
  const [seenId, setSeenId] = useState<string | null | undefined>(undefined);
  const visible = open || onHome;
  useEffect(() => {
    if (!hydrated) return;
    const latest = latestReplyId(messages);
    setSeenId((prev) => (prev === undefined || visible ? latest : prev));
  }, [hydrated, messages, visible]);
  const unseen = hasUnseenReply(messages, seenId, visible);

  const value = useMemo(
    () => ({ open, activate, close, unseen, state, launcherRef }),
    [open, activate, close, unseen, state],
  );

  return (
    <GlobalCommandContext.Provider value={value}>
      {children}
      {/* Away from the Command Center (which mounts its own), replies are still
          announced to screen readers, whether or not the panel is open. */}
      {!onHome && <ConversationAnnouncer />}
    </GlobalCommandContext.Provider>
  );
}

/* ------------------------------------------------------------------ launcher */

/** The top-bar field. A button, not an input: typing happens in the surface it opens. */
export function GlobalCommandLauncher() {
  const pathname = usePathname();
  const { open, activate, unseen, launcherRef } = useGlobalCommand();
  const onHome = isCommandCenter(pathname);
  const presence = useShellPresence();
  const label = unseen ? "Lilith replied" : "Ask Lilith, or give a command…";
  const name = unseen ? "Lilith replied. Open the conversation" : "Ask Lilith";
  // On the Command Center it moves focus to the hero input; elsewhere it opens a dialog.
  const popup = onHome
    ? {}
    : ({ "aria-haspopup": "dialog", "aria-expanded": open, "aria-controls": GLOBAL_PANEL_ID } as const);

  return (
    <>
      <button
        ref={launcherRef}
        type="button"
        onClick={activate}
        aria-label={name}
        aria-description={PRESENCE_DETAIL[presence]}
        title={PRESENCE_DETAIL[presence]}
        aria-keyshortcuts="Control+Space"
        data-global-command-launcher=""
        data-presence-state={presence}
        {...popup}
        className="glass group relative hidden h-10 max-w-[460px] flex-1 items-center gap-3 overflow-hidden rounded-full px-4 text-left text-sm text-ink-muted transition-[border-color,box-shadow,color] hover:border-wine/30 hover:text-ink hover:shadow-[0_14px_40px_-22px_rgba(201,84,115,0.75)] md:flex"
      >
        <span className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-pearl/30 to-transparent" />
        <PresenceMark state={presence} />
        <span className={cn("flex-1 truncate", unseen && "text-ink")}>{label}</span>
        {unseen ? (
          <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-wine-bright shadow-[0_0_10px_rgba(225,132,157,0.9)]" />
        ) : presenceShowsLabel(presence) ? (
          // Words only for states that mean something to act on or wait for;
          // when everything is normal the mark alone says so.
          <span aria-hidden data-presence-label="" className="hidden shrink-0 font-mono text-micro uppercase tracking-[0.12em] text-ink-faint sm:block">
            {PRESENCE_LABEL[presence]}
          </span>
        ) : null}
        <kbd className="hidden items-center rounded-md border border-white/10 bg-black/15 px-1.5 py-0.5 font-mono text-micro text-ink-faint lg:flex">
          Ctrl Space
        </kbd>
      </button>

      {/* Narrow screens: the same action as a single control. */}
      <button
        type="button"
        onClick={activate}
        aria-label={name}
        aria-description={PRESENCE_DETAIL[presence]}
        title={PRESENCE_DETAIL[presence]}
        {...popup}
        className="glass relative grid h-10 w-10 shrink-0 place-items-center rounded-full md:hidden"
      >
        <PresenceMark state={presence} />
        {unseen && <span aria-hidden className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-wine-bright" />}
      </button>
      <PresenceAnnouncer state={presence} />
    </>
  );
}

/* --------------------------------------------------------------------- panel */

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** The conversation surface that opens over the current workspace. */
export function GlobalCommandPanel() {
  const pathname = usePathname();
  const { open, close, state, launcherRef } = useGlobalCommand();
  const { messages, status, error, stop, stopped, hydrated, recording } = useConversation();
  const { submit, activeTask, history, historyOpen, setHistoryOpen, recentInputs } = useCommand();
  const { health, refresh } = useShellHealth();
  const panel = useRef<HTMLDivElement | null>(null);
  const presence = useShellPresence();
  const [editFill, setEditFill] = useState<{ text: string; nonce: number } | undefined>();
  const onHome = isCommandCenter(pathname);

  const sending = status === "sending";
  const hasConversation = messages.length > 0 || !!error || !!stopped;
  const sendable = canSend({ hydrated, sending, error, stopped: !!stopped, health: health.state });
  const unavailable = health.state === "unconfigured";

  // A failed turn is the freshest evidence about the backend: measure again.
  useEffect(() => {
    if (error) refresh();
  }, [error, refresh]);

  // Modal focus: remember the opener, keep Tab inside, Escape closes, focus
  // returns to the launcher. The history drawer, when open, owns the keyboard.
  const historyOpenRef = useRef(historyOpen);
  historyOpenRef.current = historyOpen;
  useEffect(() => {
    if (!open) return;
    // Opened by the shortcut, nothing in particular had focus: return it to the launcher.
    const active = document.activeElement as HTMLElement | null;
    const opener = active && active !== document.body ? active : launcherRef.current;
    // The field takes focus itself. When it cannot (nothing can be sent), the
    // dialog does, so focus is never left behind on the page underneath.
    const settle = requestAnimationFrame(() => {
      if (!panel.current?.contains(document.activeElement)) panel.current?.focus();
    });
    function onKey(event: KeyboardEvent) {
      if (historyOpenRef.current) return;
      if (event.key === "Escape") {
        if (event.defaultPrevented) return; // the input used it (leaving recall)
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || !panel.current) return;
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (!panel.current.contains(active)) {
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
      (opener && document.contains(opener) ? opener : launcherRef.current)?.focus();
    };
  }, [open, close, launcherRef]);

  function handleSubmit(text: string) {
    // The command store decides: a recognised real intent enters the command
    // lifecycle, anything else is a conversational turn. Same path as the hero.
    submit(text, { context: { surface: surfaceFor(pathname) } });
  }

  return (
    <>
      <AnimatePresence>
        {open && (
          <>
            <motion.button
              type="button"
              tabIndex={-1}
              aria-label="Close Lilith"
              onClick={close}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={fade}
              className="fixed inset-0 z-40 cursor-default bg-black/45"
            />
            <div className="pointer-events-none fixed inset-x-0 top-3 z-50 flex justify-center px-3">
              <motion.div
                ref={panel}
                id={GLOBAL_PANEL_ID}
                role="dialog"
                aria-modal="true"
                aria-label="Lilith"
                tabIndex={-1}
                data-global-command-panel=""
                data-surface-state={state}
                initial={{ opacity: 0, y: -10, scale: 0.985 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.99, transition: fade }}
                transition={spring}
                style={{ transformOrigin: "top center" }}
                className="glass-strong pointer-events-auto relative flex max-h-[min(80dvh,720px)] outline-none w-full max-w-[680px] flex-col overflow-hidden rounded-2xl shadow-[0_40px_120px_-40px_rgba(0,0,0,0.95),0_24px_80px_-48px_rgba(201,84,115,0.55)]"
              >
                <span className="pointer-events-none absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-pearl/45 to-transparent" />

                {/* header: who this is, what is happening, and the way to the full surface */}
                <header className="flex items-center gap-3 px-5 pb-3 pt-4">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-white/[0.09] bg-black/20">
                    <PresenceMark state={presence} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-body font-semibold leading-tight tracking-[-0.01em] text-ink">Lilith</p>
                    <p
                      role="status"
                      aria-live="polite"
                      data-surface-line=""
                      className={cn(
                        "truncate text-caption leading-snug",
                        state === "error" ? "text-rose" : state === "unavailable" || state === "disconnected" ? "text-amber" : "text-ink-faint",
                      )}
                    >
                      {SURFACE_LINE[state]}
                    </p>
                  </div>
                  {history.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setHistoryOpen(true)}
                      className="flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-caption text-ink-faint transition-colors hover:bg-white/[0.05] hover:text-ink-muted"
                    >
                      <History className="h-3.5 w-3.5" /> History · {history.length}
                    </button>
                  )}
                  <Link
                    href="/"
                    onClick={close}
                    className="flex items-center gap-1 rounded-full px-2.5 py-1.5 text-caption text-ink-faint transition-colors hover:bg-white/[0.05] hover:text-ink-muted"
                  >
                    Command Center <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                  <button
                    type="button"
                    onClick={close}
                    aria-label="Close"
                    className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-faint transition-colors hover:bg-white/[0.06] hover:text-ink"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </header>

                {/* body: connection truth first, then the one conversation / the active command */}
                <div className="scroll-area flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-5 pb-1">
                  {unavailable && (
                    <InlineNotice
                      data-surface-notice="unavailable"
                      message="No backend is configured for this app, so Lilith cannot answer here."
                    />
                  )}
                  {health.state === "unreachable" && (
                    <InlineNotice
                      data-surface-notice="disconnected"
                      message="Lilith's backend did not answer the last check. A message may not get through."
                      onAction={refresh}
                      actionLabel="Check again"
                    />
                  )}
                  {isRecordingActive(recording) && (
                    <InlineNotice
                      data-surface-notice="recording"
                      message="This conversation is being recorded (started on the Command Center)."
                    />
                  )}

                  {!hydrated ? (
                    <LoadingRegion label="the conversation" className="space-y-2.5 py-2">
                      <Skeleton className="ml-auto h-9 w-2/5 rounded-lg" />
                      <Skeleton className="h-14 w-3/5 rounded-lg" />
                    </LoadingRegion>
                  ) : activeTask ? (
                    <div className="flex justify-center py-1">
                      <CommandConsole onEditRequest={(text) => setEditFill({ text, nonce: Date.now() })} />
                    </div>
                  ) : hasConversation ? (
                    <ConversationView className="max-h-none lg:max-h-none" />
                  ) : (
                    <p className="py-6 text-center text-body leading-relaxed text-ink-muted">
                      {unavailable
                        ? "Nothing can be sent until a backend is configured."
                        : "This is the same conversation as on the Command Center. Lilith does not see what is open on this page unless you tell her."}
                    </p>
                  )}
                </div>

                <div className="px-4 pb-4 pt-3">
                  <CommandInput
                    id={GLOBAL_INPUT_ID}
                    autoFocus
                    onSubmit={handleSubmit}
                    loading={sending}
                    onStop={stop}
                    historyItems={recentInputs}
                    fill={editFill}
                    disabled={!sendable && !sending}
                    disabledPlaceholder={unavailable ? "Unavailable — no backend is configured" : "Restoring the conversation…"}
                  />
                </div>
              </motion.div>
            </div>
          </>
        )}
      </AnimatePresence>

      {/* The Command Center mounts its own history drawer. */}
      {!onHome && <CommandHistory />}
    </>
  );
}
