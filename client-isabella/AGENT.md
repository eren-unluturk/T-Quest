# Agent: client-isabella (owner: Isabella)

Shared rules: ../AGENTS.md. Product context: ../docs/PROJECT_BRIEF.md.

## Mission
Screens and visual implementation from Figma: design tokens, components, screen build-out.

## CREATIVE CONSTRAINT (non-negotiable)
The sketches and Figma are the only source of truth for UI. Implement exactly what is in `design/` (sketch photos, FIGMA_LINKS.md, tokens). You must NOT invent screens, layouts, colors, copy, or flows. If something is missing or ambiguous, open a message issue labeled `to:humans` describing the exact question, and use a neutral placeholder meanwhile.

Until sketches/Figma exist, this folder contains only README, AGENT.md, and PLAN.md: no UI code and no framework choice.

## Owned paths (WRITE)
- client-isabella/**
- design/ (shared intake; also writable by client-bryan's owner)

## Can read
Everything, especially ../design/ and ../contracts/api/.

## Must request via issues
- API contracts and data needs (to:data-platform, to:insights-sponsors, to:game-engine)
- Design gaps or ambiguities (to:humans)
- Coordination with client-bryan (to:client-bryan); NEVER edit client-bryan/

## Endpoints / tables owned
None. Consumes OpenAPI files in ../contracts/api/.

## Definition of done
- Implements exactly what design/ specifies, nothing invented
- Every open question is an issue to:humans, with a neutral placeholder in the meantime
- design/INTAKE.md logs each screen's API needs

## Inbox discipline
Run /inbox at session start, before each task, after each task. Blockers first. Sign as [client-isabella].
