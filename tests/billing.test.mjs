// Billing safety tests. Run: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { processHits, persistentHits, scrubEnv, fixText, describe, checkBilling } from '../scripts/billing.mjs';

const repo = path.resolve(import.meta.dirname, '..');
const FAKE = 'sk-ant-FAKE-test-value-0123456789';

test('processHits finds only set, non-empty billing vars', () => {
  assert.deepEqual(processHits({ PATH: 'x' }), []);
  assert.deepEqual(processHits({ ANTHROPIC_API_KEY: '' }), []);
  assert.deepEqual(processHits({ ANTHROPIC_API_KEY: FAKE, ANTHROPIC_AUTH_TOKEN: 't' }), ['ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN']);
});

test('scrubEnv removes both vars, case-insensitively, keeps the rest', () => {
  const out = scrubEnv({ ANTHROPIC_API_KEY: FAKE, anthropic_auth_token: 't', PATH: 'p', HOME: 'h' });
  assert.deepEqual(out, { PATH: 'p', HOME: 'h' });
});

test('persistentHits checks Windows User and Machine scopes', () => {
  const isSet = (name, scope) => name === 'ANTHROPIC_API_KEY' && scope === 'Machine';
  assert.deepEqual(persistentHits({ platform: 'win32', isSet }), [{ name: 'ANTHROPIC_API_KEY', scope: 'Machine' }]);
  assert.deepEqual(persistentHits({ platform: 'win32', isSet: () => false }), []);
  assert.deepEqual(persistentHits({ platform: 'linux', isSet: () => true }), []);
});

test('checkBilling ok only when nothing is set anywhere', () => {
  assert.equal(checkBilling({ env: {}, platform: 'win32', isSet: () => false }).ok, true);
  assert.equal(checkBilling({ env: { ANTHROPIC_API_KEY: FAKE }, platform: 'win32', isSet: () => false }).ok, false);
  assert.equal(checkBilling({ env: {}, platform: 'win32', isSet: (n, s) => s === 'User' }).ok, false);
});

test('messages name the variables and exact fix but never a value', () => {
  const res = checkBilling({ env: { ANTHROPIC_API_KEY: FAKE }, platform: 'win32', isSet: (n, s) => n === 'ANTHROPIC_AUTH_TOKEN' && s === 'User' });
  const text = describe(res) + '\n' + fixText(res);
  assert.match(text, /ANTHROPIC_API_KEY/);
  assert.match(text, /SetEnvironmentVariable\('ANTHROPIC_AUTH_TOKEN', \$null, 'User'\)/);
  assert.doesNotMatch(text, /FAKE/);
});

test('doctor FAILS when a key is in the environment and never prints it', () => {
  const r = spawnSync(process.execPath, [path.join(repo, 'scripts', 'doctor.mjs')], {
    cwd: repo, encoding: 'utf8', env: { ...process.env, ANTHROPIC_API_KEY: FAKE },
  });
  const out = r.stdout + r.stderr;
  assert.match(out, /FAIL\s+billing safety/);
  assert.match(out, /Remove-Item Env:ANTHROPIC_API_KEY/);
  assert.doesNotMatch(out, /FAKE/);
  assert.notEqual(r.status, 0);
});

test('duo dry-run notes the removal and never prints the key', () => {
  const r = spawnSync(process.execPath, [path.join(repo, 'scripts', 'duo.mjs'), 'data-platform', 'planner', '--dry-run'], {
    cwd: repo, encoding: 'utf8', env: { ...process.env, ANTHROPIC_API_KEY: FAKE },
  });
  const out = r.stdout + r.stderr;
  assert.doesNotMatch(out, /FAKE/);
  if (r.status === 0) assert.match(out, /removed ANTHROPIC_API_KEY from the child environment/);
});

test('--allow-api-key is not used by any VS Code task or doc command', () => {
  for (const f of ['.vscode/tasks.json', 'tquest.code-workspace']) {
    assert.doesNotMatch(readFileSync(path.join(repo, f), 'utf8'), /allow-api-key/, f);
  }
});

test('.env.example has no Anthropic key variable assignment', () => {
  assert.doesNotMatch(readFileSync(path.join(repo, '.env.example'), 'utf8'), /^\s*ANTHROPIC_(API_KEY|AUTH_TOKEN)\s*=/m);
});
