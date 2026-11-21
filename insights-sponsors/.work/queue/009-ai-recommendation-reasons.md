---
id: 009
title: Optional AI-written reasons for recommendations, with a deterministic fallback
status: cancelled
issue:
depends_on: [006]
---
> CANCELLED: no API-key / per-token billing for this hackathon (see AGENTS.md "Billing", DECISIONS.md D15). Do not build. Possible future feature only. Recommendations stay deterministic SQL.

## Goal
The brief asks for "AI-assisted recommendations". The SQL/in-memory logic stays the only thing that picks and orders recommendations. When `ANTHROPIC_API_KEY` is set, an LLM rewrites only the short `reason` text in a friendlier tone. With no key, a timeout, or an error, the deterministic reason from 006 is returned unchanged. The contract does not change.

## Context
- `src/insights_sponsors/recommend.py`, `routes/insights.py` (from 006)
- `src/insights_sponsors/config.py`
- `../.env.example` (`ANTHROPIC_API_KEY`, optional)
- Anthropic Python SDK docs (Messages API). Use the official `anthropic` package.

## Steps
1. Settings: `anthropic_api_key: str | None = None` (env `ANTHROPIC_API_KEY`), `recs_ai_model: str = "claude-haiku-5-5"` (env `RECS_AI_MODEL`), `recs_ai_timeout_s: float = 4.0`.
2. `src/insights_sponsors/ai_reasons.py`: `rewrite_reasons(items) -> list[str]`. One Messages API call for the whole list (not one per item). Send only the recommendation titles, kinds and deterministic reasons, never the user id, place visits or any personal data. Ask for a JSON array of strings of the same length, each 140 characters or fewer, with no emojis and no claims about sponsors. Validate the length and types. On any failure return the original reasons.
3. Call it from the `/recommendations` route after ranking. It must never reorder, add or drop items, and never change `sponsored` or `score`.
4. Cache results in-process by a hash of the input reasons, with a 10-minute TTL, to keep cost and latency down.
5. Add `anthropic` to the runtime deps.
6. Tests in `tests/test_ai_reasons.py` (never call the real API; monkeypatch the client): no key leaves the output unchanged, success replaces only the reasons, a wrong-length response falls back, an exception or timeout falls back, the payload sent contains no `user-` ids, and the order, score and sponsored fields are identical before and after.

## Acceptance criteria
- The endpoint behaves identically without a key (existing tests are unchanged and pass).
- No personal data leaves the service. A test asserts this.
- `python -m pytest -q` passes, with no network access in tests.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`

## Out of scope
- LLM-chosen recommendations, embeddings, and changes to the OpenAPI contract.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
