/** Small deterministic math helpers for the Atlas — no dependencies. */

/** Seeded PRNG (mulberry32) — the brain must look identical on every load. */
export function mulberry32(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a — stable 32-bit hash of a string. */
export function hashString(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Deterministic 0–1 from a string plus a salt. */
export function hash01(value: string, salt = 0): number {
  return mulberry32(hashString(value) + salt * 7919)();
}

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function smoothstep(e0: number, e1: number, x: number): number {
  const t = clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
}

function lattice(ix: number, iy: number, iz: number): number {
  let h = Math.imul(ix, 374761393) ^ Math.imul(iy, 668265263) ^ Math.imul(iz, 1440662683);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

/** Smooth 3D value noise in [-1, 1]. Its zero-crossings draw the cortical folds. */
export function noise3(x: number, y: number, z: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const iz = Math.floor(z);
  const fx = x - ix;
  const fy = y - iy;
  const fz = z - iz;
  const ux = fx * fx * (3 - 2 * fx);
  const uy = fy * fy * (3 - 2 * fy);
  const uz = fz * fz * (3 - 2 * fz);
  const c000 = lattice(ix, iy, iz);
  const c100 = lattice(ix + 1, iy, iz);
  const c010 = lattice(ix, iy + 1, iz);
  const c110 = lattice(ix + 1, iy + 1, iz);
  const c001 = lattice(ix, iy, iz + 1);
  const c101 = lattice(ix + 1, iy, iz + 1);
  const c011 = lattice(ix, iy + 1, iz + 1);
  const c111 = lattice(ix + 1, iy + 1, iz + 1);
  const x00 = c000 + (c100 - c000) * ux;
  const x10 = c010 + (c110 - c010) * ux;
  const x01 = c001 + (c101 - c001) * ux;
  const x11 = c011 + (c111 - c011) * ux;
  const y0 = x00 + (x10 - x00) * uy;
  const y1 = x01 + (x11 - x01) * uy;
  return (y0 + (y1 - y0) * uz) * 2 - 1;
}

/** History fraction (0 = oldest) for a timestamp. Live arrivals pin to the end. */
export function bornAt(createdAt: number, origin: number, now: number): number {
  return Math.min(0.96, Math.max(0, ((createdAt - origin) / (now - origin)) * 0.96));
}
