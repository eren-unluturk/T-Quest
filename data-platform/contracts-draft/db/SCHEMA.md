# T-Quest Tiger Data schema contract (v0 draft)

Owner: data-platform. Source of truth: `data-platform/migrations/*.sql`. This document describes migrations 0000 to 0002; section "Planned (v0.1)" lists what comes next.

All ids are either MBTA string ids (`text`) or `uuid` (`gen_random_uuid()`). All timestamps are `timestamptz`.

## How to connect
- Local: `docker compose up -d` in `data-platform/`, copy `.env.example` to `.env`, then `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tquest`.
- Tiger Cloud: `DATABASE_URL=postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require`.
- Apply the schema to either: `pip install -e .[dev]` then `python -m data_platform.migrate` (ordered, idempotent, recorded in `schema_migrations`).
- Optional dev data: `python -m data_platform.seed`.

## Write ownership
| Writer | Tables |
|---|---|
| game-engine | `rider_events`, `points_ledger`, `user_collections`, `redemptions`, `friends` |
| insights-sponsors | `stop_facts`, `sponsors`, `stores`, `offers`, `rewards`, `quests`, `physical_rewards`, `store_inventory`, `consent` |
| data-platform | `routes`, `stops`, `route_stops`, `ranks`, `badges` (initial), realtime tables, `schema_migrations` |
| shared | `users` (created by whichever service owns sign-up; data-platform owns the table) |

Everyone may read everything.

## Extensions (0000)
`timescaledb`, `pgcrypto`.

## Migration bookkeeping
### schema_migrations
`version text pk`, `applied_at timestamptz default now()`, `checksum text`.

## Transit (0001)
### routes
`id text pk` (MBTA route id: `Red`, `Green-B`, `1`), `short_name`, `long_name`, `mode text` in (`subway`,`light_rail`,`bus`,`commuter_rail`,`ferry`), `route_type int` (GTFS), `color`, `text_color`, `line_id text` (e.g. `line-Green`), `sort_order int`.

### stops
`id text pk` (MBTA stop or parent-station id), `name not null`, `lat`/`lon double precision not null`, `parent_station`, `location_type int`, `municipality`, `wheelchair_boarding int`, `is_freedom_trail boolean not null default false`, `neighborhood`, `updated_at`. Index `(lat, lon)`.

### route_stops
`route_id fk routes`, `stop_id fk stops`, `direction_id smallint`, `stop_sequence int`. pk `(route_id, stop_id, direction_id)`. Used for "complete a line" and line leaderboards.

### stop_facts
`id bigserial pk`, `stop_id fk stops null` (null = general loading-screen fact), `kind` in (`fast_fact`,`history`,`freedom_trail`,`loading_screen`), `title`, `body not null`, `source_url`, `created_at`. Index on `stop_id`.

## Users and social (0001)
### users
`id uuid pk`, `username text unique not null`, `display_name`, `created_at`, `home_line_override text null`.

### consent
`user_id fk users`, `scope` in (`location`,`place_visits`,`recommendations`,`marketing`), `granted_at not null default now()`, `revoked_at null`, `policy_version not null default 'v0'`, `updated_at`. pk `(user_id, scope)`: one row per user and scope; re-granting updates the row in place.

### friends
`user_id fk`, `friend_id fk`, `created_at`. pk `(user_id, friend_id)`, check `user_id <> friend_id`. Directed rows; writers insert both directions for a mutual friendship.

### ranks
`rank int pk`, `min_lifetime_points int`, `discount_pct int`. Seeded: (1,0,3), (2,1000,5), (3,4000,7), (4,12000,10), (5,30000,12), matching game-engine config.

## Events and points (0001)
### rider_events (hypertable on `time`, chunk 7 days)
`id uuid default gen_random_uuid()`, `time not null`, `user_id uuid not null`, `event_type` in (`checkin`,`ride_start`,`ride_end`,`route_segment`,`visit`), `stop_id`, `route_id`, `mode`, `lat`, `lon`, `client_time`, `points_awarded int`, `payload jsonb default '{}'`. pk `(id, time)`. Indexes `(user_id, time desc)`, `(stop_id, time desc)`, `(user_id, stop_id, time desc)`. No foreign keys (cheap inserts); the writer validates `user_id` and `stop_id`.

