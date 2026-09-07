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
} from "react";
import {
  DemoCommandCore,
  applyCommandEvent,
  commandPresenceEvent,
  commandPresenceIntent,
  isTerminal,
  markCancelRequested,
  matchFixture,
  type CommandContext,
  type CommandCore,
  type CommandPresenceIntent,
  type CommandTask,
} from "@/lib/command";
import { RealCommandCore, runCoreSelfTest } from "@/lib/command/core";
import { useConversation } from "@/components/conversation/conversation-provider";
import { usePresence } from "@/components/presence/presence-engine";

/**
 * The Command System store.
 *
 * Owns the set of command tasks, the currently-surfaced task, and the command
 * history. It routes plain conversational input to the real conversation
 * backend (kept honest, no faking) and recognised commands through the
 * {@link DemoCommandCore} lifecycle. It also translates command status into
 * *semantic* presence — emitting `command.*` events and publishing a
 * Director-facing {@link CommandPresenceIntent} — without ever choosing a
 * scenario or pose (the Presence Director owns that).
 */

interface CommandStoreValue {
  /** All tasks, oldest first. */
  tasks: CommandTask[];
  /** The task currently shown in the command console, if any. */
  activeTask: CommandTask | null;
  /** Terminal tasks, newest first. */
  history: CommandTask[];
  historyOpen: boolean;
  setHistoryOpen: (open: boolean) => void;

  /**
   * Submit user input. Plain conversation goes to the real backend; recognised
   * commands enter the lifecycle. `forceCommand` runs it as a command even if
   * it doesn't match a known template (yielding an honest capability boundary).
   * Returns true if it was handled as a command.
   */
  submit: (
    input: string,
    opts?: { forceCommand?: boolean; context?: CommandContext },
  ) => boolean;

  run: (taskId: string) => void;
  approve: (taskId: string) => void;
  deny: (taskId: string) => void;
  cancel: (taskId: string) => void;
  resume: (taskId: string) => void;
  retry: (taskId: string) => void;
  /** Drop a task that is still in review. */
  discard: (taskId: string) => void;
  /** Close the active console without discarding the task (keeps it in history). */
  dismissActive: () => void;
  /** Re-open a task from history into the console. */
  reopen: (taskId: string) => void;

  /** Director-facing semantic intent for the active task. */
  presenceIntent: CommandPresenceIntent;

  /** Prior submitted inputs (oldest→newest) for command recall. */
  recentInputs: string[];
}

