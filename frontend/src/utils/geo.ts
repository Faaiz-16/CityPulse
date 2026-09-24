/** Small geometry helpers for map visuals (no dependencies). */

export type LatLon = [number, number];

/** Ray casting: is the point inside the polygon ring? */
export function pointInRing([lat, lon]: LatLon, ring: LatLon[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [lat1, lon1] = ring[i];
    const [lat2, lon2] = ring[j];
    if (lon1 > lon !== lon2 > lon && lat < ((lat2 - lat1) * (lon - lon1)) / (lon2 - lon1) + lat1) inside = !inside;
  }
  return inside;
}

/** Deterministic pseudo-random numbers, so visual scatter doesn't jump on every refresh. */
export function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** `count` stable points scattered inside a ring, clustered towards `center`. */
export function scatterInRing(ring: LatLon[], center: LatLon, count: number, seed: number, spread = 0.035): LatLon[] {
  const rand = seeded(seed);
  const out: LatLon[] = [];
  let guard = 0;
  while (out.length < count && guard++ < count * 40) {
    // Box–Muller for a soft, rain-cell-like cluster
    const r = Math.sqrt(-2 * Math.log(rand() + 1e-9)) * spread * 0.55;
    const a = rand() * Math.PI * 2;
    const p: LatLon = [center[0] + r * Math.cos(a) * 0.8, center[1] + r * Math.sin(a)];
    if (pointInRing(p, ring)) out.push(p);
  }
  return out;
}
