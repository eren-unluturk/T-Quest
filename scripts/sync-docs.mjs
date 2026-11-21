#!/usr/bin/env node
// Regenerates ONLY the AUTO blocks in PLAN.md and PITCH.md. No LLM, no secrets, idempotent.
//   AUTO:status  per-agent roadmap checkbox counts + open issue counts by to: label (PLAN.md)
//   AUTO:issues  open blockers (PLAN.md)
//   AUTO:numbers headline sections of docs/TIGER_DATA_RESULTS.md, copied verbatim (PITCH.md)
// Exits non-zero if a marker pair is missing. gh parts are skipped gracefully when gh is unavailable.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

export function replaceBlock(text, name, body) {
  const start = `<!-- AUTO:${name}:start -->`;
  const end = `<!-- AUTO:${name}:end -->`;
  const i = text.indexOf(start);
  const j = text.indexOf(end);
  if (i === -1 || j === -1 || j < i) throw new Error(`missing marker pair AUTO:${name}`);
  return `${text.slice(0, i + start.length)}\n${body.trim()}\n${text.slice(j)}`;
}

export function countCheckboxes(md) {
  const done = (md.match(/^\s*- \[x\]/gim) || []).length;
  const open = (md.match(/^\s*- \[ \]/gm) || []).length;
  return { done, open, total: done + open };
}

export function extractNumbers(md) {
  const out = [];
  for (const name of ['synthetic', 'real']) {
    const m = md.match(new RegExp(`<!-- section:${name}:start -->([\\s\\S]*?)<!-- section:${name}:end -->`));
    if (!m) throw new Error(`missing section:${name} in TIGER_DATA_RESULTS.md`);
    let s = m[1];
    // drop the SQL listings, keep headline tables and the summary paragraph
    s = s.replace(/### Exact queries[\s\S]*?(?=### Summary|$)/, '');
    s = s.replace(/^Aggregate query:[\s\S]*?(?=\nThe dataset is)/m, '');
    s = s.replace(/^## /gm, '#### ').replace(/^### /gm, '##### ');
    out.push(s.trim());
  }
  return out.join('\n\n');
}

function gh(args) {
  const r = spawnSync('gh', args, { encoding: 'utf8' });
  return r.status === 0 ? r.stdout : null;
}

export function issueBlocks(issues) {
  if (!issues) return { status: '_Issue counts unavailable (gh not authenticated)._', blockers: '_Open blockers unavailable (gh not authenticated)._' };
  const byTo = {};
  for (const it of issues) {
    for (const l of it.labels.map((x) => x.name)) if (l.startsWith('to:')) byTo[l] = (byTo[l] || 0) + 1;
  }
  const rows = Object.keys(byTo).sort().map((k) => `| \`${k}\` | ${byTo[k]} |`);
  const blockers = issues.filter((it) => it.labels.some((l) => l.name === 'priority:blocker'));
  return {
    status: `| Open issues addressed to | Count |\n|---|---|\n${rows.join('\n') || '| (none) | 0 |'}\n\nTotal open issues: ${issues.length}.`,
    blockers: blockers.length
      ? blockers.map((b) => `- #${b.number} ${b.title}`).join('\n')
      : 'No open issues carry `priority:blocker`.',
  };
}

export function run(root) {
  const agents = ['data-platform', 'insights-sponsors', 'game-engine', 'client-bryan', 'client-isabella'];
  const rows = agents.map((a) => {
    const f = path.join(root, a, '.work', 'ROADMAP.md');
    if (!existsSync(f)) return `| ${a} | no roadmap | |`;
    const c = countCheckboxes(readFileSync(f, 'utf8'));
    return `| ${a} | ${c.done} of ${c.total} | ${c.open} |`;
  });
  const out = gh(['issue', 'list', '--state', 'open', '--limit', '200', '--json', 'number,title,labels']);
  let issues = null;
  try { issues = out ? JSON.parse(out) : null; } catch { issues = null; }
  const ib = issueBlocks(issues);

  const planPath = path.join(root, 'PLAN.md');
  let plan = readFileSync(planPath, 'utf8');
  plan = replaceBlock(plan, 'status',
    `Roadmap checkbox progress (counted from each agent's \`.work/ROADMAP.md\`; checkboxes can lag the real state, see the hand-written status below).\n\n| Agent | Items done | Items open |\n|---|---|---|\n${rows.join('\n')}\n\n${ib.status}`);
  plan = replaceBlock(plan, 'issues', ib.blockers);

  const pitchPath = path.join(root, 'PITCH.md');
  let pitch = readFileSync(pitchPath, 'utf8');
  pitch = replaceBlock(pitch, 'numbers', extractNumbers(readFileSync(path.join(root, 'docs', 'TIGER_DATA_RESULTS.md'), 'utf8')));

  writeFileSync(planPath, plan);
  writeFileSync(pitchPath, pitch);
}

if (import.meta.url === `file://${process.argv[1].replace(/\\/g, '/')}` || process.argv[1]?.endsWith('sync-docs.mjs')) {
  try {
    const root = path.resolve(import.meta.dirname, '..');
    run(root);
    console.log('sync-docs: PLAN.md and PITCH.md AUTO blocks updated.');
  } catch (e) {
    console.error(`sync-docs: ${e.message}`);
    process.exit(1);
  }
}
