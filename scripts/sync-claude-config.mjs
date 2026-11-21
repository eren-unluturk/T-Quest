#!/usr/bin/env node
// Single source of truth: copies .claude-template/ into root .claude/ and every agent folder's .claude/.
// Placeholder {{SCRIPTS}} -> "scripts" (root) or "../scripts" (agent folder).
import { mkdirSync, readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { repoRoot, readTeam, allAgents } from './lib.mjs';

const root = repoRoot();
const tpl = path.join(root, '.claude-template');
const targets = [
  { dir: root, scripts: 'scripts' },
  ...allAgents(readTeam(root)).map((a) => ({ dir: path.join(root, a), scripts: '../scripts' })),
];

function walk(d, base = d) {
  return readdirSync(d).flatMap((n) => {
    const p = path.join(d, n);
    return statSync(p).isDirectory() ? walk(p, base) : [path.relative(base, p)];
  });
}

let count = 0;
for (const t of targets) {
  mkdirSync(t.dir, { recursive: true });
  for (const rel of walk(tpl)) {
    const out = path.join(t.dir, '.claude', rel);
    mkdirSync(path.dirname(out), { recursive: true });
    writeFileSync(out, readFileSync(path.join(tpl, rel), 'utf8').replaceAll('{{SCRIPTS}}', t.scripts));
    count++;
  }
}
console.log(`Synced ${count} files into ${targets.length} .claude/ directories.`);
