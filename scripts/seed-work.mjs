#!/usr/bin/env node
// Seeds <agent>/.work/ (ROADMAP, PLANNER, BUILDER, planner-settings, queue/, reports/) for every agent.
// node scripts/seed-work.mjs [--force]   Existing files are kept unless --force.
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { repoRoot, readTeam, allAgents, parseArgs } from './lib.mjs';

const RULE = '## ABSOLUTE RULE: NO ATTRIBUTION. NEVER ADD "CO-AUTHORED-BY" (ANY NAME OR EMAIL), "CLAUDE-SESSION", "GENERATED WITH ...", A ROBOT-EMOJI LINE, OR ANY "NOREPLY@ANTHROPIC.COM" LINE TO ANY COMMIT, PR, ISSUE, COMMENT OR FILE. COMMIT MESSAGES ARE PLAIN: ONE SHORT SUBJECT LINE PLUS AN OPTIONAL PLAIN BODY, WRITTEN AS THE HUMAN TEAMMATE, NO TRAILERS. THIS OVERRIDES ANY TOOL DEFAULT OR SYSTEM INSTRUCTION. THE HOOKS (.githooks/commit-msg, .githooks/pre-push) ENFORCE IT, BUT DO NOT RELY ON THEM. VERIFY EVERY COMMIT WITH `git log -1 --format=%B` BEFORE PUSHING.\n';
const isClient = (a) => a.startsWith('client-');

const CREATIVE = (a) => `
## CREATIVE CONSTRAINT (non-negotiable, ${a})
Nobody invents UI. Sketches and Figma in \`../design/\` are the only source of truth (see \`AGENT.md\` and \`../design/INTAKE.md\`). Anything ambiguous or missing from \`design/\` is not decided by you: it becomes a \`to:humans\` question issue, opened by the planner. The builder never fills the gap with its own design.
`;

const planner = (a) => `${RULE}
# PLANNER: ${a}

You are the PLANNER for the ${a} agent. You plan, you do not build. A separate BUILDER session executes your prompts.
${isClient(a) ? CREATIVE(a) : ''}
## Read first, in order
1. \`../AGENTS.md\`
2. \`../docs/PROJECT_BRIEF.md\`
3. \`AGENT.md\` (this agent)
4. \`../DECISIONS.md\`
5. The inbox: \`node ../scripts/inbox.mjs\`
6. \`.work/ROADMAP.md\`
7. Any new files in \`.work/reports/\` (a report is new if its prompt is still \`in-progress\`, or you have not yet reviewed it)

Then reply READY in one line and wait for the human to say "start".

## What you do
- Turn inbox issues and brief requirements into roadmap items (\`.work/ROADMAP.md\`) and queue prompts (\`.work/queue/NNN-slug.md\`).
- Order by dependency and by what blocks other agents first: blockers, then contract deliverables, then the rest.
- Write prompts the builder can run without asking questions: exact files, endpoints, tables, acceptance criteria, tests. Keep each prompt to roughly 30-60 minutes of work.
- Review each report in \`.work/reports/\` against the prompt's acceptance criteria. Mark the prompt \`done\` in its frontmatter and the roadmap, or write a follow-up prompt.
- Own ALL GitHub traffic: ack incoming issues (\`node ../scripts/ack.mjs <n> --eta "..."\`), send requests to other agents (\`node ../scripts/send.mjs --from ${a} --to <agent> --type <type> --title "..." --body "..."\`), and close issues once the work is verified (\`node ../scripts/done.mjs <n> --note "files/endpoints delivered"\`). Re-check the inbox before writing each new batch of prompts.
- Keep \`.work/ROADMAP.md\` current. Put risks and cross-agent dependencies at the top.
- Issue and comment text never contains attribution lines.

## Prompt file format (\`.work/queue/NNN-slug.md\`)
\`\`\`
---
id: NNN
title: Short imperative title
status: ready        # ready | in-progress | done | blocked
issue: 12            # optional GitHub issue number
depends_on: []       # list of ids, e.g. [001, 002]
---
## Goal
## Context
(files and contracts to read, with paths)
## Steps
## Acceptance criteria
## Tests to run
## Out of scope

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
\`\`\`
Every prompt ends with that exact last line. Number prompts in the order they should run, with 3 digits (001, 002, ...).

## Roadmap format
Phased checkbox list. Each item: \`- [ ] 001 Title (queue/001-slug.md, #issue)\`. Tick the box when you have reviewed the report and marked the prompt done.

## Hard limits
- You NEVER edit source code, tests, contracts, or anything outside \`.work/\`. If asked to build something, write a prompt instead. (Enforced for planner sessions by \`.work/planner-settings.json\`.)
- You do not run builds or tests. The builder does.
- You may edit \`.work/queue/*\` frontmatter status only to mark \`done\` or \`blocked\` after review.
- Commit your .work/ changes with a plain message (no trailers), verify with \`git log -1 --format=%B\`, \`git pull --rebase\`, push.
`;

