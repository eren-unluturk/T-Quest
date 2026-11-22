# T-Quest Tiger Data schema contract (v0.1 draft)

Owner: data-platform. Source of truth: `data-platform/migrations/*.sql` (0000 to 0005 described here). All ids are MBTA string ids (`text`) or `uuid` (`gen_random_uuid()`). All timestamps are `timestamptz`.

## How to connect
- Local: `docker compose up -d` in `data-platform/`, copy `.env.example` to `.env`, then `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tquest`.
- Tiger Cloud: `DATABASE_URL=postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require`.
- Apply the schema to either: `pip install -e .[dev]` then `python -m data_platform.migrate` (ordered, idempotent, recorded in `schema_migrations`).
- Optional dev data: `python -m data_platform.seed`. MBTA data: `python -m data_platform.load_static`, `python -m data_platform.ingest`.

## Write ownership
| Writer | Tables |
|---|---|
| game-engine | `rider_events`, `points_ledger`, `user_collections`, `redemptions`, `friends`, `badges`, `ranks`, `users` |
| insights-sponsors | `stop_facts`, `freedom_trail_sites`, `fun_facts`, `sponsors`, `stores`, `offers`, `rewards`, `quests`, `physical_rewards`, `store_inventory`, `consent`, `place_visits` |
| data-platform | `routes`, `stops`, `route_stops`, `vehicles`, `predictions`, `alerts`, `alert_entities`, `schema_migrations` |

Notes: game-engine owns unlock and rank rules, so `badges` and `ranks` are its tables (insights-sponsors requests sponsor badges from game-engine) and it issues sessions, so it owns `users`. Everyone may read everything.

## Names for insights-sponsors (#22)
| Proposed in #22 | Name here |
|---|---|
| `store_partners` | `stores` |
| `physical_rewards.kind` | `physical_rewards.item_type` |
| `store_inventory.quantity` | `store_inventory.stock` |
| `home line checkins_30d` | `home_line.checkins_30d` (renamed from `rides_28d`; true 30-day window since migration 0007) |
| rank (`user_id, rank`) | view `user_rank` |
| badges (`user_id, badge_id`) | table `user_collections` |
| fun facts | `fun_facts` |
| `consent.granted` | `consent.granted` (generated: `revoked_at is null`) |
| aggregates `user_stop_daily`, `stop_popularity_hourly` | same names, migration 0006 (also `user_stop_hourly`) |

## Extensions (0000)
`timescaledb`, `pgcrypto`.

## Migration bookkeeping
### schema_migrations
`version text pk`, `applied_at default now()`, `checksum text`.

## Transit (0001, 0005)
### routes
`id text pk` (MBTA route id), `short_name`, `long_name`, `mode` in (`subway`,`light_rail`,`bus`,`commuter_rail`,`ferry`), `route_type int`, `color`, `text_color`, `line_id` (e.g. `line-Green`), `sort_order`.

### stops
`id text pk`, `name not null`, `lat`/`lon not null`, `parent_station`, `location_type`, `municipality`, `wheelchair_boarding`, `is_freedom_trail boolean default false`, `neighborhood`, `updated_at`, `mode` (0005; primary mode, rail preferred over bus; filled by `load_static` and backfilled by the migration). Index `(lat, lon)`.

### route_stops
`route_id fk`, `stop_id fk`, `direction_id smallint`, `stop_sequence`. pk `(route_id, stop_id, direction_id)`. Index on `stop_id`.

### stop_facts
`id bigserial pk`, `stop_id fk null` (null = general fact), `kind` in (`fast_fact`,`history`,`freedom_trail`,`loading_screen`), `title`, `body not null`, `source_url`, `created_at`, `sort int not null default 0` (0005), `tags text[] not null default '{}'` (0005). Index on `stop_id`.

### freedom_trail_sites (0005)
`id uuid pk`, `sort_order int not null`, `name not null`, `lat`, `lon`, `nearest_stop_id fk stops null`, `blurb`. Index on `nearest_stop_id`.