### points_ledger (hypertable on `at`, default chunk interval)
`id uuid default gen_random_uuid()`, `at default now()`, `user_id uuid not null`, `delta int not null`, `reason text not null` (`checkin`, `first_visit`, `complete_line`, `delay_compensation`, `redemption`, ...), `ref_type`, `ref_id`, `route_id`. pk `(id, at)`. Index `(user_id, at desc)`. No foreign keys.
**Append-only:** a `BEFORE UPDATE OR DELETE` trigger (`points_ledger_no_mutation`, function `points_ledger_append_only()`) raises an exception. Corrections are new rows with an opposite `delta`.

### Views
- `active_consent`: `consent` rows where `revoked_at is null`.
- `user_points`: per `user_id`, `balance = sum(delta)`, `lifetime = sum(delta) filter (delta > 0)`. Spending points does not reduce lifetime.
- `user_rank`: `user_id, balance, lifetime, rank, discount_pct` using the highest `ranks` row with `min_lifetime_points <= lifetime`. Users with no ledger rows have no row; treat as rank 1.

## Sponsors and rewards (0002)
### sponsors
`id uuid pk`, `name not null`, `category` in (`food`,`clothing`,`sports`,`retail`,`other`), `website`, `logo_url`, `active default true`, `created_at`.

### stores
`id uuid pk`, `sponsor_id fk`, `name`, `address`, `lat`, `lon`, `nearest_stop_id fk stops null`, `store_key_hash` (hash of the X-Store-Key; never the raw key), `active`. Index on `nearest_stop_id`.

### offers
`id uuid pk`, `sponsor_id fk`, `store_id fk null` (null = all stores of the sponsor), `title`, `description`, `kind` in (`discount`,`free_item`,`local_pick`), `min_rank default 1`, `points_cost default 0`, `discount_pct`, `max_value_usd numeric(6,2)`, `stock` (null = unlimited), `starts_at`, `ends_at`, `active`.

### rewards
`id uuid pk`, `sponsor_id fk null`, `title`, `description`, `kind` in (`merch`,`ticket`,`digital`,`other`), `points_cost not null`, `min_rank default 1`, `stock`, `active`.

### badges
`id text pk` (slug such as `line-red-complete`), `name`, `description`, `kind` in (`line_complete`,`rank`,`trail`,`stop_count`,`event`,`sponsor`), `criteria jsonb default '{}'`, `image_url`.

### quests
`id uuid pk`, `title`, `goal`, `criteria jsonb`, `sponsor_id fk null`, `reward_points default 0`, `reward_badge_id fk badges null`, `starts_at`, `ends_at`, `active`.

### physical_rewards
`id uuid pk`, `sponsor_id fk null`, `name`, `item_type` in (`sticker`,`patch`,`pin`,`other`), `badge_id fk badges not null` (every physical reward maps to a badge), `min_rank default 1`, `per_user_limit default 1`, `image_url`, `active`.

### store_inventory
`store_id fk`, `physical_reward_id fk`, `stock int not null check (stock >= 0)`, `updated_at`. pk `(store_id, physical_reward_id)`.

### user_collections
`user_id fk users`, `badge_id fk badges`, `earned_at default now()`, `source` (`checkin`, `quest`, `rank`), `source_ref`. pk `(user_id, badge_id)`.

### redemptions
`id uuid pk`, `code text unique not null` (regex `^[A-HJ-NP-Z2-9]{10}$`, no 0/O/1/I), `user_id fk`, `store_id fk null`, `offer_id` / `reward_id` / `physical_reward_id` (fk, null; constraint `redemptions_one_target`: exactly one is set), `status` in (`issued`,`claimed`,`expired`) default `issued`, `points_spent default 0`, `issued_at default now()`, `expires_at not null`, `claimed_at`, `claimed_store_id fk null`. Indexes `(user_id, store_id, issued_at desc)` (weekly limit lookup), `(status, expires_at)`.

### Function expire_redemptions()
`expire_redemptions() returns integer`: sets `status = 'expired'` where `status = 'issued' and expires_at < now()` and returns the count. Not scheduled; callers invoke it.

## Planned (v0.1), names and purpose only
- `vehicles` (hypertable, 1 day chunks): MBTA vehicle positions by poll time; compressed after 1 day, dropped after 30.
- `predictions` (hypertable, 1 day chunks): MBTA predictions by poll time; same compression and retention.
- `alerts`, `alert_entities`: upserted MBTA alerts and the routes/stops they affect; view `active_alerts`.
- Continuous aggregates and views: `leaderboard_daily` plus function `leaderboard(scope, period, user, route, limit)`; `home_line_weekly` plus view `home_line` and function `users_affected_by_alert(alert_id)`; `personal_stats_daily` plus view `user_stop_visits`.
