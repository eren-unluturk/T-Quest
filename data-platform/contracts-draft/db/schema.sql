-- GENERATED FILE. Migrations in data-platform/migrations/ are the source of truth.
-- NOTE: this is a concatenation of migrations 0000 to 0010, NOT a pg_dump. It was built
-- without a database. To replace it with a real dump, run from data-platform/:
--   docker compose up -d; python -m data_platform.migrate
--   docker compose exec db pg_dump -U postgres -d tquest --schema-only --no-owner > contracts-draft/db/schema.sql
-- (then re-add this header).

-- ===== migrations/0000_extensions.sql =====
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ===== migrations/0001_core.sql =====
-- Core schema: transit, users, consent, friends, ranks, rider_events, points_ledger.
-- Idempotent: safe to re-run.

-- ---------------------------------------------------------------- transit
CREATE TABLE IF NOT EXISTS routes (
    id            text PRIMARY KEY,           -- MBTA route id: Red, Green-B, 1
    short_name    text,
    long_name     text,
    mode          text CHECK (mode IN ('subway','light_rail','bus','commuter_rail','ferry')),
    route_type    int,                        -- GTFS route_type
    color         text,
    text_color    text,
    line_id       text,                       -- MBTA line id, e.g. line-Green
    sort_order    int
);

CREATE TABLE IF NOT EXISTS stops (
    id                  text PRIMARY KEY,     -- MBTA stop / parent-station id
    name                text NOT NULL,
    lat                 double precision NOT NULL,
    lon                 double precision NOT NULL,
    parent_station      text,
    location_type       int,
    municipality        text,
    wheelchair_boarding int,
    is_freedom_trail    boolean NOT NULL DEFAULT false,
    neighborhood        text,
    updated_at          timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stops_lat_lon_idx ON stops (lat, lon);

CREATE TABLE IF NOT EXISTS route_stops (
    route_id      text NOT NULL REFERENCES routes (id),
    stop_id       text NOT NULL REFERENCES stops (id),
    direction_id  smallint NOT NULL,
    stop_sequence int,
    PRIMARY KEY (route_id, stop_id, direction_id)
);
CREATE INDEX IF NOT EXISTS route_stops_stop_idx ON route_stops (stop_id);

CREATE TABLE IF NOT EXISTS stop_facts (
    id         bigserial PRIMARY KEY,
    stop_id    text REFERENCES stops (id),    -- NULL = general loading-screen fact
    kind       text CHECK (kind IN ('fast_fact','history','freedom_trail','loading_screen')),
    title      text,
    body       text NOT NULL,
    source_url text,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stop_facts_stop_idx ON stop_facts (stop_id);

-- ------------------------------------------------------------------ users
CREATE TABLE IF NOT EXISTS users (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username           text UNIQUE NOT NULL,
    display_name       text,
    created_at         timestamptz DEFAULT now(),
    home_line_override text
);

CREATE TABLE IF NOT EXISTS consent (
    user_id        uuid NOT NULL REFERENCES users (id),
    scope          text NOT NULL CHECK (scope IN ('location','place_visits','recommendations','marketing')),
    granted_at     timestamptz NOT NULL DEFAULT now(),
    revoked_at     timestamptz,
    policy_version text NOT NULL DEFAULT 'v0',
    updated_at     timestamptz DEFAULT now(),
    PRIMARY KEY (user_id, scope)
);

CREATE OR REPLACE VIEW active_consent AS
    SELECT * FROM consent WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS friends (
    user_id    uuid NOT NULL REFERENCES users (id),
    friend_id  uuid NOT NULL REFERENCES users (id),
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (user_id, friend_id),
    CHECK (user_id <> friend_id)
);

-- ------------------------------------------------------------------ ranks
CREATE TABLE IF NOT EXISTS ranks (
    rank                int PRIMARY KEY,
    min_lifetime_points int NOT NULL,
    discount_pct        int NOT NULL
);
INSERT INTO ranks (rank, min_lifetime_points, discount_pct) VALUES
    (1, 0, 3), (2, 1000, 5), (3, 4000, 7), (4, 12000, 10), (5, 30000, 12)
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------ rider_events
-- No FK to users/stops: hypertable inserts stay cheap. user_id and stop_id are
-- validated by the writing service.
CREATE TABLE IF NOT EXISTS rider_events (
    id             uuid NOT NULL DEFAULT gen_random_uuid(),
    time           timestamptz NOT NULL,
    user_id        uuid NOT NULL,
    event_type     text CHECK (event_type IN ('checkin','ride_start','ride_end','route_segment','visit')),
    stop_id        text,
    route_id       text,
    mode           text,
    lat            double precision,
    lon            double precision,
    client_time    timestamptz,
    points_awarded int,
    payload        jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (id, time)
);
SELECT create_hypertable('rider_events', 'time',
    chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS rider_events_user_time_idx      ON rider_events (user_id, time DESC);
CREATE INDEX IF NOT EXISTS rider_events_stop_time_idx      ON rider_events (stop_id, time DESC);
CREATE INDEX IF NOT EXISTS rider_events_user_stop_time_idx ON rider_events (user_id, stop_id, time DESC);

-- ----------------------------------------------------------- points_ledger
-- Append-only. No FK to users (same reason as rider_events).
CREATE TABLE IF NOT EXISTS points_ledger (
    id       uuid NOT NULL DEFAULT gen_random_uuid(),
    at       timestamptz NOT NULL DEFAULT now(),
    user_id  uuid NOT NULL,
    delta    int NOT NULL,
    reason   text NOT NULL,   -- checkin, first_visit, complete_line, delay_compensation, redemption
    ref_type text,
    ref_id   text,
    route_id text,            -- for line leaderboards
    PRIMARY KEY (id, at)
);
SELECT create_hypertable('points_ledger', 'at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS points_ledger_user_at_idx ON points_ledger (user_id, at DESC);

CREATE OR REPLACE FUNCTION points_ledger_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'points_ledger is append-only (% not allowed)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS points_ledger_no_mutation ON points_ledger;
CREATE TRIGGER points_ledger_no_mutation
    BEFORE UPDATE OR DELETE ON points_ledger
    FOR EACH ROW EXECUTE FUNCTION points_ledger_append_only();

CREATE OR REPLACE VIEW user_points AS
    SELECT user_id,
           sum(delta)                          AS balance,
           sum(delta) FILTER (WHERE delta > 0) AS lifetime
    FROM points_ledger
    GROUP BY user_id;

CREATE OR REPLACE VIEW user_rank AS
    SELECT p.user_id,
           p.balance,
           COALESCE(p.lifetime, 0) AS lifetime,
           r.rank,
           r.discount_pct
    FROM user_points p
    JOIN LATERAL (
        SELECT rank, discount_pct
        FROM ranks
        WHERE min_lifetime_points <= COALESCE(p.lifetime, 0)
        ORDER BY min_lifetime_points DESC
        LIMIT 1
    ) r ON true;

-- ===== migrations/0002_rewards.sql =====
-- Rewards: sponsors, stores, offers, rewards, badges, quests, physical rewards,
-- inventory, user collections, redemptions. Idempotent.

CREATE TABLE IF NOT EXISTS sponsors (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    category   text CHECK (category IN ('food','clothing','sports','retail','other')),
    website    text,
    logo_url   text,
    active     boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stores (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id      uuid NOT NULL REFERENCES sponsors (id),
    name            text,
    address         text,
    lat             double precision,
    lon             double precision,
    nearest_stop_id text REFERENCES stops (id),
    store_key_hash  text,   -- hash of the X-Store-Key; never store the raw key
    active          boolean DEFAULT true
);
CREATE INDEX IF NOT EXISTS stores_nearest_stop_idx ON stores (nearest_stop_id);

CREATE TABLE IF NOT EXISTS offers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id    uuid NOT NULL REFERENCES sponsors (id),
    store_id      uuid REFERENCES stores (id),   -- NULL = all stores of the sponsor
    title         text,
    description   text,
    kind          text CHECK (kind IN ('discount','free_item','local_pick')),
    min_rank      int DEFAULT 1,
    points_cost   int DEFAULT 0,
    discount_pct  int,
    max_value_usd numeric(6,2),
    stock         int,                           -- NULL = unlimited
    starts_at     timestamptz,
    ends_at       timestamptz,
    active        boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS rewards (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id  uuid REFERENCES sponsors (id),
    title       text,
    description text,
    kind        text CHECK (kind IN ('merch','ticket','digital','other')),
    points_cost int NOT NULL,
    min_rank    int DEFAULT 1,
    stock       int,
    active      boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS badges (
    id          text PRIMARY KEY,   -- slug: line-red-complete, freedom-trail, rank-3
    name        text,
    description text,
    kind        text CHECK (kind IN ('line_complete','rank','trail','stop_count','event','sponsor')),
    criteria    jsonb DEFAULT '{}',
    image_url   text
);

CREATE TABLE IF NOT EXISTS quests (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title           text,
    goal            text,
    criteria        jsonb,
    sponsor_id      uuid REFERENCES sponsors (id),
    reward_points   int DEFAULT 0,
    reward_badge_id text REFERENCES badges (id),
    starts_at       timestamptz,
    ends_at         timestamptz,
    active          boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS physical_rewards (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id     uuid REFERENCES sponsors (id),
    name           text,
    item_type      text CHECK (item_type IN ('sticker','patch','pin','other')),
    badge_id       text NOT NULL REFERENCES badges (id),   -- each physical reward maps to a badge
    min_rank       int DEFAULT 1,
    per_user_limit int DEFAULT 1,
    image_url      text,
    active         boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS store_inventory (
    store_id           uuid NOT NULL REFERENCES stores (id),
    physical_reward_id uuid NOT NULL REFERENCES physical_rewards (id),
    stock              int NOT NULL CHECK (stock >= 0),
    updated_at         timestamptz DEFAULT now(),
    PRIMARY KEY (store_id, physical_reward_id)
);

CREATE TABLE IF NOT EXISTS user_collections (
    user_id    uuid NOT NULL REFERENCES users (id),
    badge_id   text NOT NULL REFERENCES badges (id),
    earned_at  timestamptz DEFAULT now(),
    source     text,   -- checkin, quest, rank
    source_ref text,
    PRIMARY KEY (user_id, badge_id)
);

CREATE TABLE IF NOT EXISTS redemptions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code               text UNIQUE NOT NULL CHECK (code ~ '^[A-HJ-NP-Z2-9]{10}$'),
    user_id            uuid NOT NULL REFERENCES users (id),
    store_id           uuid REFERENCES stores (id),
    offer_id           uuid REFERENCES offers (id),
    reward_id          uuid REFERENCES rewards (id),
    physical_reward_id uuid REFERENCES physical_rewards (id),
    status             text NOT NULL DEFAULT 'issued' CHECK (status IN ('issued','claimed','expired')),
    points_spent       int DEFAULT 0,
    issued_at          timestamptz DEFAULT now(),
    expires_at         timestamptz NOT NULL,
    claimed_at         timestamptz,
    claimed_store_id   uuid REFERENCES stores (id),
    CONSTRAINT redemptions_one_target CHECK (
        num_nonnulls(offer_id, reward_id, physical_reward_id) = 1
    )
);
CREATE INDEX IF NOT EXISTS redemptions_user_store_idx   ON redemptions (user_id, store_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS redemptions_status_expiry_idx ON redemptions (status, expires_at);

-- Not scheduled here; game-engine may call it or a job is added later.
CREATE OR REPLACE FUNCTION expire_redemptions() RETURNS integer AS $$
DECLARE
    n integer;
BEGIN
    UPDATE redemptions
       SET status = 'expired'
     WHERE status = 'issued' AND expires_at < now();
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

-- ===== migrations/0003_realtime.sql =====
-- MBTA realtime: vehicles and predictions hypertables (compressed, with retention),
-- alerts and alert_entities, active_alerts view. Idempotent.

CREATE TABLE IF NOT EXISTS vehicles (
    time           timestamptz NOT NULL,   -- poll time
    vehicle_id     text NOT NULL,
    route_id       text,
    trip_id        text,
    stop_id        text,
    direction_id   smallint,
    current_status text,
    lat            double precision,
    lon            double precision,
    bearing        real,
    speed          real,
    label          text,
    updated_at     timestamptz             -- from MBTA
);
SELECT create_hypertable('vehicles', 'time',
    chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS vehicles_vehicle_time_uq ON vehicles (vehicle_id, time);
CREATE INDEX IF NOT EXISTS vehicles_stop_time_idx  ON vehicles (stop_id, time DESC);
CREATE INDEX IF NOT EXISTS vehicles_route_time_idx ON vehicles (route_id, time DESC);

CREATE TABLE IF NOT EXISTS predictions (
    time                  timestamptz NOT NULL,   -- poll time
    prediction_id         text NOT NULL,
    stop_id               text,
    route_id              text,
    trip_id               text,
    direction_id          smallint,
    arrival_time          timestamptz,
    departure_time        timestamptz,
    status                text,
    schedule_relationship text
);
SELECT create_hypertable('predictions', 'time',
    chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS predictions_pred_time_uq ON predictions (prediction_id, time);
CREATE INDEX IF NOT EXISTS predictions_stop_time_idx ON predictions (stop_id, time DESC);

-- TimescaleDB only allows compression on a table with a unique index when every column of
-- that index is a segmentby or orderby column. The unique index is (vehicle_id, time), so
-- vehicle_id goes into orderby next to time. The unique index is kept: ingestion relies on
-- it (ON CONFLICT DO NOTHING) to avoid duplicate samples.
ALTER TABLE vehicles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id',
    timescaledb.compress_orderby = 'vehicle_id, time DESC'
);
-- Same rule: the unique index is (prediction_id, time), so prediction_id is in orderby.
ALTER TABLE predictions SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id',
    timescaledb.compress_orderby = 'prediction_id, time DESC'
);

SELECT add_compression_policy('vehicles',    INTERVAL '1 day',  if_not_exists => TRUE);
SELECT add_compression_policy('predictions', INTERVAL '1 day',  if_not_exists => TRUE);
SELECT add_retention_policy('vehicles',      INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('predictions',   INTERVAL '30 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS alerts (
    id            text PRIMARY KEY,
    effect        text,
    cause         text,
    severity      int,
    header        text,
    description   text,
    lifecycle     text,
    active_start  timestamptz,
    active_end    timestamptz,
    first_seen_at timestamptz DEFAULT now(),
    last_seen_at  timestamptz DEFAULT now(),
    raw           jsonb
);

CREATE TABLE IF NOT EXISTS alert_entities (
    alert_id     text NOT NULL REFERENCES alerts (id) ON DELETE CASCADE,
    route_id     text,
    stop_id      text,
    route_type   int,
    direction_id smallint
);
CREATE INDEX IF NOT EXISTS alert_entities_alert_idx ON alert_entities (alert_id);
CREATE INDEX IF NOT EXISTS alert_entities_route_idx ON alert_entities (route_id);
CREATE INDEX IF NOT EXISTS alert_entities_stop_idx  ON alert_entities (stop_id);

-- Alerts whose active window contains now(). A null start counts as already started.
CREATE OR REPLACE VIEW active_alerts AS
    SELECT *
    FROM alerts
    WHERE (active_start IS NULL OR active_start <= now())
      AND (active_end IS NULL OR active_end > now());

-- ===== migrations/0004_aggregates.sql =====
-- migrate:no-transaction
-- Continuous aggregates and the views/functions on top: leaderboards, home line,
-- personal stats. Idempotent. Each statement runs on its own (see migrate.py).

-- ------------------------------------------------------------ leaderboard
CREATE MATERIALIZED VIEW IF NOT EXISTS leaderboard_daily
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 day', at)                  AS day,
       user_id,
       route_id,
       sum(delta) FILTER (WHERE delta > 0)       AS points_earned,
       count(*)                                  AS entries
FROM points_ledger
GROUP BY time_bucket('1 day', at), user_id, route_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('leaderboard_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

-- scope: global | friends | line. period: week | month | all. Ties share a position.
CREATE OR REPLACE FUNCTION leaderboard(
    p_scope  text,
    p_period text,
    p_user   uuid DEFAULT NULL,
    p_route  text DEFAULT NULL,
    p_limit  int  DEFAULT 50
) RETURNS TABLE ("position" int, user_id uuid, username text, points bigint)
LANGUAGE sql STABLE AS $fn$
    WITH totals AS (
        SELECT l.user_id AS uid, sum(l.points_earned)::bigint AS pts
        FROM leaderboard_daily l
        WHERE (p_period = 'all'
               OR l.day >= time_bucket('1 day', now() - CASE p_period
                                                          WHEN 'week'  THEN INTERVAL '7 days'
                                                          WHEN 'month' THEN INTERVAL '30 days'
                                                        END))
          AND (p_scope <> 'line' OR l.route_id = p_route)
          AND (p_scope <> 'friends'
               OR l.user_id = p_user
               OR l.user_id IN (SELECT f.friend_id FROM friends f WHERE f.user_id = p_user))
        GROUP BY l.user_id
    )
    SELECT (rank() OVER (ORDER BY t.pts DESC NULLS LAST))::int,
           t.uid,
           u.username,
           coalesce(t.pts, 0)::bigint
    FROM totals t
    JOIN users u ON u.id = t.uid
    ORDER BY 1, u.username
    LIMIT p_limit
$fn$;

-- -------------------------------------------------------------- home line
CREATE MATERIALIZED VIEW IF NOT EXISTS home_line_weekly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('7 days', time) AS week,
       user_id,
       route_id,
       count(*)                    AS rides
FROM rider_events
WHERE event_type IN ('checkin', 'ride_start') AND route_id IS NOT NULL
GROUP BY time_bucket('7 days', time), user_id, route_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('home_line_weekly',
    start_offset => INTERVAL '90 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

-- Most-ridden route over the last 4 weekly buckets, at least 5 rides.
-- users.home_line_override wins when set.
CREATE OR REPLACE VIEW home_line AS
    WITH recent AS (
        SELECT w.user_id, w.route_id, sum(w.rides)::bigint AS rides_28d
        FROM home_line_weekly w
        WHERE w.week >= time_bucket('7 days', now() - INTERVAL '28 days')
        GROUP BY w.user_id, w.route_id
    ), ranked AS (
        SELECT r.*, row_number() OVER (PARTITION BY r.user_id
                                       ORDER BY r.rides_28d DESC, r.route_id) AS rn
        FROM recent r
    ), best AS (
        SELECT user_id, route_id, rides_28d FROM ranked WHERE rn = 1 AND rides_28d >= 5
    )
    SELECT u.id AS user_id,
           coalesce(u.home_line_override, b.route_id) AS route_id,
           b.rides_28d
    FROM users u
    LEFT JOIN best b ON b.user_id = u.id
    WHERE u.home_line_override IS NOT NULL OR b.route_id IS NOT NULL;

-- Needs alert_entities from 0003. Skipped (with a notice) when that table is missing.
DO $do$
BEGIN
    IF to_regclass('public.alert_entities') IS NULL THEN
        RAISE NOTICE 'alert_entities missing: users_affected_by_alert not created';
    ELSE
        EXECUTE $create$
            CREATE OR REPLACE FUNCTION users_affected_by_alert(p_alert_id text)
            RETURNS TABLE (user_id uuid)
            LANGUAGE sql STABLE AS $body$
                SELECT DISTINCT h.user_id
                FROM home_line h
                JOIN alert_entities e ON e.route_id = h.route_id
                WHERE e.alert_id = p_alert_id
            $body$
        $create$;
    END IF;
END
$do$;

-- --------------------------------------------------------- personal stats
CREATE MATERIALIZED VIEW IF NOT EXISTS personal_stats_daily
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 day', time)                                 AS day,
       user_id,
       count(*) FILTER (WHERE event_type = 'checkin')             AS checkins,
       count(*) FILTER (WHERE mode = 'bus')                       AS bus_events,
       count(*) FILTER (WHERE mode IN ('subway', 'light_rail'))   AS rail_events
FROM rider_events
GROUP BY time_bucket('1 day', time), user_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('personal_stats_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

-- Distinct-stop counts: DISTINCT is not allowed in continuous aggregates, so a plain view.
CREATE OR REPLACE VIEW user_stop_visits AS
    SELECT user_id,
           stop_id,
           min(time) AS first_visit,
           count(*)  AS visits
    FROM rider_events
    WHERE stop_id IS NOT NULL AND event_type IN ('checkin', 'visit')
    GROUP BY user_id, stop_id;

-- ===== migrations/0005_schema_v01.sql =====
-- Schema v0.1: insights-sponsors additions (#22) and user_rank covering every user. Idempotent.

-- 1. stops.mode: primary mode of the stop (rail wins over bus).
ALTER TABLE stops ADD COLUMN IF NOT EXISTS mode text;
ALTER TABLE stops DROP CONSTRAINT IF EXISTS stops_mode_check;
ALTER TABLE stops ADD CONSTRAINT stops_mode_check
    CHECK (mode IN ('subway','light_rail','bus','commuter_rail','ferry'));

UPDATE stops s
   SET mode = x.mode
  FROM (SELECT DISTINCT ON (rs.stop_id) rs.stop_id, r.mode
          FROM route_stops rs
          JOIN routes r ON r.id = rs.route_id
         WHERE r.mode IS NOT NULL
         ORDER BY rs.stop_id,
                  CASE r.mode WHEN 'subway' THEN 1 WHEN 'light_rail' THEN 2
                              WHEN 'commuter_rail' THEN 3 WHEN 'ferry' THEN 4 ELSE 5 END) x
 WHERE s.id = x.stop_id AND s.mode IS NULL;

-- 2. stop_facts ordering and tags.
ALTER TABLE stop_facts ADD COLUMN IF NOT EXISTS sort int NOT NULL DEFAULT 0;
ALTER TABLE stop_facts ADD COLUMN IF NOT EXISTS tags text[] NOT NULL DEFAULT '{}';

-- 3. freedom_trail_sites
CREATE TABLE IF NOT EXISTS freedom_trail_sites (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sort_order      int NOT NULL,
    name            text NOT NULL,
    lat             double precision,
    lon             double precision,
    nearest_stop_id text REFERENCES stops (id),
    blurb           text
);
CREATE INDEX IF NOT EXISTS freedom_trail_sites_stop_idx ON freedom_trail_sites (nearest_stop_id);

-- 4. fun_facts (loading-screen facts)
CREATE TABLE IF NOT EXISTS fun_facts (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    body       text NOT NULL,
    tags       text[] NOT NULL DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);

-- 5. stores.category
ALTER TABLE stores ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE stores DROP CONSTRAINT IF EXISTS stores_category_check;
ALTER TABLE stores ADD CONSTRAINT stores_category_check
    CHECK (category IN ('food','clothing','sports','retail','other'));

-- 6. offers: badge gate, per-user limit, placement, wider kind.
ALTER TABLE offers ADD COLUMN IF NOT EXISTS required_badge_id text REFERENCES badges (id);
ALTER TABLE offers ADD COLUMN IF NOT EXISTS per_user_limit int;
ALTER TABLE offers ADD COLUMN IF NOT EXISTS placement text;
ALTER TABLE offers DROP CONSTRAINT IF EXISTS offers_placement_check;
ALTER TABLE offers ADD CONSTRAINT offers_placement_check
    CHECK (placement IN ('local_pick','sponsored_quest'));
ALTER TABLE offers DROP CONSTRAINT IF EXISTS offers_kind_check;
ALTER TABLE offers ADD CONSTRAINT offers_kind_check
    CHECK (kind IN ('discount','free_item','points_item','local_pick'));

-- 7. physical_rewards.description
ALTER TABLE physical_rewards ADD COLUMN IF NOT EXISTS description text;

-- 8. consent.granted mirrors revoked_at.
ALTER TABLE consent ADD COLUMN IF NOT EXISTS granted boolean
    GENERATED ALWAYS AS (revoked_at IS NULL) STORED;

-- 9. place_visits: written by insights-sponsors only after 'place_visits' consent.
-- No foreign keys (hypertable). Raw visits are kept 90 days for privacy.
CREATE TABLE IF NOT EXISTS place_visits (
    id             uuid NOT NULL DEFAULT gen_random_uuid(),
    time           timestamptz NOT NULL,
    user_id        uuid NOT NULL,
    lat            double precision,
    lon            double precision,
    place_category text,
    store_id       uuid,
    PRIMARY KEY (id, time)
);
SELECT create_hypertable('place_visits', 'time',
    chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS place_visits_user_time_idx ON place_visits (user_id, time DESC);
SELECT add_retention_policy('place_visits', INTERVAL '90 days', if_not_exists => TRUE);

-- 10. user_rank now lists every user; users with no points are rank 1 / lifetime 0.
-- Same column names, order and types as 0001, so CREATE OR REPLACE is enough.
CREATE OR REPLACE VIEW user_rank AS
    SELECT u.id AS user_id,
           coalesce(p.balance, 0)  AS balance,
           coalesce(p.lifetime, 0) AS lifetime,
           r.rank,
           r.discount_pct
    FROM users u
    LEFT JOIN user_points p ON p.user_id = u.id
    JOIN LATERAL (
        SELECT rank, discount_pct
        FROM ranks
        WHERE min_lifetime_points <= coalesce(p.lifetime, 0)
        ORDER BY min_lifetime_points DESC
        LIMIT 1
    ) r ON true;

-- ===== migrations/0006_insights_aggregates.sql =====
-- migrate:no-transaction
-- Aggregates requested by insights-sponsors (#22) and the home_line column rename.
-- Idempotent. Each statement runs on its own (see migrate.py).

-- ---------------------------------------------------------- user_stop_daily
CREATE MATERIALIZED VIEW IF NOT EXISTS user_stop_daily
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 day', time) AS bucket,
       user_id,
       stop_id,
       route_id,
       count(*)                   AS visits
FROM rider_events
WHERE stop_id IS NOT NULL
GROUP BY time_bucket('1 day', time), user_id, stop_id, route_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('user_stop_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

-- --------------------------------------------------------- user_stop_hourly
CREATE MATERIALIZED VIEW IF NOT EXISTS user_stop_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 hour', time)                        AS bucket,
       stop_id,
       user_id,
       count(*) FILTER (WHERE event_type = 'checkin')     AS checkins
FROM rider_events
WHERE stop_id IS NOT NULL
GROUP BY time_bucket('1 hour', time), stop_id, user_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('user_stop_hourly',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

-- Per stop and hour: total check-ins and how many distinct users checked in.
CREATE OR REPLACE VIEW stop_popularity_hourly AS
    SELECT bucket,
           stop_id,
           sum(checkins)::bigint                  AS checkins,
           count(*) FILTER (WHERE checkins > 0)   AS unique_users
    FROM user_stop_hourly
    GROUP BY bucket, stop_id;

-- --------------------------------------- home_line: rides_28d -> checkins_30d
-- A view cannot rename a column in place, and users_affected_by_alert depends on it.
DROP FUNCTION IF EXISTS users_affected_by_alert(text);

DROP VIEW IF EXISTS home_line;

-- Most-ridden route over the last 4 weekly buckets, at least 5 check-ins.
-- users.home_line_override wins when set.
CREATE OR REPLACE VIEW home_line AS
    WITH recent AS (
        SELECT w.user_id, w.route_id, sum(w.rides)::bigint AS checkins_30d
        FROM home_line_weekly w
        WHERE w.week >= time_bucket('7 days', now() - INTERVAL '28 days')
        GROUP BY w.user_id, w.route_id
    ), ranked AS (
        SELECT r.*, row_number() OVER (PARTITION BY r.user_id
                                       ORDER BY r.checkins_30d DESC, r.route_id) AS rn
        FROM recent r
    ), best AS (
        SELECT user_id, route_id, checkins_30d FROM ranked WHERE rn = 1 AND checkins_30d >= 5
    )
    SELECT u.id AS user_id,
           coalesce(u.home_line_override, b.route_id) AS route_id,
           b.checkins_30d
    FROM users u
    LEFT JOIN best b ON b.user_id = u.id
    WHERE u.home_line_override IS NOT NULL OR b.route_id IS NOT NULL;

-- Needs alert_entities from 0003. Skipped (with a notice) when that table is missing.
DO $do$
BEGIN
    IF to_regclass('public.alert_entities') IS NULL THEN
        RAISE NOTICE 'alert_entities missing: users_affected_by_alert not created';
    ELSE
        EXECUTE $create$
            CREATE OR REPLACE FUNCTION users_affected_by_alert(p_alert_id text)
            RETURNS TABLE (user_id uuid)
            LANGUAGE sql STABLE AS $body$
                SELECT DISTINCT h.user_id
                FROM home_line h
                JOIN alert_entities e ON e.route_id = h.route_id
                WHERE e.alert_id = p_alert_id
            $body$
        $create$;
    END IF;
END
$do$;

-- ===== migrations/0007_home_line_30d.sql =====
-- migrate:no-transaction
-- home_line on a true 30-day window, matching game-engine delay.py:
-- rides in the last 30 days, at least 5 on the line, ties go to the most recently ridden line.
-- Idempotent. Each statement runs on its own (see migrate.py).

CREATE MATERIALIZED VIEW IF NOT EXISTS user_route_daily
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 day', time) AS bucket,
       user_id,
       route_id,
       count(*)                   AS rides,
       max(time)                  AS last_ride
FROM rider_events
WHERE event_type IN ('checkin', 'ride_start') AND route_id IS NOT NULL
GROUP BY time_bucket('1 day', time), user_id, route_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('user_route_daily',
    start_offset => INTERVAL '40 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

DROP FUNCTION IF EXISTS users_affected_by_alert(text);

DROP VIEW IF EXISTS home_line;

-- users.home_line_override wins when set (its checkins_30d is the user's count on that route, 0 if none).
CREATE OR REPLACE VIEW home_line AS
    WITH recent AS (
        SELECT d.user_id, d.route_id, sum(d.rides)::bigint AS checkins_30d, max(d.last_ride) AS last_ride
        FROM user_route_daily d
        WHERE d.bucket >= time_bucket('1 day', now() - INTERVAL '30 days')
        GROUP BY d.user_id, d.route_id
    ), ranked AS (
        SELECT r.*, row_number() OVER (PARTITION BY r.user_id
                                       ORDER BY r.checkins_30d DESC, r.last_ride DESC, r.route_id) AS rn
        FROM recent r
    ), best AS (
        SELECT user_id, route_id, checkins_30d FROM ranked WHERE rn = 1 AND checkins_30d >= 5
    )
    SELECT u.id AS user_id,
           coalesce(u.home_line_override, b.route_id) AS route_id,
           CASE WHEN u.home_line_override IS NULL THEN b.checkins_30d
                ELSE coalesce((SELECT x.checkins_30d FROM recent x
                               WHERE x.user_id = u.id AND x.route_id = u.home_line_override), 0)
           END AS checkins_30d
    FROM users u
    LEFT JOIN best b ON b.user_id = u.id
    WHERE u.home_line_override IS NOT NULL OR b.route_id IS NOT NULL;

DO $do$
BEGIN
    IF to_regclass('public.alert_entities') IS NULL THEN
        RAISE NOTICE 'alert_entities missing: users_affected_by_alert not created';
    ELSE
        EXECUTE $create$
            CREATE OR REPLACE FUNCTION users_affected_by_alert(p_alert_id text)
            RETURNS TABLE (user_id uuid)
            LANGUAGE sql STABLE AS $body$
                SELECT DISTINCT h.user_id
                FROM home_line h
                JOIN alert_entities e ON e.route_id = h.route_id
                WHERE e.alert_id = p_alert_id
            $body$
        $create$;
    END IF;
END
$do$;

-- ===== migrations/0008_rider_events_compression.sql =====
-- Columnar compression for rider_events (Tiger Data demo).
-- The primary key is (id, time), so both must be in the segmentby/orderby set.
-- Idempotent.
ALTER TABLE rider_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'user_id',
    timescaledb.compress_orderby = 'time DESC, id'
);

SELECT add_compression_policy('rider_events', INTERVAL '7 days', if_not_exists => TRUE);

-- ===== migrations/0009_real_vs_synthetic.sql =====
-- migrate:no-transaction
-- Marks synthetic rider events, adds MBTA lines and scheduled trips per hour (anchors for the
-- synthetic generator), and a continuous aggregate over live vehicle positions. Idempotent.

ALTER TABLE rider_events ADD COLUMN IF NOT EXISTS is_synthetic boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS lines (
    id         text PRIMARY KEY,          -- MBTA line id, e.g. line-Red
    short_name text,
    long_name  text,
    color      text,
    text_color text,
    sort_order int
);

-- Scheduled trips per route, direction and local hour of day (America/New_York), from
-- MBTA /schedules (first stop of each trip) on one reference service date.
CREATE TABLE IF NOT EXISTS route_schedule_hourly (
    route_id     text NOT NULL REFERENCES routes (id),
    direction_id smallint NOT NULL,
    hour_of_day  smallint NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    trips        int NOT NULL,
    service_date date,
    PRIMARY KEY (route_id, direction_id, hour_of_day)
);

-- Vehicle position reports per route per 5 minutes (live MBTA data).
CREATE MATERIALIZED VIEW IF NOT EXISTS vehicles_route_5m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('5 minutes', time) AS bucket,
       route_id,
       count(*)                       AS reports,
       avg(speed)                     AS avg_speed
FROM vehicles
GROUP BY time_bucket('5 minutes', time), route_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('vehicles_route_5m',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

-- ===== migrations/0010_nearby_spots.sql =====
-- Nearby spots, categories and verified identity labels (owner: data-platform, requested by insights-sponsors).
-- Label policy: a label is shown only when status is declared or certified, with evidence.
-- Never infer a label from a name, photo, review or menu. Idempotent.

ALTER TABLE sponsors ADD COLUMN IF NOT EXISTS demo_placeholder boolean NOT NULL DEFAULT false;
ALTER TABLE stores   ADD COLUMN IF NOT EXISTS demo_placeholder boolean NOT NULL DEFAULT false;
ALTER TABLE sponsors DROP CONSTRAINT IF EXISTS sponsors_category_check;
ALTER TABLE sponsors ADD CONSTRAINT sponsors_category_check
    CHECK (category IN ('food','clothing','sports','retail','other'));

CREATE TABLE IF NOT EXISTS spot_categories (
    slug         text PRIMARY KEY,
    display_name text NOT NULL,
    sort_order   int NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS label_types (
    slug         text PRIMARY KEY,
    display_name text NOT NULL,          -- configurable wording, the team may rename
    description  text,
    sort_order   int NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS nearby_spots (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name             text NOT NULL,
    category_slug    text NOT NULL REFERENCES spot_categories (slug),
    address          text,
    lat              double precision,
    lon              double precision,
    demo_placeholder boolean NOT NULL DEFAULT false,
    sponsor_id       uuid REFERENCES sponsors (id),
    placement_type   text NOT NULL DEFAULT 'listed' CHECK (placement_type IN ('sponsored','listed')),
    active           boolean NOT NULL DEFAULT true,
    removed_at       timestamptz,          -- set when a business asks to be removed
    source           text NOT NULL DEFAULT 'manual',
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sponsored_needs_sponsor CHECK (placement_type <> 'sponsored' OR sponsor_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS nearby_spots_category_idx ON nearby_spots (category_slug);

CREATE TABLE IF NOT EXISTS spot_stop_links (
    spot_id    uuid NOT NULL REFERENCES nearby_spots (id) ON DELETE CASCADE,
    stop_id    text NOT NULL REFERENCES stops (id),
    distance_m double precision,
    PRIMARY KEY (spot_id, stop_id)
);
CREATE INDEX IF NOT EXISTS spot_stop_links_stop_idx ON spot_stop_links (stop_id);

CREATE TABLE IF NOT EXISTS spot_labels (
    spot_id          uuid NOT NULL REFERENCES nearby_spots (id) ON DELETE CASCADE,
    label_slug       text NOT NULL REFERENCES label_types (slug),
    status           text NOT NULL CHECK (status IN ('declared','certified','pending')),
    evidence_url     text,
    declaration_note text,
    verified_at      timestamptz,
    verified_by      text,
    PRIMARY KEY (spot_id, label_slug),
    -- declared or certified rows must carry evidence and who verified them
    CONSTRAINT label_evidence_required CHECK (
        status = 'pending'
        OR ((evidence_url IS NOT NULL OR declaration_note IS NOT NULL)
            AND verified_at IS NOT NULL AND verified_by IS NOT NULL)
    )
);

-- The only thing the API reads: pending labels are not in this view.
CREATE OR REPLACE VIEW spot_labels_public AS
    SELECT spot_id, label_slug, status, evidence_url, declaration_note, verified_at, verified_by
    FROM spot_labels WHERE status IN ('declared','certified');

INSERT INTO spot_categories (slug, display_name, sort_order) VALUES
    ('restaurant','Restaurant',10), ('cafe','Cafe',20), ('store','Store',30),
    ('clothing','Clothing',40), ('grocery','Grocery',50), ('bar','Bar',60), ('other','Other',99)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO label_types (slug, display_name, description, sort_order) VALUES
    ('local-independent','Local / independent','Independently owned local business',10),
    ('woman-owned','Woman-owned',NULL,20),
    ('african-american-owned','African American-owned',NULL,30),
    ('latino-owned','Latino-owned',NULL,40),
    ('asian-owned','Asian-owned',NULL,50),
    ('immigrant-owned','Immigrant-owned',NULL,60),
    ('veteran-owned','Veteran-owned',NULL,70),
    ('lgbtq-owned','LGBTQ+-owned',NULL,80),
    ('family-owned','Family-owned',NULL,90)
ON CONFLICT (slug) DO NOTHING;

