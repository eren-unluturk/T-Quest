// Duo workflow tests. Run: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '..');
const node = process.execPath;
const duo = (...a) => spawnSync(node, [path.join(repo, 'scripts', 'duo.mjs'), ...a], { cwd: repo, encoding: 'utf8' });
const AGENTS = ['data-platform', 'insights-sponsors', 'game-engine', 'client-bryan', 'client-isabella'];

test('duo --dry-run planner uses opus, planner settings and the attribution rule', () => {
  const r = duo('data-platform', 'planner', '--dry-run');
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /cd data-platform/);
  assert.match(r.stdout, /--model opus/);
  assert.match(r.stdout, /--settings \.work\/planner-settings\.json/);
  assert.match(r.stdout, /\.work\/PLANNER\.md/);
  assert.match(r.stdout, /attribution/i);
  assert.match(r.stdout, /'start'/);
});

test('duo --dry-run builder uses sonnet, no planner settings', () => {
  const r = duo('insights-sponsors', 'builder', '--dry-run');
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /--model sonnet/);
  assert.doesNotMatch(r.stdout, /planner-settings/);
  assert.match(r.stdout, /\.work\/BUILDER\.md/);
  assert.match(r.stdout, /'go'/);
});

test('duo rejects invalid agent, invalid role, and missing args', () => {
  assert.equal(duo('nope', 'planner', '--dry-run').status, 2);
  assert.equal(duo('game-engine', 'boss', '--dry-run').status, 2);
  assert.equal(duo('game-engine').status, 2);
  assert.equal(duo().status, 2);
});

test('every agent has seeded .work files with the attribution rule on top', () => {
  for (const a of AGENTS) {
    for (const f of ['ROADMAP.md', 'PLANNER.md', 'BUILDER.md', 'planner-settings.json', 'queue/.gitkeep', 'reports/.gitkeep']) {
      assert.ok(existsSync(path.join(repo, a, '.work', f)), `${a}/.work/${f}`);
    }
    for (const f of ['PLANNER.md', 'BUILDER.md']) {
      assert.match(readFileSync(path.join(repo, a, '.work', f), 'utf8').split('\n')[0], /^## ABSOLUTE RULE: NO ATTRIBUTION/);
    }
  }
  for (const a of ['client-bryan', 'client-isabella']) {
    for (const f of ['PLANNER.md', 'BUILDER.md']) {
      assert.match(readFileSync(path.join(repo, a, '.work', f), 'utf8'), /CREATIVE CONSTRAINT/);
    }
  }
});

const guard = (file, cwd = 'C:/x/data-platform') => spawnSync(node, [path.join(repo, 'scripts', 'planner-guard.mjs')], {
  input: JSON.stringify({ tool_name: 'Write', tool_input: { file_path: file }, cwd }), encoding: 'utf8',
}).status;

test('planner-guard allows .work/ and blocks everything else', () => {
  assert.equal(guard('.work/queue/001-a.md'), 0);
  assert.equal(guard('C:/x/data-platform/.work/reports/001.md'), 0);
  assert.equal(guard('src/a.py'), 2);
  assert.equal(guard('../game-engine/.work/x.md'), 2);
  assert.equal(guard('.work/../src/a.py'), 2);
  assert.equal(guard('C:/x/data-platform/.workshop/a.md'), 2);
});

test('VS Code tasks exist for every agent/role and every person', () => {
  const t = JSON.parse(readFileSync(path.join(repo, '.vscode', 'tasks.json'), 'utf8')).tasks.map((x) => x.label);
  for (const a of AGENTS) for (const r of ['planner', 'builder']) assert.ok(t.includes(`Duo: ${a} ${r}`), `${a} ${r}`);
  for (const p of ['eren', 'tobi', 'bryan', 'isabella']) assert.ok(t.includes(`Duo up: ${p}`), p);
});
