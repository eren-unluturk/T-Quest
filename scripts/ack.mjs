#!/usr/bin/env node
// node scripts/ack.mjs <n> [--eta "text"]
import { resolveIdentity, gh, parseArgs } from './lib.mjs';

const a = parseArgs(process.argv.slice(2));
const n = a._[0];
if (!n) { console.error('Usage: ack.mjs <issue#> [--eta "..."]'); process.exit(2); }
const me = a.as && a.as !== true ? a.as : resolveIdentity().primary;
gh(['issue', 'comment', n, '--body', `[${me}] ACK. ETA: ${a.eta && a.eta !== true ? a.eta : 'TBD'}`]);
gh(['issue', 'edit', n, '--add-label', 'status:acked']);
console.log(`ACKed #${n} as ${me}`);
