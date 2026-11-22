#!/usr/bin/env node
// One command for the local demo: data-platform (8001), insights-sponsors (8002), game-engine (8003, in-memory mode),
// the demo client with the Boston maps (4321, client-bryan/demo) and the React web app (5173), all in dev mode. Waits for health, prints the URLs, stops everything on Ctrl+C.
//   node scripts/demo-up.mjs
// Refuses to start if a port is taken (so you never talk to a stale process). Prints no secrets.
// DATABASE_URL is removed from the children's environment so each service loads the repo's .env itself.
import { spawn, spawnSync } from 'node:child_process';
import net from 'node:net';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { DATABASE_URL, APP_ENV, TOKEN_SECRET, CORS_ORIGINS, ...clean } = process.env;
const py = process.platform === 'win32' ? 'python' : 'python3';

const SERVICES = [
  { name: 'data-platform', port: 8001, url: '/health', cwd: 'data-platform', cmd: py, env: { PYTHONPATH: 'src' }, args: ['-m', 'uvicorn', 'data_platform.app:app', '--port', '8001'] },
  { name: 'insights-sponsors', port: 8002, url: '/health', cwd: 'insights-sponsors', cmd: py, env: { PYTHONPATH: 'src', DATA_BACKEND: 'postgres' }, args: ['-m', 'uvicorn', 'insights_sponsors.main:app', '--port', '8002'] },
  { name: 'game-engine', port: 8003, url: '/healthz', cwd: 'game-engine/src', cmd: py, env: {}, args: ['-m', 'uvicorn', 'game_engine.app:app', '--port', '8003'] },
  { name: 'demo client', port: 4321, url: '/', cwd: 'client-bryan/demo', cmd: 'node', env: {}, args: ['server.mjs'] },
  { name: 'web', port: 5173, url: '/', cwd: 'web', cmd: process.platform === 'win32' ? 'npm.cmd' : 'npm', env: {}, args: ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], shell: process.platform === 'win32' },
];

const portFree = (port) => new Promise((res) => {
  const s = net.createServer();
  s.once('error', () => res(false));
  s.once('listening', () => s.close(() => res(true)));
  s.listen(port, '127.0.0.1');
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const healthy = async (s) => { try { return (await fetch(`http://127.0.0.1:${s.port}${s.url}`, { signal: AbortSignal.timeout(2000) })).ok; } catch { return false; } };

const children = [];
function stopAll() {
  for (const c of children) {
    if (!c.pid || c.exitCode !== null) continue;
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(c.pid), '/T', '/F'], { stdio: 'ignore' });
    else c.kill('SIGTERM');
  }
}

async function main() {
  const taken = [];
  for (const s of SERVICES) if (!(await portFree(s.port))) taken.push(s);
  if (taken.length) {
    for (const s of taken) console.error(`Port ${s.port} (${s.name}) is already in use. Stop whatever holds it (PowerShell: Get-NetTCPConnection -LocalPort ${s.port} | Select OwningProcess) and run again.`);
    process.exit(1);
  }
  for (const s of SERVICES) {
    const opts = { cwd: path.join(root, s.cwd), env: { ...clean, ...s.env }, stdio: 'ignore' };
    const c = s.shell ? spawn([s.cmd, ...s.args].join(' '), { ...opts, shell: true }) : spawn(s.cmd, s.args, opts);
    c.on('error', (e) => console.error(`${s.name}: could not start (${e.code ?? 'error'})`));
    children.push(c);
  }
  for (const s of SERVICES) {
    let ok = false;
    for (let i = 0; i < 80 && !ok; i++) { await sleep(500); ok = await healthy(s); }
    if (!ok) { console.error(`${s.name} did not answer on port ${s.port}. Stopping.`); stopAll(); process.exit(1); }
    console.log(`  up: ${s.name} on ${s.port}`);
  }
  console.log('\nT-Quest demo is running (dev mode, live MBTA data from your Tiger Data database).');
  console.log('  Demo app (maps):    http://localhost:4321   <- the one to demo (needs internet for map tiles and the MBTA schedule)');
  console.log('  React web app:     http://127.0.0.1:5173');
  console.log('  data-platform:      http://127.0.0.1:8001/docs');
  console.log('  insights-sponsors:  http://127.0.0.1:8002/docs');
  console.log('  game-engine:        http://127.0.0.1:8003/docs   (in-memory mode: check-ins write nothing to the database)');
  console.log('Press Ctrl+C to stop everything.');
  const quit = () => { stopAll(); process.exit(0); };
  process.on('SIGINT', quit);
  process.on('SIGTERM', quit);
  setInterval(() => {}, 1 << 30);
}
main();
