/**
 * Growable GPU buffers for the Atlas.
 *
 * Memory nodes and pathways are allocated once at a fixed capacity and filled
 * in place; a live event appends to the next free slot and bumps the draw
 * range. No geometry is ever rebuilt while the scene runs.
 */
import * as THREE from "three";
import type { BrainLayout } from "@/lib/memory/atlas/brain-shape";
import { REGION_BY_ID, REGION_RGB, hexToRgb } from "@/lib/memory/atlas/regions";
import { hash01, mulberry32 } from "@/lib/memory/atlas/math";
import type { AtlasLink, AtlasNode, Vec3 } from "@/lib/memory/atlas/types";

/** Birth time (scene seconds) for anything that already existed at mount. */
export const ALWAYS = -100;

const BOUNDS = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 8);

function attr(geometry: THREE.BufferGeometry, name: string, array: Float32Array, size: number) {
  const attribute = new THREE.BufferAttribute(array, size);
  geometry.setAttribute(name, attribute);
  return attribute;
}

/* ------------------------------------------------------------------ cortex */

export function buildCortexGeometry(layout: BrainLayout) {
  const geometry = new THREE.BufferGeometry();
  attr(geometry, "position", layout.positions, 3);
  attr(geometry, "aScatter", layout.scatter, 3);
  attr(geometry, "aColor", layout.colors, 3);
  attr(geometry, "aRegion", layout.regions, 1);
  attr(geometry, "aSeed", layout.seeds, 1);
  attr(geometry, "aSize", layout.sizes, 1);
  // born / birth are mutated when a region densifies, so they get private copies
  const born = attr(geometry, "aBorn", layout.born.slice(), 1);
  const birth = attr(geometry, "aBirth", new Float32Array(layout.count).fill(ALWAYS), 1);
  geometry.boundingSphere = BOUNDS;

  const used = new Set<number>();
  /** Switch on up to `count` latent particles nearest to `at` — the region grows denser. */
  const densify = (region: number, at: Vec3, count: number, time: number) => {
    const candidates = layout.latent[region].filter((i) => !used.has(i));
    candidates.sort((a, b) => dist2(layout.positions, a, at) - dist2(layout.positions, b, at));
    for (const i of candidates.slice(0, count)) {
      used.add(i);
      born.array[i] = 0.9;
      birth.array[i] = time + Math.random() * 1.6;
    }
    born.needsUpdate = true;
    birth.needsUpdate = true;
  };
  return { geometry, densify };
}

function dist2(positions: Float32Array, i: number, p: Vec3) {
  const dx = positions[i * 3] - p[0];
  const dy = positions[i * 3 + 1] - p[1];
  const dz = positions[i * 3 + 2] - p[2];
  return dx * dx + dy * dy + dz * dz;
}

/* ------------------------------------------------------------------- nodes */

export class NodeBuffers {
  readonly geometry = new THREE.BufferGeometry();
  readonly index = new Map<string, number>();
  readonly ids: string[] = [];
  readonly positions: Float32Array;
  readonly born: Float32Array;
  readonly sizes: Float32Array;
  private readonly color: THREE.BufferAttribute;
  private readonly position: THREE.BufferAttribute;
  private readonly seed: THREE.BufferAttribute;
  private readonly size: THREE.BufferAttribute;
  private readonly bornAttr: THREE.BufferAttribute;
  private readonly birth: THREE.BufferAttribute;
  private readonly pulseAttr: THREE.BufferAttribute;
  private readonly state: THREE.BufferAttribute;
  count = 0;

  constructor(readonly capacity: number) {
    const g = this.geometry;
    this.positions = new Float32Array(capacity * 3);
    this.born = new Float32Array(capacity);
    this.sizes = new Float32Array(capacity);
    this.position = attr(g, "position", this.positions, 3);
    this.color = attr(g, "aColor", new Float32Array(capacity * 3), 3);
    this.seed = attr(g, "aSeed", new Float32Array(capacity), 1);
    this.size = attr(g, "aSize", this.sizes, 1);
    this.bornAttr = attr(g, "aBorn", this.born, 1);
    this.birth = attr(g, "aBirth", new Float32Array(capacity).fill(ALWAYS), 1);
    this.pulseAttr = attr(g, "aPulse", new Float32Array(capacity).fill(ALWAYS), 1);
    this.state = attr(g, "aState", new Float32Array(capacity), 1);
    g.boundingSphere = BOUNDS;
    g.setDrawRange(0, 0);
  }

