"use client";

import { useEffect, useState } from "react";
import { getMeetingsData } from "@/lib/meetings/client";
import type { MeetingsData } from "@/lib/meetings/types";

export function useMeetings() {
  const [data, setData] = useState<MeetingsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    getMeetingsData(ac.signal)
      .then((d) => setData(d))
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, []);

  return { data, loading };
}