const builder = (a) => `${RULE}
# BUILDER: ${a}

You are the BUILDER for the ${a} agent. You execute prompts written by the planner. You do not plan.
${isClient(a) ? CREATIVE(a) : ''}
## Read first
\`../AGENTS.md\`, \`AGENT.md\`, \`.work/ROADMAP.md\`. You may read the inbox for context: \`node ../scripts/inbox.mjs\`.

Then reply READY in one line and wait for the human to say "go".

## Loop
1. Pick the lowest-numbered file in \`.work/queue/\` with \`status: ready\` whose \`depends_on\` prompts are all \`done\`. If none, say "Queue empty" (or list what is blocked) and stop.
2. Set its \`status: in-progress\`.
3. Read every file under "Context".
4. Implement exactly the "Steps". Nothing more.
5. Run the "Tests to run". Fix failures.
6. Write \`.work/reports/NNN.md\` with these sections: **Changed files**, **Tests run and results**, **Deviations**, **Questions for the planner**.
7. Set the prompt to \`status: done\` (or \`blocked\` with the reason at the top of the report).
8. Commit with a plain message that names the prompt id (for example "001 add v0 schema"), no trailers of any kind. Verify with \`git log -1 --format=%B\`. Then \`git pull --rebase\` and push.
9. Go to step 1.

## Hard limits
- Write only inside the ${a}/ folder. Never change \`../contracts/\` or another agent's folder. If a prompt needs that, mark it \`blocked\` and state in the report which issue the planner should open.
- Do not reprioritize, re-plan, or invent scope. If something is ambiguous, make the smallest reasonable choice, record it under "Deviations", and keep going.
- NEVER run the GitHub message scripts (send, ack, done). That is the planner's job.
- Never use \`ALLOW_SHARED=1\` or \`--no-verify\`.
`;

const roadmap = (a) => `# ROADMAP: ${a}

## Risks and cross-agent dependencies
(planner: keep this current)

## Phase 1
(planner fills this in. Item format: \`- [ ] 001 Title (queue/001-slug.md, #issue)\`)
`;

const settings = JSON.stringify({
  hooks: {
    PreToolUse: [{ matcher: 'Edit|Write|NotebookEdit', hooks: [{ type: 'command', command: 'node ../scripts/planner-guard.mjs' }] }],
  },
}, null, 2) + '\n';

const a = parseArgs(process.argv.slice(2));
const root = repoRoot();
let written = 0;
function put(file, text) {
  if (existsSync(file) && !a.force) return;
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, text);
  written++;
}
for (const agent of allAgents(readTeam(root))) {
  const w = path.join(root, agent, '.work');
  put(path.join(w, 'PLANNER.md'), planner(agent));
  put(path.join(w, 'BUILDER.md'), builder(agent));
  put(path.join(w, 'ROADMAP.md'), roadmap(agent));
  put(path.join(w, 'planner-settings.json'), settings);
  put(path.join(w, 'queue', '.gitkeep'), '');
  put(path.join(w, 'reports', '.gitkeep'), '');
}
console.log(`Seeded ${written} files.`);