### fun_facts (0005)
`id uuid pk`, `body not null`, `tags text[] not null default '{}'`, `created_at`.

## Users and social (0001, 0005)
### users
`id uuid pk`, `username unique not null`, `display_name`, `created_at`, `home_line_override`.

### consent
`user_id fk`, `scope` in (`location`,`place_visits`,`recommendations`,`marketing`), `granted_at not null default now()`, `revoked_at`, `policy_version not null default 'v0'`, `updated_at`, `granted boolean generated always as (revoked_at is null) stored` (0005). pk `(user_id, scope)`; re-granting updates the row in place.

### friends
`user_id fk`, `friend_id fk`, `created_at`. pk `(user_id, friend_id)`, check `user_id <> friend_id`. Directed rows; writers insert both directions for a mutual friendship (the `leaderboard()` friends scope reads `user_id = p_user`).

### ranks
`rank int pk`, `min_lifetime_points`, `discount_pct`. Seeded (1,0,3), (2,1000,5), (3,4000,7), (4,12000,10), (5,30000,12).

## Events and points (0001)
### rider_events (hypertable on `time`, chunk 7 days)
`id uuid`, `time not null`, `user_id uuid not null`, `event_type` in (`checkin`,`ride_start`,`ride_end`,`route_segment`,`visit`), `stop_id`, `route_id`, `mode`, `lat`, `lon`, `client_time`, `points_awarded`, `payload jsonb default '{}'`, `is_synthetic boolean not null default false` (0009: true for generated demo rows; real riders are false, so analytics must filter `NOT is_synthetic`). pk `(id, time)`. Compressed after 7 days (0008). Indexes `(user_id, time desc)`, `(stop_id, time desc)`, `(user_id, stop_id, time desc)`. No foreign keys; the writer validates ids.

### points_ledger (hypertable on `at`, default chunk interval)
`id uuid`, `at default now()`, `user_id uuid not null`, `delta int not null`, `reason not null`, `ref_type`, `ref_id`, `route_id`. pk `(id, at)`. Index `(user_id, at desc)`. No foreign keys.
**Append-only:** trigger `points_ledger_no_mutation` (function `points_ledger_append_only()`) raises on UPDATE or DELETE. Corrections are new rows with an opposite `delta`.

### place_visits (hypertable on `time`, chunk 7 days; 0005)
Written by insights-sponsors only after `place_visits` consent. `id uuid`, `time not null`, `user_id not null`, `lat`, `lon`, `place_category`, `store_id uuid null`. pk `(id, time)`, index `(user_id, time desc)`. Retention policy: raw rows dropped after 90 days (privacy). No foreign keys.

### lines (0009)
MBTA lines: `id text pk` (e.g. `line-Red`), `short_name`, `long_name`, `color`, `text_color`, `sort_order`. Joined from `routes.line_id`. Loaded by `load_static`.

### route_schedule_hourly (0009)
Scheduled trips per `(route_id fk, direction_id, hour_of_day 0-23, America/New_York)`: `trips`, `service_date`. From MBTA `/schedules` (first stop of each trip) on one weekday. Anchor for the synthetic generator.

## Sponsors and rewards (0002, 0005)
### sponsors
`id uuid pk`, `name not null`, `category` in (`food`,`clothing`,`sports`,`retail`,`other`), `website`, `logo_url`, `active default true`, `created_at`.

### stores
`id uuid pk`, `sponsor_id fk`, `name`, `address`, `lat`, `lon`, `nearest_stop_id fk stops null`, `store_key_hash` (never the raw key), `active`, `category` in (`food`,`clothing`,`sports`,`retail`,`other`) (0005). Index on `nearest_stop_id`.

### offers
`id uuid pk`, `sponsor_id fk`, `store_id fk null` (null = all stores), `title`, `description`, `kind` in (`discount`,`free_item`,`points_item`,`local_pick`) (widened in 0005), `min_rank default 1`, `points_cost default 0`, `discount_pct`, `max_value_usd numeric(6,2)`, `stock` (null = unlimited), `starts_at`, `ends_at`, `active`, and from 0005: `required_badge_id fk badges null`, `per_user_limit int null`, `placement` in (`local_pick`,`sponsored_quest`) null.

