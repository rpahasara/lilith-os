"use client";

import { useEffect, useState } from "react";
import { getMemoryData } from "@/lib/memory/client";
import type { MemoryData } from "@/lib/memory/types";

export function useMemory() {
  const [data, setData] = useState<MemoryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    getMemoryData(ac.signal)
      .then((d) => setData(d))
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, []);

  return { data, loading };
}
