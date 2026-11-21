# Message protocol

GitHub Issues is the only inter-agent channel. Never edit another agent's folder; open an issue.

## Sending
- Use the "Agent message" issue form on GitHub, or `node scripts/send.mjs --from <agent> --to <recipient> --type <type> --title "..." --body "..." [--files "..."] [--by "..."]`.
- Fields: From, To, Type, Summary, What I need, Contract/files involved, Needed by.
- To: data-platform, insights-sponsors, game-engine, client-bryan, client-isabella, client (both clients), humans, all.
- Type: request, question, blocker, contract-change, handoff, done.
- `.github/workflows/route-issues.yml` applies `to:`, `from:`, `type:` labels, adds `priority:blocker` for blockers, and posts a one-line routing comment. `send.mjs` also applies labels directly.
- Sign every issue/comment with `[agent-name]`. Prefer small, specific requests naming the exact contract needed.

## Receiving
1. Check the inbox at session start (SessionStart hook), before each task, and after each task: `/inbox` or `node scripts/inbox.mjs`. Blockers first.
2. ACK: comment "ACK" with an ETA and add `status:acked` (`node scripts/ack.mjs <n> --eta "..."`).
3. Deliver, commit with `Closes #n`, then comment pointing to the files/endpoints delivered and close (`node scripts/done.mjs <n> --note "..."`).
4. `node scripts/watch-inbox.mjs` (VS Code task "Watch inbox") polls every 45s in a spare terminal and prints only new/changed items.

## Contracts
`contracts/{api,db,events}` are shared. A change needs a `type:contract-change` issue naming every consumer; each consumer ACKs before the change is merged. Additive, backwards-compatible changes are preferred.

## Ownership guard
`.githooks/pre-commit` reads `.team/me` + `team.json` and refuses staged files outside your folders. Always allowed: `docs/`, `DECISIONS.md`. Override with `ALLOW_SHARED=1`.

## Git flow
Commit to `main` inside your own folders. `git pull --rebase` before push.

## Attribution
No Co-Authored-By / "Generated with" / Claude or AI attribution anywhere. `.githooks/commit-msg` strips it from commit messages.