  add(node: AtlasNode, birthTime: number) {
    if (this.count >= this.capacity || this.index.has(node.id)) return;
    const i = this.count++;
    this.index.set(node.id, i);
    this.ids.push(node.id);
    this.positions.set(node.position, i * 3);
    this.color.array.set(REGION_RGB[REGION_BY_ID[node.region].index], i * 3);
    this.seed.array[i] = hash01(node.id, 11);
    this.sizes[i] = 0.028 + (node.importance / 100) * 0.044;
    this.born[i] = node.born;
    this.birth.array[i] = birthTime;
    for (const a of [this.position, this.color, this.seed, this.size, this.bornAttr, this.birth]) {
      a.needsUpdate = true;
    }
    this.geometry.setDrawRange(0, this.count);
  }

  pulse(id: string, time: number) {
    const i = this.index.get(id);
    if (i === undefined) return;
    this.pulseAttr.array[i] = time;
    this.pulseAttr.needsUpdate = true;
  }

  setStates(states: ReadonlyMap<string, number>) {
    const array = this.state.array as Float32Array;
    array.fill(0, 0, this.count);
    states.forEach((value, id) => {
      const i = this.index.get(id);
      if (i !== undefined) array[i] = value;
    });
    this.state.needsUpdate = true;
  }
}

/* ---------------------------------------------------------------- pathways */

const SEGMENTS = 16;
const VERTS = SEGMENTS * 2;

/** Curved pathways drawn as line segments, plus one travelling packet each. */
export class PathBuffers {
  readonly lines = new THREE.BufferGeometry();
  readonly packets = new THREE.BufferGeometry();
  readonly index = new Map<string, number>();
  private readonly l: Record<string, THREE.BufferAttribute>;
  private readonly p: Record<string, THREE.BufferAttribute>;
  count = 0;

  constructor(readonly capacity: number) {
    const lv = capacity * VERTS;
    this.l = {
      position: attr(this.lines, "position", new Float32Array(lv * 3), 3),
      color: attr(this.lines, "aColor", new Float32Array(lv * 3), 3),
      t: attr(this.lines, "aT", new Float32Array(lv), 1),
      seed: attr(this.lines, "aSeed", new Float32Array(lv), 1),
      born: attr(this.lines, "aBorn", new Float32Array(lv), 1),
      birth: attr(this.lines, "aBirth", new Float32Array(lv).fill(ALWAYS), 1),
      state: attr(this.lines, "aState", new Float32Array(lv), 1),
      strength: attr(this.lines, "aStrength", new Float32Array(lv), 1),
    };
    this.p = {
      position: attr(this.packets, "position", new Float32Array(capacity * 3), 3),
      p1: attr(this.packets, "aP1", new Float32Array(capacity * 3), 3),
      p2: attr(this.packets, "aP2", new Float32Array(capacity * 3), 3),
      color: attr(this.packets, "aColor", new Float32Array(capacity * 3), 3),
      seed: attr(this.packets, "aSeed", new Float32Array(capacity), 1),
      born: attr(this.packets, "aBorn", new Float32Array(capacity), 1),
      birth: attr(this.packets, "aBirth", new Float32Array(capacity).fill(ALWAYS), 1),
      state: attr(this.packets, "aState", new Float32Array(capacity), 1),
      strength: attr(this.packets, "aStrength", new Float32Array(capacity), 1),
    };
    this.lines.boundingSphere = BOUNDS;
    this.packets.boundingSphere = BOUNDS;
    this.lines.setDrawRange(0, 0);
    this.packets.setDrawRange(0, 0);
  }

  add(
    id: string,
    a: Vec3, control: Vec3, b: Vec3,
    colorA: Vec3, colorB: Vec3,
    strength: number, born: number, birthTime: number,
  ) {
    if (this.count >= this.capacity || this.index.has(id)) return;
    const i = this.count++;
    this.index.set(id, i);
    const seed = hash01(id, 13);
    const { l, p } = this;
    const at = (t: number, out: number[]) => {
      const k = 1 - t;
      for (let c = 0; c < 3; c++) out[c] = k * k * a[c] + 2 * k * t * control[c] + t * t * b[c];
    };
    const v = [0, 0, 0];
    for (let s = 0; s < SEGMENTS; s++) {
      for (let e = 0; e < 2; e++) {
        const t = (s + e) / SEGMENTS;
        const o = i * VERTS + s * 2 + e;
        at(t, v);
        l.position.array.set(v, o * 3);
        for (let c = 0; c < 3; c++) l.color.array[o * 3 + c] = colorA[c] + (colorB[c] - colorA[c]) * t;
        l.t.array[o] = t;
        l.seed.array[o] = seed;
        l.born.array[o] = born;
        l.birth.array[o] = birthTime;
        l.strength.array[o] = strength;
      }
    }
    p.position.array.set(a, i * 3);
    p.p1.array.set(control, i * 3);
    p.p2.array.set(b, i * 3);
    for (let c = 0; c < 3; c++) p.color.array[i * 3 + c] = (colorA[c] + colorB[c]) / 2;
    p.seed.array[i] = seed;
    p.born.array[i] = born;
    p.birth.array[i] = birthTime;
    p.strength.array[i] = strength;
    for (const key in l) l[key].needsUpdate = true;
    for (const key in p) p[key].needsUpdate = true;
    this.lines.setDrawRange(0, this.count * VERTS);
    this.packets.setDrawRange(0, this.count);
  }

