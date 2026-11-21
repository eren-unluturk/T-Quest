# Demo (backend tour)

> Demo placeholder. No partnership, endorsement or real discount is implied. Sponsors, stores, offers and labels are placeholders. Rider data is synthetic; MBTA data is real.

There is no rider UI yet (it waits on `design/`), so this demo shows the live backends. For UI beats see the placeholders in [PITCH.md](../PITCH.md).

## Run it
From the repo root, in PowerShell. A stale `DATABASE_URL` in your shell overrides `.env`, so clear it first:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
node scripts/demo.mjs            # starts the 3 services, runs the tour, stops them
node scripts/demo.mjs --serve    # same, then keeps them running (Ctrl+C to stop) so you can open the /docs pages
```

Needs: Python deps installed for each service, a reachable database in `.env`, and (for fresh live vehicles) the collector running: `python -m data_platform.collector` from `data-platform/`. Also available as the VS Code task "Demo tour".

If the nearby spots or content are empty, reload the seed (both idempotent, from `insights-sponsors/`): `python scripts/load_seed.py` then `python -m ingest_content.run`.

## What the tour shows (about 3 minutes)
1. **Real live MBTA data** from Tiger Data: Red Line vehicles reporting in the last 2 minutes, active alerts (data-platform :8001).
2. **Nearby spots at Harvard**, no filters, with filter chips (counts per category and label). Mint Julep shows no label because its only label is pending.
3. **Filters combine** on the fictional "Sample ... (demo)" spots: Davis, cafe + immigrant-owned; woman-owned returns nothing (only a pending label exists); Harvard asian-owned OR woman-owned; sponsored-first with native offers.
4. **Rank tiers** read from the shared `ranks` table (8 named ranks, placeholder percentages, top rank has a placeholder free item) and offers near Fenway.
5. **Tourist content near Park Street** with source link and attribution, plus loading-screen facts (hand-written, `needs_verify`).
6. **game-engine in in-memory demo mode** (fake stops "park" and "downtown", nothing written to the shared database): two check-ins, rank, quests. A repeat run within the cooldown shows HTTP 409; restart game-engine to reset.

## Where the Tiger Data numbers are
`docs/TIGER_DATA_RESULTS.md` (also copied into the generated block in PITCH.md). Real-data compression is TODO: measure; the continuous-aggregate latency comparison is reported as measured.

## Honest limits
- No rider UI. Real check-ins on real stops need game-engine in Postgres mode (writes to the shared database), which this tour avoids on purpose.
- Rider events are synthetic; the tour does not claim real users.
- MHC content terms are unconfirmed; Freedom Trail text and loading facts await a human check.
