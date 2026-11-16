/**
 * The brain itself — an implicit volume sampled into particles.
 *
 * Nothing here is a mesh or an asset. The shape is a signed-distance field
 * assembled from a few soft-blended ellipsoids per hemisphere (cerebrum lobes,
 * temporal lobe, cerebellum) plus a tapered stem. Sampling a thin shell of that
 * field gives the cortex; the folds come from rejecting particles along the
 * zero-crossings of a noise field (sulci) and along two named fissures.
 *
 * Brain space: +X front, +Y up, ±Z hemispheres. Roughly 3.0 long × 2.3 wide.
 *
 * Everything is seeded: the same brain is produced on every load, so a memory
 * placed here keeps its location across sessions.
 */
import { AMBIENT_REGION_INDEX, REGIONS, REGION_RGB } from "./regions";
import { clamp, hashString, mulberry32, noise3, smoothstep } from "./math";
import type { RegionId, Vec3 } from "./types";

/* ------------------------------------------------------------------- field */

const PART_CEREBRUM = 0;
const PART_CEREBELLUM = 1;
const PART_STEM = 2;

/** Which anatomical part the last `field()` call landed in. */
let lastPart = PART_CEREBRUM;

function ellipsoid(
  x: number, y: number, z: number,
  cx: number, cy: number, cz: number,
  rx: number, ry: number, rz: number,
): number {
  const dx = x - cx;
  const dy = y - cy;
  const dz = z - cz;
  const k0 = Math.hypot(dx / rx, dy / ry, dz / rz);
  const k1 = Math.hypot(dx / (rx * rx), dy / (ry * ry), dz / (rz * rz));
  return k1 > 1e-9 ? (k0 * (k0 - 1)) / k1 : -Math.min(rx, ry, rz);
}

function smin(a: number, b: number, k: number): number {
  const h = Math.max(k - Math.abs(a - b), 0) / k;
  return Math.min(a, b) - h * h * k * 0.25;
}

function cerebrum(x: number, y: number, az: number): number {
  let d = ellipsoid(x, y, az, 0.0, 0.18, 0.52, 1.42, 0.86, 0.62); // main mass
  d = smin(d, ellipsoid(x, y, az, 0.78, 0.12, 0.48, 0.72, 0.7, 0.5), 0.14); // frontal
  d = smin(d, ellipsoid(x, y, az, -0.98, 0.1, 0.42, 0.52, 0.62, 0.44), 0.14); // occipital
  d = smin(d, ellipsoid(x, y, az, 0.5, -0.5, 0.72, 0.5, 0.27, 0.31), 0.1); // temporal pole
  d = smin(d, ellipsoid(x, y, az, -0.02, -0.4, 0.76, 0.62, 0.3, 0.32), 0.1); // temporal body
  // flatten the underside: shallow at the midline, deeper under the temporal lobes
  const floor = -0.44 - 0.36 * smoothstep(0.34, 0.74, az) + 0.14 * smoothstep(0.55, 1.15, x);
  d = Math.max(d, floor - y);
  // lift the frontal underside so the temporal pole reads as its own lobe
  d = Math.max(d, -0.9 + 0.58 * smoothstep(0.64, 0.92, x) - y);
  // longitudinal fissure between the hemispheres
  d = Math.max(d, 0.05 * smoothstep(-0.15, 0.25, y) - az);
  return d;
}

function stem(x: number, y: number, z: number): number {
  const ax = -0.26, ay = -0.4, bx = -0.52, by = -1.42;
  const bax = bx - ax, bay = by - ay;
  const h = clamp(((x - ax) * bax + (y - ay) * bay) / (bax * bax + bay * bay), 0, 1);
  const shaft = Math.hypot(x - ax - bax * h, y - ay - bay * h, z) - (0.18 - 0.08 * h);
  // pons: the soft bulge where the stem meets the brain
  return smin(shaft, ellipsoid(x, y, z, -0.2, -0.62, 0, 0.25, 0.2, 0.26), 0.08);
}

