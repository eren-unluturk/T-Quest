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

-- --------------------------------------- home_line: rides_28d -> checkins_28d
-- A view cannot rename a column in place, and users_affected_by_alert depends on it.
DROP FUNCTION IF EXISTS users_affected_by_alert(text);

DROP VIEW IF EXISTS home_line;

-- Most-ridden route over the last 4 weekly buckets, at least 5 check-ins.
-- users.home_line_override wins when set.
CREATE VIEW home_line AS
    WITH recent AS (
        SELECT w.user_id, w.route_id, sum(w.rides)::bigint AS checkins_28d
        FROM home_line_weekly w
        WHERE w.week >= time_bucket('7 days', now() - INTERVAL '28 days')
        GROUP BY w.user_id, w.route_id
    ), ranked AS (
        SELECT r.*, row_number() OVER (PARTITION BY r.user_id
                                       ORDER BY r.checkins_28d DESC, r.route_id) AS rn
        FROM recent r
    ), best AS (
        SELECT user_id, route_id, checkins_28d FROM ranked WHERE rn = 1 AND checkins_28d >= 5
    )
    SELECT u.id AS user_id,
           coalesce(u.home_line_override, b.route_id) AS route_id,
           b.checkins_28d
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
