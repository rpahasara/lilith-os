"use client";

import { getCareerData } from "@/lib/career/client";
import { useWorkspaceData } from "./use-workspace-data";

export function useCareer() {
  return useWorkspaceData(getCareerData);
}