/** Signed distance to the brain surface (negative = inside). Sets `lastPart`. */
function field(x: number, y: number, z: number): number {
  const az = Math.abs(z);
  const c = cerebrum(x, y, az);
  const cb = ellipsoid(x, y, az, -0.8, -0.64, 0.36, 0.5, 0.31, 0.46);
  const st = stem(x, y, z);
  lastPart = c <= cb && c <= st ? PART_CEREBRUM : cb <= st ? PART_CEREBELLUM : PART_STEM;
  return smin(smin(c, cb, 0.04), st, 0.07);
}

function segmentDistance(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
  const abx = bx - ax, aby = by - ay;
  const h = clamp(((px - ax) * abx + (py - ay) * aby) / (abx * abx + aby * aby), 0, 1);
  return Math.hypot(px - ax - abx * h, py - ay - aby * h);
}

/* ----------------------------------------------------------------- regions */

const IDX = Object.fromEntries(REGIONS.map((r) => [r.id, r.index])) as Record<RegionId, number>;

/** Cortical territories — weighted Voronoi over anchors on one hemisphere. */
const TERRITORY: { region: number; x: number; y: number; z: number; w: number }[] = [
  { region: IDX.career, x: 1.04, y: 0.14, z: 0.45, w: 1.0 },
  { region: IDX.projects, x: 0.14, y: 0.88, z: 0.42, w: 1.05 },
  { region: IDX.people, x: -0.76, y: 0.66, z: 0.42, w: 1.0 },
  { region: IDX.knowledge, x: -1.2, y: -0.04, z: 0.4, w: 0.95 },
  { region: IDX.relationships, x: 0.24, y: -0.5, z: 0.74, w: 1.25 },
];

function regionAt(x: number, y: number, z: number, d: number, part: number): number {
  if (part === PART_CEREBELLUM) return IDX.preferences;
  if (part === PART_STEM) return IDX.personal;
  // the limbic core: deep, central, low
  if (d < -0.1 && ellipsoid(x, y, z, -0.1, -0.12, 0, 0.62, 0.36, 0.5) < 0) return IDX.personal;
  const az = Math.abs(z);
  // warp the lookup so borders between domains wander organically
  const wx = x + 0.11 * noise3(x * 2.6 + 3.1, y * 2.6, z * 2.6);
  const wy = y + 0.11 * noise3(x * 2.6, y * 2.6 + 9.4, z * 2.6);
  let best = 0;
  let bestScore = Infinity;
  for (const t of TERRITORY) {
    const score = ((wx - t.x) ** 2 + (wy - t.y) ** 2 + (az - t.z) ** 2) * t.w;
    if (score < bestScore) {
      bestScore = score;
      best = t.region;
    }
  }
  return best;
}

/* ------------------------------------------------------------------ layout */

export interface BrainLayout {
  /** total particles in the cortex buffer (surface + interior + latent + dust). */
  count: number;
  positions: Float32Array;
  /** where each particle starts before the brain assembles. */
  scatter: Float32Array;
  colors: Float32Array;
  regions: Float32Array;
  seeds: Float32Array;
  sizes: Float32Array;
  /** 0–1 growth-timeline birth; 2 = latent (hidden until the region grows). */
  born: Float32Array;
  /** per region index: latent particle indices that learning can switch on. */
  latent: number[][];
  /** per region id: candidate positions for memory nodes. */
  pools: Record<RegionId, Vec3[]>;
  /** cortex endpoints for the projection tracts that fan out from the stem. */
  tractTargets: { position: Vec3; region: number }[];
}

/** half-width of a sulcus in fold-field units — wider reads as deeper folds. */
const FOLD_WIDTH = 0.17;

const SURFACE = 23000;
const LATENT = 2100;
const INTERIOR = 3400;
const DUST = 650;

const BOUNDS = { x: [-1.62, 1.6], y: [-1.5, 1.12], z: [-1.16, 1.16] } as const;
const PEARL: Vec3 = [0.96, 0.9, 0.93];
const WINE: Vec3 = [0.79, 0.33, 0.45];

let cached: BrainLayout | null = null;