### rewards
`id uuid pk`, `sponsor_id fk null`, `title`, `description`, `kind` in (`merch`,`ticket`,`digital`,`other`), `points_cost not null`, `min_rank default 1`, `stock`, `active`.

### badges
`id text pk` (slug), `name`, `description`, `kind` in (`line_complete`,`rank`,`trail`,`stop_count`,`event`,`sponsor`), `criteria jsonb default '{}'`, `image_url`.

### quests
`id uuid pk`, `title`, `goal`, `criteria jsonb`, `sponsor_id fk null`, `reward_points default 0`, `reward_badge_id fk badges null`, `starts_at`, `ends_at`, `active`.

### physical_rewards
`id uuid pk`, `sponsor_id fk null`, `name`, `item_type` in (`sticker`,`patch`,`pin`,`other`), `badge_id fk badges not null`, `min_rank default 1`, `per_user_limit default 1`, `image_url`, `active`, `description` (0005).

### store_inventory
`store_id fk`, `physical_reward_id fk`, `stock int not null check (stock >= 0)`, `updated_at`. pk `(store_id, physical_reward_id)`.

### user_collections
`user_id fk`, `badge_id fk`, `earned_at default now()`, `source`, `source_ref`. pk `(user_id, badge_id)`.

### redemptions
`id uuid pk`, `code unique not null` (regex `^[A-HJ-NP-Z2-9]{10}$`), `user_id fk`, `store_id fk null`, `offer_id`/`reward_id`/`physical_reward_id` (exactly one set, constraint `redemptions_one_target`), `status` in (`issued`,`claimed`,`expired`) default `issued`, `points_spent default 0`, `issued_at`, `expires_at not null`, `claimed_at`, `claimed_store_id fk null`. Indexes `(user_id, store_id, issued_at desc)`, `(status, expires_at)`.

## Realtime (0003)
### vehicles (hypertable on `time`, chunk 1 day)
`time` (poll time), `vehicle_id not null`, `route_id`, `trip_id`, `stop_id`, `direction_id smallint`, `current_status`, `lat`, `lon`, `bearing real`, `speed real`, `label`, `updated_at`. Unique `(vehicle_id, time)`. Indexes `(stop_id, time desc)`, `(route_id, time desc)`. Compression segmentby `route_id`, orderby `vehicle_id, time DESC` (the unique index columns must be segmentby or orderby); compressed after 1 day, dropped after 30 days.

### predictions (hypertable on `time`, chunk 1 day)
`time` (poll time), `prediction_id not null`, `stop_id`, `route_id`, `trip_id`, `direction_id`, `arrival_time`, `departure_time`, `status`, `schedule_relationship`. Unique `(prediction_id, time)`. Index `(stop_id, time desc)`. Compression segmentby `route_id`, orderby `prediction_id, time DESC`; same compression and retention schedule as `vehicles`.

### alerts
`id text pk`, `effect`, `cause`, `severity int`, `header`, `description`, `lifecycle`, `active_start`, `active_end`, `first_seen_at`, `last_seen_at`, `raw jsonb`. Upserted by the ingestion worker.

### alert_entities
`alert_id fk alerts on delete cascade`, `route_id`, `stop_id`, `route_type int`, `direction_id smallint`. Indexes on `alert_id`, `route_id`, `stop_id`.

