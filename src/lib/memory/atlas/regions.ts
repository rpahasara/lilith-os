/**
 * The seven knowledge domains and where each lives in the brain.
 *
 * Brain space: +X = front, +Y = up, ±Z = the two hemispheres. Every region is
 * mirrored across both hemispheres.
 *
 * Colours stay inside the LILITH palette: wine / rose own the personal core,
 * orchid the people around it, gold is the rare luxury accent (ambition),
 * cyan is knowledge and data, emerald is settled habit.
 */
import type { AtlasRegion, RegionId } from "./types";

export const REGIONS: AtlasRegion[] = [
  {
    id: "career",
    index: 0,
    label: "Career",
    lobe: "Frontal field",
    blurb: "Ambitions, roles and the decisions that shape them.",
    color: "#dcb86e",
    anchor: [1.14, 0.3, 0.5],
    side: 1,
    labelAt: [1.5, 0.98, 0],
    focusAt: [1.0, 0.2, 0],
  },
  {
    id: "projects",
    index: 1,
    label: "Projects",
    lobe: "Superior crown",
    blurb: "What is being built, and where each build stands.",
    color: "#8ea3f4",
    anchor: [0.2, 0.96, 0.42],
    side: -1,
    labelAt: [0.36, 1.17, 0],
    focusAt: [0.2, 0.8, 0],
  },
  {
    id: "people",
    index: 2,
    label: "People",
    lobe: "Parietal arc",
    blurb: "Everyone Lilith can place — who they are and how they fit.",
    color: "#bb8ce2",
    anchor: [-0.78, 0.8, 0.46],
    side: 1,
    labelAt: [-0.84, 1.1, 0],
    focusAt: [-0.72, 0.68, 0],
  },
  {
    id: "knowledge",
    index: 3,
    label: "Knowledge",
    lobe: "Occipital reach",
    blurb: "Facts, references and things learned along the way.",
    color: "#5fd0e2",
    anchor: [-1.34, 0.14, 0.42],
    side: -1,
    labelAt: [-1.66, 0.84, 0],
    focusAt: [-1.2, 0.05, 0],
  },
  {
    id: "preferences",
    index: 4,
    label: "Preferences",
    lobe: "Cerebellar fold",
    blurb: "Habits and settled ways — how things should be done.",
    color: "#52d6a6",
    anchor: [-1.02, -0.8, 0.46],
    side: 1,
    labelAt: [-1.5, -1.14, 0],
    focusAt: [-0.86, -0.7, 0],
  },
  {
    id: "relationships",
    index: 5,
    label: "Relationships",
    lobe: "Temporal band",
    blurb: "The ties between people — history, trust and context.",
    color: "#f29ab5",
    anchor: [0.46, -0.6, 0.92],
    side: -1,
    labelAt: [1.06, -1.02, 0],
    focusAt: [0.3, -0.48, 0],
  },
  {
    id: "personal",
    index: 6,
    label: "Personal",
    lobe: "Limbic core",
    blurb: "The centre of it all — who you are when nobody is asking.",
    color: "#e2527c",
    // the stem: on the midline, so it never changes hemisphere
    anchor: [-0.44, -1.12, 0],
    side: 0,
    labelAt: [0.02, -1.3, 0],
    focusAt: [-0.2, -0.3, 0],
  },
];

/** Shader index reserved for particles that belong to no domain (ambient dust). */
export const AMBIENT_REGION_INDEX = 7;

export const REGION_BY_ID = Object.fromEntries(REGIONS.map((r) => [r.id, r])) as Record<
  RegionId,
  AtlasRegion
>;

/** sRGB hex → [r, g, b] in 0–1, kept in display space (shaders output raw). */
export function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export const REGION_RGB: [number, number, number][] = REGIONS.map((r) => hexToRgb(r.color));
