#!/usr/bin/env node
// Setup checklist: node scripts/doctor.mjs
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { repoRoot, readTeam, readMe } from './lib.mjs';

const root = repoRoot();
const checks = [];
const add = (name, ok, fix, required = true) => checks.push({ name, ok, fix, required });
const run = (cmd, args) => spawnSync(cmd, args, { cwd: root, encoding: 'utf8' });

const hp = run('git', ['config', 'core.hooksPath']).stdout.trim();
add(`git core.hooksPath = ".githooks" (got "${hp}")`, hp === '.githooks', 'node scripts/setup-me.mjs <person>');
const me = readMe(root);
const team = readTeam(root);
add(`.team/me exists and is in team.json (${me ?? 'missing'})`, !!me && !!team[me], 'node scripts/setup-me.mjs <eren|tobi|bryan|isabella>');
add('hooks present (.githooks/commit-msg, pre-commit)', ['commit-msg', 'pre-commit'].every((h) => existsSync(path.join(root, '.githooks', h))), 'git pull');
add('gh authenticated', run('gh', ['auth', 'status']).status === 0, 'gh auth login');
const major = Number(process.versions.node.split('.')[0]);
add(`node >= 20 (got ${process.versions.node})`, major >= 20, 'install Node LTS');
add('.env exists (optional)', existsSync(path.join(root, '.env')), 'copy .env.example to .env', false);

for (const c of checks) console.log(`${c.ok ? 'PASS' : c.required ? 'FAIL' : 'WARN'}  ${c.name}${c.ok ? '' : `\n      fix: ${c.fix}`}`);
process.exit(checks.every((c) => c.ok || !c.required) ? 0 : 1);
