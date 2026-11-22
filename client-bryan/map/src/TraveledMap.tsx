// Traveled map: the real T network, track you have ridden drawn solid, the rest dotted, and check pins on the
// landmarks and Freedom Trail sites you unlocked (within 500 m of a station you reached).
import type { MapMouseEvent } from 'maplibre-gl';
import { useEffect, useMemo, useState } from 'react';
import { loadGis, loadTransit } from './data';
import type { Gis, MapServices, Transit } from './data';
import { bounds, fc, ll, metres, pt } from './geo';
import { addIconic, declutter, iconicPopup } from './layers';
import { FONT, LINE_COLOR, LINES, P, lineOf } from './theme';
import type { Line } from './theme';
import { dotted, segment } from './track';
import { maplibre, useMapLibre } from './ui';

/** One ridden stretch. `route` takes an MBTA route id (data-platform /me/travel's route_id) or a line name. */
export interface RiddenSegment { route: string; from: string; to: string }
export interface UnlockedSpot { name: string; lat: number; lon: number; facts: number; stop: string }
export interface TraveledSummary { miles: Record<Line, number>; total: number; unlocked: UnlockedSpot[] }

const UNLOCK_M = 500;

export function summarize(t: Transit, g: Gis, segs: RiddenSegment[], reached: string[] = []) {
  const st = (id: string) => t.stations.find((s) => s.id === id);
  const ridden = segs.map((r) => {
    const line = lineOf(r.route);
    const a = st(r.from), b = st(r.to);
    return { line, seg: a && b && LINE_COLOR[line] ? segment(t.shapes, line, a, b) : null };
  }).filter((r) => r.seg);
  const miles = Object.fromEntries(LINES.map((l) => [l, 0])) as Record<Line, number>;
  for (const r of ridden) miles[r.line] += r.seg!.miles;
  const reachedSt = [...new Set([...reached, ...segs.flatMap((r) => [r.from, r.to])])].map(st).filter((s) => !!s);
  const pool = g.places.map((p) => ({ name: p.name, lat: p.lat, lon: p.lon, facts: (p.designated ? 1 : 0) + (p.blurb ? 1 : 0) || 1 }));
  const unlocked: UnlockedSpot[] = [];
  for (const p of pool) {
    const near = reachedSt.map((s) => ({ s, d: metres(s, p) })).sort((a, b) => a.d - b.d)[0];
    if (near && near.d < UNLOCK_M) unlocked.push({ ...p, stop: near.s.name });
  }
  return { ridden, reachedSt, summary: { miles, total: LINES.reduce((a, l) => a + miles[l], 0), unlocked } };
}

export function TraveledMap({ services, segments, reached, selected = 0, onSummary, onPickSpot, padding = { top: 230, bottom: 230, left: 50, right: 50 } }: {
  services: MapServices; segments: RiddenSegment[]; reached?: string[]; selected?: number;
  onSummary?: (s: TraveledSummary) => void; onPickSpot?: (index: number) => void;
  padding?: { top: number; bottom: number; left: number; right: number };
}) {
  const [data, setData] = useState<{ t: Transit; g: Gis } | null>(null);
  const [error, setError] = useState<string>();
  useEffect(() => {
    let live = true;
    Promise.all([loadTransit(services), loadGis()]).then(([t, g]) => live && setData({ t, g }), (e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [services.dp, services.mbta]); // eslint-disable-line react-hooks/exhaustive-deps
  const key = JSON.stringify([segments, reached]);
  const s = useMemo(() => (data ? summarize(data.t, data.g, segments, reached) : null), [data, key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (s) onSummary?.(s.summary); }, [s]); // eslint-disable-line react-hooks/exhaustive-deps

  const { ref, map, ready, error: mapError } = useMapLibre({ center: [-71.08, 42.36], zoom: 11.8, pitch: 30, bearing: -10, attributionControl: { compact: true, customAttribution: 'BPDA · MBTA' } });

  useEffect(() => {
    if (!map || !ready || !data || !s) return;
    const ids = ['ridden', 'ridden-under', 'st', 'st-labels', 'not-yet', 'iconic-3d', 'iconic-base'];
    for (const id of ids) if (map.getLayer(id)) map.removeLayer(id);
    for (const id of ['ridden', 'st', 'dots', 'iconic']) if (map.getSource(id)) map.removeSource(id);
    map.addSource('dots', { type: 'geojson', data: dotted(data.t.shapes, 140) });
    map.addLayer({ id: 'not-yet', type: 'circle', source: 'dots', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 1.8, 14, 3.5], 'circle-color': ['get', 'color'] } });
    map.addSource('ridden', { type: 'geojson', data: fc(s.ridden.map((r) => ({ type: 'Feature' as const, properties: { color: LINE_COLOR[r.line] }, geometry: { type: 'LineString' as const, coordinates: r.seg!.coords } }))) });
    map.addLayer({ id: 'ridden-under', type: 'line', source: 'ridden', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': P.navy, 'line-width': 11 } });
    map.addLayer({ id: 'ridden', type: 'line', source: 'ridden', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 7 } });
    addIconic(map, data.g);
    map.addSource('st', { type: 'geojson', data: fc(s.reachedSt.map((x) => pt(x.lon, x.lat, { name: x.name }))) });
    map.addLayer({ id: 'st', type: 'circle', source: 'st', paint: { 'circle-radius': 5, 'circle-color': '#fff', 'circle-stroke-color': P.navy, 'circle-stroke-width': 2.5 } });
    map.addLayer({ id: 'st-labels', type: 'symbol', source: 'st', layout: { 'text-field': ['get', 'name'], 'text-font': FONT, 'text-size': 10, 'text-offset': [0.8, 0], 'text-anchor': 'left' }, paint: { 'text-color': P.navy, 'text-halo-color': '#fff', 'text-halo-width': 1.6 } });
    const box = bounds([...s.reachedSt, ...s.ridden.flatMap((r) => r.seg!.coords.map(ll))]);
    if (box) map.fitBounds(box, { padding, maxZoom: 14.5, duration: 0 });
  }, [map, ready, data, s]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!map) return;
    const click = (e: MapMouseEvent) => { iconicPopup(map, e); };
    map.on('click', click);
    return () => { map.off('click', click); };
  }, [map]);

  useEffect(() => {
    if (!map || !s) return;
    const pins = s.summary.unlocked.map((u, j) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'tqm-check' + (j === selected ? ' sel' : '');
      b.setAttribute('aria-label', u.name);
      b.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg>`;
      b.onclick = (e) => { e.stopPropagation(); onPickSpot?.(j); };
      return new (maplibre()).Marker({ element: b }).setLngLat([u.lon, u.lat]).addTo(map);
    });
    const tidy = () => declutter(map, pins, selected, 30);
    map.on('moveend', tidy);
    tidy();
    return () => { map.off('moveend', tidy); pins.forEach((m) => m.remove()); };
  }, [map, s, selected]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="tqm-root">
      <div ref={ref} className="tqm-canvas" />
      {(error || mapError) && <div className="tqm-box tqm-msg" role="alert">Map unavailable: {error ?? mapError}</div>}
    </div>
  );
}
