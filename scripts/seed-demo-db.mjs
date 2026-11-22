#!/usr/bin/env node
// Seeds the SEPARATE demo database. Wrapper around `python -m data_platform.seed_demo`.
//   node scripts/seed-demo-db.mjs --dry-run     check and print the plan, write nothing
//   node scripts/seed-demo-db.mjs               do it (needs DEMO_DATABASE_URL; refuses if it equals DATABASE_URL)
// Never prints connection strings. Run only after creating the demo database (docs/DEPLOY.md).
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const r = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['-m', 'data_platform.seed_demo', ...process.argv.slice(2)], {
  cwd: path.join(root, 'data-platform'),
  env: { ...process.env, PYTHONPATH: 'src' },
  stdio: 'inherit',
});
process.exit(r.status ?? 1);
