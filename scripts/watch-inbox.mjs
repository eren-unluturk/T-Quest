#!/usr/bin/env node
// Poll every 45s; print only new or changed items.
import { resolveIdentity, listInbox, formatItem } from './lib.mjs';

const id = resolveIdentity();
const seen = new Map();
console.log(`Watching inbox for ${id.agents.join(', ')} every 45s. Ctrl+C to stop.`);

function tick() {
  try {
    for (const i of listInbox(id.agents)) {
      const sig = `${i.updatedAt}|${i.labels.join(',')}|${i.comments?.length ?? 0}`;
      const prev = seen.get(i.number);
      if (prev !== sig) {
        console.log(`${new Date().toLocaleTimeString()} ${prev ? 'CHANGED' : 'NEW    '} ${formatItem(i)}`);
        seen.set(i.number, sig);
      }
    }
  } catch (e) {
    console.log(`poll failed: ${e.message}`);
  }
}
tick();
setInterval(tick, 45000);
