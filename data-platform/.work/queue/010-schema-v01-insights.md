---
id: 010
title: Schema v0.1 - insights-sponsors additions (#22) and user_rank for zero-point users
status: ready
issue: 22
depends_on: [004, 006]
---
## Goal
Add the tables and columns insights-sponsors asked for in #22 that 0001/0002 lack, make `user_rank` cover every user, and refresh the contract drafts so Eren can publish v0.1.

## Context
- Issue #22 text (summary below; `gh issue view 22` to read it in full)
- `migrations/0001_core.sql`, `0002_rewards.sql`, and whatever 005/006 added (`0003`, `0004`)
- `contracts-draft/db/SCHEMA.md`, `contracts-draft/db/schema.sql` from 004
- Report 002 question: `user_rank` omits users with no ledger rows. Decision: include them as rank 1.

## Steps
Create the next free migration number (expected `0005_schema_v01.sql`), idempotent (`ADD COLUMN IF NOT EXISTS`, `CREATE ... IF NOT EXISTS`, drop-and-recreate CHECK constraints by name):
1. `stops`: add `mode text null check in ('subway','light_rail','bus','commuter_rail','ferry')` (primary mode; the MBTA loader in 007 fills it from the routes serving the stop; if 007 already ran, backfill with an UPDATE from route_stops+routes choosing rail over bus).
2. `stop_facts`: add `sort int not null default 0`, `tags text[] not null default '{}'`.
3. New `freedom_trail_sites`: `id uuid pk default gen_random_uuid()`, `sort_order int not null`, `name text not null`, `lat double precision`, `lon double precision`, `nearest_stop_id text fk stops null`, `blurb text`.
4. New `fun_facts`: `id uuid pk`, `body text not null`, `tags text[] not null default '{}'`, `created_at`.
5. `stores`: add `category text check in ('food','clothing','sports','retail','other') null`.
6. `offers`: add `required_badge_id text fk badges null`, `per_user_limit int null`, `placement text check in ('local_pick','sponsored_quest') null`; widen the `kind` check to `('discount','free_item','points_item','local_pick')`.
7. `physical_rewards`: add `description text`.
8. `consent`: add `granted boolean generated always as (revoked_at is null) stored`.
9. New `place_visits` hypertable on `time` (written by insights-sponsors only after consent `place_visits`): `id uuid default gen_random_uuid()`, `time timestamptz not null`, `user_id uuid not null`, `lat double precision`, `lon double precision`, `place_category text`, `store_id uuid null`, pk `(id, time)`, index `(user_id, time desc)`. Retention policy 90 days (privacy). Chunk interval 7 days.
10. Replace `user_rank` so every row of `users` appears: left join `user_points`, `coalesce(lifetime,0)`, `coalesce(balance,0)`; users with 0 lifetime get rank 1. Keep the existing column names and order (CREATE OR REPLACE VIEW requires it; drop and recreate if it must change, and recreate dependents).
11. Regenerate `contracts-draft/db/schema.sql` (if no DB is available, hand-concatenate the migrations under a header saying so) and update `contracts-draft/db/SCHEMA.md`: new tables/columns, and a "Names for insights-sponsors (#22)" table mapping their proposals to ours: `store_partners` -> `stores`, `physical_rewards.kind` -> `item_type`, `store_inventory.quantity` -> `stock`, `home line checkins_28d` -> `home_line.checkins_28d`, rank -> `user_rank`, badges -> `user_collections`, fun facts -> `fun_facts`, aggregates `user_stop_daily`, `stop_popularity_hourly`.

## Acceptance criteria
- Migration applies after the previous ones and re-runs as a no-op.
- A user with no ledger rows appears in `user_rank` with rank 1, discount 3, lifetime 0.
- `offers` accepts kind `points_item` and placement `sponsored_quest`; rejects placement `popup`.
- `consent.granted` flips to false when `revoked_at` is set.
- `place_visits` is a hypertable with a retention job.
- SCHEMA.md lists every table, column and view in all migrations.

## Tests to run
`pytest -q`; add `tests/test_schema_v01.py` for the criteria above (DB tests skip without a DB, as before).

## Out of scope
Consent enforcement logic (insights-sponsors). Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
