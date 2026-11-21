#!/usr/bin/env node
// node scripts/done.mjs <n> --note "files/endpoints delivered"
import { resolveIdentity, gh, parseArgs } from './lib.mjs';

const a = parseArgs(process.argv.slice(2));
const n = a._[0];
if (!n || !a.note || a.note === true) {
  console.error('Usage: done.mjs <issue#> --note "what was delivered, with paths/endpoints"');
  process.exit(2);
}
const me = a.as && a.as !== true ? a.as : resolveIdentity().primary;
gh(['issue', 'comment', n, '--body', `[${me}] DONE. ${a.note}`]);
gh(['issue', 'edit', n, '--add-label', 'type:done']);
gh(['issue', 'close', n]);
console.log(`Closed #${n} as ${me}`);
