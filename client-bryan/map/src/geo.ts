// Small geometry helpers shared by the maps, routing and ride verification.

export interface LatLon { lat: number; lon: number }
export type Coord = [number, number]; // [lon, lat], GeoJSON order

export interface Feature<G = GeoJSON.Geometry, P = Record<string, unknown>> { type: 'Feature'; geometry: G; properties: P }
export interface Collection<G = GeoJSON.Geometry, P = Record<string, unknown>> { type: 'FeatureCollection'; features: Feature<G, P>[] }

export const fc = <G, P>(features: Feature<G, P>[]): Collection<G, P> => ({ type: 'FeatureCollection', features });
export const pt = <P>(lon: number, lat: number, properties: P): Feature<GeoJSON.Point, P> =>
  ({ type: 'Feature', properties, geometry: { type: 'Point', coordinates: [lon, lat] } });
export const ll = ([lon, lat]: Coord | number[]): LatLon => ({ lat, lon });

/** Great-circle distance in metres. */
export function metres(a: LatLon, b: LatLon): number {
  const R = 6371000, t = Math.PI / 180;
  const dLat = (b.lat - a.lat) * t, dLon = (b.lon - a.lon) * t;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * t) * Math.cos(b.lat * t) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function nearest<T extends LatLon>(list: T[], p: LatLon): (T & { d: number }) | null {
  let best: (T & { d: number }) | null = null;
  for (const s of list) {
    const d = metres(p, s);
    if (!best || d < best.d) best = { ...s, d };
  }
  return best;
}

/** Google encoded polyline (MBTA shapes) to [lon, lat] pairs. */
export function decodePolyline(str: string): Coord[] {
  const pts: Coord[] = [];
  let i = 0, lat = 0, lon = 0;
  while (i < str.length) {
    for (const k of [0, 1]) {
      let shift = 0, res = 0, b: number;
      do { b = str.charCodeAt(i++) - 63; res |= (b & 31) << shift; shift += 5; } while (b >= 32);
      const v = res & 1 ? ~(res >> 1) : res >> 1;
      if (k === 0) lat += v; else lon += v;
    }
    pts.push([lon / 1e5, lat / 1e5]);
  }
  return pts;
}

/** A polygon approximating a circle of `m` metres around `c`. */
export function circle(c: LatLon, m: number, n = 64): Feature<GeoJSON.Polygon, Record<string, never>> {
  const ring: Coord[] = [];
  for (let k = 0; k <= n; k++) {
    const a = (k / n) * 2 * Math.PI;
    ring.push([c.lon + (m * Math.cos(a)) / (111320 * Math.cos((c.lat * Math.PI) / 180)), c.lat + (m * Math.sin(a)) / 110540]);
  }
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [ring] } };
}

/** [[west, south], [east, north]] around the points, or null with fewer than two. */
export function bounds(pts: LatLon[]): [Coord, Coord] | null {
  if (pts.length < 2) return null;
  const lons = pts.map((p) => p.lon), lats = pts.map((p) => p.lat);
  return [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
}