const CommandStore = createContext<CommandStoreValue | null>(null);

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `task-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function CommandProvider({ children }: { children: ReactNode }) {
  const conversation = useConversation();
  const { emit } = usePresence();

  // Two cores behind the one frozen contract: the fixture-driven demo core and
  // the REAL Cognitive Core. Each owns its own taskIds; an ownership map routes
  // follow-up actions (run/cancel/…) back to the core that created the task.
  const demoRef = useRef<DemoCommandCore | null>(null);
  if (!demoRef.current) demoRef.current = new DemoCommandCore();
  const realRef = useRef<RealCommandCore | null>(null);
  if (!realRef.current) realRef.current = new RealCommandCore();
  const ownerRef = useRef<Map<string, CommandCore>>(new Map());

  const [tasks, setTasks] = useState<Map<string, CommandTask>>(new Map());
  const [order, setOrder] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [recentInputs, setRecentInputs] = useState<string[]>([]);

  // Fold a lifecycle event into the reducer + ordering (shared by both cores).
  const foldEvent = useCallback((event: Parameters<Parameters<CommandCore["subscribe"]>[0]>[0]) => {
    setTasks((prev) => {
      const current = prev.get(event.taskId);
      const nextTask = applyCommandEvent(current, event);
      if (!nextTask || nextTask === current) return prev;
      const next = new Map(prev);
      next.set(event.taskId, nextTask);
      return next;
    });
    if (event.type === "task.created") {
      setOrder((prev) => (prev.includes(event.taskId) ? prev : [...prev, event.taskId]));
    }
  }, []);

  // Subscribe the store to BOTH cores; restore durable real-task history once.
  useEffect(() => {
    const demo = demoRef.current!;
    const real = realRef.current!;
    const unsubDemo = demo.subscribe(foldEvent);
    const unsubReal = real.subscribe(foldEvent);
    // Rebuild persisted real tasks from the authoritative backend so history
    // survives reload without depending on localStorage. Async: the backend is
    // the source of truth.
    let cancelled = false;
    void real.restore().then((events) => {
      if (cancelled) return;
      for (const event of events) {
        ownerRef.current.set(event.taskId, real);
        foldEvent(event);
        // Surface a task restored still waiting for approval so the user can
        // act on it (approve/deny) after a reload, rather than it being buried.
        if (event.type === "approval.requested") setActiveId(event.taskId);
      }
    });
    return () => {
      cancelled = true;
      unsubDemo();
      unsubReal();
      demo.dispose?.();
      real.dispose?.();
      demoRef.current = null;
      realRef.current = null;
    };
  }, [foldEvent]);

  const orderedTasks = useMemo(
    () => order.map((id) => tasks.get(id)).filter((t): t is CommandTask => !!t),
    [order, tasks],
  );

  const activeTask = activeId ? tasks.get(activeId) ?? null : null;

  const history = useMemo(
    () => orderedTasks.filter((t) => isTerminal(t.status)).slice().reverse(),
    [orderedTasks],
  );

  /* ---- presence: react to the active task's status transitions ----------- */
  const lastPresenceStatus = useRef<string | null>(null);
  useEffect(() => {
    const status = activeTask?.status ?? null;
    if (status === lastPresenceStatus.current) return;
    lastPresenceStatus.current = status;
    if (!status) return;
    const evt = commandPresenceEvent(status);
    if (evt) emit({ type: evt });
  }, [activeTask?.status, emit]);

  const presenceIntent = useMemo(
    () => commandPresenceIntent(activeTask?.status ?? "draft"),
    [activeTask?.status],
  );

  /* ---- actions ----------------------------------------------------------- */
  const submit = useCallback<CommandStoreValue["submit"]>(
    (input, opts) => {
      const text = input.trim();
      if (!text) return false;
      setRecentInputs((prev) => (prev[prev.length - 1] === text ? prev : [...prev, text].slice(-40)));

      // Priority: a REAL Cognitive-Core intent wins; else a demo fixture; else
      // plain conversation (unchanged, real backend). Real and simulated never
      // mix — each task carries its source, surfaced in the UI.
      const realIntent = RealCommandCore.matches(text);
      const core: CommandCore | null = realIntent
        ? realRef.current
        : opts?.forceCommand || matchFixture(text) !== null
          ? demoRef.current
          : null;

      if (!core) {
        conversation.send(text);
        return false;
      }
      const taskId = makeId();
      ownerRef.current.set(taskId, core);
      setActiveId(taskId);
      core.dispatch({ type: "submit", taskId, input: text, context: opts?.context });
      return true;
    },
    [conversation],
  );

  // Route a follow-up action back to the core that owns the task.
  const ownerOf = useCallback((taskId: string): CommandCore | null => {
    return ownerRef.current.get(taskId) ?? demoRef.current;
  }, []);

  const run = useCallback((taskId: string) => {
    ownerOf(taskId)?.dispatch({ type: "run", taskId });
  }, [ownerOf]);
  const approve = useCallback((taskId: string) => {
    ownerOf(taskId)?.dispatch({ type: "approve", taskId });
  }, [ownerOf]);
  const deny = useCallback((taskId: string) => {
    ownerOf(taskId)?.dispatch({ type: "deny", taskId });
  }, [ownerOf]);
  const cancel = useCallback((taskId: string) => {
    setTasks((prev) => {
      const t = prev.get(taskId);
      if (!t) return prev;
      const next = new Map(prev);
      next.set(taskId, markCancelRequested(t));
      return next;
    });
    ownerOf(taskId)?.dispatch({ type: "cancel", taskId });
  }, [ownerOf]);
  const resume = useCallback((taskId: string) => {
    ownerOf(taskId)?.dispatch({ type: "resume", taskId });
  }, [ownerOf]);
  const retry = useCallback((taskId: string) => {
    ownerOf(taskId)?.dispatch({ type: "retry", taskId });
  }, [ownerOf]);
  const discard = useCallback((taskId: string) => {
    ownerOf(taskId)?.dispatch({ type: "discard", taskId });
    ownerRef.current.delete(taskId);
    setActiveId((cur) => (cur === taskId ? null : cur));
    setOrder((prev) => prev.filter((id) => id !== taskId));
    setTasks((prev) => {
      if (!prev.has(taskId)) return prev;
      const next = new Map(prev);
      next.delete(taskId);
      return next;
    });
  }, [ownerOf]);
  const dismissActive = useCallback(() => setActiveId(null), []);
  const reopen = useCallback((taskId: string) => {
    setActiveId(taskId);
    setHistoryOpen(false);
  }, []);

  /* ---- dev-only harness (parity with __lilithPresence) ------------------- */
  useEffect(() => {
    if (process.env.NODE_ENV === "production" || typeof window === "undefined") return;
    const samples: Record<string, string> = {
      "aws-cost-compare": "check aws cost and compare with last month",
      "inbox-triage": "summarise my inbox",
      "send-followups": "send follow-up emails to the team",
      "restart-worker": "restart the hermes worker",
      "delete-files": "delete these files",
      "buy-something": "buy this now",
    };
    (window as unknown as Record<string, unknown>).__lilithCommand = {
      launch: (fixtureId: keyof typeof samples) => submit(samples[fixtureId] ?? String(fixtureId), { forceCommand: true }),
      samples,
      list: () => orderedTasks,
    };
    (window as unknown as Record<string, unknown>).__lilithCore = {
      // Real read-only task via the Cognitive Core.
      run: () => submit("system health summary"),
      // Deterministic lifecycle self-test (success/cancel/fail/malformed/partial/retry/restore).
      selfTest: () => runCoreSelfTest(),
    };
  }, [submit, orderedTasks]);

  const value = useMemo<CommandStoreValue>(
    () => ({
      tasks: orderedTasks,
      activeTask,
      history,
      historyOpen,
      setHistoryOpen,
      submit,
      run,
      approve,
      deny,
      cancel,
      resume,
      retry,
      discard,
      dismissActive,
      reopen,
      presenceIntent,
      recentInputs,
    }),
    [orderedTasks, activeTask, history, historyOpen, submit, run, approve, deny, cancel, resume, retry, discard, dismissActive, reopen, presenceIntent, recentInputs],
  );

  return <CommandStore.Provider value={value}>{children}</CommandStore.Provider>;
}

export function useCommand() {
  const ctx = useContext(CommandStore);
  if (!ctx) throw new Error("useCommand must be used within a CommandProvider");
  return ctx;
}
