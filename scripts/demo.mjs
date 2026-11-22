#!/usr/bin/env node
// One-command demo tour. Starts data-platform (8001), insights-sponsors (8002) and game-engine (8003, in-memory
// demo mode) if they are not already running, prints a short tour of real calls, then stops what it started.
//   node scripts/demo.mjs            run the tour
//   node scripts/demo.mjs --serve    keep the services running after the tour (Ctrl+C to stop)
// Never prints secrets. DATABASE_URL is removed from the child environment; each Python service reads .env itself
// (game-engine runs in memory mode on purpose, so the tour writes nothing to the shared database).
import { spawn } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const serve = process.argv.includes('--serve');
const { DATABASE_URL, ...cleanEnv } = process.env;
const started = [];

const services = [
  { name: 'data-platform', port: 8001, health: '/health', cwd: 'data-platform', env: { PYTHONPATH: 'src' }, args: ['-m', 'uvicorn', 'data_platform.app:app', '--port', '8001'] },
  { name: 'insights-sponsors', port: 8002, health: '/health', cwd: 'insights-sponsors', env: { PYTHONPATH: 'src', DATA_BACKEND: 'postgres' }, args: ['-m', 'uvicorn', 'insights_sponsors.main:app', '--port', '8002'] },
  { name: 'game-engine', port: 8003, health: '/healthz', cwd: 'game-engine/src', env: {}, args: ['-m', 'uvicorn', 'game_engine.app:app', '--port', '8003'] },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function up(s) {
  try { return (await fetch(`http://127.0.0.1:${s.port}${s.health}`, { signal: AbortSignal.timeout(2000) })).ok; } catch { return false; }
}

async function ensure(s) {
  if (await up(s)) { console.log(`  ${s.name}: already running on ${s.port}`); return; }
  const child = spawn(process.platform === 'win32' ? 'python' : 'python3', s.args, {
    cwd: path.join(root, s.cwd), env: { ...cleanEnv, ...s.env }, stdio: 'ignore',
  });
  started.push(child);
  for (let i = 0; i < 40; i++) { await sleep(500); if (await up(s)) { console.log(`  ${s.name}: started on ${s.port}`); return; } }
  throw new Error(`${s.name} did not become healthy`);
}

const get = async (port, p, user = 'demo-rider') => {
  const r = await fetch(`http://127.0.0.1:${port}${p}`, { headers: { Authorization: `Bearer ${user}` } });
  return { status: r.status, body: await r.json() };
};
const post = async (port, p, body, user = 'demo-rider') => {
  const r = await fetch(`http://127.0.0.1:${port}${p}`, { method: 'POST', headers: { Authorization: `Bearer ${user}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return { status: r.status, body: await r.json() };
};
const h = (t) => console.log(`\n=== ${t}`);
const spot = (s) => `${s.name} [${s.category.slug}${s.placement_type === 'sponsored' ? ', sponsored' : ''}${s.demo ? ', demo' : ''}] labels: ${s.labels.map((l) => `${l.display_name} (${l.status})`).join(', ') || 'none'}${s.fun_fact ? `
     fun fact (demo): ${s.fun_fact}` : ''}`;

async function tour() {
  console.log('Demo placeholder. No partnership, endorsement or real discount is implied. Rider data is synthetic; MBTA data is real.');

  h('1. REAL live MBTA data in Tiger Data (data-platform :8001)');
  const v = await get(8001, '/vehicles?route_id=Red');
  console.log(`  Red Line vehicles reporting in the last 2 minutes: ${v.body.length}`);
  v.body.slice(0, 3).forEach((x) => console.log(`  vehicle ${x.label} on ${x.route_id}: ${x.current_status} at (${x.lat}, ${x.lon}) @ ${x.time}`));
  const al = await get(8001, '/alerts');
  console.log(`  active alerts right now: ${Array.isArray(al.body) ? al.body.length : 'n/a'}`);

  h('2. Nearby spots at Harvard (insights-sponsors :8002), no filters');
  const all = (await get(8002, '/stops/place-harsq/nearby')).body;
  all.spots.forEach((s) => console.log('  ' + spot(s)));
  console.log('  filter chips:', all.facets.categories.map((c) => `${c.slug}:${c.count}`).join(' '), '|', all.facets.labels.map((c) => `${c.slug}:${c.count}`).join(' '));
  console.log('  note: Mint Julep holds a pending label, so no label is shown for it.');

  h('3. Filters combine: Davis, cafe + immigrant-owned (fictional sample spots)');
  (await get(8002, '/stops/place-davis/nearby?category=cafe&label=immigrant-owned')).body.spots.forEach((s) => console.log('  ' + spot(s)));
  h('   Davis, label woman-owned (only a PENDING label exists, so nothing matches)');
  console.log('  results:', (await get(8002, '/stops/place-davis/nearby?label=woman-owned')).body.total);
  h('   Harvard, asian-owned OR woman-owned (match=any)');
  (await get(8002, '/stops/place-harsq/nearby?label=asian-owned&label=woman-owned&match=any')).body.spots.forEach((s) => console.log('  ' + spot(s)));
  h('   Davis, sponsored first, with native offers');
  (await get(8002, '/stops/place-davis/nearby?sort=sponsored_first')).body.spots.slice(0, 1).forEach((s) => { console.log('  ' + spot(s)); s.offers.forEach((o) => console.log(`     offer: ${o.title} (rank ${o.min_rank}+, demo=${o.demo})`)); });

  h('4. Rank tiers, from the shared ranks table (game-engine\'s 8 ranks; percentages are demo placeholders)');
  (await get(8002, '/rank-tiers')).body.forEach((t) => console.log(`  ${t.rank}. ${t.name.padEnd(20)} from ${String(t.min_lifetime_points).padStart(5)} pts  ${t.discount_pct}%${t.free_item ? '  + free item' : ''}  offers: ${t.offers.length}`));
  h('   Offers near Fenway (Red Sox demo placeholder)');
  (await get(8002, '/offers?stop_id=place-fenwy')).body.forEach((o) => console.log(`  ${o.title} (rank ${o.min_rank}+, demo=${o.demo})`));

  h('5. Tourist content near Park Street with attribution');
  const c = (await get(8002, '/stops/place-pktrm/content?limit=4')).body;
  c.forEach((i) => console.log(`  ${i.title} (${i.category}, ${i.distance_m} m)\n     source: ${i.source_url}\n     attribution: ${i.attribution}`));
  const fb = (await get(8002, '/stops/place-fenwy/facts')).body;
  if (fb.fallback) console.log(`  Fenway has no stop facts: "${fb.note}" fallback fact: ${fb.facts[0]?.body}`);
  const lf = (await fetch('http://127.0.0.1:8002/loading-facts?limit=2')).json();
  (await lf).forEach((f) => console.log(`  loading fact: ${f.body}`));

  h('6. Game engine (demo mode, fake stops, nothing written to the database)');
  const now = new Date().toISOString();
  for (const [stop, lat, lon] of [['park', 42.3564, -71.0624], ['downtown', 42.3555, -71.0602]]) {
    const r = await post(8003, '/checkins', { stop_id: stop, lat, lon, client_time: now }, 'demo-rider');
    console.log(`  check-in at ${stop}: HTTP ${r.status}`, r.status === 201 ? `+${r.body.points ?? r.body.points_awarded ?? '?'} points` : r.status === 409 ? '(cooldown: already checked in recently, restart game-engine to reset the demo)' : JSON.stringify(r.body).slice(0, 100));
  }
  const rank = (await get(8003, '/me/rank')).body;
  console.log(`  rank: ${rank.name} (${rank.lifetime_points} pts), next: ${rank.next_rank_name} at ${rank.next_rank_at}`);
  const q = (await get(8003, '/quests')).body;
  console.log(`  quests: ${q.map((x) => x.title).join(', ')}`);

  console.log('\nInteractive API docs: http://127.0.0.1:8001/docs  http://127.0.0.1:8002/docs  http://127.0.0.1:8003/docs');
  console.log('Tiger Data numbers for the pitch: PITCH.md (generated block) / docs/TIGER_DATA_RESULTS.md');
}

console.log('Starting services...');
try {
  for (const s of services) await ensure(s);
  await tour();
} catch (e) {
  console.error('demo failed:', e.message);
  process.exitCode = 1;
}
if (serve && !process.exitCode) {
  console.log('\nServices stay up. Ctrl+C to stop.');
  process.on('SIGINT', () => { started.forEach((c) => c.kill()); process.exit(0); });
  await new Promise(() => {});
} else {
  started.forEach((c) => c.kill());
}
