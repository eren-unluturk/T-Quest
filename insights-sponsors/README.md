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

## Run locally

Windows PowerShell, from the `insights-sponsors/` folder:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m insights_sponsors.main
```

The service listens on http://localhost:8002 (`GET /health` needs no token; every other route except `GET /fun-facts` needs `Authorization: Bearer <user id>` in dev mode).

Settings are read from the environment or from the repo-root `.env` (copy `../.env.example`; the file is optional):

| Variable | Default | Meaning |
| --- | --- | --- |
| `INSIGHTS_SPONSORS_PORT` | `8002` | Port for `python -m insights_sponsors.main` |
| `AUTH_MODE` | `dev` | `dev`: the bearer token is the user id. `strict`: returns 501 until session verification is wired |
| `DATA_BACKEND` | `memory` | `memory` uses the seed JSON in `data/seed/`. `postgres` is not implemented yet |
| `DATABASE_URL` | unset | Tiger Data connection string, for the future Postgres backend |

## Contract

The OpenAPI draft lives in `openapi/insights-sponsors.yaml` until it is promoted to `contracts/api/insights-sponsors.yaml` (done by a human, builders never write to `contracts/`).
