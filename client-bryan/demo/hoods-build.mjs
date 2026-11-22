#!/usr/bin/env node
// Build public/data/ethnic.geojson: Ethnic Boston neighborhoods for the map.
//   Boundaries: City of Boston "Boston Neighborhood Boundaries" (BPDA, data.boston.gov)
//   Heritage notes and the "heart of the neighborhood" points: curated for the demo (check wording with Isabella, #45)
// node hoods-build.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = 'https://data.boston.gov/dataset/bf1a7b50-4c72-4637-b0fa-11d632e3aff1/resource/e5849875-a6f6-4c9c-9d8a-5048b0fbd03e/download/boston_neighborhood_boundaries.geojson';
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public', 'data', 'ethnic.geojson');

// pastel fills from the canvas palette, lightened
const HOODS = {
  Chinatown: { heritage: 'Chinese & Southeast Asian', color: '#F8C8DC', heart: 'Chinatown Gate', hub: [-71.0606, 42.3513],
    blurb: 'New England’s largest Chinatown, home to Chinese, Vietnamese and other Asian American communities since the 1870s.' },
  'North End': { heritage: 'Italian', color: '#D5EDC8', heart: 'Hanover Street', hub: [-71.0545, 42.3637],
    blurb: 'Boston’s oldest neighborhood and its Little Italy, shaped by Italian immigrants since the late 1800s.' },
  'East Boston': { heritage: 'Latin American', color: '#FFE7A0', heart: 'Maverick Square', hub: [-71.0395, 42.3691],
    blurb: 'Home to one of Boston’s largest Latino communities, with Salvadoran, Colombian and other Latin American spots around Maverick and Central Squares.' },
  'Jamaica Plain': { heritage: 'Latin Quarter', color: '#FBD3B5', heart: 'Hyde Square', hub: [-71.1090, 42.3215],
    blurb: 'Hyde Square is Boston’s Latin Quarter, a state-designated cultural district with Dominican, Puerto Rican and Cuban roots.' },
  Roxbury: { heritage: 'Black Boston', color: '#DCCFEF', heart: 'Nubian Square', hub: [-71.0838, 42.3294],
    blurb: 'The heart of Black Boston. Nubian Square is a center of African American, Caribbean and African community life.' },
  Dorchester: { heritage: 'Vietnamese, Cape Verdean & more', color: '#CDE8EA', heart: 'Fields Corner', hub: [-71.0617, 42.3002],
    blurb: 'Fields Corner is Boston’s Little Saigon, a state-designated cultural district. Dorchester is also home to large Cape Verdean, Haitian and Irish communities.' },
  Mattapan: { heritage: 'Haitian & Caribbean', color: '#F6D6E8', heart: 'Mattapan Square', hub: [-71.0922, 42.2677],
    blurb: 'Home to a large Haitian and Caribbean community, with bakeries and restaurants around Mattapan Square.' },
  'South Boston': { heritage: 'Irish', color: '#E2F0C4', heart: 'West Broadway', hub: [-71.0493, 42.3351],
    blurb: 'Historically the center of Irish Boston and home of the city’s St. Patrick’s Day parade.' },
  Allston: { heritage: 'Korean & Brazilian', color: '#D9E4F5', heart: 'Brighton & Harvard Aves', hub: [-71.1316, 42.3529],
    blurb: 'A student hub with Korean, Brazilian and other international restaurants along Brighton and Harvard Avenues.' },
};

const round = (c) => (typeof c[0] === 'number' ? [Math.round(c[0] * 1e5) / 1e5, Math.round(c[1] * 1e5) / 1e5] : c.map(round));
const src = await (await fetch(SRC)).json();
const features = src.features.filter((f) => HOODS[f.properties.name]).map((f) => ({
  type: 'Feature', geometry: { type: f.geometry.type, coordinates: round(f.geometry.coordinates) },
  properties: { name: f.properties.name, ...HOODS[f.properties.name] },
}));
const missing = Object.keys(HOODS).filter((n) => !features.some((f) => f.properties.name === n));
if (missing.length) console.warn('not found in city data:', missing.join(', '));
mkdirSync(path.dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ type: 'FeatureCollection', features, attribution: 'Neighborhood boundaries: City of Boston / BPDA (data.boston.gov)' }));
console.log(`${features.length} neighborhoods -> ${path.relative(process.cwd(), OUT)} (${Math.round(JSON.stringify(features).length / 1024)} KB)`);
