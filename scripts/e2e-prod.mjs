#!/usr/bin/env node
// End-to-end check of the PUBLIC-DEMO configuration, run locally.
// Starts the three backends with APP_ENV=prod, a throwaway TOKEN_SECRET (random, never printed) and a throwaway
// CORS origin, then runs a scripted flow plus negative cases (no token, bad token, plain username, tampered, expired,
// wrong origin, oversize body, docs hidden, login rate limit, security headers).
// game-engine runs in its in-memory demo mode, so nothing is written to any database.
//   node scripts/e2e-prod.mjs
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const ORIGIN = 'http://localhost:5199';
const EVIL = 'https://evil.example.test';
const SECRET = randomBytes(24).toString('hex');
const { DATABASE_URL, ...clean } = process.env;
const env = { ...clean, APP_ENV: 'prod', TOKEN_SECRET: SECRET, CORS_ORIGINS: ORIGIN, RATE_LOGIN_PER_MIN: '8' };
const py = process.platform === 'win32' ? 'python' : 'python3';
const B = { dp: 'http://127.0.0.1:8011', is: 'http://127.0.0.1:8012', ge: 'http://127.0.0.1:8013' };
const services = [
  { key: 'dp', cwd: 'data-platform', env: { PYTHONPATH: 'src' }, args: ['-m', 'uvicorn', 'data_platform.app:app', '--port', '8011'], health: '/health' },
  { key: 'is', cwd: 'insights-sponsors', env: { PYTHONPATH: 'src', DATA_BACKEND: 'postgres' }, args: ['-m', 'uvicorn', 'insights_sponsors.main:app', '--port', '8012'], health: '/health' },
  { key: 'ge', cwd: 'game-engine/src', env: {}, args: ['-m', 'uvicorn', 'game_engine.app:app', '--port', '8013'], health: '/healthz' },
];
const started = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra = '') => { results.push({ name, ok }); console.log(`  ${ok ? 'PASS' : 'FAIL'} ${name}${ok || !extra ? '' : ` (${extra})`}`); };

async function up(s) { try { return (await fetch(B[s.key] + s.health, { signal: AbortSignal.timeout(2000) })).ok; } catch { return false; } }
async function start(s) {
  started.push(spawn(py, s.args, { cwd: path.join(root, s.cwd), env: { ...env, ...s.env }, stdio: 'ignore' }));
  for (let i = 0; i < 60; i++) { await sleep(500); if (await up(s)) return; }
  throw new Error(`${s.key} did not start`);
}
function mint(username, ttl, now) {
  const r = spawnSync(py, ['-c', 'import sys,os;sys.path.insert(0,"shared");import tquest_auth as a;print(a.issue_token(sys.argv[1],os.environ["TOKEN_SECRET"],ttl_s=int(sys.argv[2]),now=float(sys.argv[3])))', username, String(ttl), String(now)], { cwd: root, env, encoding: 'utf8' });
  return r.stdout.trim();
}
async function call(svc, p, { method = 'GET', token, origin = ORIGIN, body, headers = {} } = {}) {
  const h = { Origin: origin, ...headers };
  if (token) h.Authorization = `Bearer ${token}`;
  if (body !== undefined && !h['Content-Type']) h['Content-Type'] = 'application/json';
  const r = await fetch(B[svc] + p, { method, headers: h, body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body) });
  let json = null; try { json = await r.clone().json(); } catch { /* not json */ }
  return { status: r.status, headers: r.headers, json, text: await r.text() };
}

