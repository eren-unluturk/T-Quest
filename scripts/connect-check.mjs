#!/usr/bin/env node
// Front-end readiness check. For every screen in design/canvas, calls the endpoints it needs the way a browser app on
// another origin (Vite dev server or a Vercel deployment) would: a CORS preflight with the Authorization header, then
// the real request. Starts the three services if they are not running and stops what it started.
//   node scripts/connect-check.mjs [--origin https://your-app.vercel.app]
// Exit code 1 if anything fails. Prints no secrets.
import { spawn } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const oi = process.argv.indexOf('--origin');
const ORIGIN = oi > 0 ? process.argv[oi + 1] : 'http://localhost:5173';
const { DATABASE_URL, ...cleanEnv } = process.env;
const started = [];
const B = { dp: 'http://127.0.0.1:8001', is: 'http://127.0.0.1:8002', ge: 'http://127.0.0.1:8003' };

const services = [
  { port: 8001, health: '/health', cwd: 'data-platform', env: { PYTHONPATH: 'src' }, args: ['-m', 'uvicorn', 'data_platform.app:app', '--port', '8001'] },
  { port: 8002, health: '/health', cwd: 'insights-sponsors', env: { PYTHONPATH: 'src', DATA_BACKEND: 'postgres' }, args: ['-m', 'uvicorn', 'insights_sponsors.main:app', '--port', '8002'] },
  { port: 8003, health: '/healthz', cwd: 'game-engine/src', env: {}, args: ['-m', 'uvicorn', 'game_engine.app:app', '--port', '8003'] },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const up = async (s) => { try { return (await fetch(`http://127.0.0.1:${s.port}${s.health}`, { signal: AbortSignal.timeout(2000) })).ok; } catch { return false; } };
async function ensure(s) {
  if (await up(s)) return;
  started.push(spawn(process.platform === 'win32' ? 'python' : 'python3', s.args, { cwd: path.join(root, s.cwd), env: { ...cleanEnv, ...s.env }, stdio: 'ignore' }));
  for (let i = 0; i < 40; i++) { await sleep(500); if (await up(s)) return; }
  throw new Error(`service on ${s.port} did not start`);
}

// screen -> [method, base, path]
const SCREENS = {
  Loading: [['GET', 'is', '/loading-facts?limit=3']],
  Home: [['GET', 'is', '/stops/place-harsq/facts'], ['GET', 'dp', '/stops/place-harsq'], ['GET', 'dp', '/vehicles?route_id=Red'],
    ['GET', 'is', '/stops/place-harsq/content?limit=5'], ['GET', 'ge', '/me/rank'], ['GET', 'ge', '/me/points']],
  Traveled: [['GET', 'dp', '/me/travel'], ['GET', 'dp', '/lines']],
  Explore: [['GET', 'is', '/categories'], ['GET', 'is', '/labels'], ['GET', 'is', '/stops/place-harsq/nearby?category=cafe&label=immigrant-owned'],
    ['GET', 'is', '/recommendations'], ['GET', 'is', '/offers?stop_id=place-harsq']],
  Faves: [['GET', 'is', '/me/faves'], ['POST', 'is', '/me/faves/fact.pktrm.1', 204], ['DELETE', 'is', '/me/faves/fact.pktrm.1', 204]],
  Profile: [['GET', 'ge', '/me/rank'], ['GET', 'is', '/rank-tiers'], ['GET', 'is', '/offers?rank=3']],
};

const AUTH = { Authorization: 'Bearer connect-check-user' };
let failures = 0;
async function check(method, base, p, okStatus = 200) {
  const url = B[base] + p;
  const out = [];
  const pre = await fetch(url, { method: 'OPTIONS', headers: { Origin: ORIGIN, 'Access-Control-Request-Method': method, 'Access-Control-Request-Headers': 'authorization,content-type' } });
  const allowO = pre.headers.get('access-control-allow-origin');
  const allowH = (pre.headers.get('access-control-allow-headers') || '').toLowerCase();
  const allowM = (pre.headers.get('access-control-allow-methods') || '').toUpperCase();
  if (!(pre.status < 300 && (allowO === '*' || allowO === ORIGIN) && allowH.includes('authorization') && (allowM.includes(method) || allowM === '*'))) out.push(`CORS preflight blocked (HTTP ${pre.status}, origin ${allowO}, methods ${allowM || 'none'})`);
  const r = await fetch(url, { method, headers: { ...AUTH, Origin: ORIGIN } });
  if (r.status !== okStatus) out.push(`HTTP ${r.status}, expected ${okStatus}`);
  if (!r.headers.get('access-control-allow-origin')) out.push('response has no Access-Control-Allow-Origin');
  if (okStatus === 200) { try { await r.json(); } catch { out.push('body is not JSON'); } }
  return out;
}

try {
  for (const s of services) await ensure(s);
  console.log(`Origin under test: ${ORIGIN}\n`);
  for (const [screen, calls] of Object.entries(SCREENS)) {
    console.log(screen);
    for (const [m, b, p, st] of calls) {
      const problems = await check(m, b, p, st);
      if (problems.length) failures++;
      console.log(`  ${problems.length ? 'FAIL' : 'ok  '} ${m} ${b}${p.length > 60 ? p.slice(0, 57) + '...' : p}${problems.length ? '\n       ' + problems.join('\n       ') : ''}`);
    }
  }
  console.log(failures ? `\n${failures} call(s) failed.` : '\nAll screen calls work from a browser origin.');
} catch (e) {
  console.error('connect-check failed:', e.message);
  failures = failures || 1;
}
started.forEach((c) => c.kill());
process.exit(failures ? 1 : 0);
