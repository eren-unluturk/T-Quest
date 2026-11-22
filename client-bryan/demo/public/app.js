// T-Quest demo client. Layout, copy and colors follow Isabella's approved canvas (design/canvas/*.dc.html).
// The two maps (Home, Traveled) are rebuilt from real GIS data, as design/canvas/README.md asks:
//   basemap OpenFreeMap (OSM) recolored to the canvas palette, MBTA line shapes, live trains,
//   and Boston's iconic buildings extruded from BPDA roofprints (public/data/iconic.geojson, gis-build.mjs).
// Data:
//   /api/dp  data-platform (Tiger Data: stations, live vehicles)
//   /api/is  insights-sponsors (fun facts, stop facts with sources, Freedom Trail, consent)
//   /api/ge  game-engine (check-ins, points, rank, collection)
//   /mbta    public MBTA V3 API via server.mjs (shapes, schedules for ride verification)

const USER = 'bryan';
const ZONE_M = 75;
const MAX_TRAIN_KMH = 80; // faster than any T train: a teleport, not a ride
const SUBWAY = ['Red', 'Mattapan', 'Orange', 'Blue', 'Green-B', 'Green-C', 'Green-D', 'Green-E'];
const LINE = { Red: '#DA291C', Mattapan: '#DA291C', Orange: '#ED8B00', Blue: '#003DA5', Green: '#00843D' };
const lineOf = (routeId) => (routeId.startsWith('Green') ? 'Green' : routeId === 'Mattapan' ? 'Red' : routeId);
const routesOf = (line) => SUBWAY.filter((r) => lineOf(r) === line);
// game-engine's memory mode ships its own stop ids; translate MBTA parent-station ids for the demo
const GE_ALIAS = { 'place-pktrm': 'park', 'place-dwnxg': 'downtown', 'place-harsq': 'harvard', 'place-alfcl': 'alewife', 'place-sstat': 'south-station' };
// canvas palette, applied to the GIS basemap and the 3D landmarks
const P = { navy: '#1D3557', cream: '#FFF8EC', red: '#E63946', yellow: '#FFC93C', pink: '#F4A6C6', lblue: '#A8DADC', steel: '#457B9D', lgreen: '#B8E0A8', land: '#F3EBDD', park: '#A8D5A2', water: '#A8DADC' };
const ICON_COLOR = { trail: P.red, landmark: P.yellow, skyline: P.lblue };
const PIN_COLOR = { station: P.red, trail: P.pink, landmark: P.lblue, skyline: P.lgreen };
const STAR = 'M12 2.8l2.8 5.8 6.3.9-4.6 4.4 1.1 6.3L12 17.2l-5.6 3 1.1-6.3L2.9 9.5l6.3-.9z';

const S = {
  pos: { lat: 42.35618, lon: -71.06212 }, // demo rider, ~30 m from Park Street
  stations: [], shapes: null, vehicles: [], iconic: null, places: [], trail: [], funFacts: [],
  geMemory: true, consent: { location: false }, policy: null, ready: false,
  timers: [], map: null, markers: [], ride: null, factCache: {},
};

// ---------- small persistence for demo-only state (faves, verified rides)
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem('tq.' + k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem('tq.' + k, JSON.stringify(v)); } catch {} },
};
// sample history so Traveled has something to draw before your first verified ride (marked as sample)
const SAMPLE_RIDES = [
  { from: 'place-harsq', to: 'place-pktrm', line: 'Red', sample: true },
  { from: 'place-pktrm', to: 'place-kencl', line: 'Green', sample: true },
  { from: 'place-gover', to: 'place-aqucl', line: 'Blue', sample: true },
];
const rides = () => store.get('rides', SAMPLE_RIDES);
const faves = () => store.get('faves', {});

// ---------- data helpers
async function api(svc, path, opts = {}) {
  const r = await fetch(`/api/${svc}${path}`, { ...opts, headers: { authorization: `Bearer ${USER}`, 'content-type': 'application/json', ...(opts.headers || {}) } });
  const body = await r.json().catch(() => null);
  if (!r.ok) throw Object.assign(new Error((body && (typeof body.detail === 'string' ? body.detail : body.detail?.[0]?.msg)) || r.statusText), { status: r.status });
  return body;
}
const mbta = (path) => fetch('/mbta' + path).then((r) => r.json());
const geId = (id) => (S.geMemory ? GE_ALIAS[id] || id : id);
const mbtaId = (id) => (S.geMemory ? Object.keys(GE_ALIAS).find((k) => GE_ALIAS[k] === id) || id : id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fc = (features) => ({ type: 'FeatureCollection', features });
const pt = (lon, lat, properties = {}) => ({ type: 'Feature', properties, geometry: { type: 'Point', coordinates: [lon, lat] } });
const station = (id) => S.stations.find((s) => s.id === id);

function metres(a, b) {
  const R = 6371000, t = Math.PI / 180;
  const dLat = (b.lat - a.lat) * t, dLon = (b.lon - a.lon) * t;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * t) * Math.cos(b.lat * t) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const ll = ([lon, lat]) => ({ lat, lon });
function nearest(p = S.pos) {
  let best = null;
  for (const s of S.stations) { const d = metres(p, s); if (!best || d < best.d) best = { ...s, d }; }
  return best;
}
function decodePolyline(str) {
  const pts = []; let i = 0, lat = 0, lon = 0;
  while (i < str.length) {
    for (const k of [0, 1]) {
      let shift = 0, res = 0, b;
      do { b = str.charCodeAt(i++) - 63; res |= (b & 31) << shift; shift += 5; } while (b >= 32);
      const v = res & 1 ? ~(res >> 1) : res >> 1;
      if (k === 0) lat += v; else lon += v;
    }
    pts.push([lon / 1e5, lat / 1e5]);
  }
  return pts;
}
function circle(c, m, n = 64) {
  const ring = [];
  for (let k = 0; k <= n; k++) {
    const a = (k / n) * 2 * Math.PI;
    ring.push([c.lon + (m * Math.cos(a)) / (111320 * Math.cos((c.lat * Math.PI) / 180)), c.lat + (m * Math.sin(a)) / 110540]);
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] } };
}

// ---------- loaders
async function loadStations() {
  const byId = {};
  await Promise.all(SUBWAY.map(async (rid) => {
    for (const s of await api('dp', `/stops?route_id=${rid}&limit=500`)) {
      const st = (byId[s.id] ||= { id: s.id, name: s.name, lat: s.lat, lon: s.lon, lines: [] });
      if (!st.lines.includes(lineOf(rid))) st.lines.push(lineOf(rid));
    }
  }));
  S.stations = Object.values(byId);
}
async function loadShapes() {
  const features = [];
  for (const rid of SUBWAY) {
    const res = await mbta(`/shapes?filter[route]=${rid}`);
    const longest = (res.data || []).sort((a, b) => b.attributes.polyline.length - a.attributes.polyline.length).slice(0, 2);
    for (const sh of longest) features.push({ type: 'Feature', properties: { color: LINE[lineOf(rid)], line: lineOf(rid), route: rid }, geometry: { type: 'LineString', coordinates: decodePolyline(sh.attributes.polyline) } });
  }
  S.shapes = fc(features);
}
async function loadVehicles() {
  const all = await Promise.all(SUBWAY.map((rid) => api('dp', `/vehicles?route_id=${rid}`).catch(() => [])));
  S.vehicles = all.flat();
}
async function loadIconic() {
  S.iconic = await fetch('/data/iconic.geojson').then((r) => r.json()).catch(() => fc([]));
  const tallest = {};
  for (const f of S.iconic.features) {
    const p = f.properties;
    if (!tallest[p.name] || p.height_m > tallest[p.name].properties.height_m) tallest[p.name] = f;
  }
  // one point per place (at its tallest part), and every part reports the place's full height
  S.places = Object.values(tallest).map((f) => {
    const ring = f.geometry.coordinates[0];
    const [lon, lat] = ring.reduce((a, p) => [a[0] + p[0] / ring.length, a[1] + p[1] / ring.length], [0, 0]);
    return { ...f.properties, lon, lat };
  });
  for (const f of S.iconic.features) f.properties.place_height_ft = tallest[f.properties.name].properties.height_ft;
}
// Ethnic Boston neighborhoods: city boundaries + curated heritage notes (hoods-build.mjs)
async function loadEthnic() {
  S.ethnic = await fetch('/data/ethnic.geojson').then((r) => r.json()).catch(() => fc([]));
  S.ethnicHubs = fc(S.ethnic.features.map((f) => pt(f.properties.hub[0], f.properties.hub[1], { label: `${f.properties.name}\n${f.properties.heritage}` })));
}
// the subway as a graph: consecutive stops of each route's main patterns (MBTA route_patterns, parent stations)
async function loadNetwork() {
  const res = await mbta(`/route_patterns?filter[route]=${SUBWAY.join(',')}&filter[direction_id]=0&include=representative_trip.stops&fields[stop]=name,parent_station&fields[route_pattern]=typicality&fields[trip]=headsign`);
  const inc = {};
  for (const x of res.included || []) inc[x.type + x.id] = x;
  const adj = {};
  const link = (a, b, route, toward) => (adj[a] ||= []).push({ to: b, route, toward });
  for (const pat of res.data || []) {
    if (pat.attributes.typicality !== 1) continue;
    const trip = inc['trip' + pat.relationships.representative_trip.data.id];
    const ids = (trip?.relationships?.stops?.data || []).map((d) => inc['stop' + d.id]?.relationships?.parent_station?.data?.id || d.id);
    if (ids.length < 2) continue;
    const name = (id) => station(id)?.name || id;
    for (let i = 1; i < ids.length; i++) {
      link(ids[i - 1], ids[i], pat.relationships.route.data.id, name(ids[ids.length - 1]));
      link(ids[i], ids[i - 1], pat.relationships.route.data.id, name(ids[0]));
    }
  }
  S.net = adj;
}
const STOP_MIN = 2, TRANSFER_MIN = 5;
// fewest minutes from station a to station b: ~2 min a stop, +5 min to change trains
function tRoute(a, b) {
  if (a === b) return { legs: [], minutes: 0 };
  const dist = { [a + '|']: 0 }, prev = {}, done = new Set(), queue = [[0, a, '']];
  while (queue.length) {
    queue.sort((x, y) => x[0] - y[0]);
    const [d, st, route] = queue.shift(), key = st + '|' + route;
    if (done.has(key)) continue;
    done.add(key);
    if (st === b) {
      const steps = [];
      for (let k = key; prev[k]; k = prev[k].from) steps.unshift(prev[k]);
      const legs = [];
      for (const e of steps) {
        const last = legs[legs.length - 1];
        if (last && last.route === e.route) { last.to = e.to; last.stops++; last.toward = e.toward; }
        else legs.push({ route: e.route, from: e.st, to: e.to, stops: 1, toward: e.toward });
      }
      return { legs, minutes: d };
    }
    for (const e of S.net[st] || []) {
      const nd = d + STOP_MIN + (route && route !== e.route ? TRANSFER_MIN : 0), nk = e.to + '|' + e.route;
      if (nd < (dist[nk] ?? Infinity)) { dist[nk] = nd; prev[nk] = { from: key, st, to: e.to, route: e.route, toward: e.toward }; queue.push([nd, e.to, e.route]); }
    }
  }
  return null;
}
// on shared Green Line track any branch works, so only name the branch when the leg needs it
const servedBy = (id) => new Set((S.net[id] || []).map((e) => e.route));
const routeName = (r, l) => {
  if (r === 'Mattapan') return 'Mattapan Trolley';
  if (!r.startsWith('Green-')) return `${r} Line`;
  const shared = l && [...servedBy(l.from)].filter((x) => x.startsWith('Green-') && servedBy(l.to).has(x)).length > 1;
  return shared ? 'Green Line (any branch)' : `Green Line ${r.slice(6)} branch`;
};

