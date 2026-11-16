/**
 * Cognitive Atlas — domain types.
 *
 * The Atlas is a spatial VIEW over memory: every memory is a node placed in a
 * brain-shaped volume, every association is a pathway between two nodes, and
 * everything that happens to memory arrives as an `AtlasEvent`.
 *
 * PROTOTYPE STATUS: the only event source today is the synthetic simulation in
 * `simulation.ts`. Nothing here reads, writes or implies real LILITH memory.
 * The event contract below is the seam a real source will plug into later
 * (see `docs/engineering/cognitive-atlas-prototype.md`).
 */
import type { MemoryKind, ProvenanceKind } from "@/lib/memory/types";

export const REGION_IDS = [
  "career",
  "projects",
  "people",
  "knowledge",
  "preferences",
  "relationships",
  "personal",
] as const;

export type RegionId = (typeof REGION_IDS)[number];

export type Vec3 = [number, number, number];

export interface AtlasRegion {
  id: RegionId;
  /** stable index used by shaders (0–6). */
  index: number;
  label: string;
  /** the part of the brain this domain occupies — poetic, not clinical. */
  lobe: string;
  blurb: string;
  /** display colour, sRGB hex. */
  color: string;
  /** the point on the cortex this domain's label points at. `z` is the
   *  hemisphere offset; the scene mirrors it toward whichever side faces the camera. */
  anchor: Vec3;
  /** which hemisphere the label prefers when the brain is seen head-on
   *  (1 / -1), so labels split left and right instead of stacking. 0 = midline. */
  side: 1 | -1 | 0;
  /** a fixed label position for the still (no-WebGL) rendering. */
  labelAt: Vec3;
  /** centre of mass used for camera focus. */
  focusAt: Vec3;
}

export interface AtlasNode {
  id: string;
  region: RegionId;
  title: string;
  detail: string;
  kind: MemoryKind;
  tags: string[];
  /** named entities this memory mentions. */
  entities: string[];
  provenance: { kind: ProvenanceKind; label: string; at: number };
  /** 0–100 */
  confidence: number;
  /** 0–100 — drives node size. */
  importance: number;
  createdAt: number; // epoch ms
  reinforcedAt?: number;
  reinforcements: number;
  recalls: number;
  /** position in brain space — assigned by the layout, stable per id. */
  position: Vec3;
  /** 0–1 position on the growth timeline (0 = oldest). */
  born: number;
  /** true when the node arrived through the live event stream this session. */
  live: boolean;
}

export interface AtlasLink {
  id: string;
  source: string;
  target: string;
  /** human label for the association. */
  kind: string;
  /** 0–1 */
  strength: number;
  createdAt: number;
  born: number;
  live: boolean;
}

/* ------------------------------------------------------------------ events */

/** A memory as it arrives on the wire — no layout, no derived fields. */
export type AtlasNodeInput = Omit<
  AtlasNode,
  "position" | "born" | "live" | "reinforcements" | "recalls"
>;

export type AtlasLinkInput = Pick<AtlasLink, "source" | "target" | "kind" | "strength">;

export type AtlasEvent =
  | { type: "memory.learned"; at: number; node: AtlasNodeInput; links: AtlasLinkInput[] }
  | { type: "memory.linked"; at: number; link: AtlasLinkInput }
  | { type: "memory.reinforced"; at: number; nodeId: string; confidence?: number }
  | { type: "memory.recalled"; at: number; cue: string; chain: string[] };

/** One line in the "live cognition" feed. */
export interface AtlasActivity {
  id: string;
  at: number;
  type: AtlasEvent["type"];
  text: string;
  region: RegionId;
  nodeId?: string;
}

export interface AtlasState {
  nodes: AtlasNode[];
  links: AtlasLink[];
  activity: AtlasActivity[];
  /** counts of what arrived through the live stream this session. */
  session: { learned: number; linked: number; reinforced: number; recalled: number };
}

/** A traced association chain — the output of a recall. */
export interface RecallTrace {
  id: number;
  cue: string;
  nodes: string[];
  /** link ids; links[i] joins nodes[i] → nodes[i + 1]. */
  links: string[];
}

/** What the scene should emphasise right now. */
export interface AtlasFocus {
  /** 1 = related, 2 = primary. Absent = normal. */
  nodes: Map<string, 1 | 2>;
  links: Set<string>;
  /** region index to keep lit while the rest dims, or -1. */
  region: number;
  /** 0 = no dimming, 1 = everything outside the focus recedes. */
  dim: number;
}
