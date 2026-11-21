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
