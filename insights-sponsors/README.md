# insights-sponsors

Owner: Eren. Python 3.11+ FastAPI service (see DECISIONS.md).

Own route analytics, recommendations, the sponsor/offer data model and matching, store partners and the physical-reward catalog (stickers/patches), tourist content (stop facts, Freedom Trail, fun facts), and consent-based tracking logic.

See AGENT.md for charter, owned paths and definition of done.

- `src/` - service code
- `tests/` - tests

## Develop

- Install: `pip install -e ".[dev]"`
- Run: `python -m insights_sponsors.main` (serves on port 8002, see `INSIGHTS_SPONSORS_PORT`)
- Test: `pytest`
