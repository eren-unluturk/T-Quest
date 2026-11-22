// MapLibre layers in Isabella's palette.
import type { GeoJSONSource, Map as MlMap, MapMouseEvent, Marker } from 'maplibre-gl';
import type { Gis, Vehicle } from './data';
import { hubPoints } from './data';
import { bounds, fc, ll, pt } from './geo';
import type { LatLon } from './geo';
import type { TRoute } from './network';
import { FONT, ICON_COLOR, LINE_COLOR, P, lineOf } from './theme';
import { segment } from './track';
import { maplibre } from './ui';
import type { Shapes } from './track';
import type { Station } from './verify';

const set = (map: MlMap, id: string, prop: string, v: unknown) => { try { map.setPaintProperty(id, prop, v); } catch { /* layer lacks the property */ } };

/** Recolors the OpenFreeMap basemap to the canvas palette and hides its POIs. */
export function paintCanvas(map: MlMap) {
  // keep the credits behind the (i) button so they don't cover a small map card
  map.getContainer().querySelectorAll('.maplibregl-compact-show').forEach((e) => e.classList.remove('maplibregl-compact-show'));
  for (const l of map.getStyle().layers) {
    const id = l.id;
    if (l.type === 'background') set(map, id, 'background-color', P.land);
    else if (l.type === 'fill') {
      if (/water/.test(id)) set(map, id, 'fill-color', P.water);
      else if (/park|grass|wood|forest|cemetery|pitch|landcover/.test(id)) { set(map, id, 'fill-color', P.park); set(map, id, 'fill-opacity', 0.75); }
      else if (/building/.test(id)) { set(map, id, 'fill-color', '#E8DCC6'); set(map, id, 'fill-outline-color', '#D9CBB2'); }
      else set(map, id, 'fill-color', P.land);
    } else if (l.type === 'line') {
      if (/water|river/.test(id)) set(map, id, 'line-color', P.water);
      else if (/casing|outline/.test(id)) set(map, id, 'line-color', '#E2D5BF');
      else if (/road|highway|street|bridge|tunnel|path|motorway|trunk|primary|secondary|tertiary|minor|service/.test(id)) set(map, id, 'line-color', '#FFFFFF');
      else if (/rail/.test(id)) set(map, id, 'line-opacity', 0.25);
    } else if (l.type === 'symbol') {
      set(map, id, 'text-color', /water/.test(id) ? P.steel : '#5B6B80');
      set(map, id, 'text-halo-color', P.land);
      if (/poi/.test(id)) map.setLayoutProperty(id, 'visibility', 'none');
    }
  }
}

export function addLines(map: MlMap, shapes: Shapes) {
  map.addSource('lines', { type: 'geojson', data: shapes });
  map.addLayer({ id: 'lines', type: 'line', source: 'lines', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 3, 16, 7], 'line-opacity': 0.9 } });
}

/** BPDA roofprints extruded to their real height, rising from the flat city once the map has drawn. */
export function addIconic(map: MlMap, gis: Gis) {
  map.addSource('iconic', { type: 'geojson', data: gis.iconic });
  map.addLayer({ id: 'iconic-base', type: 'line', source: 'iconic', paint: { 'line-color': P.navy, 'line-width': 1.5 } });
  map.addLayer({ id: 'iconic-3d', type: 'fill-extrusion', source: 'iconic',
    paint: { 'fill-extrusion-color': ['match', ['get', 'category'], 'trail', ICON_COLOR.trail, 'skyline', ICON_COLOR.skyline, ICON_COLOR.landmark],
      'fill-extrusion-height': 0, 'fill-extrusion-opacity': 0.95, 'fill-extrusion-vertical-gradient': true } });
  map.once('idle', () => {
    map.setPaintProperty('iconic-3d', 'fill-extrusion-height-transition', { duration: 1400, delay: 0 });
    map.setPaintProperty('iconic-3d', 'fill-extrusion-height', ['get', 'height_m']);
  });
}

export function addStations(map: MlMap, stations: Station[], id = 'stations', minLabelZoom = 12.5) {
  map.addSource(id, { type: 'geojson', data: fc(stations.map((s) => pt(s.lon, s.lat, { name: s.name, id: s.id }))) });
  map.addLayer({ id, type: 'circle', source: id,
    paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2.5, 16, 6], 'circle-color': '#fff', 'circle-stroke-color': P.navy, 'circle-stroke-width': 2.5 } });
  map.addLayer({ id: id + '-labels', type: 'symbol', source: id, minzoom: minLabelZoom,
    layout: { 'text-field': ['get', 'name'], 'text-font': FONT, 'text-size': 10, 'text-offset': [0.8, 0], 'text-anchor': 'left' },
    paint: { 'text-color': P.navy, 'text-halo-color': '#fff', 'text-halo-width': 1.6 } });
}

const vehicleData = (vs: Vehicle[]) => fc(vs.map((v) => pt(v.lon!, v.lat!, { color: LINE_COLOR[lineOf(v.route_id!)] })));
export function addVehicles(map: MlMap, vs: Vehicle[]) {
  map.addSource('vehicles', { type: 'geojson', data: vehicleData(vs) });
  map.addLayer({ id: 'vehicles', type: 'circle', source: 'vehicles', paint: { 'circle-radius': 5, 'circle-color': ['get', 'color'], 'circle-stroke-color': P.navy, 'circle-stroke-width': 2 } });
}
export const setVehicles = (map: MlMap, vs: Vehicle[]) => (map.getSource('vehicles') as GeoJSONSource | undefined)?.setData(vehicleData(vs));

