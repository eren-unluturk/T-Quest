#!/usr/bin/env node
// PreToolUse hook for planner sessions: block Edit/Write/NotebookEdit outside <agent>/.work/.
// Reads the hook JSON on stdin. Exit 2 = block (stderr is shown to the model).
import { readFileSync } from 'node:fs';
import path from 'node:path';

let input = {};
try { input = JSON.parse(readFileSync(0, 'utf8')); } catch { process.exit(0); }
const ti = input.tool_input || {};
const target = ti.file_path || ti.notebook_path;
if (!target) process.exit(0);

const cwd = path.resolve(input.cwd || process.cwd());
const allowed = path.join(cwd, '.work') + path.sep;
const resolved = path.resolve(cwd, target);
const norm = (p) => (process.platform === 'win32' ? p.toLowerCase() : p);
if (norm(resolved + path.sep).startsWith(norm(allowed)) || norm(resolved).startsWith(norm(allowed))) process.exit(0);

console.error(`planner-guard: planners may only write inside .work/ (blocked: ${target}). Write a queue prompt in .work/queue/ for the builder instead.`);
process.exit(2);
