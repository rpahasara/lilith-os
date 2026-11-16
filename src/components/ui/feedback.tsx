import type { HTMLAttributes, ReactNode } from "react";
import { RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Feedback states — the one way each of these is said, everywhere.
 *
 *   loading      <LoadingRegion> around <Skeleton> blocks
 *   error        <InlineError>: what failed, and a way to try again
 *   notice       <InlineNotice>: something true the person should know
 *   not yet      a disabled control (`unavailable()` in ./unavailable) plus,
 *                where the label alone would mislead, a <NotYetTag>
 *   unavailable  a whole workspace without data: <WorkspaceUnavailable> in
 *                ./data-state
 *
 * Each carries its own role, so assistive technology hears the same thing a
 * sighted person sees. None of them animates beyond a pulse, which the
 * reduced-motion rule in the stylesheet stills.
 */

/** A placeholder block while content loads. Size and shape come from `className`. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-md bg-white/[0.04]", className)} />;
}

/** Wraps skeletons: one polite "loading" for the whole region, not one per block. */
export function LoadingRegion({
  label,
  className,
  children,
}: {
  /** what is loading, e.g. "Career" */
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" data-feedback="loading" className={cn("animate-pulse", className)}>
      <span className="sr-only">Loading {label}…</span>
      {children}
    </div>
  );
}

function ActionButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex shrink-0 items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
    >
      <RotateCcw className="h-3 w-3" /> {label}
    </button>
  );
}

type RowProps = Omit<HTMLAttributes<HTMLDivElement>, "children" | "role"> & {
  message: ReactNode;
  /** offered only when there is something to retry */
  onAction?: () => void;
  actionLabel?: string;
};

/** Something failed. States it plainly and offers the retry, if there is one. */
export function InlineError({ message, onAction, actionLabel = "Retry", className, ...rest }: RowProps) {
  return (
    <div
      role="alert"
      data-feedback="error"
      {...rest}
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border border-rose/25 bg-rose/[0.08] px-3.5 py-2",
        className,
      )}
    >
      <span className="text-compact text-rose">{message}</span>
      {onAction && <ActionButton label={actionLabel} onClick={onAction} />}
    </div>
  );
}

/** Something true and not alarming: a stopped turn, a disconnected service. */
export function InlineNotice({ message, onAction, actionLabel = "Try again", className, ...rest }: RowProps) {
  return (
    <div
      role="status"
      data-feedback="notice"
      {...rest}
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-3.5 py-2",
        className,
      )}
    >
      <span className="text-caption leading-snug text-ink-muted">{message}</span>
      {onAction && <ActionButton label={actionLabel} onClick={onAction} />}
    </div>
  );
}

/** The visible half of "not available yet", for a control whose label alone would promise it. */
export function NotYetTag({ className }: { className?: string }) {
  return (
    <span className={cn("font-mono text-micro uppercase tracking-wider text-ink-faint", className)}>Not yet</span>
  );
}
