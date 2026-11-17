/**
 * Cognitive Atlas — domain types.
 *
 * The Atlas is a spatial VIEW over memory: every memory is a node placed in a
 * brain-shaped volume, every association is a pathway between two nodes, and
 * everything that happens to memory arrives as an `AtlasEvent`.
 *
 * Two sources feed it, never mixed in one store:
 *  - SIMULATION: the synthetic graph and activity in `synthetic.ts` /
 *    `simulation.ts`. Invented, and labelled as such.
 *  - REAL MEMORY: a read-only projection of the authorized memory read model
 *    (`real-source.ts`). Only what the backend returns; nothing is filled in.
 * See `docs/engineering/cognitive-atlas-real-memory.md`.
 */
import type { EntityType, MemoryCategory, MemoryKind, ProvenanceKind } from "@/lib/memory/types";

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

/** Where a node or link came from. One store holds one origin only. */
export type AtlasOrigin = "synthetic" | "real";

export interface AtlasEntityRef {
  id: string;
  type: EntityType;
  label: string;
}

export interface AtlasNode {
  id: string;
  origin: AtlasOrigin;
  region: RegionId;
  /** Real records: the category the source gave, kept even where the brain
   *  places it in a region of another name (Work sits in the Career field). */
  category?: MemoryCategory;
  title: string;
  detail: string;
  kind: MemoryKind;
  tags: string[];
  /** named entities this memory mentions. */
  entities: string[];
  /** Real records keep the structured references, for the inspector. */
  entityRefs?: AtlasEntityRef[];
  /** `at` and `account` only when the source states them. */
  provenance: { kind: ProvenanceKind; label: string; at?: number; account?: string };
  /** 0–100, as stated by the source. Absent when the source gives none. */
  confidence?: number;
  /** 0–100, as stated by the source. Absent when the source gives none. Node
   *  size falls back to a rendering default (`renderWeight`), never to this. */
  importance?: number;
  /** epoch ms. Synthetic: when it was "learned". Real: the record's own
   *  created_at, if any — not proof of when Lilith learned it. */
  createdAt?: number;
  /** Real records: the record's updated_at, if any. */
  updatedAt?: number;
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

/**
 * Why two memories are joined.
 *  - synthetic:     invented by the simulation.
 *  - explicit:      the source lists the two records as related.
 *  - shared-entity: derived here — the source tagged both with the same
 *                   entity. A lookup, not a claim that the memories relate.
 * Entity-to-entity relationships are not memory links; they are shown on the
 * entities themselves (inspector), never drawn as pathways.
 */
export type LinkBasis = "synthetic" | "explicit" | "shared-entity";

export interface AtlasLink {
  id: string;
  source: string;
  target: string;
  basis: LinkBasis;
  /** shared-entity links: the entities both memories carry (labels, ids). */
  via?: string[];
  viaIds?: string[];
  /** human label for the association. */
  kind: string;
  /** 0–1. Real links: a rendering weight, not a measured strength. */
  strength: number;
  createdAt?: number;
  born: number;
  live: boolean;
}

/* ------------------------------------------------------------------ events */

/** A memory as it arrives on the wire — no layout, no derived fields. */
export type AtlasNodeInput = Omit<
  AtlasNode,
  "position" | "born" | "live" | "reinforcements" | "recalls"
>;

export type AtlasLinkInput = Pick<AtlasLink, "source" | "target" | "kind" | "strength"> &
  Partial<Pick<AtlasLink, "id" | "basis" | "via" | "viaIds">>;

/**
 * Simulation events (`memory.*`) describe invented cognition. Real-memory
 * events (`record.*`, `link.*`) describe only what differs between two
 * successful snapshots of the read model — never learning, forgetting or recall.
 */
export type AtlasEvent =
  | { type: "memory.learned"; at: number; node: AtlasNodeInput; links: AtlasLinkInput[] }
  | { type: "memory.linked"; at: number; link: AtlasLinkInput }
  | { type: "memory.reinforced"; at: number; nodeId: string; confidence?: number }
  | { type: "memory.recalled"; at: number; cue: string; chain: string[] }
  | { type: "record.observed"; at: number; node: AtlasNodeInput; links: AtlasLinkInput[] }
  | { type: "record.changed"; at: number; node: AtlasNodeInput }
  | { type: "record.withdrawn"; at: number; nodeId: string }
  /** `quiet`: a change to what is drawn (derived pathways), not to what the
   *  source states — applied to the graph, not logged or counted. */
  | { type: "link.observed"; at: number; link: AtlasLinkInput; quiet?: boolean }
  | { type: "link.withdrawn"; at: number; linkId: string; quiet?: boolean };

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
  /** counts of what arrived through the live stream this session (simulation). */
  session: { learned: number; linked: number; reinforced: number; recalled: number };
  /** differences observed between real snapshots this session. */
  changes: { observed: number; changed: number; withdrawn: number; links: number };
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
  /** associations to draw only while focused (real memory: those the
   *  simplified drawing leaves out). */
  extra?: { id: string; source: string; target: string; strength: number }[];
}
