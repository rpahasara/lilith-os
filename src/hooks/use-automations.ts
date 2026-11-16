"use client";

import { getAutomationsData } from "@/lib/automations/client";
import { useWorkspaceData } from "./use-workspace-data";

export function useAutomations() {
  return useWorkspaceData(getAutomationsData);
}
