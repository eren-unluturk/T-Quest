#!/usr/bin/env node
// node scripts/setup-me.mjs <person>
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { repoRoot, readTeam } from './lib.mjs';

const root = repoRoot();
const team = readTeam(root);
const who = (process.argv[2] || '').toLowerCase();
if (!team[who]) {
  console.error(`Usage: setup-me.mjs <${Object.keys(team).join('|')}>`);
  process.exit(2);
}
mkdirSync(path.join(root, '.team'), { recursive: true });
writeFileSync(path.join(root, '.team', 'me'), who + '\n');
const set = spawnSync('git', ['config', 'core.hooksPath', '.githooks'], { cwd: root, encoding: 'utf8' });
const got = spawnSync('git', ['config', 'core.hooksPath'], { cwd: root, encoding: 'utf8' }).stdout.trim();
if (set.status !== 0 || got !== '.githooks') {
  console.error('FAILED to set git core.hooksPath to .githooks. Run: git config core.hooksPath .githooks');
  process.exit(1);
}
console.log('Hooks verified: core.hooksPath = .githooks');
const p = team[who];
console.log(`Identity set: ${who}`);
console.log(`Agents:  ${p.agents.join(', ')}`);
console.log(`Folders: ${p.folders.join(', ')}  (commits allowed only here, plus docs/ and DECISIONS.md)`);
console.log('\nStart here:');
for (const a of p.agents) console.log(`  - Open a terminal in ${a}/ and run: claude   (or Claude Code extension with ${a}/ as working folder)`);
console.log('  - Read AGENTS.md, docs/PROJECT_BRIEF.md, then <agent>/AGENT.md');
console.log('  - Run /inbox (or node ../scripts/inbox.mjs) before and after every task');
console.log('  - Check your setup any time: node scripts/doctor.mjs');
console.log('  - Second terminal: VS Code task "Watch inbox"');