async function loadConsent() {
  for (const c of await api('is', '/consent')) { S.consent[c.scope] = c.granted; S.policy = c.policy_version; }
}
async function loadAll(step = () => {}) {
  const health = await api('ge', '/healthz').catch(() => null);
  S.geMemory = !health || health.store === 'memory';
  step('loading stations from Tiger Data…');
  if (!S.stations.length) await loadStations();
  step('drawing the T lines…');
  if (!S.shapes) await loadShapes();
  step('raising Boston’s landmarks…');
  if (!S.iconic) await loadIconic();
  if (!S.ethnic) await Promise.all([loadEthnic(), loadNetwork()]);
  step('finding live trains…');
  await Promise.all([loadVehicles(), loadConsent(), api('is', '/freedom-trail').then((t) => (S.trail = t)).catch(() => {})]);
  S.ready = true;
  step(`${S.stations.length} stations · ${S.vehicles.length} trains running`);
}

// ---------- GIS basemap in the canvas palette
const BASEMAP = 'https://tiles.openfreemap.org/styles/positron';
function paintCanvas(map) {
  // keep the credits behind the (i) button so they don't cover the small map card
  document.querySelectorAll('.maplibregl-compact-show').forEach((e) => e.classList.remove('maplibregl-compact-show'));
  const set = (id, prop, v) => { try { map.setPaintProperty(id, prop, v); } catch {} };
  for (const l of map.getStyle().layers) {
    const id = l.id;
    if (l.type === 'background') set(id, 'background-color', P.land);
    else if (l.type === 'fill') {
      if (/water/.test(id)) set(id, 'fill-color', P.water);
      else if (/park|grass|wood|forest|cemetery|pitch|landcover/.test(id)) { set(id, 'fill-color', P.park); set(id, 'fill-opacity', 0.75); }
      else if (/building/.test(id)) { set(id, 'fill-color', '#E8DCC6'); set(id, 'fill-outline-color', '#D9CBB2'); }
      else set(id, 'fill-color', P.land);
    } else if (l.type === 'line') {
      if (/water|river/.test(id)) set(id, 'line-color', P.water);
      else if (/casing|outline/.test(id)) set(id, 'line-color', '#E2D5BF');
      else if (/road|highway|street|bridge|tunnel|path|motorway|trunk|primary|secondary|tertiary|minor|service/.test(id)) set(id, 'line-color', '#FFFFFF');
      else if (/rail/.test(id)) set(id, 'line-opacity', 0.25);
    } else if (l.type === 'symbol') {
      set(id, 'text-color', /water/.test(id) ? P.steel : '#5B6B80');
      set(id, 'text-halo-color', P.land);
      if (/poi/.test(id)) map.setLayoutProperty(id, 'visibility', 'none');
    }
  }
}
function addLines(map) {
  map.addSource('lines', { type: 'geojson', data: S.shapes });
  map.addLayer({ id: 'lines', type: 'line', source: 'lines', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 3, 16, 7], 'line-opacity': 0.9 } });
}
function addIconic(map) {
  map.addSource('iconic', { type: 'geojson', data: S.iconic });
  const color = ['match', ['get', 'category'], 'trail', ICON_COLOR.trail, 'skyline', ICON_COLOR.skyline, ICON_COLOR.landmark];
  map.addLayer({ id: 'iconic-base', type: 'line', source: 'iconic', paint: { 'line-color': P.navy, 'line-width': 1.5 } });
  map.addLayer({ id: 'iconic-3d', type: 'fill-extrusion', source: 'iconic', paint: { 'fill-extrusion-color': color, 'fill-extrusion-height': 0, 'fill-extrusion-opacity': 0.95, 'fill-extrusion-vertical-gradient': true } });
  // the "pop": landmarks rise from the flat city once the map has drawn
  map.once('idle', () => {
    map.setPaintProperty('iconic-3d', 'fill-extrusion-height-transition', { duration: 1400, delay: 0 });
    map.setPaintProperty('iconic-3d', 'fill-extrusion-height', ['get', 'height_m']);
  });
}
function addStations(map) {
  map.addSource('stations', { type: 'geojson', data: fc(S.stations.map((s) => pt(s.lon, s.lat, { name: s.name, id: s.id }))) });
  map.addLayer({ id: 'stations', type: 'circle', source: 'stations', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2.5, 16, 6], 'circle-color': '#fff', 'circle-stroke-color': P.navy, 'circle-stroke-width': 2.5 } });
  map.addLayer({ id: 'station-labels', type: 'symbol', source: 'stations', minzoom: 12.5, layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Bold'], 'text-size': 10, 'text-offset': [0.8, 0], 'text-anchor': 'left' }, paint: { 'text-color': P.navy, 'text-halo-color': '#fff', 'text-halo-width': 1.6 } });
}
function addVehicles(map) {
  const data = () => fc(S.vehicles.map((v) => pt(v.lon, v.lat, { color: LINE[lineOf(v.route_id)] })));
  map.addSource('vehicles', { type: 'geojson', data: data() });
  map.addLayer({ id: 'vehicles', type: 'circle', source: 'vehicles', paint: { 'circle-radius': 5, 'circle-color': ['get', 'color'], 'circle-stroke-color': P.navy, 'circle-stroke-width': 2 } });
  S.timers.push(setInterval(async () => { await loadVehicles(); map.getSource('vehicles')?.setData(data()); }, 15000));
}
// hide pins that would overlap on screen, keeping earlier (more important) ones and the selected one
function declutter(map, list, keep, px = 30) {
  const shown = [];
  list.forEach((m, i) => {
    const p = map.project(m.getLngLat());
    const clash = i !== keep && shown.some((q) => Math.hypot(q.x - p.x, q.y - p.y) < px);
    m.getElement().style.visibility = clash ? 'hidden' : '';
    if (!clash) shown.push(p);
  });
}
function marker(map, el, lon, lat) {
  const m = new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
  S.markers.push(m);
  return m;
}
function iconicPopup(map, e) {
  const hit = map.getLayer('iconic-3d') && map.queryRenderedFeatures(e.point, { layers: ['iconic-3d'] })[0];
  if (!hit) return false;
  const p = hit.properties;
  const kind = p.category === 'trail' ? 'Freedom Trail' : p.category === 'skyline' ? 'Boston skyline' : 'Boston Landmark';
  const has = (v) => v != null && v !== 'null' && v !== '';
  new maplibregl.Popup({ closeButton: false, maxWidth: '230px', offset: 6 }).setLngLat(e.lngLat).setHTML(
    `<div class="icard"><span class="hand" style="font-size:17px;color:${p.category === 'trail' ? P.red : P.steel}">${kind}${has(p.designated) ? ` since ${p.designated}` : ''}</span>
     <b>${esc(p.name)}</b><span style="font-size:12px;font-weight:700">${p.place_height_ft} ft tall</span>
     ${has(p.blurb) ? `<p>${esc(p.blurb)}</p>` : ''}<div class="src">BPDA Building Roofprints${kind === 'Boston Landmark' ? ' · Boston Landmarks Commission' : ''}</div></div>`).addTo(map);
  return true;
}

// ---------- router
const screens = {};
const app = () => document.getElementById('screen');
const go = (hash) => { location.hash = hash; };
async function render() {
  S.timers.forEach(clearInterval); S.timers = [];
  S.markers.forEach((m) => m.remove()); S.markers = [];
  if (S.map) { S.map.remove(); S.map = null; }
  const [name] = (location.hash.replace(/^#\/?/, '') || 'loading').split('/');
  const fn = screens[name] || screens.loading;
  document.getElementById('nav').classList.toggle('hidden', ['loading', 'faves'].includes(name) || !screens[name]);
  document.querySelectorAll('.tq-nav a').forEach((a) => a.classList.toggle('on', a.dataset.tab === name));
  try {
    if (name !== 'loading' && screens[name] && !S.ready) await loadAll();
    await fn();
  } catch (e) {
    app().innerHTML = `<div class="page" style="padding:24px;gap:10px"><span class="hand" style="font-size:24px;color:${P.red}">uh oh</span><h1 class="head" style="margin:0">Something broke</h1><div class="box" style="padding:12px">${esc(e.message)}</div><p class="src">Are all three services running? See README.</p></div>`;
  }
}
window.addEventListener('hashchange', render);
// the bubble nav icons are Isabella's SVGs (design/icons), inlined so their Fredoka lettering renders
document.querySelectorAll('[data-icon]').forEach(async (el) => { el.innerHTML = await fetch(`/icons/${el.dataset.icon}.svg`).then((r) => r.text()); });

const starBtn = () => `<a href="#/faves" class="round" aria-label="Your faved fun facts"><svg width="24" height="24" viewBox="0 0 24 24" fill="${P.yellow}" stroke="${P.navy}" stroke-width="2" stroke-linejoin="round"><path d="${STAR}"/></svg></a>`;

// ---------- Loading (Loading.dc.html)
screens.loading = async () => {
  S.funFacts = await api('is', '/fun-facts').catch(() => []);
  let i = Math.floor(Math.random() * Math.max(1, S.funFacts.length));
  const fact = () => S.funFacts[i]?.body || 'America’s first subway opened right here in Boston, in 1897.';
  app().innerHTML = `<div class="loading">
    <div class="head" style="font-size:34px;letter-spacing:-.5px">T-Quest</div>
    <button class="fact" id="next" aria-label="Show another fun fact">
      <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="${P.lblue}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>
      <svg width="220" height="60" viewBox="0 0 220 60" fill="none" stroke="${P.steel}" stroke-width="4" stroke-linecap="round"><path d="M4 14c18-10 36 10 54 0s36 10 54 0 36 10 54 0 36 10 50 0"/><path d="M4 32c18-10 36 10 54 0s36 10 54 0 36 10 54 0 36 10 50 0"/><path d="M4 50c18-10 36 10 54 0s36 10 54 0 36 10 54 0 36 10 50 0"/></svg>
      <span style="display:flex;flex-direction:column;gap:10px;align-items:center"><span style="font-size:12px;font-weight:700;letter-spacing:1.5px;color:${P.lblue}">FUN FACT</span>
      <p id="fact" style="margin:0;font-size:19px;line-height:1.45;text-align:center;min-height:84px">${esc(fact())}</p></span>
      <span style="font-size:13px;color:${P.lblue}">Tap for another fact</span></button>
    <div style="width:100%;display:flex;flex-direction:column;gap:8px;align-items:center">
      <button class="start" id="start" disabled>Start exploring</button>
      <span id="step" style="font-size:11px;color:${P.lblue}">getting ready…</span></div></div>`;
  document.getElementById('next').onclick = () => { i = (i + 1) % Math.max(1, S.funFacts.length); document.getElementById('fact').textContent = fact(); };
  await loadAll((t) => { const el = document.getElementById('step'); if (el) el.textContent = t; });
  const btn = document.getElementById('start');
  if (!btn) return;
  btn.disabled = false;
  btn.onclick = async () => {
    // game-engine refuses check-ins without location consent; starting the demo grants "while using the app"
    if (!S.consent.location) await api('is', '/consent', { method: 'POST', body: JSON.stringify({ scope: 'location', policy_version: S.policy }) }).then(loadConsent).catch(() => {});
    go('#/home');
  };
};

// ---------- Home (Main.dc.html) with the GIS map
async function stopFacts(id) {
  if (!S.factCache[id]) S.factCache[id] = api('is', `/stops/${id}/facts`).then((r) => r.facts || []).catch(() => []);
  return S.factCache[id];
}
// spots around the nearest station: the station itself, Freedom Trail sites and iconic buildings (real GIS points)
async function spotsAround(n) {
  const spots = [];
  const sf = await stopFacts(n.id);
  spots.push({ id: n.id, name: `${n.name} station`, kind: 'station', lon: n.lon, lat: n.lat, facts: sf.map((f) => ({ text: f.body, src: f.source_url })) });
  for (const t of S.trail) {
    if (metres(n, t) > 650) continue;
    spots.push({ id: 'ft:' + t.name, name: t.name, kind: 'trail', lon: t.lon, lat: t.lat, facts: t.blurb ? [{ text: t.blurb }] : [] });
  }
  for (const p of S.places) {
    if (metres(n, p) > 650 || spots.some((s) => s.name.startsWith(p.name))) continue;
    const facts = [];
    if (p.designated) facts.push({ text: `Protected as an official Boston Landmark since ${p.designated}.`, src: 'https://www.boston.gov/departments/landmarks-commission' });
    if (p.category === 'skyline') facts.push({ text: `Its roof stands ${p.place_height_ft} ft above the street, one of the tallest in the city.` });
    spots.push({ id: 'ic:' + p.name, name: p.name, kind: p.category, lon: p.lon, lat: p.lat, facts });
  }
  return spots.sort((a, b) => metres(n, a) - metres(n, b)).slice(0, 8);
}

screens.home = async () => {
  const rank = await api('ge', '/me/rank').catch(() => null);
  let n = nearest(), spots = [], sel = 0, fi = 0;
  app().innerHTML = `<div class="home">
    <div style="display:flex;align-items:center;gap:12px">
      <a href="#/profile" aria-label="Open your user page" style="width:52px;height:52px;border-radius:50%;background:${P.yellow};border:3px solid ${P.navy};box-shadow:3px 3px 0 ${P.navy};display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:9px;font-weight:700;text-align:center;line-height:1.1">[your<br>avatar]</a>
      <div style="display:flex;flex-direction:column;flex-grow:1"><span class="hand" style="font-size:21px;color:${P.red}">hey ${USER}!</span><span class="head" style="font-size:22px;line-height:1.15">Ready to ride?</span></div>
      ${starBtn()}</div>
    ${pointsBar(rank)}
    <div class="factcard" id="fact"></div>
    <div class="mapcard"><div id="map"></div>
      <button class="tapin" id="tapin"></button><button class="tilt" id="tilt" aria-label="2D / 3D">2D</button>
      <button class="ethnic-toggle" id="ethnic" aria-pressed="false">Ethnic Boston</button>
      <span class="maplabel" id="maplabel">tap a spot to learn about it</span></div></div>`;

  const map = (S.map = new maplibregl.Map({ container: 'map', style: BASEMAP, center: [n.lon, n.lat], zoom: 15.4, pitch: 50, bearing: -15, maxPitch: 70,
    attributionControl: { compact: true, customAttribution: 'BPDA · Boston Landmarks Commission · MBTA' } }));
  map.on('load', () => {
    paintCanvas(map); addLines(map); addIconic(map); addVehicles(map); addStations(map);
    addEthnic(map, ethnicOn);
    if (ethnicOn) setEthnic(true);
    map.addSource('zone', { type: 'geojson', data: fc([circle(n, ZONE_M)]) });
    map.addLayer({ id: 'zone', type: 'line', source: 'zone', paint: { 'line-color': P.navy, 'line-width': 2, 'line-dasharray': [2, 2] } });
  });
  const you = document.createElement('div'); you.className = 'you';
  const youMarker = marker(map, you, S.pos.lon, S.pos.lat);

  function drawCard() {
    const s = spots[sel]; if (!s) return;
    const k = s.facts.length, f = s.facts[Math.min(fi, Math.max(0, k - 1))];
    const key = `${s.name}::${f?.text || ''}`, faved = !!faves()[key];
    const near = spots.find((x) => x !== s && x.facts.length);
    document.getElementById('fact').innerHTML = `
      <span class="tag" style="background:${k ? P.red : P.steel}">${k ? 'did you know?!' : 'no history yet!'}</span>
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:6px">
        <span class="head" style="font-size:18px;line-height:1.15">${esc(s.name)}</span>
        <button id="fave" class="round" style="width:40px;height:40px;border-width:2.5px;box-shadow:none" aria-pressed="${faved}" aria-label="Fave this fun fact" ${k ? '' : 'disabled'}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="${faved ? P.yellow : 'none'}" stroke="${P.navy}" stroke-width="2" stroke-linejoin="round"><path d="${STAR}"/></svg></button></div>
      ${k ? `<p>${esc(f.text)}</p>` : `<p style="font-weight:800">No history recorded yet.</p><p style="font-size:14px"><span class="hand" style="font-size:19px">but nearby...</span> ${esc(near?.facts[0].text || 'Every stop has a story. Help us find this one.')}</p>`}
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:auto">
        <div style="display:flex;min-height:28px">${k > 1 ? s.facts.map((_, j) => `<button data-dot="${j}" aria-label="Fact ${j + 1} of ${k}" style="width:28px;height:28px;border:0;background:transparent;padding:0;display:flex;align-items:center;justify-content:center"><span style="display:block;width:12px;height:12px;border-radius:50%;border:2.5px solid ${P.navy};background:${j === fi ? P.navy : '#fff'}"></span></button>`).join('') : ''}</div>
        ${f?.src ? `<a class="learn" href="${esc(f.src)}" target="_blank" rel="noopener">Learn more →</a>` : `<span class="learn" style="opacity:.5">Learn more →</span>`}</div>`;
    document.getElementById('fave').onclick = () => {
      const all = faves();
      if (all[key]) delete all[key]; else all[key] = { place: s.name, fact: f.text, line: LINE[n.lines[0]] };
      store.set('faves', all); drawCard();
    };
    document.querySelectorAll('[data-dot]').forEach((b) => (b.onclick = () => { fi = +b.dataset.dot; drawCard(); }));
  }
  function drawPins() {
    S.markers.filter((m) => m !== youMarker).forEach((m) => m.remove());
    S.markers = [youMarker];
    const pins = spots.map((s, j) => {
      const b = document.createElement('button');
      b.className = 'pin' + (j === sel ? ' sel' : ''); b.style.background = PIN_COLOR[s.kind]; b.style.display = ethnicOn ? 'none' : '';
      b.setAttribute('aria-label', s.name); b.innerHTML = '<i></i>';
      b.onclick = (e) => { e.stopPropagation(); sel = j; fi = 0; drawPins(); drawCard(); };
      return marker(map, b, s.lon, s.lat);
    });
    const tidy = () => declutter(map, pins, sel, 34);
    map.off('moveend', S.tidy); S.tidy = tidy; map.on('moveend', tidy); tidy();
  }
  function drawTapIn() {
    const btn = document.getElementById('tapin'), inside = n.d <= ZONE_M;
    btn.disabled = !inside;
    btn.textContent = inside ? `Tap in at ${n.name} →` : `${Math.round(n.d)} m to ${n.name}`;
    btn.onclick = () => openRide(n);
  }
  async function update(fly) {
    n = nearest();
    youMarker.setLngLat([S.pos.lon, S.pos.lat]);
    map.getSource('zone')?.setData(fc([circle(n, ZONE_M)]));
    if (fly) map.easeTo({ center: [n.lon, n.lat], duration: 700 });
    spots = await spotsAround(n); sel = 0; fi = 0;
    drawPins(); drawCard(); drawTapIn();
  }
  // Ethnic Boston: pastel neighborhoods over the city; tap one for T directions from your station
  let ethnicOn = store.get('ethnic', false);
  const setEthnic = (on, move = true) => {
    ethnicOn = on; store.set('ethnic', on);
    const btn = document.getElementById('ethnic');
    btn.setAttribute('aria-pressed', on); btn.classList.toggle('on', on);
    document.getElementById('maplabel').textContent = on ? 'tap a neighborhood' : 'tap a spot to learn about it';
    for (const id of ['ethnic-fill', 'ethnic-line', 'ethnic-labels']) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
    S.markers.forEach((m) => { if (m !== youMarker) m.getElement().style.display = on ? 'none' : ''; });
    if (move) map.easeTo(on ? { center: [-71.075, 42.322], zoom: 11.4, pitch: 25, bearing: 0, duration: 900 } : { center: [n.lon, n.lat], zoom: 15.4, pitch: 50, bearing: -15, duration: 900 });
  };
  document.getElementById('ethnic').onclick = () => { clearRoute(map); setEthnic(!ethnicOn); };
  // tap a landmark for its card, a neighborhood for directions; tap anywhere else to move the demo rider
  map.on('click', (e) => {
    if (iconicPopup(map, e)) return;
    const hood = ethnicOn && map.queryRenderedFeatures(e.point, { layers: ['ethnic-fill'] })[0];
    if (hood) return openDirections(map, S.ethnic.features.find((f) => f.properties.name === hood.properties.name), n);
    if (ethnicOn) return;
    S.pos = { lat: e.lngLat.lat, lon: e.lngLat.lng }; update(true);
  });
  document.getElementById('tilt').onclick = (e) => {
    const flat = map.getPitch() > 5;
    map.easeTo({ pitch: flat ? 0 : 50, bearing: flat ? 0 : -15, duration: 700 });
    e.currentTarget.textContent = flat ? '3D' : '2D';
  };
  await update(false);
};

function addEthnic(map, on) {
  const vis = on ? 'visible' : 'none';
  map.addSource('ethnic', { type: 'geojson', data: S.ethnic });
  map.addLayer({ id: 'ethnic-fill', type: 'fill', source: 'ethnic', layout: { visibility: vis }, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.55 } });
  map.addLayer({ id: 'ethnic-line', type: 'line', source: 'ethnic', layout: { visibility: vis }, paint: { 'line-color': P.navy, 'line-width': 1.5, 'line-dasharray': [3, 2], 'line-opacity': 0.7 } });
  map.addSource('ethnic-hubs', { type: 'geojson', data: S.ethnicHubs });
  map.addLayer({ id: 'ethnic-labels', type: 'symbol', source: 'ethnic-hubs', layout: { visibility: vis, 'text-field': ['get', 'label'], 'text-font': ['Noto Sans Bold'], 'text-size': 11, 'text-max-width': 9, 'text-line-height': 1.15, 'text-allow-overlap': false },
    paint: { 'text-color': P.navy, 'text-halo-color': '#fff', 'text-halo-width': 2 } });
}
function clearRoute(map) {
  for (const id of ['route-walk', 'route', 'route-under', 'route-stops']) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of ['route', 'route-walk', 'route-stops']) if (map.getSource(id)) map.removeSource(id);
}
function openDirections(map, hood, from) {
  const h = hood.properties, hub = { lon: h.hub[0], lat: h.hub[1] };
  const dest = nearest(hub), walkMin = Math.max(1, Math.round(metres(dest, hub) / 80));
  const r = tRoute(from.id, dest.id);
  const total = r ? r.minutes + walkMin : null;
  const wrap = document.createElement('div');
  wrap.className = 'sheetwrap';
  const legRow = (l) => `<div class="leg"><span class="dot" style="width:16px;height:16px;background:${LINE[lineOf(l.route)]}"></span>
      <span style="display:flex;flex-direction:column"><b>Take the ${esc(routeName(l.route, l))}</b><span>toward ${esc(l.toward)} · ${l.stops} stop${l.stops > 1 ? 's' : ''}</span><span>${esc(station(l.from)?.name)} → ${esc(station(l.to)?.name)}</span></span></div>`;
  wrap.innerHTML = `<div class="sheet" style="padding-top:0;gap:12px">
    <div style="margin:0 -18px;padding:16px 18px 12px;background:${h.color};border-bottom:3px solid ${P.navy};border-radius:26px 26px 0 0;display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
      <span style="display:flex;flex-direction:column;gap:2px"><span class="hand" style="font-size:20px;color:${P.red}">ethnic boston</span><span class="head" style="font-size:24px;line-height:1.1">${esc(h.name)}</span>
        <span style="align-self:flex-start;margin-top:4px;background:#fff;border:2px solid ${P.navy};border-radius:999px;padding:1px 9px;font-size:11px;font-weight:800">${esc(h.heritage)}</span></span>
      <button class="round" id="close" aria-label="Close" style="width:40px;height:40px;box-shadow:none"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
    <p style="margin:0;font-size:14px;line-height:1.4;font-weight:500">${esc(h.blurb)}</p>
    <div class="box" style="padding:12px 14px;display:flex;flex-direction:column;gap:12px">
      <div style="display:flex;justify-content:space-between;align-items:baseline"><span style="font-weight:800">From ${esc(from.name)}</span>${total != null ? `<span class="head" style="font-size:22px">~${total} min</span>` : ''}</div>
      ${!r ? `<span style="font-weight:700">No subway route found from here.</span>` : r.legs.length ? r.legs.map((l, i) => (i ? `<div class="leg change"><span>↻</span><span>Change at <b>${esc(station(l.from)?.name)}</b></span></div>` : '') + legRow(l)).join('') : `<div class="leg"><span class="dot" style="width:16px;height:16px;background:${P.yellow}"></span><b>You’re already at ${esc(dest.name)}</b></div>`}
      <div class="leg"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="13" cy="4" r="2"/><path d="M10 21l2-7 3 3v5M9 10l3-3 3 2 2 3M9 10l-2 4"/></svg>
        <span style="display:flex;flex-direction:column"><b>Walk ${walkMin} min to ${esc(h.heart)}</b><span>from ${esc(dest.name)}</span></span></div></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><a class="bigbtn" href="#/explore" style="display:grid;place-items:center">Spots here</a><button class="bigbtn yellow" id="show">Show on map</button></div>
    <span class="src">Boundaries: City of Boston / BPDA · Routes: MBTA route patterns · times are estimates (${STOP_MIN} min a stop, ${TRANSFER_MIN} min to change)</span></div>`;
  wrap.querySelector('#close').onclick = () => wrap.remove();
  wrap.querySelector('#show').onclick = () => { wrap.remove(); if (r) drawRoute(map, r, dest, hub); };
  app().appendChild(wrap);
}
function drawRoute(map, r, dest, hub) {
  clearRoute(map);
  const legs = r.legs.map((l) => ({ l, seg: segment(lineOf(l.route), station(l.from), station(l.to)) })).filter((x) => x.seg);
  map.addSource('route', { type: 'geojson', data: fc(legs.map(({ l, seg }) => ({ type: 'Feature', properties: { color: LINE[lineOf(l.route)] }, geometry: { type: 'LineString', coordinates: seg.coords } }))) });
  map.addLayer({ id: 'route-under', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': P.navy, 'line-width': 11 } });
  map.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 7 } });
  map.addSource('route-walk', { type: 'geojson', data: fc([{ type: 'Feature', geometry: { type: 'LineString', coordinates: [[dest.lon, dest.lat], [hub.lon, hub.lat]] } }]) });
  map.addLayer({ id: 'route-walk', type: 'line', source: 'route-walk', paint: { 'line-color': P.navy, 'line-width': 3, 'line-dasharray': [1, 1.5] } });
  const ends = [...r.legs.flatMap((l) => [station(l.from), station(l.to)]), hub].filter(Boolean);
  map.addSource('route-stops', { type: 'geojson', data: fc(ends.map((p) => pt(p.lon, p.lat))) });
  map.addLayer({ id: 'route-stops', type: 'circle', source: 'route-stops', paint: { 'circle-radius': 6, 'circle-color': P.yellow, 'circle-stroke-color': P.navy, 'circle-stroke-width': 2.5 } });
  const all = [...legs.flatMap(({ seg }) => seg.coords.map(ll)), hub];
  const lons = all.map((p) => p.lon), lats = all.map((p) => p.lat);
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: { top: 60, bottom: 50, left: 40, right: 40 }, maxZoom: 15, pitch: 30, duration: 900 });
}

