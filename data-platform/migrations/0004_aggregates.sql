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