export function buildBrainLayout(): BrainLayout {
  if (cached) return cached;
  const rand = mulberry32(0x11117a5);
  const count = SURFACE + LATENT + INTERIOR + DUST;

  const positions = new Float32Array(count * 3);
  const scatter = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const regions = new Float32Array(count);
  const seeds = new Float32Array(count);
  const sizes = new Float32Array(count);
  const born = new Float32Array(count);
  const latent: number[][] = REGIONS.map(() => []);
  const pools = Object.fromEntries(REGIONS.map((r) => [r.id, [] as Vec3[]])) as Record<RegionId, Vec3[]>;
  const tractTargets: BrainLayout["tractTargets"] = [];

  let n = 0;
  const put = (
    x: number, y: number, z: number,
    region: number, rgb: Vec3, gain: number, size: number, bornAt: number, assembles: boolean,
  ) => {
    positions[n * 3] = x;
    positions[n * 3 + 1] = y;
    positions[n * 3 + 2] = z;
    if (assembles) {
      // start on a wide shell — the vertex shader spirals each particle home
      const u = rand() * 2 - 1;
      const phi = rand() * Math.PI * 2;
      const r = 2.5 + rand() * 2.6;
      const s = Math.sqrt(1 - u * u);
      scatter[n * 3] = r * s * Math.cos(phi);
      scatter[n * 3 + 1] = r * u * 0.72;
      scatter[n * 3 + 2] = r * s * Math.sin(phi);
    } else {
      scatter[n * 3] = x;
      scatter[n * 3 + 1] = y;
      scatter[n * 3 + 2] = z;
    }
    colors[n * 3] = rgb[0] * gain;
    colors[n * 3 + 1] = rgb[1] * gain;
    colors[n * 3 + 2] = rgb[2] * gain;
    regions[n] = region;
    seeds[n] = rand();
    sizes[n] = size;
    born[n] = bornAt;
    n++;
  };

  const sample = (): Vec3 => [
    BOUNDS.x[0] + rand() * (BOUNDS.x[1] - BOUNDS.x[0]),
    BOUNDS.y[0] + rand() * (BOUNDS.y[1] - BOUNDS.y[0]),
    BOUNDS.z[0] + rand() * (BOUNDS.z[1] - BOUNDS.z[0]),
  ];

  /* cortex shell ---------------------------------------------------------- */
  const SHELL = 0.075;
  let surface = 0;
  let hidden = 0;
  let guard = 0;
  while (surface + hidden < SURFACE + LATENT && guard++ < 4_000_000) {
    const [x, y, z] = sample();
    const d = field(x, y, z);
    if (d > 0 || d < -SHELL) continue;
    const part = lastPart;
    const az = Math.abs(z);
    let crest = 1;
    if (part === PART_CEREBRUM) {
      // sulci: thin winding creases where the fold field crosses zero
      const fold =
        noise3(x * 3.1 + 11.3, y * 3.1 + 5.1, z * 3.1 + 7.7) +
        0.3 * noise3(x * 6.6, y * 6.6 + 3.3, z * 6.6);
      const depth = Math.abs(fold);
      if (depth < FOLD_WIDTH && rand() < 0.95) continue;
      crest = 0.55 + 0.6 * smoothstep(FOLD_WIDTH, 0.55, depth);
      // lateral (Sylvian) fissure and central sulcus — the two iconic grooves
      if (az > 0.42 && segmentDistance(x, y, 0.84, -0.3, -0.36, 0.13) < 0.045) continue;
      if (az > 0.08 && segmentDistance(x, y, 0.1, 1.04, 0.3, 0.02) < 0.03) continue;
    } else if (part === PART_CEREBELLUM) {
      // folia: fine horizontal leaves
      if (Math.sin((y + x * 0.22) * 50) > 0.25 && rand() < 0.92) continue;
    }
    const region = regionAt(x, y, z, d, part);
    const tint = REGION_RGB[region];
    const blend = 0.18 + rand() * 0.34;
    const rgb: Vec3 = [
      tint[0] + (PEARL[0] - tint[0]) * blend,
      tint[1] + (PEARL[1] - tint[1]) * blend,
      tint[2] + (PEARL[2] - tint[2]) * blend,
    ];
    const spark = rand() < 0.055;
    const gain = (spark ? 1.25 : 0.42 + rand() * 0.42) * crest;
    const size = spark ? 0.034 + rand() * 0.02 : 0.013 + rand() * 0.014;

    const makeLatent = hidden < LATENT && rand() < LATENT / (SURFACE + LATENT);
    if (makeLatent || surface >= SURFACE) {
      if (hidden >= LATENT) continue;
      latent[region].push(n);
      put(x, y, z, region, rgb, gain * 1.1, size, 2, false);
      hidden++;
    } else {
      const bornAt = rand() < 0.3 ? 0 : Math.pow(rand(), 0.85) * 0.94;
      put(x, y, z, region, rgb, gain, size, bornAt, true);
      surface++;
      if (part === PART_CEREBRUM && tractTargets.length < 150 && rand() < 0.02) {
        tractTargets.push({ position: [x * 0.95, y * 0.95, z * 0.95], region });
      }
    }
  }

  /* interior — white matter haze, and the pool of places memories can sit --- */
  let interior = 0;
  guard = 0;
  const POOL_CAP = 260;
  while ((interior < INTERIOR || !poolsFull(pools, POOL_CAP)) && guard++ < 1_500_000) {
    const [x, y, z] = sample();
    const d = field(x, y, z);
    if (d > -0.05 || d < -0.62) continue;
    const part = lastPart;
    const region = regionAt(x, y, z, d, part);
    const regionId = REGIONS[region].id;
    // memories live just under the cortex (or anywhere inside the core)
    const shallow = d > -0.2 || regionId === "personal" || regionId === "preferences";
    if (shallow && pools[regionId].length < POOL_CAP) pools[regionId].push([x, y, z]);
    if (interior >= INTERIOR) continue;
    const tint = REGION_RGB[region];
    const mix = 0.45;
    const rgb: Vec3 = [
      tint[0] + (WINE[0] - tint[0]) * mix,
      tint[1] + (WINE[1] - tint[1]) * mix,
      tint[2] + (WINE[2] - tint[2]) * mix,
    ];
    put(x, y, z, region, rgb, 0.2 + rand() * 0.22, 0.011 + rand() * 0.012, rand() < 0.4 ? 0 : rand() * 0.9, true);
    interior++;
  }

  /* ambient dust — depth and parallax around the brain ---------------------- */
  for (let i = 0; i < DUST; i++) {
    const u = rand() * 2 - 1;
    const phi = rand() * Math.PI * 2;
    const r = 2.2 + Math.pow(rand(), 0.7) * 3.4;
    const s = Math.sqrt(1 - u * u);
    const warm = rand() < 0.35;
    put(
      r * s * Math.cos(phi), r * u * 0.7, r * s * Math.sin(phi),
      AMBIENT_REGION_INDEX, warm ? WINE : PEARL, 0.12 + rand() * 0.2, 0.014 + rand() * 0.03, 0, false,
    );
  }

  cached = {
    count: n,
    positions, scatter, colors, regions, seeds, sizes, born,
    latent, pools, tractTargets,
  };
  return cached;
}

function poolsFull(pools: Record<RegionId, Vec3[]>, cap: number): boolean {
  for (const r of REGIONS) if (pools[r.id].length < cap * 0.6) return false;
  return true;
}

/**
 * Deterministic home for a memory: hashes the id into its region's pool, then
 * walks forward until it finds a spot clear of the memories already placed.
 */
export function placeNode(
  layout: BrainLayout,
  region: RegionId,
  id: string,
  taken: readonly Vec3[],
  minGap = 0.15,
): Vec3 {
  const pool = layout.pools[region];
  const start = hashString(id) % pool.length;
  let fallback = pool[start];
  let fallbackGap = -1;
  for (let i = 0; i < pool.length; i++) {
    const p = pool[(start + i * 7) % pool.length];
    let gap = Infinity;
    for (const t of taken) {
      const g = Math.hypot(p[0] - t[0], p[1] - t[1], p[2] - t[2]);
      if (g < gap) gap = g;
      if (gap < minGap) break;
    }
    if (gap >= minGap) return p;
    if (gap > fallbackGap) {
      fallbackGap = gap;
      fallback = p;
    }
  }
  return fallback;
}
