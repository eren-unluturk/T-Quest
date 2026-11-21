-- analytics_me.sql: GET /analytics/me
--
-- Reads (Tiger Data, names from GitHub issue #22 and data-platform's ACK):
--   user_stop_daily        continuous aggregate: bucket (1 day), user_id, stop_id, route_id, visits
--   home_line              view over the home-line aggregate: user_id, route_id, checkins_28d
--   stops                  id, name, neighborhood
-- All queries read pre-aggregated daily buckets, never raw rider_events.
--
-- Parameters (psycopg named style):
--   %(user_id)s  the caller
--   %(since)s    start of the period as timestamptz, or NULL for all time
--                (week = now() - 7 days, month = now() - 30 days, all = NULL)
--   %(limit)s    top-stops limit (the service uses 5)

-- name: totals
-- stops_visited = total check-ins, unique_stops = distinct stops, lines_ridden = distinct routes
SELECT coalesce(sum(visits), 0)                                  AS stops_visited,
       count(DISTINCT stop_id)                                   AS unique_stops,
       coalesce(array_agg(DISTINCT route_id ORDER BY route_id)
                FILTER (WHERE route_id IS NOT NULL), '{}')       AS lines_ridden
FROM user_stop_daily
WHERE user_id = %(user_id)s
  AND (%(since)s::timestamptz IS NULL OR bucket >= %(since)s);

-- name: weekly_series
-- Weeks start on Monday (time_bucket default origin), matching the Python implementation.
SELECT time_bucket('1 week', bucket)::date AS week_start,
       sum(visits)                         AS checkins,
       count(DISTINCT stop_id)             AS unique_stops
FROM user_stop_daily
WHERE user_id = %(user_id)s
  AND (%(since)s::timestamptz IS NULL OR bucket >= %(since)s)
GROUP BY 1
ORDER BY 1;

-- name: top_stops
SELECT stop_id, sum(visits) AS visits
FROM user_stop_daily
WHERE user_id = %(user_id)s
  AND (%(since)s::timestamptz IS NULL OR bucket >= %(since)s)
GROUP BY stop_id
ORDER BY visits DESC, stop_id
LIMIT %(limit)s;

-- name: neighborhoods_explored
SELECT DISTINCT s.neighborhood
FROM user_stop_daily u
JOIN stops s ON s.id = u.stop_id
WHERE u.user_id = %(user_id)s
  AND s.neighborhood IS NOT NULL
  AND (%(since)s::timestamptz IS NULL OR u.bucket >= %(since)s)
ORDER BY s.neighborhood;

-- name: home_line
-- Most-checked-in line over the last 28 days with at least 5 check-ins.
-- The threshold lives in the home_line view itself. Independent of the period.
SELECT route_id
FROM home_line
WHERE user_id = %(user_id)s;
