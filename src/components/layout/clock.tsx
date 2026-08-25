"use client";

import { useEffect, useState } from "react";
import { formatClock } from "@/lib/utils";

/** Client-only live clock (avoids SSR hydration mismatch). */
export function Clock({ withDate = false }: { withDate?: boolean }) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000 * 30);
    return () => clearInterval(id);
  }, []);

  if (!now) return <span className="opacity-0">00:00</span>;

  return (
    <span className="font-mono tabular-nums">
      {formatClock(now)}
      {withDate && (
        <span className="ml-2 text-ink-faint">
          {now.toLocaleDateString("en-US", {
            weekday: "short",
            month: "short",
            day: "numeric",
          })}
        </span>
      )}
    </span>
  );
}
