// Attribution enforcement tests. Run: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '..');
const node = process.execPath;
const hook = (n) => path.join(repo, '.githooks', n);
const sh = (cwd, ...a) => spawnSync('git', a, { cwd, encoding: 'utf8' });
const ROBOT = '\u{1F916}';

function strip(text) {
  const f = path.join(mkdtempSync(path.join(tmpdir(), 'cm-')), 'MSG');
  writeFileSync(f, text);
  const r = spawnSync(node, [hook('commit-msg'), f], { encoding: 'utf8' });
  return { status: r.status, out: readFileSync(f, 'utf8'), err: r.stderr };
}

const BANNED = [
  'Co-Authored-By: Someone <a@b.c>',
  'co-authored-by: lower <x@y.z>',
  'CO-AUTHORED-BY: UPPER <x@y.z>',
  'Co-authored-by: Some Model <noreply@anthropic.com>',
  '  Co-Authored-By : spaced <a@b.c>',
  'Claude-Session: abc123',
  'claude-session: x',
  `${ROBOT} Generated with [Claude Code](https://claude.com/claude-code)`,
  'Generated with some tool',
  'generated WITH x',
  'sent via noreply@anthropic.com',
  `${ROBOT} made by Claude`,
];

for (const line of BANNED) {
  test(`commit-msg strips: ${line.slice(0, 40)}`, () => {
    const r = strip(`Subject\n\nBody.\n\n${line}\n`);
    assert.equal(r.status, 0, r.err);
    assert.equal(r.out, 'Subject\n\nBody.\n');
  });
}

test('commit-msg strips multiple trailers and one in the middle of the body', () => {
  const r = strip('Subject\n\nFirst para.\nCo-Authored-By: A <a@a.a>\nSecond para.\n\nCo-Authored-By: B <b@b.b>\nClaude-Session: 1\n\n');
  assert.equal(r.out, 'Subject\n\nFirst para.\nSecond para.\n');
});

test('commit-msg leaves clean messages alone', () => {
  assert.equal(strip('Plain message\n\nDetails here.\n').out, 'Plain message\n\nDetails here.\n');
});

test('commit-msg aborts when empty after stripping', () => {
  const r = strip('Co-Authored-By: A <a@a.a>\nClaude-Session: 1\n');
  assert.equal(r.status, 1);
  assert.match(r.err, /empty/);
});

function makeRepo() {
  const dir = mkdtempSync(path.join(tmpdir(), 'attr-'));
  sh(dir, 'init', '-q', '-b', 'main');
  sh(dir, 'config', 'user.email', 't@t.t');
  sh(dir, 'config', 'user.name', 't');
  sh(dir, 'config', 'commit.gpgsign', 'false');
  return dir;
}
function commit(dir, msg, file = 'f.txt', content = String(Math.random())) {
  writeFileSync(path.join(dir, file), content);
  sh(dir, 'add', '-A');
  const mf = path.join(dir, '.git', 'MSGFILE');
  writeFileSync(mf, msg);
  const r = sh(dir, 'commit', '--no-verify', '-q', '-F', mf);
  assert.equal(r.status, 0, r.stderr);
  return sh(dir, 'rev-parse', 'HEAD').stdout.trim();
}
const prePush = (dir, stdin) => spawnSync(node, [hook('pre-push'), 'origin', 'x'], { cwd: dir, input: stdin, encoding: 'utf8' });
const ZERO = '0'.repeat(40);

test('pre-push rejects a range containing a trailer, with the rewrite command', () => {
  const dir = makeRepo();
  const base = commit(dir, 'base\n');
  const bad = commit(dir, 'work\n\nCo-Authored-By: X <x@x.x>\n');
  const r = prePush(dir, `refs/heads/main ${bad} refs/heads/main ${base}\n`);
  assert.equal(r.status, 1);
  assert.match(r.stderr, new RegExp(bad.slice(0, 10)));
  assert.match(r.stderr, /filter-branch/);
});

test('pre-push allows a clean range', () => {
  const dir = makeRepo();
  const base = commit(dir, 'base\n');
  const good = commit(dir, 'clean work\n');
  assert.equal(prePush(dir, `refs/heads/main ${good} refs/heads/main ${base}\n`).status, 0);
});

test('pre-push scans commits not on any remote when the remote ref is new', () => {
  const dir = makeRepo();
  const bare = mkdtempSync(path.join(tmpdir(), 'bare-'));
  sh(bare, 'init', '-q', '--bare');
  const first = commit(dir, 'base\n');
  sh(dir, 'remote', 'add', 'origin', bare);
  sh(dir, 'push', '-q', '--no-verify', 'origin', 'main');
  const bad = commit(dir, 'new work\n\nGenerated with a tool\n');
  const r = prePush(dir, `refs/heads/feat ${bad} refs/heads/feat ${ZERO}\n`);
  assert.equal(r.status, 1);
  assert.match(r.stderr, new RegExp(bad.slice(0, 10)));
  assert.doesNotMatch(r.stderr, new RegExp(first.slice(0, 10)));
});

test('pre-push ignores ref deletions', () => {
  const dir = makeRepo();
  commit(dir, 'base\n');
  assert.equal(prePush(dir, `(delete) ${ZERO} refs/heads/x abc\n`).status, 0);
});

const check = (dir) => spawnSync(node, [path.join(repo, 'scripts', 'check-attribution.mjs'), '--root', dir, '--no-gh'], { encoding: 'utf8' });

test('check-attribution passes on a clean sample repo', () => {
  const dir = makeRepo();
  commit(dir, 'one\n', 'README.md', '# hi\n');
  commit(dir, 'two\n\nplain body\n');
  const r = check(dir);
  assert.equal(r.status, 0, r.stdout);
});

test('check-attribution fails on dirty history and on a dirty tracked file', () => {
  const dir = makeRepo();
  commit(dir, 'one\n\nCo-Authored-By: Y <y@y.y>\n', 'README.md', '# hi\n');
  const h = check(dir);
  assert.equal(h.status, 1);
  assert.match(h.stdout, /FAIL {2}git history/);
  assert.match(h.stdout, /filter-branch/);

  const dir2 = makeRepo();
  commit(dir2, 'clean\n', 'docs.md', 'ok\nCo-Authored-By: Z <z@z.z>\n');
  const f = check(dir2);
  assert.equal(f.status, 1);
  assert.match(f.stdout, /FAIL {2}tracked files/);
  assert.match(f.stdout, /docs\.md:2/);
});

test('check-attribution excludes rule-carrying files from the file scan only', () => {
  const dir = makeRepo();
  commit(dir, 'clean\n', 'AGENTS.md', 'Co-Authored-By: rule text\n');
  const r = check(dir);
  assert.equal(r.status, 0, r.stdout);
});

test('check-attribution ignores an allowlisted commit but still fails on others', () => {
  const dir = makeRepo();
  const h = commit(dir, 'one\n\nCo-authored-by: Human <h@h.h>\n', 'README.md', '# hi\n');
  assert.equal(check(dir).status, 1);
  writeFileSync(path.join(dir, '.attribution-allow'), `# note\n${h.slice(0, 10)}  # human teammate\n`);
  sh(dir, 'add', '-A');
  assert.equal(sh(dir, 'commit', '--no-verify', '-q', '-m', 'allow').status, 0);
  assert.equal(check(dir).status, 0, check(dir).stdout);
  commit(dir, 'two\n\nCo-Authored-By: Bot <b@b.b>\n');
  const r = check(dir);
  assert.equal(r.status, 1);
  assert.match(r.stdout, /Bot/);
});