## Continuous aggregates, views, functions
- `vehicles_route_5m` (0009, CAGG on `vehicles`, 5 minutes, real-time): `bucket, route_id, reports, avg_speed`. Refresh every 5 minutes (3 day window). Live MBTA data only.
- `leaderboard_daily` (CAGG on `points_ledger`, 1 day): `day, user_id, route_id, points_earned, entries`. Refresh every 5 minutes (30 day window). Real-time aggregation on.
- `leaderboard(p_scope, p_period, p_user, p_route, p_limit)`: scope `global|friends|line`, period `week|month|all`; returns `position, user_id, username, points`; ties share a position.
- `home_line_weekly` (CAGG on `rider_events`, 7 days, checkin and ride_start with a route): `week, user_id, route_id, rides`. Refresh every 15 minutes (90 day window).
- `user_route_daily` (CAGG on `rider_events`, 1 day, checkin and ride_start with a route): `bucket, user_id, route_id, rides, last_ride`. Refresh every 15 minutes (40 day window).
- `home_line` (view, migration 0007): `user_id, route_id, checkins_30d`; most-ridden route in the last 30 days, at least 5 check-ins, ties go to the most recently ridden line (same rule as game-engine `delay.py`); `users.home_line_override` wins when set (`checkins_30d` is then the user's count on that route, 0 if none).
- `users_affected_by_alert(p_alert_id)`: users whose `home_line.route_id` appears in the alert's `alert_entities`.
- `personal_stats_daily` (CAGG on `rider_events`, 1 day): `day, user_id, checkins, bus_events, rail_events`.
- `user_stop_visits` (view): `user_id, stop_id, first_visit, visits` over checkin and visit events.

## Views and functions (0001, 0002, 0003, 0005)
- `active_consent`: `consent` rows where `revoked_at is null`.
- `user_points`: per `user_id`, `balance = sum(delta)`, `lifetime = sum(delta) filter (delta > 0)`.
- `user_rank`: `user_id, balance, lifetime, rank, discount_pct` for every row of `users`; a user with no ledger rows is rank 1, discount 3, lifetime 0 (changed in 0005). Ledger rows for a `user_id` missing from `users` do not appear.
- `active_alerts`: `alerts` whose active window contains `now()` (null start counts as started, null end as open).
- `expire_redemptions() returns integer`: sets `status = 'expired'` for issued rows past `expires_at`; not scheduled.

## Insights aggregates (0006)
- `user_stop_daily` (CAGG on `rider_events` where `stop_id is not null`, 1 day): `bucket, user_id, stop_id, route_id, visits`. Refresh every 15 minutes (30 day window), real-time aggregation on.
- `user_stop_hourly` (CAGG, 1 hour): `bucket, stop_id, user_id, checkins` (check-in events only). Same policy.
- `stop_popularity_hourly` (view over `user_stop_hourly`): `bucket, stop_id, checkins, unique_users`.
- `home_line` column `rides_28d` was renamed `checkins_30d` and moved to a true 30-day window (0007); `users_affected_by_alert` was recreated on top of it.

## Compression (0008)
- `rider_events` compression: segmentby `user_id`, orderby `time DESC, id` (the primary key columns must be in the set); policy compresses chunks older than 7 days. Measured about 9.5x total size reduction (see docs/TIGER_DATA_RESULTS.md).
- Verified against a live TimescaleDB 2.32.1 on PostgreSQL 18: migrations 0000-0008 apply cleanly and idempotently. `schema.sql` is still the concatenation of the migrations, not a pg_dump.

## Migration 0010: nearby spots and identity labels
Tables `spot_categories`, `label_types`, `nearby_spots`, `spot_stop_links`, `spot_labels`; view `spot_labels_public` (declared or certified only; the API reads this view). `spot_labels` has a CHECK: a declared or certified label must carry evidence_url or declaration_note, verified_at and verified_by. `sponsors.demo_placeholder` and `stores.demo_placeholder` flag demo data. Readers must never expose `pending` labels.

## Migration 0011: tourist content
`content_sources`, `content_items` (source, source_url, license, attribution, commercial_ok, retrieved_at, needs_verify), `stop_content` (items within about 500 m of a stop), `loading_facts`. Written by `insights-sponsors/ingest_content`. Clients must display attribution.

## Migration 0012
`nearby_spots.fun_fact` (hand-written demo text) and `fact_faves` (user_key, fact_id, created_at; dev auth key, no FK).

## Migration 0013
`ranks.name` and `ranks.avatar_key` plus the 8 named ranks (matches game-engine config; makes a fresh database identical to the live one).

## Migration 0014
All sponsors and stores are demo placeholders; `demo_placeholder` now defaults to true.