export const ETHNIC_LAYERS = ['ethnic-fill', 'ethnic-line', 'ethnic-labels'];
/** Ethnic Boston: pastel neighborhood fills with a dashed edge and a label at each neighborhood's heart. */
export function addEthnic(map: MlMap, gis: Gis, on: boolean) {
  const visibility = on ? 'visible' : 'none';
  map.addSource('ethnic', { type: 'geojson', data: gis.ethnic });
  map.addLayer({ id: 'ethnic-fill', type: 'fill', source: 'ethnic', layout: { visibility }, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.55 } });
  map.addLayer({ id: 'ethnic-line', type: 'line', source: 'ethnic', layout: { visibility }, paint: { 'line-color': P.navy, 'line-width': 1.5, 'line-dasharray': [3, 2], 'line-opacity': 0.7 } });
  map.addSource('ethnic-hubs', { type: 'geojson', data: hubPoints(gis) });
  map.addLayer({ id: 'ethnic-labels', type: 'symbol', source: 'ethnic-hubs',
    layout: { visibility, 'text-field': ['get', 'label'], 'text-font': FONT, 'text-size': 11, 'text-max-width': 9, 'text-line-height': 1.15 },
    paint: { 'text-color': P.navy, 'text-halo-color': '#fff', 'text-halo-width': 2 } });
}
export function showEthnic(map: MlMap, on: boolean) {
  for (const id of ETHNIC_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
}

const ROUTE_LAYERS = ['route-walk', 'route', 'route-under', 'route-stops'];
export function clearRoute(map: MlMap) {
  for (const id of ROUTE_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of ['route', 'route-walk', 'route-stops']) if (map.getSource(id)) map.removeSource(id);
}

/** T legs on real track (navy casing), a dotted walk to the destination, yellow stops, then fit the view. */
export function drawRoute(map: MlMap, shapes: Shapes, station: (id: string) => Station | undefined, r: TRoute, dest: LatLon, hub: LatLon) {
  clearRoute(map);
  const legs = r.legs.map((l) => {
    const a = station(l.from), b = station(l.to);
    return { l, seg: a && b ? segment(shapes, lineOf(l.route), a, b) : null };
  }).filter((x) => x.seg);
  map.addSource('route', { type: 'geojson', data: fc(legs.map(({ l, seg }) => ({ type: 'Feature' as const, properties: { color: LINE_COLOR[lineOf(l.route)] }, geometry: { type: 'LineString' as const, coordinates: seg!.coords } }))) });
  map.addLayer({ id: 'route-under', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': P.navy, 'line-width': 11 } });
  map.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 7 } });
  map.addSource('route-walk', { type: 'geojson', data: fc([{ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: [[dest.lon, dest.lat], [hub.lon, hub.lat]] } }]) });
  map.addLayer({ id: 'route-walk', type: 'line', source: 'route-walk', paint: { 'line-color': P.navy, 'line-width': 3, 'line-dasharray': [1, 1.5] } });
  const ends = [...r.legs.flatMap((l) => [station(l.from), station(l.to)]), hub].filter((p): p is LatLon => !!p);
  map.addSource('route-stops', { type: 'geojson', data: fc(ends.map((p) => pt(p.lon, p.lat, {}))) });
  map.addLayer({ id: 'route-stops', type: 'circle', source: 'route-stops', paint: { 'circle-radius': 6, 'circle-color': P.yellow, 'circle-stroke-color': P.navy, 'circle-stroke-width': 2.5 } });
  const box = bounds([...legs.flatMap(({ seg }) => seg!.coords.map(ll)), dest, hub]);
  if (box) map.fitBounds(box, { padding: { top: 60, bottom: 50, left: 40, right: 40 }, maxZoom: 15, pitch: 30, duration: 900 });
}

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));

/** Card for a tapped 3D landmark. Returns false when the tap missed every landmark. */
export function iconicPopup(map: MlMap, e: MapMouseEvent): boolean {
  const hit = map.getLayer('iconic-3d') && map.queryRenderedFeatures(e.point, { layers: ['iconic-3d'] })[0];
  if (!hit) return false;
  const p = hit.properties as Record<string, unknown>;
  const kind = p.category === 'trail' ? 'Freedom Trail' : p.category === 'skyline' ? 'Boston skyline' : 'Boston Landmark';
  const has = (v: unknown) => v != null && v !== 'null' && v !== '';
  new (maplibre()).Popup({ closeButton: false, maxWidth: '230px', offset: 6, className: 'tqm-popup' }).setLngLat(e.lngLat).setHTML(
    `<div class="tqm-icard"><span class="tqm-hand" style="font-size:17px;color:${p.category === 'trail' ? P.red : P.steel}">${kind}${has(p.designated) ? ` since ${esc(p.designated)}` : ''}</span>
     <b>${esc(p.name)}</b><span style="font-size:12px;font-weight:700">${esc(p.place_height_ft)} ft tall</span>
     ${has(p.blurb) ? `<p>${esc(p.blurb)}</p>` : ''}<div class="tqm-src">BPDA Building Roofprints${kind === 'Boston Landmark' ? ' · Boston Landmarks Commission' : ''}</div></div>`).addTo(map);
  return true;
}

/** Hides markers that would overlap on screen, keeping earlier (more important) ones and the selected one. */
export function declutter(map: MlMap, list: Marker[], keep: number, px = 30) {
  const shown: { x: number; y: number }[] = [];
  list.forEach((m, i) => {
    const p = map.project(m.getLngLat());
    const clash = i !== keep && shown.some((q) => Math.hypot(q.x - p.x, q.y - p.y) < px);
    m.getElement().style.visibility = clash ? 'hidden' : '';
    if (!clash) shown.push(p);
  });
}
