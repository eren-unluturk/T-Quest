-- analytics_boston.sql: GET /analytics/boston (anonymous, aggregate only)
--
-- Reads (Tiger Data, names from GitHub issue #22 and data-platform's ACK):
--   stop_popularity_hourly  view over an hourly continuous aggregate: bucket, stop_id, checkins, unique_users
--   rider_events            hypertable: time, user_id, event_type, stop_id, route_id (distinct riders only)
--   stops                   id, name, neighborhood
--
-- PRIVACY (k-anonymity): no user id is ever selected into a result. Every bucket must be
-- backed by at least %(min_users)s distinct riders (the service uses 3). unique_users in
-- the hourly aggregate cannot be summed across hours, so distinct riders for a whole period
-- come from rider_events with count(DISTINCT user_id) and gate the aggregate counts.
--
-- Parameters:
--   %(since)s       period start (now() - 7 days for week, now() - 30 days for month)
--   %(prev_since)s  start of the previous period of equal length (since minus the period)
--   %(min_users)s   minimum distinct riders per bucket (3)
--   %(limit)s       busiest stops limit (10); trending uses 5 in the service

-- name: totals
-- active_riders and total_checkins are 0 when fewer than min_users riders were active.
WITH riders AS (
    SELECT count(DISTINCT user_id) AS n
    FROM rider_events
    WHERE time >= %(since)s AND event_type = 'checkin'
)
SELECT CASE WHEN r.n >= %(min_users)s THEN r.n ELSE 0 END AS active_riders,
       CASE WHEN r.n >= %(min_users)s
            THEN (SELECT coalesce(sum(checkins), 0) FROM stop_popularity_hourly WHERE bucket >= %(since)s)
            ELSE 0 END AS total_checkins
FROM riders r;

-- name: busiest_stops
WITH eligible AS (
    SELECT stop_id
    FROM rider_events
    WHERE time >= %(since)s AND event_type = 'checkin' AND stop_id IS NOT NULL
    GROUP BY stop_id
    HAVING count(DISTINCT user_id) >= %(min_users)s
),
daily AS (
    SELECT time_bucket('1 day', p.bucket) AS day, p.stop_id, sum(p.checkins) AS checkins
    FROM stop_popularity_hourly p
    WHERE p.bucket >= %(since)s
    GROUP BY 1, 2
)
SELECT d.stop_id, s.name AS stop_name, sum(d.checkins) AS checkins
FROM daily d
JOIN eligible e ON e.stop_id = d.stop_id
JOIN stops s    ON s.id = d.stop_id
GROUP BY d.stop_id, s.name
ORDER BY checkins DESC, d.stop_id
LIMIT %(limit)s;

-- name: trending_neighborhoods
-- Current period vs the previous period of equal length. A neighborhood needs at least 5
-- check-ins and min_users distinct riders now. A previous period under min_users riders
-- (or with no data) counts as zero, which reports +100%.
WITH rider_counts AS (
    SELECT s.neighborhood,
           count(DISTINCT e.user_id) FILTER (WHERE e.time >= %(since)s)                             AS riders_now,
           count(DISTINCT e.user_id) FILTER (WHERE e.time >= %(prev_since)s AND e.time < %(since)s) AS riders_prev
    FROM rider_events e
    JOIN stops s ON s.id = e.stop_id
    WHERE e.time >= %(prev_since)s AND e.event_type = 'checkin' AND s.neighborhood IS NOT NULL
    GROUP BY s.neighborhood
),
daily AS (
    SELECT time_bucket('1 day', p.bucket) AS day, s.neighborhood, sum(p.checkins) AS checkins
    FROM stop_popularity_hourly p
    JOIN stops s ON s.id = p.stop_id
    WHERE p.bucket >= %(prev_since)s AND s.neighborhood IS NOT NULL
    GROUP BY 1, 2
),
periods AS (
    SELECT neighborhood,
           coalesce(sum(checkins) FILTER (WHERE day >= %(since)s), 0)                          AS checkins_now,
           coalesce(sum(checkins) FILTER (WHERE day >= %(prev_since)s AND day < %(since)s), 0) AS checkins_prev
    FROM daily
    GROUP BY neighborhood
)
SELECT p.neighborhood,
       p.checkins_now AS checkins,
       CASE WHEN r.riders_prev >= %(min_users)s AND p.checkins_prev > 0
            THEN round(100.0 * (p.checkins_now - p.checkins_prev) / p.checkins_prev, 1)
            ELSE 100.0 END AS change_pct
FROM periods p
JOIN rider_counts r ON r.neighborhood = p.neighborhood
WHERE p.checkins_now >= 5 AND r.riders_now >= %(min_users)s
ORDER BY change_pct DESC, checkins DESC, p.neighborhood
LIMIT 5;

-- name: lines_by_day
-- Per line and day. Days with fewer than min_users riders are dropped by HAVING; lines whose
-- whole period has fewer than min_users riders are dropped by the eligible CTE.
WITH eligible AS (
    SELECT route_id
    FROM rider_events
    WHERE time >= %(since)s AND event_type = 'checkin' AND route_id IS NOT NULL
    GROUP BY route_id
    HAVING count(DISTINCT user_id) >= %(min_users)s
)
SELECT e.route_id,
       time_bucket('1 day', e.time)::date AS day,
       count(*)                           AS checkins
FROM rider_events e
JOIN eligible g ON g.route_id = e.route_id
WHERE e.time >= %(since)s AND e.event_type = 'checkin'
GROUP BY e.route_id, time_bucket('1 day', e.time)
HAVING count(DISTINCT e.user_id) >= %(min_users)s
ORDER BY e.route_id, day;
