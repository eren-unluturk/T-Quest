-- migrate:no-transaction
-- Marks synthetic rider events, adds MBTA lines and scheduled trips per hour (anchors for the
-- synthetic generator), and a continuous aggregate over live vehicle positions. Idempotent.

ALTER TABLE rider_events ADD COLUMN IF NOT EXISTS is_synthetic boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS lines (
    id         text PRIMARY KEY,          -- MBTA line id, e.g. line-Red
    short_name text,
    long_name  text,
    color      text,
    text_color text,
    sort_order int
);

-- Scheduled trips per route, direction and local hour of day (America/New_York), from
-- MBTA /schedules (first stop of each trip) on one reference service date.
CREATE TABLE IF NOT EXISTS route_schedule_hourly (
    route_id     text NOT NULL REFERENCES routes (id),
    direction_id smallint NOT NULL,
    hour_of_day  smallint NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    trips        int NOT NULL,
    service_date date,
    PRIMARY KEY (route_id, direction_id, hour_of_day)
);

-- Vehicle position reports per route per 5 minutes (live MBTA data).
CREATE MATERIALIZED VIEW IF NOT EXISTS vehicles_route_5m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('5 minutes', time) AS bucket,
       route_id,
       count(*)                       AS reports,
       avg(speed)                     AS avg_speed
FROM vehicles
GROUP BY time_bucket('5 minutes', time), route_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('vehicles_route_5m',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);