async function main() {
  console.log('Starting services with APP_ENV=prod (throwaway secret and origin)...');
  for (const s of services) await start(s);

  console.log('\nFlow');
  const login = await call('is', '/auth/demo-login', { method: 'POST', body: { username: 'e2eRider1' } });
  check('login issues a signed token (not the username)', login.status === 200 && login.json.token && login.json.token !== 'e2eRider1' && login.json.token.includes('.'));
  const token = login.json?.token;
  check('login response has CORS for the allowed origin', login.headers.get('access-control-allow-origin') === ORIGIN);
  const stops = await call('dp', '/stops?lat=42.3564&lon=-71.0624&radius_m=300&limit=5');
  check('list stops near Park Street (public, real MBTA data)', stops.status === 200 && stops.json.length > 0);
  const checkin = await call('ge', '/checkins', { method: 'POST', token, body: { stop_id: 'park', lat: 42.3564, lon: -71.0624, client_time: new Date().toISOString() } });
  check('check-in with the token (game-engine demo mode)', checkin.status === 201 && checkin.json.points_awarded > 0, `HTTP ${checkin.status}`);
  const rank = await call('ge', '/me/rank', { token });
  const pts = await call('ge', '/me/points', { token });
  check('rank and points reflect the check-in', rank.status === 200 && pts.status === 200 && pts.json.lifetime > 0 && typeof rank.json.name === 'string');
  const nb = await call('is', '/stops/place-davis/nearby?category=cafe&label=immigrant-owned', { token });
  check('nearby filter category + label (Sample spot only)', nb.status === 200 && nb.json.total === 1 && nb.json.spots[0].name.startsWith('Sample'));
  const pend = await call('is', '/stops/place-davis/nearby?label=woman-owned', { token });
  check('pending label never matches', pend.status === 200 && pend.json.total === 0);
  const offers = await call('is', '/offers?rank=2', { token });
  check('offers by rank (all demo)', offers.status === 200 && offers.json.length > 0 && offers.json.every((o) => o.demo === true));
  const content = await call('is', '/stops/place-pktrm/content?limit=3', { token });
  check('content has attribution and source on every item', content.status === 200 && content.json.length > 0 && content.json.every((c) => c.attribution && c.source_url));
  const travel = await call('dp', '/me/travel', { token });
  check('travel zero state for a new rider', travel.status === 200 && travel.json.total_miles === 0);
  const fave = await call('is', '/me/faves/fact.pktrm.1', { method: 'POST', token });
  const faves = await call('is', '/me/faves', { token });
  check('fave and list faves', fave.status === 204 && faves.json.length === 1);
  await call('is', '/me/faves/fact.pktrm.1', { method: 'DELETE', token });

  console.log('\nAuth negatives');
  for (const [svc, p] of [['ge', '/me/rank'], ['is', '/me/faves'], ['dp', '/me/travel']]) {
    check(`${svc} ${p}: no token -> 401`, (await call(svc, p)).status === 401);
    check(`${svc} ${p}: garbage token -> 401`, (await call(svc, p, { token: 'not-a-token' })).status === 401);
    check(`${svc} ${p}: plain username -> 401 in prod`, (await call(svc, p, { token: 'e2eRider1' })).status === 401);
    const t = token.split('.');
    check(`${svc} ${p}: tampered signature -> 401`, (await call(svc, p, { token: `${t[0]}.${t[1].slice(0, -3)}AAA` })).status === 401);
    check(`${svc} ${p}: expired token -> 401`, (await call(svc, p, { token: mint('e2eRider1', 60, 1000) })).status === 401);
    check(`${svc} ${p}: token signed with another secret -> 401`, (await call(svc, p, { token: spawnSync(py, ['-c', 'import sys;sys.path.insert(0,"shared");import tquest_auth as a;print(a.issue_token("e2eRider1","z"*32))'], { cwd: root, encoding: 'utf8' }).stdout.trim() })).status === 401);
  }
  check('401 body is generic (no stack trace)', !/Traceback|File "/.test((await call('ge', '/me/rank', { token: 'x' })).text));

  console.log('\nCORS');
  for (const svc of ['dp', 'is', 'ge']) {
    const good = await fetch(B[svc] + (svc === 'ge' ? '/me/rank' : svc === 'is' ? '/me/faves' : '/me/travel'), { method: 'OPTIONS', headers: { Origin: ORIGIN, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization' } });
    const bad = await fetch(B[svc] + '/health', { method: 'OPTIONS', headers: { Origin: EVIL, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization' } });
    check(`${svc}: preflight from the exact origin allowed`, good.headers.get('access-control-allow-origin') === ORIGIN);
    check(`${svc}: preflight from another origin gets no allow-origin`, !bad.headers.get('access-control-allow-origin'));
    const wild = await call(svc, svc === 'dp' ? '/health' : svc === 'is' ? '/health' : '/healthz', { origin: EVIL });
    check(`${svc}: simple request from another origin has no allow-origin`, !wild.headers.get('access-control-allow-origin'));
  }

  console.log('\nHardening');
  check('security headers present', (await call('is', '/health')).headers.get('x-content-type-options') === 'nosniff');
  check('interactive docs and openapi hidden in prod (insights, data-platform)', (await call('is', '/docs')).status === 404 && (await call('dp', '/openapi.json')).status === 404);
  const big = await call('is', '/auth/demo-login', { method: 'POST', body: JSON.stringify({ username: 'a'.repeat(200000) }) });
  check('oversize request body -> 413', big.status === 413, `HTTP ${big.status}`);
  check('bad usernames rejected (422)', (await call('is', '/auth/demo-login', { method: 'POST', body: { username: 'a@b.com' } })).status === 422);
  let limited = 0;
  for (let i = 0; i < 12; i++) if ((await call('is', '/auth/demo-login', { method: 'POST', body: { username: `rate${i}x` } })).status === 429) limited++;
  check('login is rate limited (429)', limited > 0);
  const lim = await call('is', '/auth/demo-login', { method: 'POST', body: { username: 'rateZZZ' } });
  check('429 carries CORS headers so the browser can read it', lim.status !== 429 || lim.headers.get('access-control-allow-origin') === ORIGIN);

  console.log('\nFail closed');
  const bad = spawnSync(py, ['-c', 'import insights_sponsors.main'], { cwd: path.join(root, 'insights-sponsors'), env: { ...env, TOKEN_SECRET: '', PYTHONPATH: 'src' }, encoding: 'utf8' });
  check('prod without TOKEN_SECRET refuses to start', bad.status !== 0);
  const bad2 = spawnSync(py, ['-c', 'import insights_sponsors.main'], { cwd: path.join(root, 'insights-sponsors'), env: { ...env, CORS_ORIGINS: '*', PYTHONPATH: 'src' }, encoding: 'utf8' });
  check('prod with wildcard CORS refuses to start', bad2.status !== 0);
}

try { await main(); } catch (e) { console.error('e2e failed:', e.message); results.push({ name: 'run', ok: false }); }
started.forEach((c) => c.kill());
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} checks passed${failed ? `, ${failed} FAILED` : ''}.`);
process.exit(failed ? 1 : 0);
