/** Small geometry helpers for map visuals (no dependencies). */

export type LatLon = [number, number];

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

/** `count` stable points scattered inside a (grid-cell) rectangle, kept off its edges. */
export function scatterInRect(ring: LatLon[], count: number, seed: number): LatLon[] {
  const lats = ring.map((p) => p[0]), lons = ring.map((p) => p[1]);
  const [s, n, w, e] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const rand = seeded(seed);
  return Array.from({ length: count }, () => [
    s + (n - s) * (0.08 + 0.84 * rand()),
    w + (e - w) * (0.08 + 0.84 * rand()),
  ] as LatLon);
}
