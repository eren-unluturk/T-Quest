-- recs_unvisited_neighborhoods.sql: GET /recommendations (kind = neighborhood)
--
-- Neighborhoods that are popular right now, that the user has never visited,
-- and that are reachable on a line the user already rides.
--
-- Reads:
--   stop_popularity_hourly  view over an hourly continuous aggregate: bucket, stop_id, checkins, unique_users
--   user_stop_daily         continuous aggregate: user_id, stop_id, route_id, visits (what the user did)
--   route_stops             route_id, stop_id (which stops each line serves)
--   stops                   id, neighborhood
--
-- Score = 1 / popularity rank among the eligible neighborhoods (rank 1 = most popular).
-- No place_visits data is used, so no consent gate applies. Sponsorship is not an input.
--
-- Parameters:
--   %(user_id)s  the caller
--   %(since)s    popularity window start, now() - 30 days
--   %(limit)s    maximum rows

WITH ridden AS (
    SELECT DISTINCT route_id
    FROM user_stop_daily
    WHERE user_id = %(user_id)s AND route_id IS NOT NULL
),
visited AS (
    SELECT DISTINCT s.neighborhood
    FROM user_stop_daily u
    JOIN stops s ON s.id = u.stop_id
    WHERE u.user_id = %(user_id)s AND s.neighborhood IS NOT NULL
),
reachable AS (
    SELECT s.neighborhood, array_agg(DISTINCT rs.route_id ORDER BY rs.route_id) AS via_routes
    FROM route_stops rs
    JOIN ridden r ON r.route_id = rs.route_id
    JOIN stops s  ON s.id = rs.stop_id
    WHERE s.neighborhood IS NOT NULL
    GROUP BY s.neighborhood
),
popular AS (
    SELECT s.neighborhood, sum(p.checkins) AS checkins
    FROM stop_popularity_hourly p
    JOIN stops s ON s.id = p.stop_id
    WHERE p.bucket >= %(since)s AND s.neighborhood IS NOT NULL
    GROUP BY s.neighborhood
    HAVING sum(p.checkins) > 0
)
SELECT p.neighborhood,
       p.checkins,
       r.via_routes,
       row_number() OVER (ORDER BY p.checkins DESC, p.neighborhood)       AS popularity_rank,
       1.0 / row_number() OVER (ORDER BY p.checkins DESC, p.neighborhood) AS score
FROM popular p
JOIN reachable r ON r.neighborhood = p.neighborhood
WHERE p.neighborhood NOT IN (SELECT neighborhood FROM visited)
ORDER BY popularity_rank
LIMIT %(limit)s;
