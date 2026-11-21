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
