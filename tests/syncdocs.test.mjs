// sync-docs tests. Run: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { replaceBlock, countCheckboxes, extractNumbers, issueBlocks } from '../scripts/sync-docs.mjs';

const repo = path.resolve(import.meta.dirname, '..');

test('replaceBlock replaces only the block and is idempotent', () => {
  const t = 'head\n<!-- AUTO:x:start -->\nold\n<!-- AUTO:x:end -->\ntail';
  const a = replaceBlock(t, 'x', 'new');
  assert.equal(a, 'head\n<!-- AUTO:x:start -->\nnew\n<!-- AUTO:x:end -->\ntail');
  assert.equal(replaceBlock(a, 'x', 'new'), a);
});

test('replaceBlock throws on missing marker', () => {
  assert.throws(() => replaceBlock('nothing', 'x', 'y'), /missing marker/);
});

test('countCheckboxes counts done and open', () => {
  assert.deepEqual(countCheckboxes('- [x] a\n- [ ] b\n  - [X] c\ntext'), { done: 2, open: 1, total: 3 });
});

test('extractNumbers copies tables and drops SQL', () => {
  const md = '<!-- section:synthetic:start -->\n## S\n### Data\n| a |\n### Exact queries\n```sql\nSELECT 1\n```\n### Summary for the pitch\nfoo\n<!-- section:synthetic:end -->\n<!-- section:real:start -->\n## R\n| b |\n<!-- section:real:end -->';
  const out = extractNumbers(md);
  assert.match(out, /\| a \|/);
  assert.match(out, /foo/);
  assert.doesNotMatch(out, /SELECT 1/);
});

test('issueBlocks degrades gracefully without gh', () => {
  assert.match(issueBlocks(null).status, /unavailable/);
  const r = issueBlocks([{ number: 3, title: 'X', labels: [{ name: 'to:eren' }, { name: 'priority:blocker' }] }]);
  assert.match(r.status, /to:eren/);
  assert.match(r.blockers, /#3 X/);
});

test('real repo: running sync-docs twice leaves files unchanged and exits 0', () => {
  const run = () => spawnSync(process.execPath, [path.join(repo, 'scripts', 'sync-docs.mjs')], { encoding: 'utf8' });
  assert.equal(run().status, 0);
  const snap = ['PLAN.md', 'PITCH.md'].map((f) => readFileSync(path.join(repo, f), 'utf8'));
  assert.equal(run().status, 0);
  assert.deepEqual(['PLAN.md', 'PITCH.md'].map((f) => readFileSync(path.join(repo, f), 'utf8')), snap);
});
