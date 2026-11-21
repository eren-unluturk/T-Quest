-- recs_place_affinity.sql: GET /recommendations (kind = stop)
--
-- CONSENT GATE: this file reads place_visits. It may run ONLY after
-- has_consent(user, "place_visits") returned true in the service. Never run it,
-- or any variant of it, for a user without that consent. Revoking consent makes
-- stored place-visit data ineligible for recommendations.
--
-- Boosts stops that have a partner store in a category the user likes
-- (category share of their place visits), skipping stops they already visit.
--
-- Reads:
--   place_visits      hypertable: time, user_id, place_category, store_id (90-day retention)
--   stores            id, category, nearest_stop_id, active (store_partners in issue #22)
--   user_stop_daily   continuous aggregate: user_id, stop_id (stops already visited)
--
-- Score = 0.6 * highest category share among the stop's partner stores.
-- Sponsorship is not an input; the service flags sponsored items afterwards.
--
-- Parameters:
--   %(user_id)s  the caller
--   %(since)s    window start, now() - 90 days
--   %(limit)s    maximum rows

WITH cats AS (
    SELECT place_category,
           count(*)::float / sum(count(*)) OVER () AS share
    FROM place_visits
    WHERE user_id = %(user_id)s AND time >= %(since)s
    GROUP BY place_category
),
visited AS (
    SELECT DISTINCT stop_id
    FROM user_stop_daily
    WHERE user_id = %(user_id)s
)
SELECT st.nearest_stop_id AS stop_id,
       0.6 * max(c.share) AS score,
       array_agg(DISTINCT c.place_category ORDER BY c.place_category) AS categories
FROM stores st
JOIN cats c ON c.place_category = st.category
WHERE st.active
  AND st.nearest_stop_id NOT IN (SELECT stop_id FROM visited)
GROUP BY st.nearest_stop_id
ORDER BY score DESC, stop_id
LIMIT %(limit)s;
