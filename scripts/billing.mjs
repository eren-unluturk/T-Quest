// Billing safety helpers. Claude Code must run on each person's own plan, never on API/per-token billing.
// An ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN in the environment makes Claude Code bill the API instead of the plan.
// These helpers only ever report variable NAMES, never values.
import { spawnSync } from 'node:child_process';

export const BILLING_VARS = ['ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'];
export const SCOPES = ['User', 'Machine'];

// Names of vars set (non-empty) in an env object (default: this process).
export function processHits(env = process.env) {
  return BILLING_VARS.filter((n) => typeof env[n] === 'string' && env[n].trim() !== '');
}

// Reads Windows User/Machine environment via PowerShell. Returns true/false only, never the value.
export function windowsIsSet(name, scope) {
  const ps = `if ([Environment]::GetEnvironmentVariable('${name}','${scope}')) { 'SET' } else { 'UNSET' }`;
  const r = spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps], { encoding: 'utf8' });
  return r.status === 0 && r.stdout.trim() === 'SET';
}

// [{ name, scope }] for vars set at Windows User/Machine level. isSet is injectable for tests.
export function persistentHits({ platform = process.platform, isSet = windowsIsSet } = {}) {
  if (platform !== 'win32') return [];
  const hits = [];
  for (const scope of SCOPES) for (const name of BILLING_VARS) if (isSet(name, scope)) hits.push({ name, scope });
  return hits;
}

// Copy of env without the billing vars (case-insensitive, since Windows env names are).
export function scrubEnv(env = process.env) {
  const out = {};
  const bad = new Set(BILLING_VARS);
  for (const [k, v] of Object.entries(env)) if (!bad.has(k.toUpperCase())) out[k] = v;
  return out;
}

// Exact commands to fix what was found.
export function fixText({ process: p = [], persistent = [] }) {
  const lines = [];
  for (const n of new Set([...p, ...persistent.map((h) => h.name)])) {
    lines.push(`Remove-Item Env:${n} -ErrorAction SilentlyContinue`);
  }
  for (const h of persistent) {
    lines.push(`[Environment]::SetEnvironmentVariable('${h.name}', $null, '${h.scope}')${h.scope === 'Machine' ? '   # run PowerShell as Administrator' : ''}`);
  }
  if (lines.length) lines.push('Then close ALL terminals and VS Code, reopen, run /status in claude and confirm it shows your plan (not API usage billing).');
  return lines.join('\n');
}

// Full check result used by doctor and duo.
export function checkBilling(opts = {}) {
  const p = processHits(opts.env);
  const persistent = persistentHits(opts);
  return { process: p, persistent, ok: p.length === 0 && persistent.length === 0 };
}

export function describe(res) {
  const parts = [...res.process.map((n) => `${n} (this process)`), ...res.persistent.map((h) => `${h.name} (Windows ${h.scope} env)`)];
  return parts.join(', ');
}
