"use client";

import { useEffect, useState } from "react";
import { getAutomationsData } from "@/lib/automations/client";
import type { AutomationsData } from "@/lib/automations/types";

export function useAutomations() {
  const [data, setData] = useState<AutomationsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    getAutomationsData(ac.signal)
      .then((d) => setData(d))
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, []);

  return { data, loading };
}
