#!/usr/bin/env node
// node scripts/send.mjs --from <agent> --to <recipient> --type <type> --title "..." --body "..."
import { resolveIdentity, gh, parseArgs, TYPES, RECIPIENTS, SENDERS } from './lib.mjs';

const a = parseArgs(process.argv.slice(2));
const id = resolveIdentity();
const from = a.from || id.primary;
const { to, type, title, body } = a;
for (const [k, v] of Object.entries({ to, type, title, body })) {
  if (!v || v === true) {
    console.error(`Missing --${k}\nUsage: send.mjs --from <agent> --to <recipient> --type <type> --title "..." --body "..."`);
    process.exit(2);
  }
}
if (!SENDERS.includes(from)) { console.error(`Bad --from "${from}". One of: ${SENDERS.join(', ')}`); process.exit(2); }
if (!RECIPIENTS.includes(to)) { console.error(`Bad --to "${to}". One of: ${RECIPIENTS.join(', ')}`); process.exit(2); }
if (!TYPES.includes(type)) { console.error(`Bad --type "${type}". One of: ${TYPES.join(', ')}`); process.exit(2); }

const opt = (v) => (v && v !== true ? v : '_No response_');
const text = [
  '### From', '', from, '',
  '### To', '', to, '',
  '### Type', '', type, '',
  '### Summary', '', title, '',
  '### What I need', '', body, '',
  '### Contract/files involved', '', opt(a.files), '',
  '### Needed by', '', opt(a.by), '',
  `[${from}]`,
].join('\n');

const labels = [`to:${to}`, `from:${from}`, `type:${type}`];
if (type === 'blocker') labels.push('priority:blocker');
const args = ['issue', 'create', '--title', `[${from}] ${title}`, '--body', text];
for (const l of labels) args.push('--label', l);
console.log(gh(args).trim());
