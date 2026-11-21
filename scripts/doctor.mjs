#!/usr/bin/env node
// Setup checklist: node scripts/doctor.mjs
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { repoRoot, readTeam, readMe, agentFromCwd } from './lib.mjs';
import { checkBilling, describe, fixText } from './billing.mjs';

const root = repoRoot();
const checks = [];
const add = (name, ok, fix, required = true) => checks.push({ name, ok, fix, required });
const run = (cmd, args) => spawnSync(cmd, args, { cwd: root, encoding: 'utf8' });

const hp = run('git', ['config', 'core.hooksPath']).stdout.trim();
add(`git core.hooksPath = ".githooks" (got "${hp}")`, hp === '.githooks', 'node scripts/setup-me.mjs <person>');
const me = readMe(root);
const team = readTeam(root);
add(`.team/me exists and is in team.json (${me ?? 'missing'})`, !!me && !!team[me], 'node scripts/setup-me.mjs <eren|tobi|bryan|isabella>');
const HOOKS = ['commit-msg', 'pre-commit', 'pre-push'];
add('hooks present (commit-msg, pre-commit, pre-push)', HOOKS.every((h) => existsSync(path.join(root, '.githooks', h))), 'git pull');
// Executable = mode 100755 in the git index (the portable truth on Windows).
const notExec = HOOKS.filter((h) => !run('git', ['ls-files', '-s', `.githooks/${h}`]).stdout.startsWith('100755'));
add(`hooks executable in git index${notExec.length ? ` (not: ${notExec.join(', ')})` : ''}`, notExec.length === 0, 'git update-index --chmod=+x .githooks/<hook>');
add('origin remote present', run('git', ['remote', 'get-url', 'origin']).status === 0, 'git remote add origin <url>');
const here = agentFromCwd(process.cwd(), root, team);
const mine = me && team[me] ? team[me].agents : [];
add(`current folder resolves to one of my agents (${here ?? 'repo root / not an agent folder'})`, !!here && mine.includes(here), 'cd into your agent folder, e.g. cd ' + (mine[0] ?? '<agent>'), false);
const attr = run(process.execPath, [path.join(root, 'scripts', 'check-attribution.mjs')]);
add('attribution check (history, files, issues/PRs)', attr.status === 0, 'node scripts/check-attribution.mjs  (prints hits and the cleanup command)');
const bill = checkBilling();
add(`billing safety: no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN (${bill.ok ? 'none set' : describe(bill)})`, bill.ok, '\n' + fixText(bill).split('\n').map((l) => '        ' + l).join('\n'));
add('gh authenticated', run('gh', ['auth', 'status']).status === 0, 'gh auth login');
const major = Number(process.versions.node.split('.')[0]);
add(`node >= 20 (got ${process.versions.node})`, major >= 20, 'install Node LTS');
add('.env exists (optional)', existsSync(path.join(root, '.env')), 'copy .env.example to .env', false);

for (const c of checks) console.log(`${c.ok ? 'PASS' : c.required ? 'FAIL' : 'WARN'}  ${c.name}${c.ok ? '' : `\n      fix: ${c.fix}`}`);
process.exit(checks.every((c) => c.ok || !c.required) ? 0 : 1);
