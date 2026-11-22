// Cutting real track out of the MBTA line shapes (Traveled map, route drawing).
import { fc, ll, metres, pt } from './geo';
import type { Collection, Coord, LatLon } from './geo';
import type { Line } from './theme';

export interface ShapeProps { color: string; line: Line; route: string }
export type Shapes = Collection<GeoJSON.LineString, ShapeProps>;

/** The stretch of track between two stations, from the shape of `line` that passes closest to both. */
export function segment(shapes: Shapes, line: Line, a: LatLon, b: LatLon): { coords: Coord[]; miles: number } | null {
  let best: { err: number; coords: Coord[] } | null = null;
  for (const f of shapes.features) {
    if (f.properties.line !== line) continue;
    const c = f.geometry.coordinates as Coord[];
    const idx = (s: LatLon) => c.reduce((bi, p, i) => (metres(ll(p), s) < metres(ll(c[bi]), s) ? i : bi), 0);
    const ia = idx(a), ib = idx(b);
    const err = metres(ll(c[ia]), a) + metres(ll(c[ib]), b);
    if (!best || err < best.err) best = { err, coords: c.slice(Math.min(ia, ib), Math.max(ia, ib) + 1) };
  }
  if (!best || best.err > 600 || best.coords.length < 2) return null;
  let m = 0;
  for (let i = 1; i < best.coords.length; i++) m += metres(ll(best.coords[i - 1]), ll(best.coords[i]));
  return { coords: best.coords, miles: m / 1609.34 };
}

/** Track not ridden yet, as evenly spaced dots. Branches that share track share dots, so it never looks solid. */
export function dotted(shapes: Shapes, step = 140) {
  const kept: (LatLon & { line: Line; color: string })[] = [];
  for (const f of shapes.features) {
    const c = f.geometry.coordinates as Coord[];
    let carry = 0;
    for (let i = 1; i < c.length; i++) {
      const a = ll(c[i - 1]), b = ll(c[i]), d = metres(a, b);
      for (let t = step - carry; t < d; t += step) {
        const q = { lat: a.lat + ((b.lat - a.lat) * t) / d, lon: a.lon + ((b.lon - a.lon) * t) / d };
        if (!kept.some((k) => k.line === f.properties.line && Math.abs(k.lat - q.lat) < 0.0008 && metres(k, q) < step * 0.6)) {
          kept.push({ ...q, line: f.properties.line, color: f.properties.color });
        }
      }
      carry = (carry + d) % step;
    }
  }
  return fc(kept.map((k) => pt(k.lon, k.lat, { color: k.color })));
}
