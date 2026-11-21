#!/usr/bin/env node
// Create/update all message-board labels (idempotent).
import { gh, RECIPIENTS, SENDERS, TYPES } from './lib.mjs';

const labels = [
  ...RECIPIENTS.map((r) => [`to:${r}`, '1f6feb', `Message addressed to ${r}`]),
  ...SENDERS.map((r) => [`from:${r}`, '8250df', `Message sent by ${r}`]),
  ...TYPES.map((t) => [`type:${t}`, 'fbca04', `Message type: ${t}`]),
  ['priority:blocker', 'd73a4a', 'Blocks someone; handle first'],
  ['status:acked', '0e8a16', 'Recipient acknowledged'],
];
for (const [name, color, description] of labels) {
  gh(['label', 'create', name, '--color', color, '--description', description, '--force']);
  console.log(`label ${name}`);
}
