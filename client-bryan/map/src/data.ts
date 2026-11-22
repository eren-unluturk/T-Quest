// Data the maps need, loaded once per page and shared by every map.
//   data-platform (Tiger Data): stations per subway route, live vehicles
//   MBTA V3 API (public, CORS-enabled): line shapes, route patterns, schedules
//   data/*.geojson: Boston GIS extracts (built by client-bryan/demo/gis-build.mjs and hoods-build.mjs)
import iconicUrl from '../data/iconic.geojson?url';
import ethnicUrl from '../data/ethnic.geojson?url';
import { decodePolyline, fc, pt } from './geo';
import type { Collection, Coord } from './geo';
import { buildNetwork } from './network';
import type { Network, RoutePatternsResponse } from './network';
import { LINE_COLOR, SUBWAY, lineOf, routesOf } from './theme';
import type { Line } from './theme';
import type { Shapes } from './track';
import { scheduleWindow, tripsFromSchedules } from './verify';
import type { SchedulesResponse, Station, Trip } from './verify';

export interface MapServices {
  /** data-platform base URL, e.g. the web app's cfg.dp ("/api/dp" in dev). */
  dp: string;
  /** MBTA V3 API base. Defaults to the public API. */
  mbta?: string;
}

export interface Vehicle { vehicle_id: string; route_id: string | null; lat: number | null; lon: number | null; label?: string | null }
export interface IconicProps { name: string; category: 'trail' | 'landmark' | 'skyline'; height_m: number; height_ft: number; place_height_ft?: number; designated?: string | null; blurb?: string | null }
export interface Place extends IconicProps { lat: number; lon: number }
export interface HoodProps { name: string; heritage: string; color: string; heart: string; hub: Coord; blurb: string }
/** `mbtaError` is set when the MBTA API failed (it allows 20 requests a minute without a key): lines and directions are missing. */
export interface Transit { stations: Station[]; shapes: Shapes; net: Network; mbtaError?: string }
export interface Gis { iconic: Collection<GeoJSON.Polygon, IconicProps>; places: Place[]; ethnic: Collection<GeoJSON.Polygon | GeoJSON.MultiPolygon, HoodProps> }

