#!/usr/bin/env node
// Removes the rows the demo wrote to the database: demo users ("demo_" prefix) with their check-ins, points, badges,
// friends and redemptions, plus faves flagged is_demo. Never touches MBTA tables or any unmarked row.
//   node scripts/reset-demo.mjs          DRY RUN: prints the counts, deletes nothing
//   node scripts/reset-demo.mjs --yes    prints the counts, then deletes them
// Prints no secrets. DATABASE_URL is removed from the child so the repo's .env is used.
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { DATABASE_URL, ...clean } = process.env;
const yes = process.argv.includes('--yes');
const r = spawnSync(process.platform === 'win32' ? 'python' : 'python3',
  ['-m', 'game_engine.demo_reset', ...(yes ? [] : ['--dry-run'])], {
    cwd: path.join(root, 'game-engine', 'src'),
    env: { ...clean, GE_ALLOW_DB_WRITES: yes ? '1' : '' },
    stdio: 'inherit',
  });
if (!yes && r.status === 0) console.log('\nDry run only. Run with --yes to delete these rows.');
process.exit(r.status ?? 1);
