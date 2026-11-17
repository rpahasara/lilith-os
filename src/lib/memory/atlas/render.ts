/**
 * Rendering parameters — how big and bright a node is drawn.
 *
 * These are presentation choices, not facts about a memory. A real record with
 * no stated importance is drawn at a neutral default; that default is never
 * shown to anyone as importance, and nothing reads it back as data.
 */
import type { AtlasNode } from "./types";

/** Neutral size for a node whose source states no importance. */
export const DEFAULT_RENDER_WEIGHT = 55;

/** 0–100 drawing weight: the stated importance, or the neutral default. */
export function renderWeight(node: Pick<AtlasNode, "importance">): number {
  return typeof node.importance === "number" ? node.importance : DEFAULT_RENDER_WEIGHT;
}
