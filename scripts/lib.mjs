// Shared helpers for tquest scripts. Node only, cross-platform.
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

export function repoRoot(cwd = process.cwd()) {
  const r = spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8' });
  if (r.status !== 0) throw new Error('Not inside a git repo');
  return path.resolve(r.stdout.trim());
}

export function readTeam(root = repoRoot()) {
  return JSON.parse(readFileSync(path.join(root, 'team.json'), 'utf8'));
}

export function allAgents(team) {
  return [...new Set(Object.values(team).flatMap((p) => p.agents))];
}

export function readMe(root = repoRoot()) {
  const f = path.join(root, '.team', 'me');
  if (!existsSync(f)) return null;
  const v = readFileSync(f, 'utf8').trim().toLowerCase();
  return v || null;
}

// Agent folder the cwd is inside of (or null).
export function agentFromCwd(cwd = process.cwd(), root = repoRoot(cwd), team = readTeam(root)) {
  const rel = path.relative(root, path.resolve(cwd)).split(path.sep)[0];
  return allAgents(team).includes(rel) ? rel : null;
}

// { me, agents: [...active agents], primary }
export function resolveIdentity(cwd = process.cwd()) {
  const root = repoRoot(cwd);
  const team = readTeam(root);
  const me = readMe(root);
  const fromCwd = agentFromCwd(cwd, root, team);
  let agents;
  if (fromCwd) agents = [fromCwd];
  else if (me && team[me]) agents = team[me].agents;
  else agents = [allAgents(team)[0]];
  return { root, team, me, agents, primary: agents[0] };
}

export function gh(args, opts = {}) {
  const r = spawnSync('gh', args, { encoding: 'utf8', ...opts });
  if (r.error) throw new Error(`gh not runnable: ${r.error.message}`);
  if (r.status !== 0) throw new Error(`gh ${args.slice(0, 3).join(' ')} failed: ${(r.stderr || '').trim()}`);
  return r.stdout;
}

export function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      const n = argv[i + 1];
      if (n === undefined || n.startsWith('--')) out[k] = true;
      else { out[k] = n; i++; }
    } else out._.push(a);
  }
  return out;
}

export const TYPES = ['request', 'question', 'blocker', 'contract-change', 'handoff', 'done'];
export const RECIPIENTS = ['data-platform', 'insights-sponsors', 'game-engine', 'client-bryan', 'client-isabella', 'client', 'humans', 'all'];
export const SENDERS = ['data-platform', 'insights-sponsors', 'game-engine', 'client-bryan', 'client-isabella', 'humans'];

// Labels that make an issue relevant to the given agents.
export function inboxLabels(agents) {
  const s = new Set(['to:all', ...agents.map((a) => `to:${a}`)]);
  if (agents.some((a) => a.startsWith('client-'))) s.add('to:client');
  return s;
}

export function listInbox(agents) {
  const raw = gh(['issue', 'list', '--state', 'open', '--limit', '100', '--json', 'number,title,labels,updatedAt,comments']);
  const want = inboxLabels(agents);
  return JSON.parse(raw)
    .map((i) => ({ ...i, labels: i.labels.map((l) => l.name) }))
    .filter((i) => i.labels.some((l) => want.has(l)))
    .map((i) => ({
      ...i,
      blocker: i.labels.includes('priority:blocker') || i.labels.includes('type:blocker'),
      acked: i.labels.includes('status:acked'),
    }))
    .sort((a, b) => (b.blocker - a.blocker) || (a.acked - b.acked) || a.number - b.number);
}

export function formatItem(i) {
  const from = (i.labels.find((l) => l.startsWith('from:')) || 'from:?').slice(5);
  const type = (i.labels.find((l) => l.startsWith('type:')) || 'type:?').slice(5);
  const flags = `${i.blocker ? '!' : ' '}${i.acked ? 'A' : ' '}`;
  return `${flags} #${i.number} [${type}] from ${from}: ${i.title}`;
}
