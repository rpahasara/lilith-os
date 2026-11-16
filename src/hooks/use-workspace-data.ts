"use client";

import { useCallback, useEffect, useState } from "react";
import { isUnavailable, type Loaded, type Unavailable } from "@/lib/data-mode";

interface WorkspaceState<T> {
  /** The workspace's data: live, or sample data when that was opted into. */
  data: T | null;
  /** Set when the backend did not answer and nothing may be shown. */
  unavailable: Unavailable | null;
  loading: boolean;
}

/**
 * Load a workspace once on mount. Exactly one of `data` / `unavailable` is set
 * when loading finishes; `retry` runs the load again.
 *
 * `load` must be a stable function (the workspace clients are module-level).
 */
export function useWorkspaceData<T>(load: (signal: AbortSignal) => Promise<Loaded<T>>) {
  const [state, setState] = useState<WorkspaceState<T>>({
    data: null,
    unavailable: null,
    loading: true,
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ac = new AbortController();
    setState((s) => ({ ...s, loading: true }));
    load(ac.signal).then((result) => {
      if (ac.signal.aborted) return;
      setState(
        isUnavailable(result)
          ? { data: null, unavailable: result, loading: false }
          : { data: result, unavailable: null, loading: false },
      );
    });
    return () => ac.abort();
  }, [load, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}