function pointsBar(rank) {
  if (!rank) return `<div class="box" style="padding:8px 12px;font-size:12px;font-weight:700">points unavailable (is game-engine running?)</div>`;
  const span = rank.next_rank_at || rank.lifetime_points || 1;
  const x = 8 + Math.min(1, rank.lifetime_points / span) * 304;
  return `<div class="box" style="padding:8px 12px;display:flex;flex-direction:column;gap:4px">
    <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:700">
      <span style="background:${P.pink};border:2px solid ${P.navy};border-radius:999px;padding:1px 9px">${esc(rank.name)}</span>
      <span>${rank.lifetime_points.toLocaleString()} pts${rank.next_rank_name ? ` · ${rank.points_to_next} to ${esc(rank.next_rank_name)}` : ''}</span></div>
    <svg width="100%" height="18" viewBox="0 0 320 18" fill="none"><path d="M8 9H312" stroke="${P.lblue}" stroke-width="7" stroke-linecap="round"/><path d="M8 9H${x}" stroke="${P.red}" stroke-width="7" stroke-linecap="round"/>
      <circle cx="8" cy="9" r="6" fill="#fff" stroke="${P.navy}" stroke-width="2.5"/><circle cx="312" cy="9" r="6" fill="#fff" stroke="${P.navy}" stroke-width="2.5"/><circle cx="${x}" cy="9" r="7" fill="${P.yellow}" stroke="${P.navy}" stroke-width="2.5"/></svg></div>`;
}

