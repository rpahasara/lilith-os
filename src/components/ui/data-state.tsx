"use client";

import { CloudOff, FlaskConical, RotateCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Diagnostics } from "@/lib/api";
import { unavailableReason } from "@/lib/data-mode";
import { GlassCard } from "@/components/ui/card";
import { WorkspaceHeader } from "@/components/ui/primitives";
import { EmptyState } from "@/components/ui/workspace";

/** Who a workspace is, independent of whether it has data to show. */
export interface WorkspaceIdentity {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
}

/**
 * A workspace that could not reach its data. It keeps its identity, says
 * plainly that nothing is shown, and never substitutes sample content.
 */
export function WorkspaceUnavailable({
  identity,
  what,
  diagnostics,
  onRetry,
}: {
  identity: WorkspaceIdentity;
  /** what is missing, e.g. "Career data" */
  what: string;
  diagnostics: Diagnostics;
  onRetry?: () => void;
}) {
  return (
    <>
      <WorkspaceHeader {...identity} unavailable diagnostics={diagnostics} />
      <GlassCard className="p-4" animated={false} panel data-workspace-state="unavailable">
        <EmptyState
          icon={CloudOff}
          title={`${what} unavailable`}
          description={`${unavailableReason(diagnostics)} Nothing is shown until Lilith can read it. No sample data is substituted.`}
          action={
            onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.1] bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
              >
                <RotateCw className="h-3 w-3" />
                Try again
              </button>
            )
          }
        />
      </GlassCard>
    </>
  );
}

/**
 * Shown at the top of any page that is rendering the bundled sample data.
 * Sample data only appears when `NEXT_PUBLIC_LILITH_DEMO_DATA=true` was set, and
 * this banner is what makes it impossible to mistake for Lilith's own.
 */
export function DemoBanner() {
  return (
    <div
      role="note"
      data-workspace-state="demo"
      className="flex items-start gap-3 rounded-[var(--radius-md)] border border-amber/30 bg-amber/[0.09] px-4 py-3"
    >
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
      <div>
        <p className="text-sm font-medium text-amber">Simulated data</p>
        <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">
          Everything on this page is sample content for development. None of it comes from Lilith
          or from your accounts.
        </p>
      </div>
    </div>
  );
}
