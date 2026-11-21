# DECISIONS

Format: decision, alternatives, why. Append new entries; do not rewrite others'.

## D1. Backend: Python 3.11+ FastAPI, one service per backend agent, contract-first OpenAPI
- Alternatives: Node/TypeScript services; a single monolith.
- Why: team default; OpenAPI in contracts/api/ lets clients generate typed clients; one service per agent keeps ownership clean. Changeable by issue.

## D2. One shared Tiger Data database, schema owned by data-platform
- Alternatives: DB per service.
- Why: rider_events, aggregates and recommendations need joins in SQL; it is the prize angle.

## D3. Client split: Bryan = app foundation, Isabella = screens/visuals
- Alternatives: split by feature area.
- Why: foundation vs Figma implementation is a natural seam. Changeable by issue between to:client-bryan and to:client-isabella.

## D4. No framework or UI code until sketches/Figma exist
- Why: nobody invents UI; sketches/Figma are the only source of truth.

## D5. Hooks are CommonJS, scripts are ESM `.mjs`
- Alternatives: `.mjs` hooks.
- Why: git hooks are extensionless files; Node treats extensionless files as CommonJS on older LTS, so `require` is portable. Found while testing.

## D6. Ownership guard allowlist
- Always allowed: own folders, docs/, DECISIONS.md. Everything else (contracts/, scripts/, .github/, team.json, design/ for non-owners) needs ALLOW_SHARED=1.
- Missing `.team/me` blocks commits (run setup-me). Alternatives: warn only. Why: a silent guard is no guard.
- Consequence: contracts/ edits need ALLOW_SHARED=1 even for data-platform, which makes the contract-change process deliberate. Root files (AGENTS.md, TEAM.md, team.json, scripts/) are shared and edited rarely, with ALLOW_SHARED=1.

## D7. Identity resolution
- Active agent = agent folder of cwd; else the person's agents from .team/me (first is primary); else first agent in team.json.

## D8. `send.mjs` applies labels directly as well as via the workflow
- Why: instant routing and works even if Actions is disabled. The workflow is idempotent.

## D9. Labels and seed issues created by scripts
- `scripts/setup-labels.mjs`, `scripts/seed-issues.mjs`. The data-platform -> game-engine/insights-sponsors ingestion seed is two issues (one per recipient) because the form's To field is single-valued.

## D10. Docker-compose is deferred to data-platform
- Bootstrap builds skeleton and automation only. data-platform delivers docker-compose in its v0 schema issue.

## D11. Branches: commit straight to main
- Per brief. Alternatives: PR flow. Why: 4 people, hackathon speed; ownership guard prevents collisions.

## D13. Per-path ownership via team.json "paths" (weekend default)
- Decision: each person has an optional `paths` list of globs ("dir/**" = prefix, "/*" = any root-level file, else exact path) that the pre-commit guard allows in addition to their folders, docs/ and DECISIONS.md.
  - eren: contracts/db/**, contracts/api/data-platform.yaml, contracts/api/insights-sponsors.yaml, scripts/, .github/, .githooks/, .claude-template/, .claude/, .vscode/, tests/, team.json, TEAM.md, and all root files.
  - tobi: contracts/api/game-engine.yaml.
  - bryan, isabella: none beyond their folders (design/ is a shared folder for both).
  - contracts/events/** and any other contracts/ path: ALLOW_SHARED=1 only (needs a contract-change issue acked by consumers).
- Alternatives: everything outside own folders behind ALLOW_SHARED=1 (D6); per-agent rather than per-person paths.
- Why: owners can edit their own specs without friction while shared infrastructure stays with Eren for the weekend. Revisit after the hackathon. Supersedes the consequence noted in D6.

## D14. setup-me sets hooksPath; doctor checks setup
- `setup-me.mjs` runs and verifies `git config core.hooksPath .githooks` (fails loudly otherwise). `doctor.mjs` prints a pass/fail checklist: hooksPath, .team/me, hooks present, gh auth, Node >= 20 (.env optional warning).

## D12. Tiger Data findings (researched 2026-11-21; verify before relying)
- Tiger Cloud has a Free plan (Postgres + TimescaleDB + vector); pick "Free Plan" at signup rather than the 30-day trial. A third-party listing showed paid tiers starting around $30/mo, so check the pricing page for free-tier limits.
- Fastest path: install Tiger CLI (Windows supported; install script at cli.tigerdata.com, or package managers), `tiger auth login`, `tiger service create`.
- The Tiger MCP server is built into the CLI: `tiger mcp install <client>` configures Claude Code, Cursor, VS Code and others, and it proxies Postgres/TimescaleDB doc search. Worth installing for data-platform.
- Docs: https://www.tigerdata.com/docs/get-started/quickstart/tiger-cli , https://www.tigerdata.com/docs/ai/latest/mcp-server/
- Local fallback: a timescaledb docker image via docker-compose (data-platform to add).
- Demo numbers to capture: compression ratio on realtime tables, continuous-aggregate query latency vs raw.

## D15. Attribution enforcement is mechanical
- `.githooks/attribution.cjs` holds the banned-line patterns (any Co-Authored-By trailer with any name, Claude-Session, "Generated with", the vendor noreply address, robot-emoji lines with Claude/Generated). `commit-msg` strips them and aborts on an empty message; `pre-push` scans every commit in the pushed range (new remote refs: commits not on any remote) and refuses with a non-interactive `git filter-branch --msg-filter` fix, which catches `--no-verify` commits. `scripts/check-attribution.mjs` audits full history, tracked files (rule-carrying files excluded: AGENTS.md, CLAUDE.md, AGENT.md, .work/PLANNER.md and BUILDER.md, docs/ONBOARDING.md, docs/DUO.md, .githooks/, .claude-template/, .claude/, tests/) and issues/PRs via gh. `doctor.mjs` runs it.
- Why: the rule must hold even when a tool default or --no-verify tries to add trailers. Existing history was audited: clean, nothing rewritten.

## D16. Script verification against the live repo
- send, ack, done and watch-inbox were exercised with throwaway issues (closed afterward). The route-issues workflow applied to:/from:/type: labels to a fresh issue. No fixes were needed.

## D17. Planner/builder duo
- Each agent has `.work/` (ROADMAP, PLANNER, BUILDER, planner-settings.json, queue/, reports/), seeded by `scripts/seed-work.mjs` and launched by `scripts/duo.mjs` (planner: `--model opus`, builder: `--model sonnet`, prompt passed as the positional argument). VS Code tasks exist per agent and role, plus `Duo up: <person>`.
- The initial prompt makes each session read its role file and reply READY, then wait for `start` (planner) or `go` (builder), so a four-pane launch does not start spending all at once. Alternative: begin immediately.
- Planner write restriction uses a PreToolUse hook (`scripts/planner-guard.mjs`, loaded via `--settings .work/planner-settings.json`) instead of permission deny rules, because deny rules cannot express "everything except .work/". Verified live: a Write to src/ was blocked and a Write to .work/tmp/ succeeded. It does not stop shell-based writes, so PLANNER.md also forbids them.
- Ownership: .work/ lives inside each agent folder, so the existing folder allowlist covers it (tests added).
