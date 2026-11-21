---
id: 002
title: Core schema - transit, users, consent, friends, rider_events, points_ledger, ranks
status: ready
issue: 4
depends_on: [001]
---
## Goal
Migrations for the core tables that game-engine and insights-sponsors depend on, including the `rider_events` and `points_ledger` hypertables and an append-only guard on the ledger.

## Context
- `../contracts/api/game-engine.yaml` (schemas CheckinRequest, CheckinResult, PointsSummary, Rank, Friend, LeaderboardRow; `x-rules` ranks)
- `../game-engine/src/game_engine/config.py` (RANKS tuples), `points.py` (ledger semantics: delta + reason, lifetime = sum of positive deltas), `checkin.py` (needs stop lat/lon, last check-in per user+stop)
- Issue #4 (game-engine) and #6 (insights-sponsors) requirements, summarized below
- Migration runner from 001

## Steps
Create `migrations/0001_core.sql` (idempotent: `IF NOT EXISTS` everywhere, `create_hypertable(..., if_not_exists => TRUE)`, `ON CONFLICT DO NOTHING` for seeds):
1. `routes`: `id text pk` (MBTA route id, e.g. `Red`, `Green-B`, `1`), `short_name`, `long_name`, `mode text check in ('subway','light_rail','bus','commuter_rail','ferry')`, `route_type int` (GTFS), `color text`, `text_color text`, `line_id text` (MBTA line, e.g. `line-Green`), `sort_order int`.
2. `stops`: `id text pk` (MBTA stop/parent-station id), `name`, `lat double precision not null`, `lon double precision not null`, `parent_station text null`, `location_type int`, `municipality text`, `wheelchair_boarding int`, `is_freedom_trail boolean not null default false`, `neighborhood text`, `updated_at timestamptz default now()`. Index on `(lat, lon)`.
3. `route_stops`: `route_id fk`, `stop_id fk`, `direction_id smallint`, `stop_sequence int`, pk `(route_id, stop_id, direction_id)`. Needed for "complete a line" and line leaderboards.
4. `stop_facts` (insights-sponsors #6): `id bigserial pk`, `stop_id text null fk` (null = general loading-screen fact), `kind text check in ('fast_fact','history','freedom_trail','loading_screen')`, `title text`, `body text not null`, `source_url text`, `created_at`.
5. `users`: `id uuid pk default gen_random_uuid()`, `username text unique not null`, `display_name`, `created_at`, `home_line_override text null`.
6. `consent` (#6; matches insights-sponsors' consent endpoints, which re-grant by updating the row in place): `user_id uuid fk`, `scope text check in ('location','place_visits','recommendations','marketing')`, `granted_at timestamptz not null default now()`, `revoked_at timestamptz null`, `policy_version text not null default 'v0'`, `updated_at timestamptz default now()`, pk `(user_id, scope)`. Add a view `active_consent` (rows with `revoked_at is null`).
7. `friends`: `user_id fk`, `friend_id fk`, `created_at`, pk `(user_id, friend_id)`, check `user_id <> friend_id`.
8. `ranks`: `rank int pk`, `min_lifetime_points int not null`, `discount_pct int not null`. Seed from game-engine config: (1,0,3),(2,1000,5),(3,4000,7),(4,12000,10),(5,30000,12).
9. `rider_events` hypertable on `time`: `id uuid default gen_random_uuid()`, `time timestamptz not null`, `user_id uuid not null`, `event_type text check in ('checkin','ride_start','ride_end','route_segment','visit')`, `stop_id text null`, `route_id text null`, `mode text null`, `lat double precision null`, `lon double precision null`, `client_time timestamptz null`, `points_awarded int null`, `payload jsonb not null default '{}'`. PK `(id, time)`. Chunk interval 7 days. Indexes: `(user_id, time desc)`, `(stop_id, time desc)`, `(user_id, stop_id, time desc)` (cooldown lookup). No FK from hypertable to users (keep inserts cheap); document that.
10. `points_ledger` hypertable on `at`: `id uuid default gen_random_uuid()`, `at timestamptz not null default now()`, `user_id uuid not null`, `delta int not null`, `reason text not null` (e.g. `checkin`, `first_visit`, `complete_line`, `delay_compensation`, `redemption`), `ref_type text null`, `ref_id text null`, `route_id text null` (for line leaderboards). PK `(id, at)`. Index `(user_id, at desc)`. Append-only: a `BEFORE UPDATE OR DELETE` trigger that raises an exception. Also a regular view `user_points` = per user `sum(delta) as balance`, `sum(delta) filter (where delta > 0) as lifetime`, plus a view `user_rank` joining `ranks` (highest rank with `min_lifetime_points <= lifetime`).
11. Seed nothing else here (stops/routes are loaded by ingestion later). Add a tiny `seeds/dev_seed.sql` (not a migration) with 3 routes, 5 stops, 2 users for local testing, and a `python -m data_platform.seed` command that applies it.

## Acceptance criteria
- Migration applies cleanly on a fresh DB and re-running migrate is a no-op.
- `rider_events` and `points_ledger` appear in `timescaledb_information.hypertables`.
- UPDATE or DELETE on `points_ledger` raises.
- `user_rank` returns rank 2 / 5% for a user with 1500 lifetime points and a later -200 redemption delta (lifetime stays 1500).
- Only one consent row per user and scope; `active_consent` hides revoked rows.

## Tests to run
`pytest -q` with compose DB up. Add `tests/test_core_schema.py` covering every acceptance criterion above (use a transaction or unique test user ids so tests are repeatable).

## Out of scope
Sponsors, rewards, badges, redemptions (003). MBTA realtime tables (005). Continuous aggregates (006). Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
