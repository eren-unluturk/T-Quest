-- recs_routes.sql: GET /recommendations (kind = route)
--
-- Routes the user has not ridden that connect to their home line, ranked by
-- how many stops they share with it (more transfer points = easier to try).
--
-- Reads:
--   home_line         view over the home-line aggregate: user_id, route_id, checkins_28d
--   user_stop_daily   continuous aggregate: user_id, route_id (routes already ridden)
--   route_stops       route_id, stop_id (direction rows collapsed with DISTINCT)
--
-- Score = 0.8 * shared_stops / max(shared_stops). Returns no rows when the user
-- has no home line yet. No place_visits data is used. Sponsorship is not an input.
--
-- Parameters:
--   %(user_id)s  the caller
--   %(limit)s    maximum rows

WITH home AS (
    SELECT route_id FROM home_line WHERE user_id = %(user_id)s
),
ridden AS (
    SELECT DISTINCT route_id
    FROM user_stop_daily
    WHERE user_id = %(user_id)s AND route_id IS NOT NULL
),
home_stops AS (
    SELECT DISTINCT rs.stop_id
    FROM route_stops rs
    JOIN home h ON h.route_id = rs.route_id
),
candidates AS (
    SELECT rs.route_id, count(DISTINCT rs.stop_id) AS shared_stops
    FROM route_stops rs
    WHERE rs.stop_id IN (SELECT stop_id FROM home_stops)
      AND rs.route_id NOT IN (SELECT route_id FROM ridden)
    GROUP BY rs.route_id
)
SELECT route_id,
       shared_stops,
       0.8 * shared_stops::float / max(shared_stops) OVER () AS score
FROM candidates
ORDER BY shared_stops DESC, route_id
LIMIT %(limit)s;
