#!/usr/bin/env node
// Pre-demo checklist for the local demo. Prints no secrets (variable NAMES and OK/FAIL only).
//   node scripts/preflight.mjs                run all checks (starts the services briefly via connect-check)
//   node scripts/preflight.mjs --running      also require the services and web app to be up right now
//   node scripts/preflight.mjs --skip-connect skip the (slower) connect-check
// Exit code 1 if any check fails.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const args = process.argv.slice(2);
const py = process.platform === 'win32' ? 'python' : 'python3';
const FRESH_MIN = 5;
let failed = 0;
const line = (tag, msg) => console.log(`  ${tag.padEnd(4)} ${msg}`);
const ok = (m) => line('OK', m);
const warn = (m) => line('WARN', m);
const fail = (m) => { failed++; line('FAIL', m); };

// Parse .env keys and values in memory only; values are compared, never printed.
function parseEnv(text) {
  const out = {};
  for (const l of text.split(/\r?\n/)) {
    const m = l.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m && !l.trim().startsWith('#')) out[m[1]] = m[2].replace(/^(['"])(.*)\1$/, '$2');
  }
  return out;
}

function run(cmd, a, opts = {}) {
  return spawnSync(cmd, a, { encoding: 'utf8', cwd: root, shell: process.platform === 'win32' && /npm|npx/.test(cmd), ...opts });
}

console.log('Preflight');
// 1 tools
const major = Number(process.versions.node.split('.')[0]);
major >= 18 ? ok(`Node ${process.versions.node}`) : fail('Node 18 or newer is required');
const pv = run(py, ['--version']);
pv.status === 0 ? ok(pv.stdout.trim() || pv.stderr.trim()) : fail('Python not found on PATH');
const mods = run(py, ['-c', 'import fastapi, uvicorn, psycopg, dotenv, pydantic']);
mods.status === 0 ? ok('Python packages installed (fastapi, uvicorn, psycopg, dotenv, pydantic)') : fail('Python packages missing: pip install -e data-platform -e insights-sponsors, and game-engine/requirements.txt');
existsSync(path.join(root, 'web', 'node_modules')) ? ok('web dependencies installed') : fail('web/node_modules missing: cd web && npm install');

// 2 environment
const envFile = path.join(root, '.env');
const fileEnv = existsSync(envFile) ? parseEnv(readFileSync(envFile, 'utf8')) : null;
if (!fileEnv) fail('.env not found (copy .env.example to .env and fill in DATABASE_URL)');
else {
  for (const name of ['DATABASE_URL']) fileEnv[name] ? ok(`${name} is set in .env`) : fail(`${name} is missing in .env`);
  for (const name of ['MBTA_API_KEY']) fileEnv[name] ? ok(`${name} is set in .env`) : warn(`${name} is not set in .env (the collector may be rate limited)`);
}
if (process.env.DATABASE_URL) {
  if (!fileEnv?.DATABASE_URL) warn('DATABASE_URL is set in your shell but not in .env; remove it from the shell environment');
  else if (process.env.DATABASE_URL !== fileEnv.DATABASE_URL) fail('A stale DATABASE_URL in your shell differs from .env (PowerShell: Remove-Item Env:DATABASE_URL). Services started from this shell would use the wrong database.');
  else warn('DATABASE_URL is also set in your shell (same value as .env). Fine, but remove it to avoid surprises.');
} else ok('no DATABASE_URL in the shell environment (the repo loads .env)');
for (const name of ['APP_ENV', 'TOKEN_SECRET', 'CORS_ORIGINS']) if (process.env[name]) warn(`${name} is set in the shell; the local demo expects dev mode with it unset`);

// 3 database and collector (DATABASE_URL removed so .env is used)
const { DATABASE_URL, ...clean } = process.env;
const probe = `
import sys
sys.path.insert(0, "src")
from data_platform import db
try:
    with db.connect(connect_timeout=8) as c:
        r = c.execute("select extract(epoch from now() - max(time)) from vehicles where time > now() - interval '1 day'").fetchone()
    print("FRESH", "none" if r[0] is None else int(r[0]))
except Exception as e:
    print("ERR", type(e).__name__)
`;
const db = spawnSync(py, ['-c', probe], { cwd: path.join(root, 'data-platform'), env: { ...clean, PYTHONPATH: 'src' }, encoding: 'utf8' });
const out = (db.stdout || '').trim();
if (out.startsWith('FRESH')) {
  ok('database reachable');
  const v = out.split(' ')[1];
  if (v === 'none') fail('collector: no vehicle rows in the last day. Start it (see docs/DEMO.md).');
  else if (Number(v) > FRESH_MIN * 60) fail(`collector is stale: newest vehicle row is ${Math.round(Number(v) / 60)} min old (limit ${FRESH_MIN}). Check that the collector process is running.`);
  else ok(`collector is fresh: newest vehicle row is ${v}s old`);
} else fail(`database not reachable (${out.replace(/^ERR\s*/, '') || 'no answer'}). Check the network and DATABASE_URL in .env.`);

// 4 services and web
const probes = [['data-platform', 8001, '/health'], ['insights-sponsors', 8002, '/health'], ['game-engine', 8003, '/healthz'], ['demo client (maps)', 4321, '/'], ['web app', 5173, '/']];
for (const [name, port, p] of probes) {
  let up = false;
  try { up = (await fetch(`http://127.0.0.1:${port}${p}`, { signal: AbortSignal.timeout(2000) })).ok; } catch { /* down */ }
  if (up) ok(`${name} answers on ${port}`);
  else if (args.includes('--running')) fail(`${name} does not answer on ${port} (start: node scripts/demo-up.mjs)`);
  else line('INFO', `${name} is not running on ${port} (fine before: node scripts/demo-up.mjs)`);
}

// 5 connect-check
if (!args.includes('--skip-connect')) {
  const c = run('node', ['scripts/connect-check.mjs']);
  c.status === 0 ? ok('connect-check passed (every screen\'s endpoints, with CORS)') : fail('connect-check failed: run node scripts/connect-check.mjs to see which endpoint');
}

console.log(failed ? `\nPreflight FAILED (${failed} problem${failed > 1 ? 's' : ''}).` : '\nPreflight passed.');
process.exit(failed ? 1 : 0);
