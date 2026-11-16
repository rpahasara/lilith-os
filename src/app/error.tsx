"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import Link from "next/link";
import { RotateCw, TriangleAlert } from "lucide-react";
import { GlassCard } from "@/components/ui/card";
import { reportProblem } from "@/lib/diagnostics";

/**
 * The safety net for every workspace. A render error in a page lands here
 * instead of blanking the application: the shell (navigation, top bar, status)
 * stays in place, the failure is stated plainly, and the page can be retried.
 *
 * Nothing about the error is sent anywhere. One sanitized line (the error's
 * name and a truncated message, never the object or its stack) goes to the
 * console through the shared diagnostics sink.
 */
export default function WorkspaceError({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  useEffect(() => {
    reportProblem("workspace", "a page failed to render", error);
  }, [error]);

  const digest =
    typeof error === "object" && error !== null && "digest" in error
      ? String((error as { digest?: unknown }).digest ?? "")
      : "";

  return (
    <div className="workspace-page grid h-full place-items-center">
      <GlassCard strong animated={false} className="w-full max-w-md p-7 text-center" role="alert">
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-2xl border border-rose/25 bg-rose/10 text-rose">
          <TriangleAlert className="h-5 w-5" />
        </span>
        <h1 className="mt-4 text-lg font-semibold tracking-tight text-ink">This workspace hit a problem</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          Something went wrong while drawing this page. The rest of Lilith OS is unaffected, and
          nothing was changed.
        </p>
        {digest && <p className="mt-2 font-mono text-[11px] text-ink-faint">reference · {digest}</p>}
        <div className="mt-5 flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => retry()}
            className="inline-flex items-center gap-1.5 rounded-full border border-wine/30 bg-gradient-to-r from-wine-deep/60 to-wine/40 px-4 py-2 text-xs font-medium text-ink transition-[border-color,box-shadow] hover:border-wine-bright/50 hover:shadow-[0_10px_30px_-14px_rgba(201,84,115,0.9)]"
          >
            <RotateCw className="h-3.5 w-3.5" />
            Try again
          </button>
          <Link
            href="/"
            className="rounded-full border border-white/[0.1] bg-white/[0.04] px-4 py-2 text-xs font-medium text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
          >
            Command Center
          </Link>
        </div>
      </GlassCard>
    </div>
  );
}
