#!/usr/bin/env node
// Print open issues addressed to my agent(s). Blockers first. Never fails a hook.
import { resolveIdentity, listInbox, formatItem } from './lib.mjs';

try {
  const id = resolveIdentity();
  const items = listInbox(id.agents);
  console.log(`INBOX for ${id.agents.join(', ')}${id.me ? ` (${id.me})` : ''}: ${items.length} open  (! blocker, A acked)`);
  for (const i of items) console.log(formatItem(i));
  if (!items.length) console.log('  (empty)');
  if (items.some((i) => i.blocker)) console.log('Handle blockers first. ACK with: node scripts/ack.mjs <n> --eta "..."');
} catch (e) {
  console.log(`INBOX unavailable: ${e.message}`);
}
process.exit(0);
