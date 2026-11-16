"use client";

import { getMeetingsData } from "@/lib/meetings/client";
import { useWorkspaceData } from "./use-workspace-data";

export function useMeetings() {
  return useWorkspaceData(getMeetingsData);
}
