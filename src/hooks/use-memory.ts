"use client";

import { getMemoryData } from "@/lib/memory/client";
import { useWorkspaceData } from "./use-workspace-data";

export function useMemory() {
  return useWorkspaceData(getMemoryData);
}
