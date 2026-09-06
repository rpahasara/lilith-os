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
  type CommandPresenceIntent,
  type CommandTask,
} from "@/lib/command";
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

  const coreRef = useRef<DemoCommandCore | null>(null);
  if (!coreRef.current) coreRef.current = new DemoCommandCore();

  const [tasks, setTasks] = useState<Map<string, CommandTask>>(new Map());
  const [order, setOrder] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [recentInputs, setRecentInputs] = useState<string[]>([]);

  // Subscribe the store to the core's lifecycle events → reduce into tasks.
  useEffect(() => {
    const core = coreRef.current!;
    const unsub = core.subscribe((event) => {
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
    });
    return () => {
      unsub();
      core.dispose?.();
      coreRef.current = null;
    };
  }, []);

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
      const isCommand = opts?.forceCommand || matchFixture(text) !== null;
      if (!isCommand) {
        conversation.send(text);
        return false;
      }
      const taskId = makeId();
      setActiveId(taskId);
      coreRef.current!.dispatch({ type: "submit", taskId, input: text, context: opts?.context });
      return true;
    },
    [conversation],
  );

  const run = useCallback((taskId: string) => {
    coreRef.current!.dispatch({ type: "run", taskId });
  }, []);
  const approve = useCallback((taskId: string) => {
    coreRef.current!.dispatch({ type: "approve", taskId });
  }, []);
  const deny = useCallback((taskId: string) => {
    coreRef.current!.dispatch({ type: "deny", taskId });
  }, []);
  const cancel = useCallback((taskId: string) => {
    setTasks((prev) => {
      const t = prev.get(taskId);
      if (!t) return prev;
      const next = new Map(prev);
      next.set(taskId, markCancelRequested(t));
      return next;
    });
    coreRef.current!.dispatch({ type: "cancel", taskId });
  }, []);
  const resume = useCallback((taskId: string) => {
    coreRef.current!.dispatch({ type: "resume", taskId });
  }, []);
  const retry = useCallback((taskId: string) => {
    coreRef.current!.dispatch({ type: "retry", taskId });
  }, []);
  const discard = useCallback((taskId: string) => {
    coreRef.current!.dispatch({ type: "discard", taskId });
    setActiveId((cur) => (cur === taskId ? null : cur));
    setOrder((prev) => prev.filter((id) => id !== taskId));
    setTasks((prev) => {
      if (!prev.has(taskId)) return prev;
      const next = new Map(prev);
      next.delete(taskId);
      return next;
    });
  }, []);
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
