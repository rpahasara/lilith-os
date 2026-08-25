"use client";

import { useEffect, useState } from "react";
import { getCareerData } from "@/lib/career/client";
import type { CareerData } from "@/lib/career/types";

export function useCareer() {
  const [data, setData] = useState<CareerData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    getCareerData(ac.signal)
      .then((d) => setData(d))
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, []);

  return { data, loading };
}
