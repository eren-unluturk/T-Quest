// stdin -> stdout filter for: git filter-branch --msg-filter "node .githooks/strip-msg.cjs"
const { stripBanned } = require('./attribution.cjs');
let d = '';
process.stdin.on('data', (c) => (d += c));
process.stdin.on('end', () => process.stdout.write(stripBanned(d)));