  setStates(lit: ReadonlySet<string>) {
    const ls = this.l.state.array as Float32Array;
    const ps = this.p.state.array as Float32Array;
    ls.fill(0, 0, this.count * VERTS);
    ps.fill(0, 0, this.count);
    lit.forEach((id) => {
      const i = this.index.get(id);
      if (i === undefined) return;
      ls.fill(1, i * VERTS, (i + 1) * VERTS);
      ps[i] = 1;
    });
    this.l.state.needsUpdate = true;
    this.p.state.needsUpdate = true;
  }
}

/** Control point for an association: long ties dive through the interior like
 *  white-matter tracts; short local ties bow gently outward. */
export function linkControl(a: Vec3, b: Vec3): Vec3 {
  const mid: Vec3 = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
  const span = Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  if (span > 0.8) return [mid[0] * 0.52, mid[1] * 0.52 - 0.04, mid[2] * 0.52];
  const len = Math.hypot(mid[0], mid[1], mid[2]) || 1;
  const bow = span * 0.2;
  return [mid[0] + (mid[0] / len) * bow, mid[1] + (mid[1] / len) * bow, mid[2] + (mid[2] / len) * bow];
}

export function addLink(
  paths: PathBuffers,
  link: AtlasLink,
  source: AtlasNode,
  target: AtlasNode,
  birthTime: number,
) {
  paths.add(
    link.id,
    source.position,
    linkControl(source.position, target.position),
    target.position,
    REGION_RGB[REGION_BY_ID[source.region].index],
    REGION_RGB[REGION_BY_ID[target.region].index],
    0.35 + link.strength * 0.65,
    link.born,
    birthTime,
  );
}

/** Projection tracts: faint fibres fanning from the stem into every lobe. */
export function buildTracts(layout: BrainLayout): PathBuffers {
  const tracts = new PathBuffers(layout.tractTargets.length);
  const root = hexToRgb(REGION_BY_ID.personal.color);
  const rand = mulberry32(0x7ac7);
  layout.tractTargets.forEach((target, i) => {
    const [x, y, z] = target.position;
    const from: Vec3 = [-0.3 + (rand() - 0.5) * 0.1, -0.62, (rand() - 0.5) * 0.12];
    const control: Vec3 = [x * 0.3 - 0.2, y * 0.25 - 0.08, z * 0.55];
    // born at -1: the tracts are structure, present at every point on the timeline
    tracts.add(`tract-${i}`, from, control, target.position, root, REGION_RGB[target.region], 0.32, -1, ALWAYS);
  });
  return tracts;
}

/**
 * A coarse hull of the brain: its most extreme particle in each of `count`
 * directions. Projected each frame, it tells the label layout how far the
 * silhouette reaches in any screen direction, so labels can sit just outside it.
 */
export function buildHull(layout: BrainLayout, count = 56): Float32Array {
  const hull = new Float32Array(count * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let k = 0; k < count; k++) {
    // Fibonacci sphere: evenly spread directions
    const y = 1 - (k / (count - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const dx = Math.cos(golden * k) * r;
    const dz = Math.sin(golden * k) * r;
    let best = -Infinity;
    for (let i = 0; i < layout.count; i++) {
      if (layout.regions[i] > 6.5 || layout.born[i] > 1) continue; // skip dust and latent
      const d = layout.positions[i * 3] * dx + layout.positions[i * 3 + 1] * y + layout.positions[i * 3 + 2] * dz;
      if (d > best) {
        best = d;
        hull.set(layout.positions.subarray(i * 3, i * 3 + 3), k * 3);
      }
    }
  }
  return hull;
}

/** Two dotted rings beneath the brain — a quiet stage. */
export function buildRingGeometry() {
  const rings: [number, number][] = [[1.9, 150], [2.55, 220]];
  const total = rings.reduce((s, [, n]) => s + n, 0);
  const angle = new Float32Array(total);
  const radius = new Float32Array(total);
  const seed = new Float32Array(total);
  const rand = mulberry32(0x51a9e);
  let i = 0;
  for (const [r, n] of rings) {
    for (let k = 0; k < n; k++, i++) {
      angle[i] = (k / n) * Math.PI * 2;
      radius[i] = r;
      seed[i] = k % 12 === 0 ? 1 : rand() * 0.9;
    }
  }
  const geometry = new THREE.BufferGeometry();
  attr(geometry, "position", new Float32Array(total * 3), 3);
  attr(geometry, "aAngle", angle, 1);
  attr(geometry, "aRadius", radius, 1);
  attr(geometry, "aSeed", seed, 1);
  geometry.boundingSphere = BOUNDS;
  return geometry;
}
