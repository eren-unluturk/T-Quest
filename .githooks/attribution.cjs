// Shared banned-attribution patterns for commit-msg, pre-push, strip-msg. CommonJS.
const ROBOT = '\u{1F916}';
const rules = [
  (l) => /^\s*Co-Authored-By\s*:/i.test(l),
  (l) => /^\s*Claude-Session\s*:/i.test(l),
  (l) => /generated with/i.test(l),
  (l) => /noreply@anthropic\.com/i.test(l),
  (l) => l.includes(ROBOT) && /claude|generated/i.test(l),
];
const isBanned = (line) => rules.some((r) => r(line));

function stripBanned(text) {
  const lines = text.split(/\r?\n/).filter((l) => !isBanned(l));
  while (lines.length && lines[lines.length - 1].trim() === '') lines.pop();
  return lines.length ? lines.join('\n') + '\n' : '';
}

const hasBanned = (text) => text.split(/\r?\n/).some(isBanned);
module.exports = { isBanned, stripBanned, hasBanned };
