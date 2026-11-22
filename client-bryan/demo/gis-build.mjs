#!/usr/bin/env node
// Build public/data/iconic.geojson: real footprints + heights of Boston's iconic buildings.
//   Footprints/heights: BPDA Building Roofprints (gis.bostonplans.org)
//   Which buildings:    Freedom Trail sites (insights-sponsors), Boston Landmarks Commission
//                       designations (gisportal.boston.gov), and the two skyline towers.
// node gis-build.mjs   (needs insights-sponsors on :8002)
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOF = 'https://gis.bostonplans.org/hosting/rest/services/Boston_Building_Roofprints/FeatureServer/15/query';
const LANDMARKS = 'https://gisportal.boston.gov/arcgis/rest/services/Historic_Districts_Landmarks_Viewing/FeatureServer/0/query';
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public', 'data', 'iconic.geojson');
const FIELDS = 'OBJECTID,BLD_ID,Name,Address,Bld_Height_Ft,Bld_Use';

// Landmarks Commission designations we treat as iconic (matched against common_name)
const ICONIC_LANDMARKS = ['Faneuil Hall', 'Old North Church', 'Old South Meeting House', 'Old Corner Bookstore', 'Boston City Hall',
  'U.S. Custom House', 'Trinity Church', 'Fenway Park', 'Parker House', 'Arlington Street Church', 'Copley Plaza Hotel',
  'Federal Reserve Bank', 'Keith Memorial', 'Old State House', 'Park Street Church', "King's Chapel", 'Ames Building',
  'Symphony Hall', 'Boston Public Library', 'Massachusetts Historical Society', 'Horticultural Hall'];
// (Filene's is left out: its landmark parcel now holds Millennium Tower, which would read as a 675 ft "Filene's")
// Freedom Trail stops that are buildings, looked up by BPDA's own names (the seed coordinates are too
// coarse for a point query). Park Street Church's sanctuary and steeple are filed under 119 Tremont St.
// Graves, open space, the ship and Bunker Hill Monument are not in the building layer.
const TRAIL_BUILDINGS = {
  'Massachusetts State House': "Name = 'State House'",
  'Park Street Church': "Name = 'Park Street Church' OR Address LIKE '119 Tremont St%'",
  "King's Chapel and Burying Ground": "Name = 'King''s Chapel'",
  'Old Corner Bookstore': "Name = 'Old Corner Bookstore'",
  'Old South Meeting House': "Name = 'Old South Meeting House'",
  'Old State House': "Name = 'Old State House'",
  'Faneuil Hall': "Name = 'Faneuil Hall'",
  'Paul Revere House': "Name = 'Paul Revere House'",
  'Old North Church': "Name = 'Old North Church'",
};
const SKYLINE = ['John Hancock Tower', 'Prudential Center and Tower'];

async function arcgis(url, params) {
  const body = new URLSearchParams({ f: 'json', outSR: '4326', geometryPrecision: '6', ...params });
  for (let attempt = 1; ; attempt++) {
    const r = await fetch(url, { method: 'POST', body });
    const j = await r.json();
    if (!j.error) return j.features || [];
    if (attempt === 3) throw new Error(`${url}: ${JSON.stringify(j.error)}`);
  }
}
const toGeo = (f) => ({ type: 'Polygon', coordinates: f.geometry.rings });
const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z]/g, '');
const centroid = (f) => { const r = f.geometry.rings[0]; return r.reduce((a, p) => [a[0] + p[0] / r.length, a[1] + p[1] / r.length], [0, 0]); };
function inside([x, y], rings) {
  let hit = false;
  for (const ring of rings) for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

const byId = new Map(); // keyed by roof part: big buildings have many parts under one BLD_ID
function add(f, props) {
  const id = f.attributes.OBJECTID;
  const prev = byId.get(id);
  // a building can be both a Freedom Trail stop and a landmark; the trail label wins, sources accumulate
  if (prev) { prev.properties.sources = [...new Set([...prev.properties.sources, ...props.sources])]; return; }
  byId.set(id, { type: 'Feature', geometry: toGeo(f), properties: {
    id, building: f.attributes.BLD_ID, name: props.name, category: props.category, sources: props.sources, blurb: props.blurb || null,
    designated: props.designated || null, address: f.attributes.Address, use: f.attributes.Bld_Use,
    height_ft: Math.round(f.attributes.Bld_Height_Ft || 0), height_m: Math.round((f.attributes.Bld_Height_Ft || 0) * 0.3048 * 10) / 10 } });
}

// 1. Freedom Trail stops (names and blurbs from insights-sponsors)
const trail = await (await fetch('http://localhost:8002/freedom-trail', { headers: { authorization: 'Bearer bryan' } })).json();
for (const t of trail.filter((t) => TRAIL_BUILDINGS[t.name])) {
  const parts = await arcgis(ROOF, { where: TRAIL_BUILDINGS[t.name], outFields: FIELDS });
  for (const f of parts) add(f, { name: t.name.replace(' and Burying Ground', ''), category: 'trail', sources: ['Freedom Trail'], blurb: t.blurb });
  console.log(`trail     ${t.name.padEnd(34)} ${parts.length} part(s), tallest ${Math.round(Math.max(0, ...parts.map((f) => f.attributes.Bld_Height_Ft)))} ft`);
}

// 2. Boston Landmarks Commission: buildings inside each iconic designation's boundary
const landmarks = await arcgis(LANDMARKS, { where: "status LIKE '%Landmark%'", outFields: 'common_name,status,date_designated_1' });
for (const lm of landmarks) {
  const name = lm.attributes.common_name?.trim();
  const match = ICONIC_LANDMARKS.find((k) => norm(name).startsWith(norm(k)));
  if (!match || (/branch/i.test(name) && !/main branch/i.test(name))) continue; // main library only, not neighbourhood branches
  const parts = await arcgis(ROOF, { geometry: JSON.stringify({ rings: lm.geometry.rings, spatialReference: { wkid: 4326 } }),
    geometryType: 'esriGeometryPolygon', inSR: '4326', spatialRel: 'esriSpatialRelIntersects', outFields: FIELDS })
    .then((fs) => fs.filter((f) => inside(centroid(f), lm.geometry.rings))); // drop neighbours that only touch the boundary
  const designated = lm.attributes.date_designated_1 ? new Date(lm.attributes.date_designated_1).getFullYear() : null;
  for (const f of parts) add(f, { name: match, category: 'landmark', sources: [`Boston Landmark (${lm.attributes.status.replace(' Landmark', '').toLowerCase()})`], designated });
  console.log(`landmark  ${match.padEnd(34)} ${parts.length} part(s)`);
}

// 3. Skyline towers, by the name BPDA gives them
for (const name of SKYLINE) {
  const parts = await arcgis(ROOF, { where: `Name = '${name}'`, outFields: FIELDS });
  for (const f of parts) add(f, { name: name.replace(' Center and Tower', ' Tower'), category: 'skyline', sources: ['Boston skyline'] });
  console.log(`skyline   ${name.padEnd(34)} ${parts.length} part(s)`);
}

const fc = { type: 'FeatureCollection', features: [...byId.values()], generated: new Date().toISOString(),
  attribution: 'Footprints and heights: BPDA Building Roofprints. Landmarks: Boston Landmarks Commission. Freedom Trail: insights-sponsors.' };
mkdirSync(path.dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(fc));
const names = new Set(fc.features.map((f) => f.properties.name));
console.log(`\n${fc.features.length} building parts, ${names.size} iconic places -> ${path.relative(process.cwd(), OUT)} (${Math.round(JSON.stringify(fc).length / 1024)} KB)`);
