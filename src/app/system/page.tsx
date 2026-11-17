"use client";

import { SystemWorkspace } from "@/components/system/system-workspace";

/** System: measured health, this device, and the preferences that already work. */
export default function SystemPage() {
  return (
    <div className="workspace-page scroll-area h-full space-y-5 overflow-y-auto pr-1">
      <SystemWorkspace />
    </div>
  );
}
