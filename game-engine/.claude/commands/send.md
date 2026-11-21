---
description: Draft and create an issue addressed to another agent
argument-hint: <to> <what you need>
---
Draft a small, specific message: $ARGUMENTS

Choose --to (data-platform, insights-sponsors, game-engine, client-bryan, client-isabella, client, humans, all) and --type (request, question, blocker, contract-change, handoff, done). Include the exact contract/files involved and a needed-by time. Show the draft, then run:
`node ../scripts/send.mjs --from <my-agent> --to <to> --type <type> --title "<title>" --body "<body>" [--files "<paths>"] [--by "<when>"]`
Never edit another agent's folder; send an issue instead.
