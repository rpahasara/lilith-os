"use client";

import { BeliefsView } from "@/components/memory/beliefs/beliefs-view";

/** Memory → Beliefs: the World Model, read-only (formerly /world). */
export default function BeliefsPage() {
  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      <BeliefsView />
    </div>
  );
}