// ---------- Ride: tap in at A, tap out at B, verified against real MBTA trips (proposal, issues #61/#62)
function openRide(from) {
  let line, dests, to;
  const t1 = Date.now();
  const pick = (l) => {
    line = l;
    // live evidence at tap-in: a real train on this line within 400 m of the station right now (data-platform /vehicles)
    const near = S.vehicles.filter((v) => lineOf(v.route_id) === line).map((v) => ({ v, d: metres(from, v) })).sort((a, b) => a.d - b.d)[0];
    S.ride = { from, line, t1, seen: near && near.d < 400 ? near.v : null };
    dests = S.stations.filter((s) => s.id !== from.id && s.lines.includes(line)).map((s) => ({ ...s, d: metres(from, s) })).sort((a, b) => a.d - b.d).slice(0, 6);
    to = dests[0];
  };
  pick(from.lines.includes('Red') ? 'Red' : from.lines[0]);
  const wrap = document.createElement('div');
  wrap.className = 'sheetwrap';
  const draw = (msg = '') => {
    wrap.innerHTML = `<div class="sheet">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="display:flex;flex-direction:column"><span class="hand" style="font-size:20px;color:${LINE[line]}">tapped in!</span><span class="head" style="font-size:22px">${esc(from.name)} · ${line} Line</span></span>
        <button class="round" id="close" aria-label="Cancel ride" style="width:40px;height:40px;box-shadow:none"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      ${from.lines.length > 1 ? `<div style="display:flex;gap:8px">${from.lines.map((l) => `<button class="pillbtn ${l === line ? 'on' : ''}" data-line="${l}" style="${l === line ? `background:${P.yellow}` : ''}"><span class="dot" style="background:${LINE[l]}"></span>${l} Line</button>`).join('')}</div>` : ''}
      <span style="font-size:12px;font-weight:700;color:${P.steel}">${S.ride.seen ? `Live train ${esc(S.ride.seen.label || S.ride.seen.vehicle_id)} seen ${Math.round(metres(from, S.ride.seen))} m from the station` : 'No live train near the station right now'}</span>
      <span style="font-size:13px;font-weight:800">Where are you getting off?</span>
      <div class="stoplist">${dests.map((d) => `<button data-to="${d.id}" class="${d.id === to.id ? 'on' : ''}"><span class="dot" style="background:${LINE[line]}"></span>${esc(d.name)}<small>${(d.d / 1609).toFixed(1)} mi</small></button>`).join('')}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <button class="bigbtn" id="now">Tap out now</button>
        <button class="bigbtn yellow" id="ride">Ride there ⏩</button></div>
      <span class="src">demo: “Ride there” skips the clock ahead to when the next real scheduled train arrives. “Tap out now” is what a GPS spoofer would do.</span>
      ${msg}</div>`;
    wrap.querySelector('#close').onclick = () => wrap.remove();
    wrap.querySelectorAll('[data-line]').forEach((b) => (b.onclick = () => { pick(b.dataset.line); draw(); }));
    wrap.querySelectorAll('[data-to]').forEach((b) => (b.onclick = () => { to = dests.find((d) => d.id === b.dataset.to); draw(); }));
    wrap.querySelector('#now').onclick = () => finish(to, Date.now());
    wrap.querySelector('#ride').onclick = async () => {
      const trip = (await scheduledTrips(from, to, line, S.ride.t1, S.ride.t1 + 90 * 60000)).find((t) => t.dep >= S.ride.t1 - 60000);
      if (!trip) return draw(`<div class="box" style="padding:10px;font-size:13px;font-weight:700">No scheduled ${line} Line train from ${esc(from.name)} to ${esc(to.name)} in the next 90 min.</div>`);
      finish(to, trip.arr);
    };
  };
  const finish = async (dest, t2) => {
    wrap.querySelector('.sheet').style.opacity = 0.6;
    const result = await verifyRide({ from, to: dest, line, t1: S.ride.t1, t2 });
    wrap.remove();
    showStamp(result);
  };
  draw();
  app().appendChild(wrap);
}

