#!/usr/bin/env node
// node scripts/duo.mjs <agent> <planner|builder> [--dry-run]
// Starts a Claude Code session in the agent folder with the planner (Opus) or builder (Sonnet) role.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { repoRoot, readTeam, allAgents, readMe, parseArgs } from './lib.mjs';

export const MODELS = { planner: 'opus', builder: 'sonnet' };
const START_WORD = { planner: 'start', builder: 'go' };
const RULE = 'Follow the attribution rule: no Co-Authored-By or any other attribution line in commits, PRs, issues, comments or files.';

export function buildCommand({ agent, role }) {
  const file = role === 'planner' ? 'PLANNER.md' : 'BUILDER.md';
  const prompt = `Read .work/${file} and follow it exactly. ${RULE} Read the files it lists, then reply READY in one line and wait until I say '${START_WORD[role]}'.`;
  const args = ['--model', MODELS[role]];
  if (role === 'planner') args.push('--settings', '.work/planner-settings.json');
  args.push(prompt);
  return { cmd: 'claude', args, cwd: agent };
}

export function parseDuoArgs(argv, agents) {
  const a = parseArgs(argv);
  const [agent, role] = a._;
  if (!agent || !role) return { error: `Usage: duo.mjs <${agents.join('|')}> <planner|builder> [--dry-run]` };
  if (!agents.includes(agent)) return { error: `Unknown agent "${agent}". One of: ${agents.join(', ')}` };
  if (!MODELS[role]) return { error: `Unknown role "${role}". Use planner or builder.` };
  return { agent, role, dryRun: a['dry-run'] === true };
}

function main() {
  const root = repoRoot();
  const team = readTeam(root);
  const p = parseDuoArgs(process.argv.slice(2), allAgents(team));
  if (p.error) { console.error(p.error); process.exit(2); }
  const { cmd, args, cwd } = buildCommand(p);
  const dir = path.join(root, cwd);
  const quote = (s) => (/[\s'"]/.test(s) ? `"${s.replace(/"/g, '\\"')}"` : s);
  console.log(`cd ${cwd}\n${cmd} ${args.map(quote).join(' ')}`);
  const me = readMe(root);
  if (me && team[me] && !team[me].agents.includes(p.agent)) console.log(`note: ${p.agent} is not one of ${me}'s agents.`);
  if (p.dryRun) process.exit(0);
  const work = path.join(dir, '.work', p.role === 'planner' ? 'PLANNER.md' : 'BUILDER.md');
  if (!existsSync(work)) { console.error(`Missing ${path.relative(root, work)}. Run: git pull  (or node scripts/seed-work.mjs)`); process.exit(1); }
  let r = spawnSync(cmd, args, { cwd: dir, stdio: 'inherit' });
  if (r.error && r.error.code === 'ENOENT' && process.platform === 'win32') {
    r = spawnSync(`${cmd} ${args.map(quote).join(' ')}`, { cwd: dir, stdio: 'inherit', shell: true });
  }
  if (r.error) { console.error(`Could not start claude: ${r.error.message}`); process.exit(1); }
  process.exit(r.status ?? 0);
}

import { fileURLToPath } from 'node:url';
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
