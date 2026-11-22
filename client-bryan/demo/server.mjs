#!/usr/bin/env node
// Local demo server: serves public/ and proxies the three backends plus the public MBTA API.
// node server.mjs   ->   http://localhost:4321
import { createServer, request as httpRequest } from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = Number(process.env.DEMO_PORT || 4321);
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public');
const BACKENDS = { dp: 8001, is: 8002, ge: 8003 }; // data-platform, insights-sponsors, game-engine
const MBTA = 'https://api-v3.mbta.com';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' };

const cache = new Map(); // MBTA static data barely changes; cache it so we stay under the keyless rate limit

function proxyBackend(req, res, port, rest) {
  const up = httpRequest({ host: '127.0.0.1', port, path: rest, method: req.method, headers: { ...req.headers, host: `127.0.0.1:${port}` } }, (r) => {
    res.writeHead(r.statusCode, r.headers);
    r.pipe(res);
  });
  up.on('error', () => send(res, 502, { error: `backend on :${port} is not running` }));
  req.pipe(up);
}

async function proxyMbta(res, rest) {
  const hit = cache.get(rest);
  if (hit && Date.now() - hit.at < 3600_000) return send(res, 200, hit.body);
  const headers = { accept: 'application/vnd.api+json' };
  if (process.env.MBTA_API_KEY) headers['x-api-key'] = process.env.MBTA_API_KEY;
  try {
    const r = await fetch(MBTA + rest, { headers });
    const body = await r.json();
    if (r.ok) cache.set(rest, { at: Date.now(), body });
    send(res, r.status, body);
  } catch (e) {
    send(res, 502, { error: 'MBTA API unreachable' });
  }
}

function send(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(body));
}

createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const m = url.pathname.match(/^\/api\/(dp|is|ge)(\/.*)$/);
  if (m) return proxyBackend(req, res, BACKENDS[m[1]], m[2] + url.search);
  if (url.pathname.startsWith('/mbta/')) return proxyMbta(res, url.pathname.slice(5) + url.search);

  const file = path.join(ROOT, url.pathname === '/' ? 'index.html' : path.normalize(url.pathname));
  if (!file.startsWith(ROOT)) return send(res, 403, { error: 'forbidden' });
  try {
    const data = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  } catch {
    send(res, 404, { error: 'not found' });
  }
}).listen(PORT, () => console.log(`T-Quest demo on http://localhost:${PORT}`));