const bostonTime = (t) => new Date(t).toLocaleTimeString('en-GB', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });
// real MBTA schedule: trips that stop at A and later at B (any platform of either station)
async function scheduledTrips(a, b, line, from, to) {
  const res = await mbta(`/schedules?filter[stop]=${a.id},${b.id}&filter[route]=${routesOf(line).join(',')}&filter[min_time]=${bostonTime(from - 20 * 60000)}&filter[max_time]=${bostonTime(to + 10 * 60000)}&include=stop&fields[schedule]=arrival_time,departure_time,stop_sequence`);
  const parent = {};
  for (const s of res.included || []) parent[s.id] = s.relationships?.parent_station?.data?.id || s.id;
  const trips = {};
  for (const d of res.data || []) {
    const st = parent[d.relationships.stop.data.id];
    (trips[d.relationships.trip.data.id] ||= { route: d.relationships.route?.data?.id })[st === a.id ? 'a' : 'b'] = d.attributes;
  }
  return Object.entries(trips)
    .filter(([, t]) => t.a && t.b && t.a.stop_sequence < t.b.stop_sequence)
    .map(([id, t]) => ({ id, route: t.route, dep: Date.parse(t.a.departure_time || t.a.arrival_time), arr: Date.parse(t.b.arrival_time || t.b.departure_time) }))
    .sort((x, y) => x.dep - y.dep);
}
async function verifyRide({ from, to, line, t1, t2 }) {
  const dist = metres(from, to), kmh = (dist / 1000) / (Math.max(t2 - t1, 1) / 3600000);
  const checks = [{ ok: true, text: `Tapped in inside the ${ZONE_M} m zone at ${from.name}` }];
  const fast = kmh > MAX_TRAIN_KMH;
  checks.push({ ok: !fast, text: fast ? `${(dist / 1609).toFixed(1)} mi in ${Math.max(1, Math.round((t2 - t1) / 1000))} s is faster than any train` : `${(dist / 1609).toFixed(1)} mi in ${Math.round((t2 - t1) / 60000)} min is a believable ride` });
  let trip = null;
  if (!fast) {
    const trips = await scheduledTrips(from, to, line, t1, t2);
    trip = trips.find((t) => t1 <= t.dep + 2 * 60000 && t1 >= t.dep - 20 * 60000 && Math.abs(t.arr - t2) <= 3 * 60000);
    checks.push({ ok: !!trip, text: trip ? `Matches ${trip.route} trip ${trip.id}: left ${bostonTime(trip.dep)}, arrived ${bostonTime(trip.arr)}` : 'No real train made this trip at these times' });
  }
  checks.push({ ok: !!S.ride?.seen, soft: true, text: S.ride?.seen ? `A live train was near ${from.name} when you tapped in` : 'No live train seen at tap-in (soft signal)' });
  const ok = !fast && !!trip;
  let points = null, note = '';
  if (ok) {
    store.set('rides', [...rides().filter((x) => !x.sample), { from: from.id, to: to.id, line, at: t2, trip: trip.id }]);
    S.pos = { lat: to.lat, lon: to.lon };
    try {
      const res = await api('ge', '/checkins', { method: 'POST', body: JSON.stringify({ stop_id: geId(to.id), lat: to.lat, lon: to.lon, client_time: new Date(t2).toISOString(), mode: 'subway', consent: S.consent.location }) });
      points = res.points_awarded;
    } catch (e) {
      note = e.status === 404 && S.geMemory ? 'Verified, but game-engine demo mode only scores Park St, Downtown Crossing, Harvard, Alewife and South Station.' : e.status === 409 ? 'Verified, but you already collected this stop in the last 30 min.' : e.message;
    }
  }
  return { ok, from, to, line, checks, trip, points, note };
}
function showStamp(r) {
  const color = r.ok ? LINE[r.line] : P.red;
  const wrap = document.createElement('div');
  wrap.className = 'stampwrap';
  wrap.innerHTML = `
    <div class="stamp" style="border-color:${color};color:${color}">
      <span class="hand" style="font-size:22px;color:${P.navy}">${r.ok ? 'stamped!' : 'nope!'}</span>
      <span class="t">${r.ok ? 'RIDE<br>VERIFIED' : 'NOT<br>VERIFIED'}</span>
      <span class="r" style="color:${P.navy}">${esc(r.from.name)} → ${esc(r.to.name)}</span>
      <span class="s" style="color:${P.navy}">${r.line} Line${r.trip ? ` · trip ${esc(r.trip.id)}` : ''}</span></div>
    ${r.points ? `<div class="burst"><i>+${r.points}</i></div>` : ''}
    <div class="box" style="width:100%;padding:12px 14px;display:flex;flex-direction:column;gap:10px">
      <div class="checks">${r.checks.map((c) => `<div><b style="background:${c.ok ? P.lgreen : c.soft ? '#fff' : P.pink}">${c.ok ? '✓' : c.soft ? '–' : '✕'}</b><span>${esc(c.text)}</span></div>`).join('')}</div>
      ${r.note ? `<span class="src">${esc(r.note)}</span>` : ''}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><button class="bigbtn" id="again">Back to map</button><a class="bigbtn yellow" href="#/traveled" style="display:grid;place-items:center">See Traveled</a></div></div>`;
  wrap.querySelector('#again').onclick = () => { wrap.remove(); render(); };
  app().appendChild(wrap);
}

