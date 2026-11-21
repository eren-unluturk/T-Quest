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
