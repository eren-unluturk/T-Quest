---
id: 014
title: Postgres backend for catalog, content, consent and place visits (supersedes 007)
status: ready
issue: 1
depends_on: [013]
---
## Goal
Run catalog, content, consent and place-visit routes against the shared Tiger Data schema (data-platform migrations 0000-0005) when `DATA_BACKEND=postgres`. Analytics and recommendations stay on the memory repo until data-platform adds our aggregates (their prompt 012; the planner will queue that separately). This supersedes 007; leave 007 as it is.

Billing rule: use a local docker TimescaleDB (`../data-platform/docker-compose.yml`) or the Tiger Cloud Free plan only. Nothing paid.

## Context
- `../data-platform/migrations/0001_core.sql` (stops, route_stops, stop_facts, users, consent), `0002_rewards.sql` (sponsors, stores, offers, badges, physical_rewards, store_inventory, user_collections), `0005_schema_v01.sql` (stops.mode, stop_facts.sort/tags, freedom_trail_sites, fun_facts, stores.category, offers.required_badge_id/per_user_limit/placement, physical_rewards.description, consent.granted generated, place_visits hypertable, user_rank view). Read only.
- `../data-platform/docker-compose.yml`, `../data-platform/README.md` (how to start the DB and run migrations), `../data-platform/seeds/dev_seed.sql`
- `src/insights_sponsors/repo/base.py`, `repo/memory.py`, `repo/__init__.py`, `config.py`, `auth.py`
- `insights-sponsors/data/seed/*.json`

## Key mapping rules
- **Ids.** Our seed uses text slugs (`st.cafe-davis`). The DB uses uuid for sponsors, stores, offers and physical_rewards. Map each slug with `uuid5(NAMESPACE, slug)` where `NAMESPACE = uuid5(NAMESPACE_URL, "https://t-quest/insights-sponsors")`. The API returns the uuid string in postgres mode, which the contract allows (ids are strings). Keep the helper in `repo/ids.py`.
- **Badge ids.** The DB uses slugs like `line-red-complete`, `freedom-trail`, `rank-3`. Rename our seed badge ids to that scheme (`badge.line.green.complete` -> `line-green-complete`, `badge.freedom-trail.complete` -> `freedom-trail`, `badge.rank.3` -> `rank-3`, and so on) in both backends, and update the tests. The loader upserts missing badge rows (`ON CONFLICT (id) DO NOTHING`, `kind` as appropriate) so the foreign keys hold.
- **Names.** `physical_rewards.item_type` maps to API `kind`, and `store_inventory.stock > 0` maps to `in_stock`. `freedom_trail_sites.sort_order` maps to `order`. `offers.store_id` NULL means all stores of the sponsor. In postgres mode, read `offers.kind = 'local_pick'` as `discount`, and say so in the report.
- **Users.** `consent.user_id` and `place_visits.user_id` are uuid FKs to `users`. Add `resolve_user(token) -> uuid` on the repo: a valid uuid is used as is; otherwise (dev) look up `users.username = token`, and insert the user if missing only when `auth_mode == "dev"`. Routes keep receiving the token from `current_user_id` and pass it through `resolve_user` inside the postgres repo only.
- **Consent.** `granted` is generated. Grant upserts `granted_at = now(), revoked_at = NULL, policy_version`. Revoke sets `revoked_at = now()`.
- **Rank and badges.** `user_rank(user_id)` reads the `user_rank` view; `user_badges` reads `user_collections`.