const MBTA = 'https://api-v3.mbta.com';
const json = async <T>(url: string): Promise<T> => {
  const r = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${new URL(url, location.href).host}: HTTP ${r.status}`);
  return r.json() as Promise<T>;
};
const mbtaBase = (s: MapServices) => (s.mbta ?? MBTA).replace(/\/+$/, '');

// Line shapes and route patterns change a few times a year: keep them a day, so reloads stay under the MBTA rate limit
const DAY_MS = 24 * 3600000;
async function cachedJson<T>(url: string): Promise<T> {
  const key = 'tqm.cache:' + url;
  try {
    const hit = JSON.parse(localStorage.getItem(key) ?? 'null') as { at: number; v: T } | null;
    if (hit && Date.now() - hit.at < DAY_MS) return hit.v;
  } catch { /* no storage, or a bad entry */ }
  const v = await json<T>(url);
  try { localStorage.setItem(key, JSON.stringify({ at: Date.now(), v })); } catch { /* full or private mode: just skip the cache */ }
  return v;
}

let transit: Promise<Transit> | null = null;
let gis: Promise<Gis> | null = null;

/** Stations, line shapes and the routing graph. Cached for the page's lifetime. */
export function loadTransit(s: MapServices): Promise<Transit> {
  transit ??= (async () => {
    const byId: Record<string, Station> = {};
    await Promise.all(SUBWAY.map(async (rid) => {
      const stops = await json<{ id: string; name: string; lat: number; lon: number }[]>(`${s.dp}/stops?route_id=${rid}&limit=500`);
      for (const st of stops) {
        const x = (byId[st.id] ||= { id: st.id, name: st.name, lat: st.lat, lon: st.lon, lines: [] });
        if (!x.lines.includes(lineOf(rid))) x.lines.push(lineOf(rid));
      }
    }));
    const base = mbtaBase(s);
    const features: Shapes['features'] = [];
    let net: Network = {};
    let mbtaError: string | undefined;
    // the map still works from data-platform alone when the MBTA API is down or rate limited
    try {
      const shapeRes = await Promise.all(SUBWAY.map((rid) =>
        cachedJson<{ data?: { attributes: { polyline: string } }[] }>(`${base}/shapes?filter[route]=${rid}&fields[shape]=polyline`).then((r) => ({ rid, r }))));
      for (const { rid, r } of shapeRes) {
        const longest = (r.data ?? []).sort((a, b) => b.attributes.polyline.length - a.attributes.polyline.length).slice(0, 2);
        for (const sh of longest) {
          features.push({ type: 'Feature', properties: { color: LINE_COLOR[lineOf(rid)], line: lineOf(rid), route: rid }, geometry: { type: 'LineString', coordinates: decodePolyline(sh.attributes.polyline) } });
        }
      }
      const patterns = await cachedJson<RoutePatternsResponse>(`${base}/route_patterns?filter[route]=${SUBWAY.join(',')}&filter[direction_id]=0&include=representative_trip.stops&fields[stop]=name,parent_station&fields[route_pattern]=typicality&fields[trip]=headsign`);
      net = buildNetwork(patterns, (id) => byId[id]?.name ?? id);
    } catch (e) {
      mbtaError = (e as Error).message;
      transit = null; // try the MBTA again next time a map opens
    }
    return { stations: Object.values(byId), shapes: fc(features), net, mbtaError };
  })().catch((e) => { transit = null; throw e; });
  return transit;
}

/** 3D landmarks and Ethnic Boston neighborhoods (static GIS extracts). */
export function loadGis(): Promise<Gis> {
  gis ??= (async () => {
    const [iconic, ethnic] = await Promise.all([json<Gis['iconic']>(iconicUrl), json<Gis['ethnic']>(ethnicUrl)]);
    const tallest: Record<string, Gis['iconic']['features'][number]> = {};
    for (const f of iconic.features) {
      const p = f.properties;
      if (!tallest[p.name] || p.height_m > tallest[p.name].properties.height_m) tallest[p.name] = f;
    }
    // one point per place (at its tallest part), and every part reports the place's full height
    const places = Object.values(tallest).map((f) => {
      const ring = f.geometry.coordinates[0];
      const [lon, lat] = ring.reduce((a, p) => [a[0] + p[0] / ring.length, a[1] + p[1] / ring.length], [0, 0]);
      return { ...f.properties, lon, lat };
    });
    for (const f of iconic.features) f.properties.place_height_ft = tallest[f.properties.name].properties.height_ft;
    return { iconic, places, ethnic };
  })().catch((e) => { gis = null; throw e; });
  return gis;
}

export async function loadVehicles(s: MapServices): Promise<Vehicle[]> {
  const all = await Promise.all(SUBWAY.map((rid) => json<Vehicle[]>(`${s.dp}/vehicles?route_id=${rid}`).catch(() => [] as Vehicle[])));
  return all.flat().filter((v) => v.lat != null && v.lon != null && v.route_id);
}

/** Real scheduled trips on `line` from station a to b between two times. */
export async function scheduledTrips(s: MapServices, a: string, b: string, line: Line, from: number, to: number): Promise<Trip[]> {
  const w = scheduleWindow(from, to);
  const res = await json<SchedulesResponse>(`${mbtaBase(s)}/schedules?filter[stop]=${a},${b}&filter[route]=${routesOf(line).join(',')}&filter[min_time]=${w.min}&filter[max_time]=${w.max}&include=stop&fields[schedule]=arrival_time,departure_time,stop_sequence&fields[stop]=parent_station`);
  return tripsFromSchedules(res, a, b);
}

export const hubPoints = (g: Gis) => fc(g.ethnic.features.map((f) => pt(f.properties.hub[0], f.properties.hub[1], { label: `${f.properties.name}\n${f.properties.heritage}` })));