// ---------- Traveled (Traveled.dc.html): real line shapes, ridden segments solid, the rest dotted
function segment(line, a, b) {
  // the stretch of real track between two stations, cut from the MBTA shape that passes closest to both
  let best = null;
  for (const f of S.shapes.features.filter((f) => f.properties.line === line)) {
    const c = f.geometry.coordinates;
    const idx = (s) => c.reduce((bi, p, i) => (metres(ll(p), s) < metres(ll(c[bi]), s) ? i : bi), 0);
    const ia = idx(a), ib = idx(b), err = metres(ll(c[ia]), a) + metres(ll(c[ib]), b);
    if (!best || err < best.err) best = { err, coords: c.slice(Math.min(ia, ib), Math.max(ia, ib) + 1) };
  }
  if (!best || best.err > 600 || best.coords.length < 2) return null;
  let m = 0;
  for (let i = 1; i < best.coords.length; i++) m += metres(ll(best.coords[i - 1]), ll(best.coords[i]));
  return { coords: best.coords, miles: m / 1609.34 };
}
// "not yet" track as evenly spaced dots; branches that share track (Green D/E, Red A/B) share dots, so it never looks solid
function dotted(step) {
  const kept = [];
  for (const f of S.shapes.features) {
    const c = f.geometry.coordinates;
    let carry = 0;
    for (let i = 1; i < c.length; i++) {
      const a = ll(c[i - 1]), b = ll(c[i]), d = metres(a, b);
      for (let t = step - carry; t < d; t += step) {
        const q = { lat: a.lat + ((b.lat - a.lat) * t) / d, lon: a.lon + ((b.lon - a.lon) * t) / d };
        if (!kept.some((k) => k.line === f.properties.line && Math.abs(k.lat - q.lat) < 0.0008 && metres(k, q) < step * 0.6)) kept.push({ ...q, line: f.properties.line, color: f.properties.color });
      }
      carry = (carry + d) % step;
    }
  }
  return fc(kept.map((k) => pt(k.lon, k.lat, { color: k.color })));
}
screens.traveled = async () => {
  const col = await api('ge', '/me/collection').catch(() => ({ stops: [] }));
  const ridden = rides().map((r) => ({ ...r, seg: station(r.from) && station(r.to) ? segment(r.line, station(r.from), station(r.to)) : null })).filter((r) => r.seg);
  const miles = { Green: 0, Red: 0, Blue: 0, Orange: 0 };
  for (const r of ridden) miles[r.line] += r.seg.miles;
  const total = Object.values(miles).reduce((a, b) => a + b, 0);
  const fmt = (m) => (m ? m.toFixed(m < 10 ? 1 : 0) : '0');
  // unlocked spots: landmarks and Freedom Trail sites within 500 m of a stop you have reached
  const reached = new Set([...col.stops.map(mbtaId), ...ridden.flatMap((r) => [r.from, r.to])]);
  const reachedSt = [...reached].map(station).filter(Boolean);
  const pool = [...S.places.map((p) => ({ name: p.name, lon: p.lon, lat: p.lat, facts: (p.designated ? 1 : 0) + (p.blurb ? 1 : 0) || 1 })),
    ...S.trail.filter((t) => !S.places.some((p) => t.name.startsWith(p.name))).map((t) => ({ name: t.name, lon: t.lon, lat: t.lat, facts: 1 }))];
  const unlocked = pool.map((p) => { const s = reachedSt.map((st) => ({ st, d: metres(st, p) })).sort((a, b) => a.d - b.d)[0]; return s && s.d < 500 ? { ...p, stop: s.st.name } : null; }).filter(Boolean);
  let sel = 0;
  const sample = ridden.some((r) => r.sample);
  app().innerHTML = `<div class="full"><div id="map"></div>
    <div class="legend"><div class="box">
      <div style="display:flex;justify-content:space-between;align-items:baseline"><span class="head" style="font-size:18px">Miles traveled</span><span class="head" style="font-size:26px;color:#C1272D">${fmt(total)}</span></div>
      <div class="miles">${['Green', 'Red', 'Blue', 'Orange'].map((l) => `<div class="${miles[l] ? '' : 'zero'}" style="background:${l === 'Red' ? '#C1272D' : LINE[l]};${miles[l] ? '' : `border-color:${LINE[l]}`}"><b>${fmt(miles[l])}</b><span>${l}</span></div>`).join('')}</div>
      <div class="keys"><span><span style="width:18px;height:5px;border-radius:3px;background:${P.navy}"></span>traveled</span><span><span style="width:18px;border-top:5px dotted ${P.navy}"></span>not yet</span><span><span class="dot" style="background:${P.yellow}"></span>unlocked spot</span></div>
      ${sample ? `<span class="src">sample rides shown until you verify your own</span>` : ''}</div>${starBtn()}</div>
    ${unlocked.length ? `<div class="spotcard" id="spot"></div>` : `<div class="spotcard"><span style="font-weight:800">Ride somewhere to unlock spots</span></div>`}</div>`;

  const map = (S.map = new maplibregl.Map({ container: 'map', style: BASEMAP, center: [-71.08, 42.36], zoom: 11.8, pitch: 30, bearing: -10,
    attributionControl: { compact: true, customAttribution: 'BPDA · MBTA' } }));
  map.on('load', () => {
    paintCanvas(map);
    map.addSource('lines', { type: 'geojson', data: S.shapes });
    map.addSource('dots', { type: 'geojson', data: dotted(140) });
    map.addLayer({ id: 'not-yet', type: 'circle', source: 'dots', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 1.8, 14, 3.5], 'circle-color': ['get', 'color'] } });
    map.addSource('ridden', { type: 'geojson', data: fc(ridden.map((r) => ({ type: 'Feature', properties: { color: LINE[r.line] }, geometry: { type: 'LineString', coordinates: r.seg.coords } }))) });
    map.addLayer({ id: 'ridden-under', type: 'line', source: 'ridden', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': P.navy, 'line-width': 11 } });
    map.addLayer({ id: 'ridden', type: 'line', source: 'ridden', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 7 } });
    addIconic(map);
    map.addSource('st', { type: 'geojson', data: fc(S.stations.filter((s) => reached.has(s.id)).map((s) => pt(s.lon, s.lat, { name: s.name }))) });
    map.addLayer({ id: 'st', type: 'circle', source: 'st', paint: { 'circle-radius': 5, 'circle-color': '#fff', 'circle-stroke-color': P.navy, 'circle-stroke-width': 2.5 } });
    map.addLayer({ id: 'st-labels', type: 'symbol', source: 'st', layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Bold'], 'text-size': 10, 'text-offset': [0.8, 0], 'text-anchor': 'left' }, paint: { 'text-color': P.navy, 'text-halo-color': '#fff', 'text-halo-width': 1.6 } });
  });
  map.on('click', (e) => iconicPopup(map, e));
  const pts = [...reachedSt, ...ridden.flatMap((r) => r.seg.coords.map(ll))];
  if (pts.length > 1) {
    const lons = pts.map((p) => p.lon), lats = pts.map((p) => p.lat);
    map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: { top: 230, bottom: 230, left: 50, right: 50 }, maxZoom: 14.5, duration: 0 });
  }
  function draw() {
    S.markers.forEach((m) => m.remove()); S.markers = [];
    const pins = unlocked.map((u, j) => {
      const b = document.createElement('button');
      b.className = 'check' + (j === sel ? ' sel' : ''); b.setAttribute('aria-label', u.name);
      b.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg>`;
      b.onclick = (e) => { e.stopPropagation(); sel = j; draw(); };
      return marker(map, b, u.lon, u.lat);
    });
    const tidy = () => declutter(map, pins, sel, 30);
    map.off('moveend', S.tidy); S.tidy = tidy; map.on('moveend', tidy); tidy();
    const u = unlocked[sel], el = document.getElementById('spot');
    if (u && el) el.innerHTML = `<span style="display:flex;flex-direction:column"><span style="font-weight:800;font-size:15px">${esc(u.name)}</span><span style="font-size:12px;font-weight:600">unlocked · ${u.facts} fact${u.facts > 1 ? 's' : ''} · near ${esc(u.stop)}</span></span><span class="hand" style="font-size:20px;flex-shrink:0">${unlocked.length} unlocked!</span>`;
  }
  draw();
};

// ---------- Explore (Explore.dc.html). Partners are Isabella's FICTIONAL demo businesses (see design/canvas/README.md)
const EX_ICON = { Restaurants: 'M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 3c-2 2-2 6 0 8v10', Drinks: 'M7 8h10l-1 13H8zM12 8l2-5h3', Sightseeing: 'M3 21h18M5 18h14M6 10v8M10 10v8M14 10v8M18 10v8M3 10l9-6 9 6z', Shopping: 'M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2', 'Cafés': 'M4 9h12v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM16 11h2a2 2 0 0 1 0 4h-2M8 3v3M12 3v3' };
const EX_LINE = { green: '#00843D', red: '#DA291C', orange: '#ED8B00', blue: '#003DA5' };
const EX_OWN = { latinx: '#E63946', women: '#F4A6C6', black: '#457B9D' };
const PARTNERS = [
  { name: 'Abuela’s Kitchen', cat: 'Restaurants', stop: 'Park Street', lines: ['green', 'red'], owners: ['latinx', 'women'], color: '#F4A6C6', promo: '15% off for Boston Lobstahs', reco: 'Your most-visited stop', along: 2, alongWhy: '2 stops ahead' },
  { name: 'Steep & Swirl Tea Bar', cat: 'Drinks', stop: 'Boylston', lines: ['green'], owners: ['women'], color: '#B8E0A8', promo: 'Buy 1 bubble tea, get 1 free', along: 1, alongWhy: 'next stop!' },
  { name: 'Old Brick Walking Tours', cat: 'Sightseeing', stop: 'Government Center', lines: ['green', 'blue'], owners: [], color: '#A8DADC', promo: '$5 off any tour', reco: 'You fave history facts', along: 3, alongWhy: '3 stops ahead' },
  { name: 'Harborlight Books', cat: 'Shopping', stop: 'Charles/MGH', lines: ['red'], owners: [], color: '#FFC93C', promo: '10% off + a free T-Quest sticker', reco: 'On your usual Red Line ride' },
  { name: 'Roxbury Roots Café', cat: 'Cafés', stop: 'Ruggles', lines: ['orange'], owners: ['black'], color: '#F4A261', promo: 'Free pastry with any coffee', reco: 'A new line to unlock', ethnic: true },
  { name: 'Copley Corner Bakery', cat: 'Cafés', stop: 'Copley', lines: ['green'], owners: ['women'], color: '#FFE3A3', promo: '20% off for Patriots', along: 9, alongWhy: 'behind you' },
  { name: 'Pho Lantern', cat: 'Restaurants', stop: 'Chinatown', lines: ['orange'], owners: [], color: '#FFD6C9', promo: 'Free spring rolls on $20+', reco: 'Near your next transfer', ethnic: true },
  { name: 'Sabor del Barrio', cat: 'Restaurants', stop: 'Jackson Square', lines: ['orange'], owners: ['latinx'], color: '#FFC9C9', promo: 'Free agua fresca for T-Quest riders', ethnic: true },
];
screens.explore = async () => {
  const st = { cat: 'All', sheet: false, lines: {}, owners: {}, ethnic: store.get('ethnic', false) };
  const CATS = ['All', 'Sightseeing', 'Restaurants', 'Drinks', 'Cafés', 'Shopping'];
  const CATC = { All: '#FFC93C', Sightseeing: '#A8DADC', Restaurants: '#F4A6C6', Drinks: '#B8E0A8', 'Cafés': '#F4A261', Shopping: '#FFE3A3' };
  const on = (o) => Object.keys(o).filter((k) => o[k]);
  const pass = (p) => (st.cat === 'All' || p.cat === st.cat)
    && (!on(st.lines).length || on(st.lines).some((l) => p.lines.includes(l)))
    && (!on(st.owners).length || on(st.owners).some((o) => o === 'local' || p.owners.includes(o)));
  const card = (p, why) => `<div class="pcard"><div class="top" style="background:${p.color}">
      <svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${EX_ICON[p.cat]}"/></svg>
      <span class="badge">LOCALLY OWNED</span><span style="position:absolute;right:8px;top:8px;display:flex">${p.owners.map((o, k) => `<span style="display:block;width:18px;height:18px;border-radius:50%;border:2.5px solid ${P.navy};background:${EX_OWN[o]};${k ? 'margin-left:-6px' : ''}"></span>`).join('')}</span></div>
    <div style="padding:10px 12px;display:flex;flex-direction:column;gap:4px"><span style="font-weight:800;font-size:15px">${esc(p.name)}</span>
      <span style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:${P.steel}"><span class="dot" style="width:10px;height:10px;background:${EX_LINE[p.lines[0]]}"></span>${p.cat} · ${esc(p.stop)}</span>
      <span style="font-size:12px;font-weight:600">${esc(why)}</span><span class="promo">${esc(p.promo)}</span></div></div>`;
  const section = (title, sub, color, list) => `<section style="display:flex;flex-direction:column;gap:8px"><div style="padding:0 18px"><h2 class="head" style="margin:0;font-size:20px">${title}</h2><span class="hand" style="font-size:18px;color:${color}">${sub}</span></div>
    <div class="hscroll" style="padding:4px 18px 10px">${list.length ? list.join('') : `<div class="hand" style="flex-shrink:0;width:300px;border:3px dashed ${P.navy};border-radius:20px;padding:18px;font-size:20px">nothing here with these filters yet</div>`}</div></section>`;
  const opt = (o) => `class="pillbtn ${o ? 'on' : ''}" style="${o ? `background:${P.yellow}` : ''}"`;
  const draw = () => {
    const reco = PARTNERS.filter((p) => p.reco && pass(p)).map((p) => card(p, p.reco));
    const along = PARTNERS.filter((p) => p.along && pass(p)).sort((a, b) => a.along - b.along).map((p) => card(p, p.alongWhy));
    const eth = PARTNERS.filter((p) => p.ethnic && pass(p)).map((p) => card(p, 'Ethnic Boston pick'));
    const active = on(st.lines).length + on(st.owners).length + (st.ethnic ? 1 : 0);
    app().innerHTML = `<div class="page">
      <div style="display:flex;align-items:center;gap:12px;padding:18px 18px 8px"><div style="display:flex;flex-direction:column;flex-grow:1"><span class="hand" style="font-size:21px;color:${P.steel}">where to next?</span><h1 class="head" style="margin:0;font-size:30px;line-height:1.1">Explore</h1></div>${starBtn()}</div>
      <div class="hscroll" style="gap:8px;padding:6px 18px 12px;flex-shrink:0">
        <button class="pillbtn" id="filter" style="background:${P.navy};color:${P.cream};flex-shrink:0;min-height:42px"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>Filter${active ? `<span style="background:${P.yellow};color:${P.navy};border-radius:999px;min-width:18px;height:18px;font-size:11px;display:flex;align-items:center;justify-content:center">${active}</span>` : ''}</button>
        ${CATS.map((c) => `<button class="pillbtn ${st.cat === c ? 'on' : ''}" data-cat="${c}" style="flex-shrink:0;min-height:42px;${st.cat === c ? `background:${CATC[c]}` : ''}">${c}</button>`).join('')}</div>
      <div class="scrolly" style="display:flex;flex-direction:column;gap:18px">
        ${section('Recommended for you', 'picked from where you ride + what you fave', P.red, reco)}
        ${section('Popular along the Green Line', 'heading inbound → closest first', '#00843D', along)}
        ${st.ethnic ? section('Ethnic Boston', 'flavors from all over, right here', P.steel, eth) : ''}</div>
      ${st.sheet ? `<div class="sheetwrap"><div class="sheet">
        <div style="display:flex;justify-content:space-between;align-items:center"><span class="head" style="font-size:22px">Filter</span><button class="round" id="close" style="width:40px;height:40px;box-shadow:none" aria-label="Close filters"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${P.navy}" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
        <div style="display:flex;flex-direction:column;gap:8px"><span style="font-size:13px;font-weight:800">Along a line</span><div style="display:flex;flex-wrap:wrap;gap:8px">${[['green', 'Green Line'], ['red', 'Red Line'], ['orange', 'Orange Line'], ['blue', 'Blue Line']].map(([k, l]) => `<button data-line="${k}" ${opt(st.lines[k])}><span class="dot" style="background:${EX_LINE[k]}"></span>Along ${l}</button>`).join('')}</div></div>
        <div style="display:flex;flex-direction:column;gap:8px"><span style="font-size:13px;font-weight:800">Owned by</span><div style="display:flex;flex-wrap:wrap;gap:8px">${[['local', 'Locally owned', '#FFFFFF'], ['latinx', 'Latinx-owned', EX_OWN.latinx], ['women', 'Women-owned', EX_OWN.women], ['black', 'Black-owned', EX_OWN.black]].map(([k, l, c]) => `<button data-own="${k}" ${opt(st.owners[k])}><span class="dot" style="background:${c}"></span>${l}</button>`).join('')}</div></div>
        <div style="display:flex;justify-content:space-between;align-items:center;background:#fff;border:2.5px solid ${P.navy};border-radius:16px;padding:10px 12px"><span style="display:flex;flex-direction:column"><span style="font-weight:800;font-size:14px">Ethnic Boston</span><span style="font-size:12px;color:${P.steel};font-weight:600">adds a section of culture-rich spots</span></span>
          <button class="switch" id="ethnic" aria-pressed="${st.ethnic}" aria-label="Ethnic Boston" style="background:${st.ethnic ? P.lgreen : '#fff'};justify-content:${st.ethnic ? 'flex-end' : 'flex-start'}"><i></i></button></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><button class="bigbtn" id="clear">Clear all</button><button class="bigbtn yellow" id="show">Show ${PARTNERS.filter(pass).length} spots</button></div></div></div>` : ''}</div>`;
    const $ = (s) => app().querySelector(s);
    $('#filter').onclick = () => { st.sheet = true; draw(); };
    app().querySelectorAll('[data-cat]').forEach((b) => (b.onclick = () => { st.cat = b.dataset.cat; draw(); }));
    if (st.sheet) {
      $('#close').onclick = $('#show').onclick = () => { st.sheet = false; draw(); };
      $('#clear').onclick = () => { st.lines = {}; st.owners = {}; st.ethnic = false; store.set('ethnic', false); draw(); };
      $('#ethnic').onclick = () => { st.ethnic = !st.ethnic; store.set('ethnic', st.ethnic); draw(); };
      app().querySelectorAll('[data-line]').forEach((b) => (b.onclick = () => { st.lines[b.dataset.line] = !st.lines[b.dataset.line]; draw(); }));
      app().querySelectorAll('[data-own]').forEach((b) => (b.onclick = () => { st.owners[b.dataset.own] = !st.owners[b.dataset.own]; draw(); }));
    }
  };
  draw();
};

// ---------- Faves (Faves.dc.html)
screens.faves = async () => {
  const BG = [P.yellow, P.pink, P.lblue, P.lgreen, '#FFE3A3'], ROT = [-1, 1, -0.8, 0.8, -0.6];
  const draw = () => {
    const items = Object.entries(faves());
    app().innerHTML = `<div class="page" style="gap:14px;padding:20px 18px;overflow-y:auto">
      <div style="display:flex;align-items:center;gap:12px">
        <a href="#/home" class="round" style="width:44px;height:44px;box-shadow:2px 2px 0 ${P.navy}" aria-label="Back"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M15 6l-6 6 6 6"/></svg></a>
        <div style="display:flex;flex-direction:column"><span class="hand" style="font-size:21px;color:${P.red}">the good stuff</span><h1 class="head" style="margin:0;font-size:26px;line-height:1.1">Faved fun facts</h1></div>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="${P.yellow}" stroke="${P.navy}" stroke-width="1.8" stroke-linejoin="round" style="margin-left:auto;transform:rotate(10deg)"><path d="${STAR}"/></svg></div>
      <span style="font-size:13px;font-weight:600;color:${P.steel}">${items.length} facts saved · tap a star to unfave</span>
      <div style="display:flex;flex-direction:column;gap:14px">${items.map(([k, f], i) => `
        <div style="background:${BG[i % 5]};border:3px solid ${P.navy};border-radius:18px;box-shadow:4px 4px 0 ${P.navy};padding:12px 14px;display:flex;flex-direction:column;gap:6px;transform:rotate(${ROT[i % 5]}deg)">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span style="display:flex;align-items:center;gap:8px;font-weight:800;font-size:15px"><span class="dot" style="width:14px;height:14px;background:${f.line}"></span>${esc(f.place)}</span>
            <button class="round" data-k="${esc(k)}" style="width:40px;height:40px;box-shadow:none;border-width:2.5px" aria-label="Unfave this fact"><svg width="20" height="20" viewBox="0 0 24 24" fill="${P.yellow}" stroke="${P.navy}" stroke-width="2" stroke-linejoin="round"><path d="${STAR}"/></svg></button></div>
          <p style="margin:0;font-size:14px;line-height:1.4;font-weight:500">${esc(f.fact)}</p></div>`).join('') || `<div class="hand" style="border:3px dashed ${P.navy};border-radius:18px;padding:20px;text-align:center;font-size:22px">no faves yet... go find some!</div>`}</div></div>`;
    app().querySelectorAll('[data-k]').forEach((b) => (b.onclick = () => { const all = faves(); delete all[b.dataset.k]; store.set('faves', all); draw(); }));
  };
  draw();
};

// ---------- User page (Profile.dc.html): real rank and points from game-engine, fictional partner perks
screens.profile = async () => {
  const rank = await api('ge', '/me/rank');
  const RANKS = ['Harbor Seal', 'Town Crier', 'Lamplighter', 'Midnight Rider', 'Tea Party Raider', 'Children of Liberty', 'Boston Lobstah', 'Patriot'];
  const step = 300 / 7, xs = RANKS.map((_, i) => 10 + i * step);
  // the points bar is a T line with one stop per rank; you sit between your rank and the next
  const youX = xs[rank.rank - 1] + (rank.next_rank_at ? Math.min(0.9, 1 - rank.points_to_next / rank.next_rank_at) * step : 0);
  const perks = [
    { name: 'Abuela’s Kitchen', where: 'Park Street · Green/Red', big: `${rank.discount_pct}% OFF`, who: `for ${rank.name}s`, detail: 'Any dine-in order', color: '#F4A6C6' },
    { name: 'Steep & Swirl Tea Bar', where: 'Boylston · Green', big: 'BOGO', who: 'bubble tea', detail: 'Weekdays after 3pm', color: '#B8E0A8' },
    { name: 'Harborlight Books', where: 'Charles/MGH · Red', big: '10% OFF', who: '+ free sticker', detail: 'Any book over $10', color: '#A8DADC' },
    { name: 'Roxbury Roots Café', where: 'Ruggles · Orange', big: 'FREE', who: 'pastry with coffee', detail: 'Once a week', color: '#F4A261' },
    ...(rank.next_rank_name ? [{ name: 'Copley Corner Bakery', where: 'Copley · Green', big: '20% OFF', who: `unlocks at ${rank.next_rank_name}`, detail: `${rank.points_to_next} points to go!`, color: '#E6E1D6', locked: true }] : []),
  ];
  app().innerHTML = `<div class="page">
    <div style="position:relative;background:${P.lblue};border-bottom:3px solid ${P.navy};padding:18px 18px 16px;display:flex;align-items:center;gap:14px">
      <svg width="390" height="170" viewBox="0 0 390 170" fill="none" style="position:absolute;left:0;top:0"><path d="M352 20l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="${P.yellow}" stroke="${P.navy}" stroke-width="2" stroke-linejoin="round"/><path d="M330 130c8-8 16 8 24 0s16 8 24 0" stroke="${P.red}" stroke-width="3" stroke-linecap="round"/><circle cx="300" cy="28" r="5" fill="${P.pink}" stroke="${P.navy}" stroke-width="2"/></svg>
      <div style="position:relative;width:112px;height:112px;flex-shrink:0;border-radius:50%;background:${P.cream};border:4px solid ${P.navy};box-shadow:4px 4px 0 ${P.navy};display:flex;align-items:center;justify-content:center;text-align:center;font-size:11px;font-weight:700;padding:12px">[Rank avatar: your ${esc(rank.name)} drawing]</div>
      <div style="position:relative;display:flex;flex-direction:column;gap:4px;align-items:flex-start"><span class="hand" style="font-size:21px">you're a...</span>
        <span class="head" style="font-size:25px;line-height:1;background:#fff;border:3px solid ${P.navy};border-radius:999px;padding:6px 14px;transform:rotate(-2deg)">${esc(rank.name)}</span>
        <span style="font-size:13px;font-weight:700;margin-top:4px">@${USER}</span></div></div>
    <div class="scrolly" style="padding-top:14px;display:flex;flex-direction:column;gap:14px">
      <div class="box" style="margin:0 18px;border-radius:18px;box-shadow:4px 4px 0 ${P.navy};padding:10px 14px;display:flex;flex-direction:column;gap:6px">
        <div style="display:flex;justify-content:space-between;align-items:baseline"><span class="head" style="font-size:19px">Points</span><span style="font-weight:800">${rank.lifetime_points.toLocaleString()} ${rank.next_rank_name ? `<span class="hand" style="font-size:18px;color:#C1272D">· ${rank.points_to_next} to ${esc(rank.next_rank_name)}!</span>` : ''}</span></div>
        <svg width="100%" height="22" viewBox="0 0 320 22" fill="none"><path d="M10 11H310" stroke="${P.lblue}" stroke-width="8" stroke-linecap="round"/><path d="M10 11H${youX}" stroke="${P.red}" stroke-width="8" stroke-linecap="round"/>
          <g fill="#fff" stroke="${P.navy}" stroke-width="2.5">${xs.map((x, i) => `<circle cx="${x}" cy="11" r="${i === 7 ? 7 : 6}"><title>${RANKS[i]}</title></circle>`).join('')}</g><circle cx="${youX}" cy="11" r="9" fill="${P.yellow}" stroke="${P.navy}" stroke-width="3"/></svg></div>
      <div style="position:relative;margin:6px 18px 0;background:${P.yellow};border:3px solid ${P.navy};border-radius:20px;box-shadow:5px 5px 0 ${P.navy};padding:14px;display:flex;flex-direction:column;gap:10px">
        <span class="hand" style="position:absolute;top:-15px;right:16px;background:${P.red};color:#fff;border:2.5px solid ${P.navy};border-radius:999px;padding:0 12px;font-size:19px;transform:rotate(3deg)">prizes!</span>
        <span class="head" style="font-size:19px;line-height:1.2">Show this page at partnered stores to get your prizes</span>
        <div style="background:#fff;border:2.5px dashed ${P.navy};border-radius:14px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center">
          <span style="display:flex;flex-direction:column"><span style="font-size:11px;font-weight:800;color:${P.steel}">T-QUEST MEMBER</span><span style="font-weight:800">@${USER} · ${esc(rank.name)}</span></span>
          <span class="head" style="font-size:18px;letter-spacing:2px">[#0042]</span></div></div>
      <div style="padding:0 18px"><h2 class="head" style="margin:0;font-size:20px">Your ${esc(rank.name)} perks</h2><span class="hand" style="font-size:18px;color:${P.red}">swipe for more →</span></div>
      <div class="hscroll" style="padding:0 18px 10px">${perks.map((o) => `
        <div style="flex-shrink:0;width:200px;background:#fff;border:3px solid ${P.navy};border-radius:20px;overflow:hidden;display:flex;flex-direction:column;${o.locked ? 'border-style:dashed;opacity:.85' : `box-shadow:4px 4px 0 ${P.navy}`}">
          <div style="background:${o.color};border-bottom:3px dashed ${P.navy};padding:12px;display:flex;flex-direction:column;gap:2px"><span class="head" style="font-size:30px;line-height:1">${esc(o.big)}</span><span style="font-size:12px;font-weight:800">${esc(o.who)}</span></div>
          <div style="padding:10px 12px;display:flex;flex-direction:column;gap:3px"><span style="font-weight:800;font-size:15px">${esc(o.name)}</span><span style="font-size:12px;font-weight:600;color:${P.steel}">${esc(o.where)}</span><span style="font-size:12px;font-weight:600">${esc(o.detail)}</span>
            <span style="margin-top:4px;align-self:flex-start;background:#fff;border:2px solid ${P.navy};border-radius:999px;padding:1px 8px;font-size:10px;font-weight:800">${o.locked ? 'LOCKED · KEEP RIDING' : 'LOCALLY OWNED'}</span></div></div>`).join('')}</div></div></div>`;
};

render();
