#!/usr/bin/env node
// Audit for AI/tool attribution lines: full git history, tracked files, and (if gh works) issues and PRs.
// node scripts/check-attribution.mjs [--root <dir>] [--no-gh]     Exit 1 on any hit.
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { parseArgs } from './lib.mjs';

const require = createRequire(import.meta.url);
const { isBanned } = require('../.githooks/attribution.cjs');

const a = parseArgs(process.argv.slice(2));
const git = (args, cwd) => spawnSync('git', args, { cwd, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const cwd = a.root && a.root !== true ? path.resolve(a.root) : process.cwd();
const root = git(['rev-parse', '--show-toplevel'], cwd).stdout.trim();

// Files that state the rule itself are not scanned (history is always scanned in full).
const EXCLUDED = [
  /^AGENTS\.md$/, /(^|\/)CLAUDE\.md$/, /(^|\/)AGENT\.md$/, /^\.work\/(PLANNER|BUILDER)\.md$/, /\/\.work\/(PLANNER|BUILDER)\.md$/,
  /^docs\/(ONBOARDING|DUO)\.md$/, /^\.githooks\//, /^\.claude-template\//, /(^|\/)\.claude\//,
  /^tests\//, /^scripts\/(check-attribution|seed-work)\.mjs$/,
];
// In files, only unambiguous attribution forms count (prose may legitimately say "generated with").
const fileHit = (l) => /^\s*[-*>]*\s*Co-Authored-By\s*:/i.test(l) || /^\s*Claude-Session\s*:/i.test(l)
  || /noreply@anthropic\.com/i.test(l) || /generated with \[?claude/i.test(l) || (l.includes('\u{1F916}') && /claude|generated/i.test(l));

const results = [];
const hit = (area, where, line) => results.push({ area, where, line: line.trim().slice(0, 100) });
const ran = [];

// 1. history
const log = git(['log', '--all', '--format=%H%x1f%B%x1e'], root);
ran.push('git history');
for (const rec of log.stdout.split('\x1e').map((s) => s.trim()).filter(Boolean)) {
  const [h, body = ''] = rec.split('\x1f');
  for (const l of body.split(/\r?\n/)) if (isBanned(l)) hit('history', h.slice(0, 10), l);
}

// 2. tracked files
ran.push('tracked files');
for (const f of git(['ls-files'], root).stdout.split('\n').map((s) => s.trim()).filter(Boolean)) {
  if (EXCLUDED.some((re) => re.test(f))) continue;
  let text;
  try { text = readFileSync(path.join(root, f), 'utf8'); } catch { continue; }
  if (text.includes('\0')) continue;
  text.split(/\r?\n/).forEach((l, i) => { if (fileHit(l)) hit('file', `${f}:${i + 1}`, l); });
}

// 3. issues and PRs (best effort)
if (!a['no-gh']) {
  const auth = spawnSync('gh', ['auth', 'status'], { cwd: root, encoding: 'utf8' });
  if (auth.status === 0) {
    for (const kind of ['issue', 'pr']) {
      const r = spawnSync('gh', [kind, 'list', '--state', 'all', '--limit', '300', '--json', 'number,title,body,comments'], { cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
      if (r.status !== 0) { console.log(`SKIP  gh ${kind} list failed`); continue; }
      ran.push(`${kind}s`);
      for (const it of JSON.parse(r.stdout)) {
        const texts = [it.title, it.body, ...(it.comments || []).map((c) => c.body)];
        for (const t of texts) for (const l of String(t || '').split(/\r?\n/)) if (isBanned(l)) hit(kind, `#${it.number}`, l);
      }
    }
  } else console.log('SKIP  gh not authenticated: issues/PRs not checked');
}

for (const area of ran) {
  const hits = results.filter((r) => r.area === area || r.area + 's' === area || (area === 'git history' && r.area === 'history') || (area === 'tracked files' && r.area === 'file'));
  console.log(`${hits.length ? 'FAIL' : 'PASS'}  ${area}`);
  for (const h of hits) console.log(`      ${h.where}: ${h.line}`);
}
if (results.some((r) => r.area === 'history')) {
  console.log('\nHistory has banned lines. Safe cleanup (rewrites history: coordinate with the team, then force-push yourself):');
  console.log(`  git filter-branch -f --msg-filter "node ${path.join(root, '.githooks', 'strip-msg.cjs').split(path.sep).join('/')}" -- --all`);
}
process.exit(results.length ? 1 : 0);
