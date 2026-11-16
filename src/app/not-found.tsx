import type { Metadata } from "next";
import Link from "next/link";
import { Compass } from "lucide-react";

export const metadata: Metadata = { title: "Not found" };

/** An address with no page behind it — shown inside the shell, never a blank screen. */
export default function NotFound() {
  return (
    <div className="workspace-page grid h-full place-items-center">
      <div className="glass-strong relative w-full max-w-md overflow-hidden rounded-[var(--radius-lg)] p-7 text-center">
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-2xl border border-white/[0.08] bg-white/[0.04] text-ink-muted">
          <Compass className="h-5 w-5" />
        </span>
        <h1 className="mt-4 text-lg font-semibold tracking-tight text-ink">Nothing lives at this address</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          This page does not exist in Lilith OS. Use the navigation to go somewhere that does.
        </p>
        <Link
          href="/"
          className="mt-5 inline-flex rounded-full border border-wine/30 bg-gradient-to-r from-wine-deep/60 to-wine/40 px-4 py-2 text-xs font-medium text-ink transition-[border-color,box-shadow] hover:border-wine-bright/50 hover:shadow-[0_10px_30px_-14px_rgba(201,84,115,0.9)]"
        >
          Command Center
        </Link>
      </div>
    </div>
  );
}
