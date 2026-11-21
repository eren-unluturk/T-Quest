// Per-path ownership tests (team.json "paths"). Run: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync, cpSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '..');

function guard(me, files, env = {}) {
  const dir = mkdtempSync(path.join(tmpdir(), 'paths-'));
  const sh = (...a) => spawnSync('git', a, { cwd: dir, encoding: 'utf8' });
  sh('init', '-q');
  cpSync(path.join(repo, 'team.json'), path.join(dir, 'team.json'));
  mkdirSync(path.join(dir, '.team'));
  writeFileSync(path.join(dir, '.team', 'me'), me);
  for (const f of files) {
    mkdirSync(path.dirname(path.join(dir, f)), { recursive: true });
    if (!existsSync(path.join(dir, f))) writeFileSync(path.join(dir, f), 'x');
  }
  sh('add', '--', ...files);
  return spawnSync(process.execPath, [path.join(repo, '.githooks', 'pre-commit')], {
    cwd: dir, encoding: 'utf8', env: { ...process.env, ALLOW_SHARED: '', ...env },
  }).status;
}

test('tobi: only his own api spec under contracts/', () => {
  assert.equal(guard('tobi', ['contracts/api/game-engine.yaml']), 0);
  assert.equal(guard('tobi', ['contracts/api/data-platform.yaml']), 1);
  assert.equal(guard('tobi', ['contracts/db/v0.sql']), 1);
});

test('eren: contracts/db, own api specs, scripts, .github, root files', () => {
  assert.equal(guard('eren', [
    'contracts/db/v0.sql', 'contracts/api/data-platform.yaml', 'contracts/api/insights-sponsors.yaml',
    'scripts/x.mjs', '.github/CODEOWNERS', 'team.json', 'TEAM.md', 'AGENTS.md', '.env.example',
  ]), 0);
});

test('eren: not game-engine spec, events, or other contracts paths without override', () => {
  assert.equal(guard('eren', ['contracts/api/game-engine.yaml']), 1);
  assert.equal(guard('eren', ['contracts/events/checkin.json']), 1);
  assert.equal(guard('eren', ['contracts/README.md']), 1);
  assert.equal(guard('eren', ['contracts/events/checkin.json'], { ALLOW_SHARED: '1' }), 0);
});

test('bryan/isabella: no scripts or root files, design/ ok', () => {
  assert.equal(guard('bryan', ['scripts/x.mjs']), 1);
  assert.equal(guard('isabella', ['AGENTS.md']), 1);
  assert.equal(guard('isabella', ['design/INTAKE.md', 'client-isabella/a.md']), 0);
});

test('eren: infrastructure dirs; others are refused', () => {
  assert.equal(guard('eren', ['.githooks/x.cjs', '.claude-template/a.md', '.vscode/tasks.json', 'tests/a.mjs']), 0);
  for (const who of ['tobi', 'bryan', 'isabella']) {
    assert.equal(guard(who, ['.githooks/pre-push']), 1);
    assert.equal(guard(who, ['.vscode/tasks.json']), 1);
  }
});

test('agent .work/ files are allowed for the owner only', () => {
  assert.equal(guard('eren', ['data-platform/.work/ROADMAP.md', 'insights-sponsors/.work/queue/001-a.md', 'data-platform/.work/reports/001.md']), 0);
  assert.equal(guard('tobi', ['game-engine/.work/queue/001-a.md']), 0);
  assert.equal(guard('bryan', ['client-bryan/.work/PLANNER.md']), 0);
  assert.equal(guard('isabella', ['client-isabella/.work/BUILDER.md']), 0);
  assert.equal(guard('tobi', ['data-platform/.work/ROADMAP.md']), 1);
  assert.equal(guard('bryan', ['client-isabella/.work/ROADMAP.md']), 1);
});