## Steps
1. `repo/ids.py` (uuid5 helper) and `repo/postgres.py` with `PostgresRepository`, using a psycopg3 `ConnectionPool` (`psycopg_pool`; add it to deps) from `settings.database_url`. Implement every Protocol method used by catalog, content, consent and place-visit routes. Haversine distance for `stores_near_stop` in SQL. For methods used only by analytics and recommendations (`rider_events`, `stop_popularity`, and similar), raise `NotImplementedError("analytics on postgres waits for data-platform aggregates")`.
2. `repo/__init__.py`: return `PostgresRepository` when `data_backend == "postgres"`. Keep a process-wide pool and close it on app shutdown (lifespan).
3. `insights-sponsors/scripts/load_seed.py`: an idempotent upsert of our seed JSON into stops (insert only if missing; never overwrite rows data-platform ingested), stop_facts (match on stop_id + title), freedom_trail_sites, fun_facts, sponsors, stores, offers, badges (placeholders), physical_rewards, store_inventory, plus dev users `user-1` to `user-6` as usernames. Use `--database-url` or the env. Print the row counts per table.
4. Rename the badge ids as described, in the seed JSON and the tests (the memory backend too).
5. Tests: `tests/test_postgres_repo.py` marked `@pytest.mark.db` and skipped unless `DATABASE_URL` is set. Register the marker in pyproject. It runs `load_seed.py` and then runs the catalog, content, consent and place-visit route tests against `data_backend=postgres` (parametrize the existing fixtures, or a focused subset covering every route). Add a unit test for `ids.py` determinism and `resolve_user` uuid passthrough. These run always and need no DB.
6. README: a "Postgres mode" section covering starting data-platform's compose, running their migrations (as their README says), `python scripts/load_seed.py`, `DATA_BACKEND=postgres`, and that analytics still uses memory.
7. If a DB is available locally (docker running), run the db tests and record the results and timings in the report. If not, say so. Do not install Docker or create cloud resources.

## Acceptance criteria
- `python -m pytest -q` passes with no DB (db tests skipped).
- With a DB: `python scripts/load_seed.py` twice gives the same counts (idempotent), and `python -m pytest -q -m db` passes.
- No writes to tables other than the ones listed in step 3, plus consent and place_visits at runtime.
- No paid services.

## Tests to run
- `cd insights-sponsors && python -m pytest -q`
- If `DATABASE_URL` is set: `python scripts/load_seed.py && python -m pytest -q -m db`

## Out of scope
- Analytics and recommendations on Postgres (later prompt, after data-platform 012). Schema changes: if a column is missing, mark this `blocked` and name the exact column in the report.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.

## Resume notes (builder, safe stop)
- Branch `wip/insights-sponsors-014` (pushed) holds the only finished part: step 4 badge rename (`badge.line.green.complete` -> `line-green-complete`, `badge.freedom-trail.complete` -> `freedom-trail`, `badge.rank.N` -> `rank-N`) in data/seed/offers.json, data/seed/physical_rewards.json, tests/test_catalog.py, tests/test_memory_repo.py; pyproject.toml gets `psycopg-pool>=3.2` and a `db` pytest marker. 149 tests passed with it. Merge or cherry-pick it into main first.
- Not started: repo/ids.py, repo/postgres.py, repo/__init__.py switch plus lifespan pool close, scripts/load_seed.py, tests/test_postgres_repo.py, unit tests for ids/resolve_user, README "Postgres mode".
- Design worked out, not yet written (the last file write was cancelled):
  - ids.py: NAMESPACE = uuid5(NAMESPACE_URL, "https://t-quest/insights-sponsors"); `slug_to_uuid`, `parse_uuid`, `to_uuid`.
  - Add `resolve_user(token)` to the Protocol (memory returns the token). Postgres: valid uuid as is, else users.username lookup, insert only when auth_mode == "dev".
  - Migration facts (read from data-platform/migrations 0001, 0002, 0005): sponsors.category is required by a CHECK (food, clothing, sports, retail, other), so derive it from the sponsor's stores. stores.sponsor_id is NOT NULL and our stores.json has none, so derive it from the store's first offer. consent has a generated `granted` column, granted_at NOT NULL, so revoking a never-granted scope must not insert a row. offers.kind allows points_item after 0005; read local_pick as discount. offers.store_id NULL means all of the sponsor's stores: expand with a join. stop_facts.id is bigserial (return str); fun_facts needs explicit created_at in the loader to keep seed order. stops.mode may be light_rail etc: map non-bus to "subway". Loader fills NULL neighborhood/mode on existing stops but never overwrites; badges and store_inventory use DO NOTHING.
  - In postgres mode analytics/recommendations/boston routes should still use memory data but real consent and place visits: add a composite repo (consent and place-visit methods to Postgres, rest to memory), a `get_insights_repository` dependency used by routes/insights.py, and override it in tests/conftest.py next to `get_repository`.
  - No Docker or Postgres was available in this environment, so DB tests could not be run; psycopg-pool 3.3.3 is installed locally.
- Tool quirk: long bash heredocs containing quotes fail to parse here; write files with the Write/Edit tools.
