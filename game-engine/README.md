# game-engine

Owner: Tobi. Python 3.11+ FastAPI service (see DECISIONS.md).

Own game logic: check-in verification (proximity + live-vehicle sanity check), points ledger logic, ranks/tiers, quests/collectibles, badge/achievement unlock rules (which achievements unlock which patches/stickers), friends/leaderboards, delay compensation, reward and physical-reward redemption (code generation, single-use, store verification endpoint), and bus parity.

See AGENT.md for charter, owned paths and definition of done.

- `src/game_engine/` - service code
- `tests/` - tests
- API spec: `contracts/api/game-engine.yaml`

## Run it

From the repo root, in PowerShell:

```powershell
pip install -r game-engine/requirements.txt
cd game-engine/src
```

**Demo mode (in memory, no database).** Data is lost when the server stops. Stops, offers and quests are fake.

```powershell
uvicorn game_engine.app:app --port 8003
```

**Real mode (Tiger Data database).** Put the database link in `DATABASE_URL`. Never commit it.

```powershell
$env:DATABASE_URL = "postgres://USER:PASSWORD@HOST:PORT/tsdb?sslmode=require"
uvicorn game_engine.app:app --port 8003
```

Open `http://127.0.0.1:8003/healthz`. It shows `"store": "postgres"` or `"store": "memory"`. Interactive docs are at `http://127.0.0.1:8003/docs`.

### Try a call

Sign-in is a demo: the bearer token is the username.

```powershell
curl -H "Authorization: Bearer ann" http://127.0.0.1:8003/me/rank
```

### Settings

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Set: use the database. Not set: in-memory demo. |
| `VEHICLE_CHECK` | `off` skips the live vehicle check. Default: on with the database, off in memory mode. |
| `STORE_KEY` | Store key accepted by `POST /redemptions/verify` (memory-mode default: `dev-store-key`). With the database, a store's `X-Store-Key` must match its sha256 hash in `stores.store_key_hash`. |

## Delay bonus job

Pays 50 points once per alert to riders whose home line has an outage. It does not run by itself. Run it on a schedule:

```powershell
cd game-engine/src
python -m game_engine.delay_job --dry-run   # count only, writes nothing
python -m game_engine.delay_job             # pay
```

## Tests

```powershell
python -m unittest discover -s game-engine/tests
```

The database tests are skipped unless `GE_TEST_DATABASE_URL` is set. They run inside a transaction that is rolled back, so the database is left unchanged.

## Numbers you can tune

All in `src/game_engine/config.py`: check-in distance and cooldown, points, the 8 ranks and discounts, redemption limits.
