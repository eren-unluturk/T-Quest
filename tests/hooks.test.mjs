// Run: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, mkdirSync, cpSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '..');
const node = process.execPath;

test('commit-msg strips attribution lines', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'msg-'));
  const f = path.join(dir, 'MSG');
  writeFileSync(f, [
    'Add schema', '', 'Body line.', '',
    'Co-Authored-By: Someone <a@b.c>',
    'co-authored-by: lower <a@b.c>',
    'Claude-Session: abc',
    '🤖 Generated with [Claude Code](https://claude.com/claude-code)', '',
  ].join('\n'));
  const r = spawnSync(node, [path.join(repo, '.githooks', 'commit-msg'), f], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  assert.equal(readFileSync(f, 'utf8'), 'Add schema\n\nBody line.\n');
});

test('commit-msg leaves clean messages alone', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'msg-'));
  const f = path.join(dir, 'MSG');
  writeFileSync(f, 'Plain message\n');
  spawnSync(node, [path.join(repo, '.githooks', 'commit-msg'), f]);
  assert.equal(readFileSync(f, 'utf8'), 'Plain message\n');
});

function tempRepo(me) {
  const dir = mkdtempSync(path.join(tmpdir(), 'guard-'));
  const sh = (...a) => spawnSync('git', a, { cwd: dir, encoding: 'utf8' });
  sh('init', '-q');
  cpSync(path.join(repo, 'team.json'), path.join(dir, 'team.json'));
  if (me) { mkdirSync(path.join(dir, '.team')); writeFileSync(path.join(dir, '.team', 'me'), me); }
  return { dir, sh };
}
function runGuard(dir, env = {}) {
  return spawnSync(node, [path.join(repo, '.githooks', 'pre-commit')], { cwd: dir, encoding: 'utf8', env: { ...process.env, ALLOW_SHARED: '', ...env } });
}
function stage(dir, sh, files) {
  for (const f of files) {
    mkdirSync(path.dirname(path.join(dir, f)), { recursive: true });
    writeFileSync(path.join(dir, f), 'x');
  }
  sh('add', '--', ...files);
}

test('guard allows own folder, docs/, DECISIONS.md', () => {
  const { dir, sh } = tempRepo('tobi');
  stage(dir, sh, ['game-engine/src/a.py', 'docs/x.md', 'DECISIONS.md']);
  assert.equal(runGuard(dir).status, 0);
});

test('guard refuses another agent folder', () => {
  const { dir, sh } = tempRepo('tobi');
  stage(dir, sh, ['game-engine/a.py', 'data-platform/b.sql']);
  const r = runGuard(dir);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /data-platform\/b\.sql/);
});

test('guard allows shared design/ for bryan but not isabella folder', () => {
  const { dir, sh } = tempRepo('bryan');
  stage(dir, sh, ['design/INTAKE.md', 'client-bryan/a.md']);
  assert.equal(runGuard(dir).status, 0);
  stage(dir, sh, ['client-isabella/a.md']);
  assert.equal(runGuard(dir).status, 1);
});

test('guard override with ALLOW_SHARED=1', () => {
  const { dir, sh } = tempRepo('tobi');
  stage(dir, sh, ['contracts/api/x.yaml']);
  assert.equal(runGuard(dir).status, 1);
  assert.equal(runGuard(dir, { ALLOW_SHARED: '1' }).status, 0);
});

test('guard refuses when identity missing', () => {
  const { dir, sh } = tempRepo(null);
  stage(dir, sh, ['docs/x.md']);
  assert.equal(runGuard(dir).status, 1);
});
