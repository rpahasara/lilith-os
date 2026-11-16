"use client";

import { useMemory } from "@/hooks/use-memory";
import { MEMORY_IDENTITY, MemoryHeader } from "@/components/memory/memory-header";
import { DemoBanner, WorkspaceUnavailable } from "@/components/ui/data-state";
import { MemoryViewSwitch } from "@/components/memory/memory-view-switch";
import { atlasPreviewEnabled } from "@/lib/memory/atlas/preview";
import { MemoryExplorer } from "@/components/memory/memory-explorer";
import { MemorySkeleton } from "@/components/memory/memory-skeleton";

/** Brain / Timeline open the Cognitive Atlas preview; a build can leave it out. */
const ATLAS_PREVIEW = atlasPreviewEnabled();

/**
 * The Memory Archive: a read-only evidence explorer over what the backend
 * returns. The exploring itself lives in `MemoryExplorer`; this page owns the
 * loading, unavailable and simulated-data states around it.
 */
export default function MemoryPage() {
  const { data, unavailable, loading, retry } = useMemory();

  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      {loading ? (
        <MemorySkeleton />
      ) : unavailable ? (
        <>
          <WorkspaceUnavailable
            identity={MEMORY_IDENTITY}
            what="Memory"
            diagnostics={unavailable.diagnostics}
            onRetry={retry}
          />
          {ATLAS_PREVIEW && (
            <div className="flex justify-end">
              <MemoryViewSwitch active="archive" />
            </div>
          )}
        </>
      ) : !data ? null : (
        <>
          {data.isDemo && <DemoBanner />}
          <MemoryHeader isDemo={data.isDemo} diagnostics={data.diagnostics} />

          {/* Brain / Timeline open the Cognitive Atlas prototype (synthetic data). */}
          {ATLAS_PREVIEW && (
            <div className="flex justify-end">
              <MemoryViewSwitch active="archive" />
            </div>
          )}

          <MemoryExplorer data={data} />
        </>
      )}
    </div>
  );
}
